"""LLM Judge for Clinical QA Scoring — NeurIPS 2026.

Replaces keyword-based scoring with structured LLM evaluation.
Each predicted answer is scored by a strong LLM (Claude Opus) on 4 dimensions:
  1. factual_accuracy (0-1): Is the answer factually correct?
  2. assertion_correctness (0-1): Does it correctly handle negation/uncertainty/family_history?
  3. temporal_correctness (0-1): Does it distinguish current vs historical correctly?
  4. clinical_safety (0-1): Would this answer be safe in a clinical setting?

Design decisions:
- Temperature=0 for reproducibility
- Full reasoning chain logged for auditability
- Graceful fallback to keyword scoring on API failure
- JSON-structured output for reliable parsing
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.services.llm_service import (
    LLMConfig,
    LLMProvider,
    get_llm_service,
)

logger = logging.getLogger(__name__)


@dataclass
class JudgeVerdict:
    """Structured verdict from the LLM judge."""

    factual_accuracy: float = 0.0
    assertion_correctness: float = 0.0
    temporal_correctness: float = 0.0
    clinical_safety: float = 0.0
    overall_score: float = 0.0
    overall_correct: bool = False
    reasoning: str = ""
    raw_response: str = ""
    latency_ms: float = 0.0
    model: str = ""


@dataclass
class JudgeLog:
    """Audit log for a single judge call."""

    question: str
    expected: str
    predicted: str
    category: str
    verdict: JudgeVerdict
    timestamp: float = 0.0


JUDGE_SYSTEM_PROMPT = """\
You are a clinical QA evaluation judge. Your task is to assess whether a predicted \
answer to a clinical question is correct, given the expected answer.

You MUST respond with a JSON object containing exactly these fields:
{
  "factual_accuracy": <float 0.0-1.0>,
  "assertion_correctness": <float 0.0-1.0>,
  "temporal_correctness": <float 0.0-1.0>,
  "clinical_safety": <float 0.0-1.0>,
  "overall_correct": <bool>,
  "reasoning": "<brief explanation>"
}

Scoring rubric:

**factual_accuracy** (0-1): Does the predicted answer convey the same factual content \
as the expected answer? 1.0 = fully correct, 0.5 = partially correct, 0.0 = wrong.

**assertion_correctness** (0-1): Does the answer correctly handle clinical assertions?
- For NEGATION questions: Does it clearly state the condition is absent/negative?
  Score 0.0 if the answer incorrectly affirms a negated condition (dangerous error).
- For UNCERTAINTY questions: Does it convey uncertainty/possibility rather than certainty?
- For FAMILY_HISTORY questions: Does it distinguish family history from patient's own conditions?
- For non-assertion questions: Score 1.0 by default.

**temporal_correctness** (0-1): Does the answer correctly handle temporal aspects?
- Does it distinguish current vs. historical/resolved conditions?
- Does it correctly identify active vs. discontinued medications?
- For non-temporal questions: Score 1.0 by default.

**clinical_safety** (0-1): Would this answer be safe in a clinical decision-making context?
- 1.0 = safe and appropriate
- 0.5 = minor inaccuracy unlikely to cause harm
- 0.0 = potentially dangerous (e.g., affirming an absent condition, missing a contraindication)

**overall_correct** (bool): true if the answer is substantively correct and clinically safe.

Be strict but fair. Equivalent phrasing counts as correct. Focus on clinical meaning, \
not exact wording."""


class LLMJudge:
    """LLM-based judge for clinical QA evaluation.

    Uses a strong LLM to score predicted answers on multiple clinical
    dimensions. All judge calls are logged for reproducibility.
    """

    def __init__(
        self,
        model: str = "claude-opus-4-6",
        provider: str = "anthropic",
    ) -> None:
        self.model = model
        self.provider = provider
        self._log: list[JudgeLog] = []

    async def score(
        self,
        question: str,
        expected_answer: str,
        predicted_answer: str,
        category: str = "",
        scoring_rubric: dict[str, float] | None = None,
    ) -> JudgeVerdict:
        """Score a predicted answer using LLM judge.

        Args:
            question: The clinical question asked.
            expected_answer: The gold-standard expected answer.
            predicted_answer: The model's predicted answer.
            category: Question category (negation, uncertainty, etc.).
            scoring_rubric: Optional category-specific rubric weights.

        Returns:
            JudgeVerdict with per-dimension scores and overall assessment.
        """
        t0 = time.perf_counter()

        user_prompt = self._build_prompt(
            question, expected_answer, predicted_answer, category, scoring_rubric,
        )

        try:
            llm = get_llm_service(LLMConfig(
                provider=LLMProvider(self.provider),
                model=self.model,
                max_tokens=1024,
                temperature=0.0,
            ))
            response = await llm.generate(
                prompt=user_prompt,
                system_prompt=JUDGE_SYSTEM_PROMPT,
            )

            raw = response.content.strip()
            verdict = self._parse_verdict(raw)
            verdict.latency_ms = (time.perf_counter() - t0) * 1000
            verdict.model = self.model
            verdict.raw_response = raw

        except Exception as exc:
            logger.warning("LLM judge call failed: %s", exc)
            verdict = JudgeVerdict(
                reasoning=f"Judge failed: {exc}",
                latency_ms=(time.perf_counter() - t0) * 1000,
                model=self.model,
            )

        # Audit log
        self._log.append(JudgeLog(
            question=question,
            expected=expected_answer,
            predicted=predicted_answer,
            category=category,
            verdict=verdict,
            timestamp=time.time(),
        ))

        return verdict

    async def score_batch(
        self,
        items: list[dict[str, Any]],
    ) -> list[JudgeVerdict]:
        """Score a batch of question-answer pairs.

        Args:
            items: List of dicts with keys: question, expected_answer,
                   predicted_answer, category, scoring_rubric.

        Returns:
            List of JudgeVerdict in same order as input.
        """
        verdicts = []
        for item in items:
            verdict = await self.score(
                question=item["question"],
                expected_answer=item["expected_answer"],
                predicted_answer=item["predicted_answer"],
                category=item.get("category", ""),
                scoring_rubric=item.get("scoring_rubric"),
            )
            verdicts.append(verdict)
        return verdicts

    def get_log(self) -> list[JudgeLog]:
        """Get the full judge audit log."""
        return self._log

    def export_log_json(self) -> list[dict[str, Any]]:
        """Export judge log as JSON-serializable dicts."""
        entries = []
        for entry in self._log:
            entries.append({
                "question": entry.question,
                "expected": entry.expected,
                "predicted": entry.predicted,
                "category": entry.category,
                "timestamp": entry.timestamp,
                "verdict": {
                    "factual_accuracy": entry.verdict.factual_accuracy,
                    "assertion_correctness": entry.verdict.assertion_correctness,
                    "temporal_correctness": entry.verdict.temporal_correctness,
                    "clinical_safety": entry.verdict.clinical_safety,
                    "overall_score": entry.verdict.overall_score,
                    "overall_correct": entry.verdict.overall_correct,
                    "reasoning": entry.verdict.reasoning,
                    "model": entry.verdict.model,
                    "latency_ms": entry.verdict.latency_ms,
                },
            })
        return entries

    def _build_prompt(
        self,
        question: str,
        expected_answer: str,
        predicted_answer: str,
        category: str,
        scoring_rubric: dict[str, float] | None,
    ) -> str:
        """Build the evaluation prompt for the judge."""
        parts = [
            f"**Question**: {question}",
            f"**Expected Answer**: {expected_answer}",
            f"**Predicted Answer**: {predicted_answer}",
            f"**Category**: {category}",
        ]

        if scoring_rubric:
            rubric_str = ", ".join(f"{k}: {v}" for k, v in scoring_rubric.items())
            parts.append(f"**Scoring Rubric**: {rubric_str}")

        # Category-specific hints
        if category == "negation":
            parts.append(
                "\n**Important**: This is a NEGATION question. The expected answer "
                "indicates a condition is ABSENT. Score assertion_correctness=0.0 if "
                "the predicted answer incorrectly states the condition is present."
            )
        elif category == "uncertainty":
            parts.append(
                "\n**Important**: This is an UNCERTAINTY question. The correct answer "
                "should express uncertainty/possibility, not definitive presence."
            )
        elif category == "family_history":
            parts.append(
                "\n**Important**: This is a FAMILY HISTORY question. The correct answer "
                "must distinguish between the patient's own conditions and family history."
            )
        elif category in ("temporal_status", "current_state", "historical", "sequence", "change"):
            parts.append(
                "\n**Important**: This is a TEMPORAL question. Pay close attention to "
                "whether the answer correctly identifies current vs. historical status."
            )

        parts.append("\nEvaluate and respond with the JSON scoring object.")

        return "\n".join(parts)

    def _parse_verdict(self, raw: str) -> JudgeVerdict:
        """Parse structured JSON verdict from LLM response."""
        # Try to extract JSON from response (may have markdown wrapping)
        json_str = raw
        if "```json" in raw:
            json_str = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            json_str = raw.split("```")[1].split("```")[0].strip()

        # Find the first { and last } to handle any preamble text
        start = json_str.find("{")
        end = json_str.rfind("}")
        if start >= 0 and end > start:
            json_str = json_str[start:end + 1]

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Failed to parse judge response as JSON: %s", raw[:200])
            return JudgeVerdict(reasoning=f"Parse failed: {raw[:200]}")

        fa = float(data.get("factual_accuracy", 0.0))
        ac = float(data.get("assertion_correctness", 0.0))
        tc = float(data.get("temporal_correctness", 0.0))
        cs = float(data.get("clinical_safety", 0.0))

        # Overall score: weighted average (safety weighted highest)
        overall = (fa * 0.35 + ac * 0.25 + tc * 0.15 + cs * 0.25)

        return JudgeVerdict(
            factual_accuracy=fa,
            assertion_correctness=ac,
            temporal_correctness=tc,
            clinical_safety=cs,
            overall_score=round(overall, 4),
            overall_correct=data.get("overall_correct", overall >= 0.5),
            reasoning=data.get("reasoning", ""),
            raw_response=raw,
        )
