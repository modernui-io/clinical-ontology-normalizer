"""Longitudinal Clinical Benchmark — experiment runner + scorer + analysis.

Executes all ablation conditions (B0-B3) across the cohort, scores answers
against HealthBench-style rubric criteria using LLM judge, and produces
the analysis report with per-tier/per-condition breakdowns.

Usage:
    runner = LongBenchRunner(session)
    report = await runner.run(cohort, conditions=[ConditionID.B0, ..., ConditionID.B3])
    analysis = LongBenchAnalyzer.analyze(report)
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import get_sync_engine
from app.services.graph_augmented_rag import GraphAugmentedRAGService
from app.services.llm_service import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    get_llm_service,
)
from app.services.longbench_schemas import (
    ConditionID,
    ConditionTierScore,
    CriterionResult,
    CriterionType,
    LongBenchCohort,
    LongBenchQuestion,
    LongBenchReport,
    LongBenchResult,
    LongitudinalTier,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Condition configs — maps ConditionID to execution parameters
# ============================================================================

CONDITION_CONFIGS: dict[ConditionID, dict[str, Any]] = {
    ConditionID.B0: {
        "label": "LLM Alone",
        "raw_note_only": False,
        "no_patient_data": True,  # B0: no context at all
        "retrieval_mode": None,
        "assertion_mode": "none",
        "temporal_mode": "no_temporal",
    },
    ConditionID.B1: {
        "label": "Latest Note Only",
        "raw_note_only": True,
        "no_patient_data": False,
        "latest_only": True,
        "retrieval_mode": "doc_only",
        "assertion_mode": "none",
        "temporal_mode": "no_temporal",
    },
    ConditionID.B2: {
        "label": "All Notes RAG",
        "raw_note_only": False,
        "no_patient_data": False,
        "retrieval_mode": "doc_only",
        "assertion_mode": "none",
        "temporal_mode": "no_temporal",
    },
    ConditionID.B3: {
        "label": "Full KG-RAG",
        "raw_note_only": False,
        "no_patient_data": False,
        "retrieval_mode": "graph_plus_doc",
        "assertion_mode": "full",
        "temporal_mode": "full_bitemporal",
    },
}


# ============================================================================
# System prompts
# ============================================================================

SYSTEM_PROMPT_BASE = """\
You are a clinical reasoning assistant answering questions about a specific patient.
Use ONLY the provided evidence to answer. Be precise and concise.
If the evidence is insufficient, say so rather than guessing.
Answer in 2-5 sentences with clinical specificity."""

SYSTEM_PROMPT_NO_CONTEXT = """\
You are a clinical reasoning assistant. Answer the following clinical question
using your medical knowledge. Be precise and concise.
Answer in 2-5 sentences."""

SYSTEM_PROMPT_EPISTEMIC = """\
You are a clinical reasoning assistant answering questions about a specific patient.
Use ONLY the provided evidence to answer. Be precise and concise.

CRITICAL — The evidence includes ASSERTION STATUS and EXPERIENCER metadata:

1. **NEGATED / ABSENT**: Patient definitively DOES NOT have that condition.
2. **UNCERTAIN / POSSIBLE**: Condition is suspected but NOT confirmed.
3. **FAMILY HISTORY / experiencer=family**: This is a relative's condition, NOT the patient's.
4. **HISTORICAL / RESOLVED**: Condition existed in the past but is now resolved.

Always check assertion status and experiencer attribution FIRST before answering.
For temporal questions, use the timeline and note changes over time.
Answer in 2-5 sentences with clinical specificity."""


# ============================================================================
# Runner
# ============================================================================


@dataclass
class LongBenchRunConfig:
    """Configuration for a longitudinal benchmark run."""

    llm_model: str = "claude-sonnet-4-5-20250929"
    llm_provider: str = "anthropic"
    judge_model: str = "claude-sonnet-4-5-20250929"
    judge_provider: str = "anthropic"
    max_hops: int = 2
    max_paths: int = 10
    random_seed: int = 42
    checkpoint_dir: str = "backend/data/benchmarks/results/longbench"


class LongBenchRunner:
    """Executes the longitudinal benchmark across all conditions."""

    def __init__(self, session: Session | None = None) -> None:
        self._session = session
        self._judge: _CriterionJudge | None = None

    async def run(
        self,
        cohort: LongBenchCohort,
        config: LongBenchRunConfig | None = None,
        conditions: list[ConditionID] | None = None,
    ) -> LongBenchReport:
        """Run the full benchmark.

        Args:
            cohort: Selected cohort with questions.
            config: Run configuration.
            conditions: Which conditions to run (default: all B0-B3).

        Returns:
            LongBenchReport with all results.
        """
        if config is None:
            config = LongBenchRunConfig()
        if conditions is None:
            conditions = list(ConditionID)

        self._judge = _CriterionJudge(
            model=config.judge_model,
            provider=config.judge_provider,
        )

        # Ensure checkpoint directory exists
        os.makedirs(config.checkpoint_dir, exist_ok=True)

        session = self._session
        if session is None:
            engine = get_sync_engine()
            session = Session(engine)

        all_results: list[LongBenchResult] = []

        try:
            for condition in conditions:
                logger.info("=" * 60)
                logger.info("Running condition: %s", condition.value)
                logger.info("=" * 60)

                # Load checkpoint for this condition
                checkpoint = self._load_checkpoint(config.checkpoint_dir, condition)

                rag_service = GraphAugmentedRAGService(session)

                for qi, question in enumerate(cohort.questions):
                    # Skip if checkpointed
                    if question.question_id in checkpoint:
                        cached = checkpoint[question.question_id]
                        all_results.append(cached)
                        continue

                    logger.info(
                        "[%s] %d/%d | %s | %s | tier=%s",
                        condition.value, qi + 1, len(cohort.questions),
                        question.question_id, question.domain.value,
                        question.tier.value,
                    )

                    result = await self._run_single(
                        question=question,
                        condition=condition,
                        config=config,
                        rag_service=rag_service,
                        session=session,
                    )
                    all_results.append(result)

                    # Checkpoint
                    self._save_checkpoint(
                        config.checkpoint_dir, condition, result, question,
                    )

                    # Reset session on error
                    if result.error:
                        try:
                            session.rollback()
                        except Exception:
                            pass
                        rag_service = GraphAugmentedRAGService(session)

        finally:
            if self._session is None:
                try:
                    session.close()
                except Exception:
                    pass

        report = LongBenchReport(
            cohort_id=cohort.cohort_id,
            results=all_results,
            total_questions=len(cohort.questions),
            total_criteria=sum(len(q.criteria) for q in cohort.questions),
        )

        # Compute aggregate scores
        report.condition_tier_scores = LongBenchAnalyzer.compute_condition_tier_scores(
            all_results, cohort.questions,
        )

        return report

    async def _run_single(
        self,
        question: LongBenchQuestion,
        condition: ConditionID,
        config: LongBenchRunConfig,
        rag_service: GraphAugmentedRAGService,
        session: Session,
    ) -> LongBenchResult:
        """Run a single question under a single condition."""
        t0 = time.perf_counter()
        cond_cfg = CONDITION_CONFIGS[condition]

        try:
            # Build the prompt based on condition
            user_prompt, system_prompt = self._build_prompt(
                question=question,
                condition=condition,
                cond_cfg=cond_cfg,
                config=config,
                rag_service=rag_service,
                session=session,
            )

            # Call LLM
            llm = get_llm_service(LLMConfig(
                provider=LLMProvider(config.llm_provider),
                model=config.llm_model,
                max_tokens=1024,
                temperature=0.0,
            ))
            response = await llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )
            predicted_answer = response.content.strip()
            latency_ms = (time.perf_counter() - t0) * 1000
            token_count = response.token_usage.total_tokens

            # Score against rubric criteria
            criterion_results = await self._judge.score_criteria(
                question=question,
                predicted_answer=predicted_answer,
            )

            result = LongBenchResult(
                question_id=question.question_id,
                patient_id=question.patient_id,
                condition=condition,
                tier=question.tier,
                domain=question.domain,
                predicted_answer=predicted_answer,
                criterion_results=criterion_results,
                latency_ms=latency_ms,
                token_count=token_count,
            )
            result.compute_scores(question.criteria)
            return result

        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.warning(
                "Question %s failed under %s: %s",
                question.question_id, condition.value, exc,
            )
            return LongBenchResult(
                question_id=question.question_id,
                patient_id=question.patient_id,
                condition=condition,
                tier=question.tier,
                domain=question.domain,
                predicted_answer="",
                latency_ms=latency_ms,
                error=str(exc)[:300],
            )

    def _build_prompt(
        self,
        question: LongBenchQuestion,
        condition: ConditionID,
        cond_cfg: dict,
        config: LongBenchRunConfig,
        rag_service: GraphAugmentedRAGService,
        session: Session,
    ) -> tuple[str, str]:
        """Build (user_prompt, system_prompt) for a condition."""
        # B0: no patient data at all
        if cond_cfg.get("no_patient_data"):
            return (
                f"Question: {question.question_text}\n\n"
                f"Answer based on your clinical knowledge.",
                SYSTEM_PROMPT_NO_CONTEXT,
            )

        # B1: latest note only
        if cond_cfg.get("raw_note_only") and cond_cfg.get("latest_only"):
            from app.services.longbench_cohort import LongBenchCohortSelector
            selector = LongBenchCohortSelector(session)
            notes = selector.get_patient_notes(question.patient_id, limit=1)
            note_text = notes[0]["text"] if notes else "No notes available."
            return (
                f"Clinical note:\n{note_text}\n\n"
                f"Question: {question.question_text}\n\n"
                f"Answer based on the note above.",
                SYSTEM_PROMPT_BASE,
            )

        # B2 / B3: use RAG pipeline
        retrieval_mode = cond_cfg.get("retrieval_mode", "doc_only")
        assertion_mode = cond_cfg.get("assertion_mode", "none")
        temporal_mode = cond_cfg.get("temporal_mode", "no_temporal")

        context = rag_service.retrieve_context(
            query=question.question_text,
            patient_id=question.patient_id,
            max_hops=config.max_hops,
            max_paths=config.max_paths,
            assertion_mode=assertion_mode,
            temporal_mode=temporal_mode,
            retrieval_mode=retrieval_mode,
        )
        evidence = context.to_llm_prompt(assertion_mode=assertion_mode)

        system = (
            SYSTEM_PROMPT_EPISTEMIC if assertion_mode == "full"
            else SYSTEM_PROMPT_BASE
        )
        return (
            f"Patient evidence:\n{evidence}\n\n"
            f"Question: {question.question_text}\n\n"
            f"Answer based on the evidence above.",
            system,
        )

    # ========================================================================
    # Checkpointing
    # ========================================================================

    def _load_checkpoint(
        self, checkpoint_dir: str, condition: ConditionID,
    ) -> dict[str, LongBenchResult]:
        """Load checkpoint for a condition."""
        path = os.path.join(checkpoint_dir, f"{condition.value}.jsonl")
        results: dict[str, LongBenchResult] = {}
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    if entry.get("error"):
                        continue  # Retry errors
                    result = LongBenchResult(
                        question_id=entry["question_id"],
                        patient_id=entry["patient_id"],
                        condition=condition,
                        tier=LongitudinalTier(entry["tier"]),
                        domain=entry.get("domain", "problem_list"),
                        predicted_answer=entry.get("predicted_answer", ""),
                        normalized_score=entry.get("normalized_score", 0.0),
                        raw_score=entry.get("raw_score", 0.0),
                        max_score=entry.get("max_score", 0.0),
                        latency_ms=entry.get("latency_ms", 0.0),
                        token_count=entry.get("token_count", 0),
                    )
                    results[result.question_id] = result
        except FileNotFoundError:
            pass
        if results:
            logger.info(
                "Loaded %d checkpointed results for %s",
                len(results), condition.value,
            )
        return results

    def _save_checkpoint(
        self,
        checkpoint_dir: str,
        condition: ConditionID,
        result: LongBenchResult,
        question: LongBenchQuestion,
    ) -> None:
        """Append a single result to the checkpoint JSONL."""
        path = os.path.join(checkpoint_dir, f"{condition.value}.jsonl")
        entry = {
            "question_id": result.question_id,
            "patient_id": result.patient_id,
            "condition": condition.value,
            "tier": result.tier.value,
            "domain": result.domain.value if hasattr(result.domain, "value") else str(result.domain),
            "predicted_answer": result.predicted_answer[:1000],
            "normalized_score": result.normalized_score,
            "raw_score": result.raw_score,
            "max_score": result.max_score,
            "latency_ms": result.latency_ms,
            "token_count": result.token_count,
            "error": result.error,
            "criterion_results": [
                {
                    "criterion_id": cr.criterion_id,
                    "satisfied": cr.satisfied,
                    "confidence": cr.confidence,
                }
                for cr in result.criterion_results
            ],
        }
        with open(path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")


# ============================================================================
# Criterion Judge — LLM-based rubric scoring
# ============================================================================

JUDGE_PROMPT = """\
You are a clinical QA rubric judge. Given a predicted answer and a list of rubric criteria,
score each criterion as SATISFIED (true) or NOT SATISFIED (false).

PREDICTED ANSWER:
{predicted_answer}

RUBRIC CRITERIA:
{criteria_text}

For EACH criterion, output a JSON object:
{{
  "criterion_id": "...",
  "satisfied": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Output a JSON array of these objects — one per criterion. No markdown, just JSON.
"""


class _CriterionJudge:
    """Scores predicted answers against rubric criteria using LLM judge."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-5-20250929",
        provider: str = "anthropic",
    ) -> None:
        self._llm_config = LLMConfig(
            provider=LLMProvider(provider),
            model=model,
            max_tokens=2048,
            temperature=0.0,
        )

    async def score_criteria(
        self,
        question: LongBenchQuestion,
        predicted_answer: str,
    ) -> list[CriterionResult]:
        """Score a predicted answer against all criteria for a question."""
        if not question.criteria or not predicted_answer:
            return []

        criteria_text = "\n".join(
            f"- [{c.criterion_id}] ({c.weight.value}): {c.text}"
            for c in question.criteria
        )

        prompt = JUDGE_PROMPT.format(
            predicted_answer=predicted_answer,
            criteria_text=criteria_text,
        )

        try:
            llm = get_llm_service(self._llm_config)
            response = await llm.generate(
                prompt=prompt,
                system_prompt="You are a precise clinical QA rubric judge. Output valid JSON only.",
            )

            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            verdicts = json.loads(raw)
            if not isinstance(verdicts, list):
                verdicts = [verdicts]

            results = []
            for v in verdicts:
                results.append(CriterionResult(
                    criterion_id=v.get("criterion_id", ""),
                    satisfied=bool(v.get("satisfied", False)),
                    confidence=float(v.get("confidence", 0.5)),
                    reasoning=v.get("reasoning", ""),
                ))
            return results

        except Exception as exc:
            logger.warning("Criterion judge failed: %s", exc)
            # Conservative fallback: mark all as not satisfied
            return [
                CriterionResult(
                    criterion_id=c.criterion_id,
                    satisfied=False,
                    confidence=0.0,
                    reasoning=f"Judge error: {exc}",
                )
                for c in question.criteria
            ]


# ============================================================================
# Analysis
# ============================================================================


class LongBenchAnalyzer:
    """Computes aggregate analysis from benchmark results."""

    @staticmethod
    def compute_condition_tier_scores(
        results: list[LongBenchResult],
        questions: list[LongBenchQuestion],
    ) -> list[ConditionTierScore]:
        """Compute per-condition x per-tier aggregate scores."""
        question_map = {q.question_id: q for q in questions}

        # Group results by (condition, tier)
        groups: dict[tuple[ConditionID, LongitudinalTier], list[LongBenchResult]] = {}
        for r in results:
            key = (r.condition, r.tier)
            groups.setdefault(key, []).append(r)

        scores: list[ConditionTierScore] = []
        for (condition, tier), group in sorted(groups.items()):
            valid = [r for r in group if not r.error]
            n = len(valid)
            if n == 0:
                scores.append(ConditionTierScore(
                    condition=condition, tier=tier, n_questions=0,
                ))
                continue

            mean = sum(r.normalized_score for r in valid) / n
            variance = sum((r.normalized_score - mean) ** 2 for r in valid) / n
            std = math.sqrt(variance)

            # Per-criterion-type breakdown
            type_satisfied: dict[str, int] = {}
            type_total: dict[str, int] = {}
            for r in valid:
                q = question_map.get(r.question_id)
                if not q:
                    continue
                crit_map = {c.criterion_id: c for c in q.criteria}
                for cr in r.criterion_results:
                    crit = crit_map.get(cr.criterion_id)
                    if not crit:
                        continue
                    ct = crit.criterion_type.value
                    type_total[ct] = type_total.get(ct, 0) + 1
                    if cr.satisfied:
                        type_satisfied[ct] = type_satisfied.get(ct, 0) + 1

            type_scores = {
                ct: type_satisfied.get(ct, 0) / type_total[ct]
                for ct in type_total
            }

            scores.append(ConditionTierScore(
                condition=condition,
                tier=tier,
                n_questions=n,
                mean_score=mean,
                std_score=std,
                criterion_type_scores=type_scores,
                criterion_type_counts=type_total,
            ))

        return scores

    @staticmethod
    def to_markdown_table(scores: list[ConditionTierScore]) -> str:
        """Format condition x tier scores as a markdown table."""
        tiers = sorted({s.tier for s in scores}, key=lambda t: t.value)
        conditions = sorted({s.condition for s in scores}, key=lambda c: c.value)

        lookup = {(s.condition, s.tier): s for s in scores}

        header = "| Condition | " + " | ".join(f"Tier {t.value}" for t in tiers) + " |"
        sep = "|---|" + "|".join("---" for _ in tiers) + "|"

        lines = [header, sep]
        for cond in conditions:
            cells = []
            for tier in tiers:
                s = lookup.get((cond, tier))
                if s and s.n_questions > 0:
                    cells.append(f"{s.mean_score:.1%} (n={s.n_questions})")
                else:
                    cells.append("N/A")
            label = CONDITION_CONFIGS[cond]["label"]
            lines.append(f"| {label} | " + " | ".join(cells) + " |")

        return "\n".join(lines)

    @staticmethod
    def to_criterion_type_table(scores: list[ConditionTierScore]) -> str:
        """Format per-criterion-type scores as a markdown table."""
        # Collect all criterion types
        all_types: set[str] = set()
        for s in scores:
            all_types.update(s.criterion_type_scores.keys())
        all_types_sorted = sorted(all_types)

        if not all_types_sorted:
            return "No criterion-type data available."

        conditions = sorted({s.condition for s in scores}, key=lambda c: c.value)

        # Aggregate across tiers per condition
        cond_type_scores: dict[ConditionID, dict[str, tuple[int, int]]] = {}
        for s in scores:
            if s.condition not in cond_type_scores:
                cond_type_scores[s.condition] = {}
            for ct in all_types_sorted:
                sat = int(s.criterion_type_scores.get(ct, 0) * s.criterion_type_counts.get(ct, 0))
                tot = s.criterion_type_counts.get(ct, 0)
                prev = cond_type_scores[s.condition].get(ct, (0, 0))
                cond_type_scores[s.condition][ct] = (prev[0] + sat, prev[1] + tot)

        header = "| Condition | " + " | ".join(all_types_sorted) + " |"
        sep = "|---|" + "|".join("---" for _ in all_types_sorted) + "|"

        lines = [header, sep]
        for cond in conditions:
            cells = []
            for ct in all_types_sorted:
                sat, tot = cond_type_scores.get(cond, {}).get(ct, (0, 0))
                if tot > 0:
                    cells.append(f"{sat / tot:.1%}")
                else:
                    cells.append("—")
            label = CONDITION_CONFIGS[cond]["label"]
            lines.append(f"| {label} | " + " | ".join(cells) + " |")

        return "\n".join(lines)

    @staticmethod
    def report_to_json(report: LongBenchReport) -> dict:
        """Serialize a report to JSON-compatible dict."""
        return {
            "cohort_id": report.cohort_id,
            "total_questions": report.total_questions,
            "total_criteria": report.total_criteria,
            "metadata": report.metadata,
            "condition_tier_scores": [
                {
                    "condition": s.condition.value,
                    "tier": s.tier.value,
                    "n_questions": s.n_questions,
                    "mean_score": s.mean_score,
                    "std_score": s.std_score,
                    "criterion_type_scores": s.criterion_type_scores,
                    "criterion_type_counts": s.criterion_type_counts,
                }
                for s in report.condition_tier_scores
            ],
            "results": [
                {
                    "question_id": r.question_id,
                    "patient_id": r.patient_id,
                    "condition": r.condition.value,
                    "tier": r.tier.value,
                    "domain": r.domain.value if hasattr(r.domain, "value") else str(r.domain),
                    "normalized_score": r.normalized_score,
                    "raw_score": r.raw_score,
                    "max_score": r.max_score,
                    "latency_ms": r.latency_ms,
                    "token_count": r.token_count,
                    "error": r.error,
                    "predicted_answer": r.predicted_answer[:500],
                }
                for r in report.results
            ],
        }
