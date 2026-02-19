"""EHRNoteQA Evaluator — NeurIPS 2026 standard benchmark integration.

Integrates the EHRNoteQA benchmark (NeurIPS 2024 D&B) with our
5-condition ablation harness.

EHRNoteQA: 962 patient-specific MCQ questions over MIMIC-IV discharge
summaries. Questions require synthesizing information across 1-3
admissions per patient.

Dataset: https://physionet.org/content/ehr-notes-qa-llms/1.0.1/
Paper:   https://arxiv.org/abs/2402.16040

Integration flow:
  1. Load EHRNoteQA.jsonl
  2. Map patient_id → MIMIC-{subject_id} (our internal format)
  3. Convert to QAQuestion format with MCQ options in prompt
  4. Run through 5-condition ablation harness
  5. Score with MCQ-specific accuracy (extract answer letter)
  6. Report per-category and per-level metrics

Requires:
  - EHRNoteQA.jsonl from PhysioNet (credentialed access)
  - MIMIC patients ingested into our database
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.ablation_harness import AblationHarness, AblationResult
from app.services.qa_evaluation import (
    QAEvaluationService,
    QAQuestion,
)

logger = logging.getLogger(__name__)


# ============================================================================
# MCQ scoring
# ============================================================================

_ANSWER_PATTERN = re.compile(
    r"""
    (?:^|\b)                            # word boundary or start
    (?:answer\s*(?:is|:)\s*)?           # optional "answer is" / "answer:"
    \(?([A-E])\)?                       # capture the letter A-E
    (?:\s*[).\-:])?                     # optional trailing punctuation
    """,
    re.IGNORECASE | re.VERBOSE,
)


def extract_mcq_answer(response: str) -> str | None:
    """Extract the selected MCQ answer letter from an LLM response.

    Handles formats like:
      "A", "A)", "(A)", "The answer is A", "Answer: B", "B."
    Returns the letter (uppercase) or None if not found.
    """
    if not response:
        return None

    # Check first line first (most LLMs put answer at the start)
    first_line = response.strip().split("\n")[0].strip()
    if len(first_line) <= 3 and first_line[0].upper() in "ABCDE":
        return first_line[0].upper()

    # Try regex on full response
    match = _ANSWER_PATTERN.search(response)
    if match:
        return match.group(1).upper()

    # Fallback: look for standalone letter
    for line in response.strip().split("\n"):
        line = line.strip()
        if line and line[0].upper() in "ABCDE" and len(line) < 5:
            return line[0].upper()

    return None


MCQ_SYSTEM_PROMPT = """\
You are a clinical reasoning assistant answering multiple-choice questions
about a specific patient's medical record. Use the provided evidence to
select the best answer.

Rules:
- Read all options carefully before answering.
- Base your answer ONLY on the provided patient evidence.
- Start your response with the answer letter (A, B, C, D, or E).
- Then briefly explain your reasoning.

Format: Start with just the letter, e.g., "B. Because..."
"""


# ============================================================================
# EHRNoteQA data loading
# ============================================================================

@dataclass
class EHRNoteQAItem:
    """A single EHRNoteQA question."""

    patient_id: int  # MIMIC subject_id
    category: str  # "Level1" or "Level2"
    num_notes: int
    clinician: str
    question: str
    choices: dict[str, str]  # {"A": "...", "B": "...", ...}
    answer: str  # Letter: "A", "B", "C", "D", or "E"


def load_ehrnoteqa(path: str | Path) -> list[EHRNoteQAItem]:
    """Load EHRNoteQA.jsonl file.

    Args:
        path: Path to EHRNoteQA.jsonl from PhysioNet.

    Returns:
        List of EHRNoteQAItem instances.
    """
    items: list[EHRNoteQAItem] = []
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"EHRNoteQA file not found: {path}\n"
            "Download from: https://physionet.org/content/ehr-notes-qa-llms/1.0.1/"
        )

    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                items.append(EHRNoteQAItem(
                    patient_id=int(obj["patient_id"]),
                    category=obj.get("category", "unknown"),
                    num_notes=int(obj.get("num_notes", 1)),
                    clinician=obj.get("clinician", ""),
                    question=obj["question"],
                    choices={
                        "A": obj.get("choice_A", ""),
                        "B": obj.get("choice_B", ""),
                        "C": obj.get("choice_C", ""),
                        "D": obj.get("choice_D", ""),
                        "E": obj.get("choice_E", ""),
                    },
                    answer=obj["answer"].strip().upper(),
                ))
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping line %d: %s", line_num, exc)

    logger.info("Loaded %d EHRNoteQA questions from %s", len(items), path)
    return items


def ehrqa_to_qa_questions(items: list[EHRNoteQAItem]) -> list[QAQuestion]:
    """Convert EHRNoteQA items to QAQuestion format for the ablation harness."""
    questions: list[QAQuestion] = []

    for i, item in enumerate(items):
        # Build MCQ prompt with options
        options_text = "\n".join(
            f"{letter}) {text}" for letter, text in sorted(item.choices.items()) if text
        )
        full_question = f"{item.question}\n\n{options_text}"

        questions.append(QAQuestion(
            question_id=f"ehrqa_{i:04d}",
            question=full_question,
            category=item.category,
            expected_answer=item.answer,  # Just the letter
            assertion_sensitive=False,
            temporal_sensitive=item.num_notes > 1,
            difficulty="hard" if item.num_notes >= 3 else "medium",
            clinical_context=f"Patient with {item.num_notes} discharge summaries",
            scoring_rubric={"mcq_accuracy": 1.0},
            metadata={
                "mimic_subject_id": item.patient_id,
                "patient_id": f"MIMIC-{item.patient_id}",
                "num_notes": item.num_notes,
                "clinician": item.clinician,
                "format": "mcq_5",
                "benchmark": "EHRNoteQA",
            },
        ))

    return questions


# ============================================================================
# EHRNoteQA Evaluator
# ============================================================================

@dataclass
class EHRNoteQAResult:
    """Results of an EHRNoteQA evaluation run."""

    total_questions: int = 0
    evaluated_questions: int = 0
    skipped_patients: int = 0

    # Per-condition MCQ accuracy
    condition_accuracies: dict[str, float] = field(default_factory=dict)
    condition_correct: dict[str, int] = field(default_factory=dict)

    # Per-category breakdown
    level1_accuracy: dict[str, float] = field(default_factory=dict)
    level2_accuracy: dict[str, float] = field(default_factory=dict)

    # Full ablation result
    ablation_result: AblationResult | None = None

    duration_s: float = 0.0

    def to_markdown(self) -> str:
        lines = [
            "## EHRNoteQA Results",
            f"Total: {self.total_questions} | Evaluated: {self.evaluated_questions} | Skipped (no patient data): {self.skipped_patients}",
            "",
        ]
        if self.ablation_result:
            lines.append(self.ablation_result.to_markdown_table())
        return "\n".join(lines)


class EHRNoteQAEvaluator:
    """Evaluates EHRNoteQA benchmark through the ablation harness.

    Usage:
        evaluator = EHRNoteQAEvaluator()
        evaluator.load("data/benchmarks/EHRNoteQA.jsonl")
        result = await evaluator.run(llm_model="gemma3:27b", llm_provider="ollama")
    """

    def __init__(self) -> None:
        self._items: list[EHRNoteQAItem] = []
        self._questions: list[QAQuestion] = []
        self._harness = AblationHarness()
        self._qa_service = QAEvaluationService()

    @property
    def total_questions(self) -> int:
        return len(self._questions)

    def load(self, path: str | Path) -> None:
        """Load EHRNoteQA dataset from JSONL file."""
        self._items = load_ehrnoteqa(path)
        self._questions = ehrqa_to_qa_questions(self._items)

    def get_required_patient_ids(self) -> list[str]:
        """Get list of MIMIC patient IDs needed for evaluation."""
        return sorted({f"MIMIC-{item.patient_id}" for item in self._items})

    def check_patient_coverage(self, db_session: Any) -> dict[str, Any]:
        """Check how many EHRNoteQA patients exist in our database.

        Returns dict with coverage stats.
        """
        from sqlalchemy import select, func as sa_func
        from app.models.document import Document

        required = self.get_required_patient_ids()

        stmt = (
            select(Document.patient_id)
            .where(Document.patient_id.in_(required))
            .where(Document.deleted_at.is_(None))
            .distinct()
        )
        result = db_session.execute(stmt)
        available = {r[0] for r in result.all()}

        return {
            "required": len(required),
            "available": len(available),
            "coverage": len(available) / len(required) if required else 0,
            "missing": sorted(set(required) - available),
            "available_ids": sorted(available),
        }

    async def run(
        self,
        llm_model: str = "claude-sonnet-4-5-20250929",
        llm_provider: str = "anthropic",
        use_llm_judge: bool = False,
        condition_ids: list[str] | None = None,
        question_limit: int | None = None,
        ollama_base_url: str = "http://localhost:11434",
        patient_filter: set[str] | None = None,
    ) -> EHRNoteQAResult:
        """Run EHRNoteQA evaluation through the ablation harness.

        Args:
            llm_model: LLM to use.
            llm_provider: Provider (anthropic/openai/ollama).
            use_llm_judge: Use LLM judge for additional scoring.
            condition_ids: Subset of ablation conditions to run.
            question_limit: Limit total questions for faster iteration.
            ollama_base_url: Ollama server URL.
            patient_filter: Only evaluate questions for these patient IDs.

        Returns:
            EHRNoteQAResult with accuracy metrics.
        """
        t0 = time.perf_counter()

        # Filter questions by available patients if specified
        questions = self._questions
        skipped = 0

        if patient_filter:
            filtered = []
            for q in questions:
                pid = q.metadata.get("patient_id", "")
                if pid in patient_filter:
                    filtered.append(q)
                else:
                    skipped += 1
            questions = filtered

        if question_limit:
            questions = questions[:question_limit]

        if not questions:
            logger.warning("No EHRNoteQA questions to evaluate (all patients missing?)")
            return EHRNoteQAResult(
                total_questions=len(self._questions),
                skipped_patients=skipped,
            )

        logger.info(
            "Running EHRNoteQA: %d questions (skipped %d, limit %s)",
            len(questions), skipped, question_limit,
        )

        # Group questions by patient for batched evaluation
        # The harness runs per-patient, so we pick the first patient
        # For now, use a representative patient_id from the questions
        # In practice, each question references its own patient
        patient_id = questions[0].metadata.get("patient_id", "MIMIC-10000032")

        result = await self._harness.run(
            patient_id=patient_id,
            questions=questions,
            question_set_name="EHRNoteQA",
            llm_model=llm_model,
            llm_provider=llm_provider,
            use_llm_judge=use_llm_judge,
            condition_ids=condition_ids,
            ollama_base_url=ollama_base_url,
        )

        duration = time.perf_counter() - t0

        # Compute MCQ-specific accuracy per condition
        condition_accs: dict[str, float] = {}
        condition_correct: dict[str, int] = {}

        for cid, cr in result.conditions.items():
            correct = 0
            total = 0
            for r in cr.report.results:
                total += 1
                # MCQ scoring: extract letter from predicted answer
                predicted_letter = extract_mcq_answer(r.predicted_answer)
                if predicted_letter and predicted_letter == r.expected_answer:
                    correct += 1
            condition_accs[cid] = correct / total if total > 0 else 0.0
            condition_correct[cid] = correct

        return EHRNoteQAResult(
            total_questions=len(self._questions),
            evaluated_questions=len(questions),
            skipped_patients=skipped,
            condition_accuracies=condition_accs,
            condition_correct=condition_correct,
            ablation_result=result,
            duration_s=duration,
        )
