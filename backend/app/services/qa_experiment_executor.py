"""QA Experiment Executor — runs QA questions through GraphRAG + LLM.

Bridges the experiment runner (which collects structural metrics) with
the QA evaluation service (which scores answers) by actually querying
the GraphRAG pipeline and an LLM for each question.

Usage:
    executor = QAExperimentExecutor()
    report = await executor.run_assertion_ablation(
        patient_id="P001",
        condition="full_epistemic",
        run_id="...",
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

import httpx
from sqlalchemy.orm import Session

from app.core.database import get_sync_engine
from app.services.graph_augmented_rag import GraphAugmentedRAGService
from app.services.llm_service import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    TokenUsage,
    CostEstimate,
    get_llm_service,
)
from app.services.qa_evaluation import (
    ASSERTION_QUESTIONS,
    RAG_QUESTIONS,
    TEMPORAL_QUESTIONS,
    QAEvaluationReport,
    QAEvaluationService,
    QAQuestion,
    QAResult,
)
from app.services.research_service import get_research_service

logger = logging.getLogger(__name__)


# ============================================================================
# System prompts for clinical QA
# ============================================================================

CLINICAL_QA_SYSTEM_PROMPT = """\
You are a clinical reasoning assistant answering questions about a specific patient.
Use ONLY the provided evidence to answer. Be precise and concise.

Key rules:
- If the evidence shows a condition is NEGATED (absent), clearly state the patient
  does NOT have that condition.
- If the evidence shows UNCERTAINTY (possible/suspected), communicate that clearly.
- If something is FAMILY HISTORY only, distinguish it from the patient's own conditions.
- If a condition is HISTORICAL (resolved/former), state that clearly.
- If a recommendation is CONDITIONAL, state the conditions required.
- For temporal questions, use the most recent data and note any changes over time.
- If the evidence is insufficient, say so rather than guessing.

Answer in 1-3 sentences. Do not hedge unnecessarily when the evidence is clear."""


# ============================================================================
# QA Experiment Executor
# ============================================================================


@dataclass
class QARunConfig:
    """Configuration for a QA experiment run.

    Fields map to the 5-condition ablation (NeurIPS 2026):
      C1: LLM alone       — raw_note_only=True
      C2: LLM+vanilla RAG — retrieval_mode="doc_only", assertion_mode="none", temporal_mode="no_temporal"
      C3: LLM+KG-RAG      — retrieval_mode="graph_plus_doc", assertion_mode="none", temporal_mode="no_temporal"
      C4: LLM+epistemic    — retrieval_mode="graph_plus_doc", assertion_mode="full", temporal_mode="full_bitemporal"
      C5: Full system      — retrieval_mode="graph_plus_doc_plus_guidelines", assertion="full",
                             temporal="full_bitemporal", calculator_enabled=True, guidelines_enabled=True
    """

    patient_id: str
    condition: str
    assertion_mode: str = "full"
    temporal_mode: str = "full_bitemporal"
    retrieval_mode: str = "graph_plus_doc"
    llm_model: str = "claude-sonnet-4-5-20250929"
    llm_provider: str = "anthropic"  # "anthropic", "openai", or "ollama"
    ollama_base_url: str = "http://localhost:11434"
    max_hops: int = 3
    max_paths: int = 10
    # NeurIPS ablation extensions
    raw_note_only: bool = False  # C1: bypass RAG, send raw note text to LLM
    calculator_enabled: bool = False  # C5: run clinical calculators on KG data
    guidelines_enabled: bool = False  # C5: include guideline retrieval
    use_llm_judge: bool = False  # Use LLM judge for scoring instead of keyword matching


# ============================================================================
# Ollama client (local models — free, no API key needed)
# ============================================================================


async def _call_ollama(
    prompt: str,
    system_prompt: str,
    model: str,
    base_url: str = "http://localhost:11434",
    temperature: float = 0.1,
) -> LLMResponse:
    """Call a local Ollama model.

    Args:
        prompt: User prompt.
        system_prompt: System prompt.
        model: Ollama model name (e.g., "alibayram/medgemma:27b").
        base_url: Ollama server URL.
        temperature: Sampling temperature.

    Returns:
        LLMResponse with generated content.
    """
    t0 = time.perf_counter()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 512,
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{base_url}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()

    content = data.get("message", {}).get("content", "")
    eval_count = data.get("eval_count", 0)
    prompt_eval_count = data.get("prompt_eval_count", 0)
    latency_ms = (time.perf_counter() - t0) * 1000

    return LLMResponse(
        content=content,
        model=model,
        provider=LLMProvider.OPENAI,  # Placeholder — not billed
        token_usage=TokenUsage(
            prompt_tokens=prompt_eval_count,
            completion_tokens=eval_count,
            total_tokens=prompt_eval_count + eval_count,
        ),
        cost_estimate=CostEstimate(),  # $0 — local model
        latency_ms=latency_ms,
    )


class QAExperimentExecutor:
    """Executes QA experiments by querying GraphRAG + LLM and scoring results."""

    def __init__(self) -> None:
        self.qa_service = QAEvaluationService()
        self.research_service = get_research_service()

    async def _ask_question(
        self,
        question: QAQuestion,
        config: QARunConfig,
        rag_service: GraphAugmentedRAGService,
    ) -> QAResult:
        """Ask a single question through GraphRAG + LLM and score the answer.

        Supports all 5 ablation conditions:
        - C1 (raw_note_only=True): bypass RAG entirely, send raw clinical context
        - C2-C4: standard RAG with varying assertion/temporal/retrieval modes
        - C5: full system with calculators + guidelines
        """
        t0 = time.perf_counter()

        try:
            # Use question-specific patient_id if available (multi-patient benchmarks)
            effective_patient_id = (
                question.metadata.get("patient_id") or config.patient_id
            )

            # === C1 bypass: raw note → LLM, no RAG ===
            if config.raw_note_only:
                evidence = self._get_raw_note_context(effective_patient_id, rag_service)
                user_prompt = (
                    f"Clinical note:\n{evidence}\n\n"
                    f"Question: {question.question}\n\n"
                    f"Answer concisely based on the note above."
                )
                evidence_pieces = 1
                graph_path_count = 0
            else:
                # Step 1: Retrieve graph-augmented context
                context = rag_service.retrieve_context(
                    query=question.question,
                    patient_id=effective_patient_id,
                    max_hops=config.max_hops,
                    max_paths=config.max_paths,
                    assertion_mode=config.assertion_mode,
                    temporal_mode=config.temporal_mode,
                    retrieval_mode=config.retrieval_mode,
                )

                # Step 2: Build LLM prompt
                evidence = context.to_llm_prompt(assertion_mode=config.assertion_mode)

                # C5: Append calculator results if enabled
                calculator_context = ""
                if config.calculator_enabled:
                    calculator_context = self._get_calculator_context(
                        effective_patient_id, question.question,
                    )
                    if calculator_context:
                        evidence += f"\n\n=== Calculator Results ===\n{calculator_context}"

                user_prompt = (
                    f"Patient evidence:\n{evidence}\n\n"
                    f"Question: {question.question}\n\n"
                    f"Answer concisely based on the evidence above."
                )
                evidence_pieces = context.total_evidence_pieces
                graph_path_count = len(context.graph_paths)

            # Step 3: Call LLM (local Ollama or cloud API)
            if config.llm_provider == "ollama":
                response = await _call_ollama(
                    prompt=user_prompt,
                    system_prompt=CLINICAL_QA_SYSTEM_PROMPT,
                    model=config.llm_model,
                    base_url=config.ollama_base_url,
                )
            else:
                llm = get_llm_service(LLMConfig(
                    provider=LLMProvider(config.llm_provider),
                    model=config.llm_model,
                    max_tokens=512,
                    temperature=0.1,
                ))
                response = await llm.generate(
                    prompt=user_prompt,
                    system_prompt=CLINICAL_QA_SYSTEM_PROMPT,
                )

            predicted_answer = response.content.strip()
            latency_ms = (time.perf_counter() - t0) * 1000

            # Step 4: Score the answer (keyword or LLM judge)
            if config.use_llm_judge:
                result = await self._score_with_llm_judge(
                    question, predicted_answer, config,
                )
            else:
                result = self.qa_service.score_answer(
                    question, predicted_answer, config.condition,
                )
            result.latency_ms = latency_ms
            result.reasoning_trace = (
                f"Evidence pieces: {evidence_pieces}, "
                f"Graph paths: {graph_path_count}, "
                f"Tokens: {response.token_usage.total_tokens}"
            )

            return result

        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.warning(
                "QA question %s failed: %s", question.question_id, exc,
            )
            return QAResult(
                question_id=question.question_id,
                predicted_answer="",
                expected_answer=question.expected_answer,
                correct=False,
                score=0.0,
                category=question.category,
                condition=config.condition,
                latency_ms=latency_ms,
                error=str(exc)[:200],
            )

    def _get_raw_note_context(
        self,
        patient_id: str,
        rag_service: GraphAugmentedRAGService,
    ) -> str:
        """Get raw clinical note text for C1 condition (no RAG).

        Retrieves the most recent document for the patient and returns
        raw text — no graph traversal, no assertion enrichment.
        """
        try:
            from sqlalchemy import select
            from app.models.document import Document

            stmt = (
                select(Document)
                .where(Document.patient_id == patient_id)
                .order_by(Document.created_at.desc())
                .limit(3)
            )
            result = rag_service._session.execute(stmt)
            docs = list(result.scalars().all())
            if docs:
                return "\n\n---\n\n".join(
                    (d.text[:2000] if d.text else "") for d in docs
                )
            return "No clinical notes available for this patient."
        except Exception as exc:
            logger.warning("Raw note retrieval failed: %s", exc)
            return "No clinical notes available for this patient."

    def _get_calculator_context(
        self,
        patient_id: str,
        question: str,
    ) -> str:
        """Get calculator results for C5 condition.

        Identifies applicable calculators from the question context,
        runs them against patient KG data, and returns formatted results.
        """
        try:
            from app.services.calculator_reasoning_service import CalculatorReasoningService

            calc_service = CalculatorReasoningService()
            applicable = calc_service.identify_applicable_calculators(question)

            if not applicable:
                return ""

            results = []
            for calc_type in applicable[:3]:  # Limit to 3 calculators per question
                try:
                    calc_result = calc_service.calculate_for_patient(
                        patient_id=patient_id,
                        calculator_type=calc_type,
                    )
                    if calc_result and calc_result.get("score") is not None:
                        name = calc_result.get("calculator_name", calc_type)
                        score = calc_result["score"]
                        interpretation = calc_result.get("interpretation", "")
                        results.append(f"{name}: {score} — {interpretation}")
                except Exception:
                    continue

            return "\n".join(results) if results else ""
        except Exception as exc:
            logger.debug("Calculator context failed: %s", exc)
            return ""

    async def _score_with_llm_judge(
        self,
        question: QAQuestion,
        predicted_answer: str,
        config: QARunConfig,
    ) -> QAResult:
        """Score using LLM judge (delegates to llm_judge module)."""
        try:
            from app.services.llm_judge import LLMJudge

            judge = LLMJudge()
            verdict = await judge.score(
                question=question.question,
                expected_answer=question.expected_answer,
                predicted_answer=predicted_answer,
                category=question.category,
                scoring_rubric=question.scoring_rubric,
            )
            return QAResult(
                question_id=question.question_id,
                predicted_answer=predicted_answer,
                expected_answer=question.expected_answer,
                correct=verdict.overall_correct,
                score=verdict.overall_score,
                category=question.category,
                condition=config.condition,
                reasoning_trace=verdict.reasoning,
            )
        except Exception as exc:
            logger.warning("LLM judge failed, falling back to keyword: %s", exc)
            return self.qa_service.score_answer(
                question, predicted_answer, config.condition,
            )

    async def run_question_set(
        self,
        questions: list[QAQuestion],
        config: QARunConfig,
        experiment_name: str,
        run_id: str | None = None,
    ) -> QAEvaluationReport:
        """Run a full question set through GraphRAG + LLM.

        Args:
            questions: Questions to evaluate.
            config: QA run configuration.
            experiment_name: Name for the report.
            run_id: Optional research run ID for metric recording.

        Returns:
            QAEvaluationReport with per-question results.
        """
        with Session(get_sync_engine()) as session:
            rag_service = GraphAugmentedRAGService(session)

            results: list[QAResult] = []
            for i, question in enumerate(questions):
                logger.info(
                    "QA [%s/%s] %s | %s | %s",
                    i + 1, len(questions),
                    config.condition,
                    question.category,
                    question.question_id,
                )
                result = await self._ask_question(question, config, rag_service)
                results.append(result)

        # Build aggregate report
        total = len(results)
        correct = sum(1 for r in results if r.correct)
        accuracy = correct / total if total > 0 else 0.0

        category_correct: dict[str, int] = {}
        category_total: dict[str, int] = {}
        for r in results:
            category_total[r.category] = category_total.get(r.category, 0) + 1
            if r.correct:
                category_correct[r.category] = category_correct.get(r.category, 0) + 1

        category_accuracies = {
            cat: category_correct.get(cat, 0) / category_total[cat]
            for cat in category_total
        }

        avg_latency = (
            sum(r.latency_ms for r in results) / total if total > 0 else 0.0
        )

        report = QAEvaluationReport(
            experiment_name=experiment_name,
            condition=config.condition,
            total_questions=total,
            correct=correct,
            accuracy=accuracy,
            category_accuracies=category_accuracies,
            avg_latency_ms=avg_latency,
            results=results,
        )

        # Record metrics to research service if run_id provided
        if run_id:
            self._record_report_metrics(run_id, report, config)

        return report

    def _record_report_metrics(
        self,
        run_id: str,
        report: QAEvaluationReport,
        config: QARunConfig,
    ) -> None:
        """Record QA evaluation metrics to the research service."""
        svc = self.research_service

        # Overall accuracy
        svc.record_metric(
            run_id, "rag", "qa_accuracy", report.accuracy,
            detail={
                "condition": config.condition,
                "assertion_mode": config.assertion_mode,
                "temporal_mode": config.temporal_mode,
                "retrieval_mode": config.retrieval_mode,
                "total_questions": report.total_questions,
                "correct": report.correct,
            },
        )

        # Per-category accuracy
        for cat, acc in report.category_accuracies.items():
            svc.record_metric(
                run_id, "rag", f"qa_accuracy_{cat}", acc,
                detail={"category": cat, "condition": config.condition},
            )

        # Clinical safety score
        safety_score = self.qa_service.compute_clinical_safety_score(report.results)
        svc.record_metric(
            run_id, "rag", "clinical_safety_score", safety_score,
            detail={"condition": config.condition},
        )

        # Latency
        svc.record_metric(
            run_id, "rag", "avg_qa_latency_ms", report.avg_latency_ms,
        )

        # Error count
        errors = sum(1 for r in report.results if r.error)
        svc.record_metric(run_id, "rag", "qa_errors", float(errors))

    # ========================================================================
    # Convenience methods for each experiment
    # ========================================================================

    async def run_assertion_ablation(
        self,
        patient_id: str,
        run_id: str | None = None,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-sonnet-4-5-20250929",
    ) -> dict[str, QAEvaluationReport]:
        """Run Experiment 2: Assertion ablation across all 3 conditions.

        Returns dict mapping condition name to evaluation report.
        """
        conditions = {
            "no_assertion": "none",
            "assertion_extracted_only": "extracted_only",
            "full_epistemic": "full",
        }

        reports = {}
        for condition, assertion_mode in conditions.items():
            config = QARunConfig(
                patient_id=patient_id,
                condition=condition,
                assertion_mode=assertion_mode,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            report = await self.run_question_set(
                questions=ASSERTION_QUESTIONS,
                config=config,
                experiment_name=f"Exp2: Assertion Ablation ({condition})",
                run_id=run_id,
            )
            reports[condition] = report
            logger.info(
                "Exp2 [%s]: accuracy=%.1f%%, safety=%.3f",
                condition,
                report.accuracy * 100,
                self.qa_service.compute_clinical_safety_score(report.results),
            )

        return reports

    async def run_temporal_ablation(
        self,
        patient_id: str,
        run_id: str | None = None,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-sonnet-4-5-20250929",
    ) -> dict[str, QAEvaluationReport]:
        """Run Experiment 3: Temporal ablation across all 3 conditions."""
        conditions = {
            "no_temporal": "no_temporal",
            "timestamps_only": "timestamps_only",
            "full_bitemporal": "full_bitemporal",
        }

        reports = {}
        for condition, temporal_mode in conditions.items():
            config = QARunConfig(
                patient_id=patient_id,
                condition=condition,
                temporal_mode=temporal_mode,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            report = await self.run_question_set(
                questions=TEMPORAL_QUESTIONS,
                config=config,
                experiment_name=f"Exp3: Temporal Ablation ({condition})",
                run_id=run_id,
            )
            reports[condition] = report
            logger.info(
                "Exp3 [%s]: accuracy=%.1f%%", condition, report.accuracy * 100,
            )

        return reports

    async def run_graphrag_comparison(
        self,
        patient_id: str,
        run_id: str | None = None,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-sonnet-4-5-20250929",
    ) -> dict[str, QAEvaluationReport]:
        """Run Experiment 4: Graph-RAG vs Document-RAG across 4 conditions."""
        conditions = {
            "doc_only": "doc_only",
            "graph_only": "graph_only",
            "graph_plus_doc": "graph_plus_doc",
            "graph_plus_doc_plus_guidelines": "graph_plus_doc_plus_guidelines",
        }

        reports = {}
        for condition, retrieval_mode in conditions.items():
            config = QARunConfig(
                patient_id=patient_id,
                condition=condition,
                retrieval_mode=retrieval_mode,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            report = await self.run_question_set(
                questions=RAG_QUESTIONS,
                config=config,
                experiment_name=f"Exp4: GraphRAG Comparison ({condition})",
                run_id=run_id,
            )
            reports[condition] = report
            logger.info(
                "Exp4 [%s]: accuracy=%.1f%%", condition, report.accuracy * 100,
            )

        return reports

    async def run_all_qa_experiments(
        self,
        patient_id: str,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-sonnet-4-5-20250929",
    ) -> dict[str, dict[str, QAEvaluationReport]]:
        """Run all QA experiments (2, 3, 4) for a patient.

        Returns nested dict: {experiment: {condition: report}}.
        """
        logger.info("=" * 60)
        logger.info("Running all QA experiments for patient %s (model=%s)", patient_id, llm_model)
        logger.info("=" * 60)

        results = {}

        logger.info("--- Experiment 2: Assertion Ablation ---")
        results["exp2_assertion"] = await self.run_assertion_ablation(
            patient_id, llm_provider=llm_provider, llm_model=llm_model,
        )

        logger.info("--- Experiment 3: Temporal Ablation ---")
        results["exp3_temporal"] = await self.run_temporal_ablation(
            patient_id, llm_provider=llm_provider, llm_model=llm_model,
        )

        logger.info("--- Experiment 4: GraphRAG Comparison ---")
        results["exp4_graphrag"] = await self.run_graphrag_comparison(
            patient_id, llm_provider=llm_provider, llm_model=llm_model,
        )

        # Print summary
        logger.info("=" * 60)
        logger.info("QA EXPERIMENT SUMMARY")
        logger.info("=" * 60)
        for exp_name, reports in results.items():
            for condition, report in reports.items():
                safety = self.qa_service.compute_clinical_safety_score(report.results)
                logger.info(
                    "  %s | %s: accuracy=%.1f%% safety=%.3f (%d/%d correct)",
                    exp_name, condition,
                    report.accuracy * 100, safety,
                    report.correct, report.total_questions,
                )

        return results


def print_ablation_table(reports: dict[str, QAEvaluationReport]) -> str:
    """Format ablation results as a markdown table for paper/logging."""
    lines = [
        "| Condition | Overall Acc | " +
        " | ".join(sorted({cat for r in reports.values() for cat in r.category_accuracies})) +
        " | Safety |",
        "|---|---|" +
        "|".join("---" for _ in sorted({cat for r in reports.values() for cat in r.category_accuracies})) +
        "|---|",
    ]

    qa_svc = QAEvaluationService()
    all_cats = sorted({cat for r in reports.values() for cat in r.category_accuracies})

    for condition, report in reports.items():
        safety = qa_svc.compute_clinical_safety_score(report.results)
        cat_values = " | ".join(
            f"{report.category_accuracies.get(cat, 0.0):.1%}" for cat in all_cats
        )
        lines.append(
            f"| {condition} | {report.accuracy:.1%} | {cat_values} | {safety:.3f} |"
        )

    return "\n".join(lines)
