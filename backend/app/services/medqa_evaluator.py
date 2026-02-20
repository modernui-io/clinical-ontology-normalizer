"""MedQA Evaluator — USMLE standard benchmark integration.

Integrates the MedQA-USMLE-4-options benchmark with our evaluation
framework. Unlike EHRNoteQA (patient-specific), MedQA tests general
medical knowledge — useful for measuring the LLM baseline and
ontology-augmentation benefit on established medical QA.

MedQA: 12,723 USMLE-style 4-option MCQ questions across Step 1 and
Step 2/3. Published baselines: GPT-4 ~86.7%, Med-PaLM 2 ~86.5%.

Dataset: https://huggingface.co/datasets/GBaker/MedQA-USMLE-4-options
Paper:   https://arxiv.org/abs/2009.13081

Integration flow:
  1. Load MedQA JSONL (from HuggingFace download or local file)
  2. Convert to QAQuestion format with 4-option MCQ in prompt
  3. Evaluate: LLM-alone vs LLM+ontology-context (optional)
  4. Score with MCQ accuracy (extract answer letter)
  5. Report per-step and overall metrics with published baselines

Does NOT require:
  - Patient data in our database
  - The full 5-condition ablation harness (no patient KG)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.ehrnoteqa_evaluator import extract_mcq_answer
from app.services.qa_evaluation import QAQuestion

logger = logging.getLogger(__name__)


# ============================================================================
# Published baselines for comparison
# ============================================================================

PUBLISHED_BASELINES: dict[str, float] = {
    "GPT-4 (2023)": 0.867,
    "Med-PaLM 2 (2023)": 0.865,
    "GPT-3.5-turbo": 0.607,
    "Claude-3 Opus": 0.780,
    "Gemma-2 27B": 0.700,
    "Llama-3 70B": 0.739,
}

MCQ_SYSTEM_PROMPT = """\
You are a medical expert answering USMLE-style multiple-choice questions.

Rules:
- Read all options carefully before answering.
- Use your medical knowledge to select the best answer.
- Start your response with the answer letter (A, B, C, or D).
- Then briefly explain your reasoning.

Format: Start with just the letter, e.g., "B. Because..."
"""


# ============================================================================
# MedQA data loading
# ============================================================================

@dataclass
class MedQAItem:
    """A single MedQA question."""

    question: str
    options: dict[str, str]  # {"A": "...", "B": "...", "C": "...", "D": "..."}
    answer: str  # Letter: "A", "B", "C", or "D"
    meta_info: str  # "step1" or "step2&3"


def load_medqa(path: str | Path) -> list[MedQAItem]:
    """Load MedQA JSONL file.

    Supports the HuggingFace GBaker/MedQA-USMLE-4-options format:
      {"question": "...", "options": {"A":"...","B":"...","C":"...","D":"..."},
       "answer_idx": "A", "answer": "...", "meta_info": "step1"}

    Also handles the original format with answer as text (maps back to letter).

    Args:
        path: Path to JSONL file (train.jsonl, dev.jsonl, or test.jsonl).

    Returns:
        List of MedQAItem instances.
    """
    items: list[MedQAItem] = []
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"MedQA file not found: {path}\n"
            "Download from: https://huggingface.co/datasets/GBaker/MedQA-USMLE-4-options"
        )

    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)

                question = obj["question"]
                options = obj.get("options", {})
                meta_info = obj.get("meta_info", "unknown")

                # Handle different answer formats
                answer_idx = obj.get("answer_idx")
                answer_text = obj.get("answer", "")

                if answer_idx and answer_idx in "ABCD":
                    # Direct letter format
                    answer = answer_idx
                elif answer_text and options:
                    # Text answer — reverse-map to letter
                    answer = _text_to_letter(answer_text, options)
                else:
                    logger.warning("Skipping line %d: no valid answer", line_num)
                    continue

                if not answer:
                    logger.warning("Skipping line %d: could not map answer", line_num)
                    continue

                items.append(MedQAItem(
                    question=question,
                    options=options,
                    answer=answer,
                    meta_info=meta_info,
                ))
            except (KeyError, ValueError, json.JSONDecodeError) as exc:
                logger.warning("Skipping line %d: %s", line_num, exc)

    logger.info("Loaded %d MedQA questions from %s", len(items), path)
    return items


def _text_to_letter(answer_text: str, options: dict[str, str]) -> str | None:
    """Map answer text back to its option letter."""
    answer_text = answer_text.strip()
    for letter, text in options.items():
        if text.strip() == answer_text:
            return letter
    # Fuzzy: check if answer text is contained in an option
    for letter, text in options.items():
        if answer_text.lower() in text.lower() or text.lower() in answer_text.lower():
            return letter
    return None


def medqa_to_qa_questions(
    items: list[MedQAItem],
    split: str = "test",
) -> list[QAQuestion]:
    """Convert MedQA items to QAQuestion format."""
    questions: list[QAQuestion] = []

    for i, item in enumerate(items):
        options_text = "\n".join(
            f"{letter}) {text}"
            for letter, text in sorted(item.options.items())
            if text
        )
        full_question = f"{item.question}\n\n{options_text}"

        questions.append(QAQuestion(
            question_id=f"medqa_{split}_{i:05d}",
            question=full_question,
            category=item.meta_info,
            expected_answer=item.answer,
            assertion_sensitive=False,
            temporal_sensitive=False,
            difficulty="hard",
            clinical_context="USMLE-style medical knowledge question",
            scoring_rubric={"mcq_accuracy": 1.0},
            metadata={
                "format": "mcq_4",
                "benchmark": "MedQA",
                "split": split,
                "exam_level": item.meta_info,
            },
        ))

    return questions


# ============================================================================
# LLM caller (lightweight, no patient context needed)
# ============================================================================

async def _call_llm(
    question: str,
    system_prompt: str,
    llm_model: str,
    llm_provider: str,
    ollama_base_url: str = "http://localhost:11434",
) -> str:
    """Call LLM with a question and return the response text."""
    if llm_provider == "ollama":
        import httpx

        url = f"{ollama_base_url}/api/chat"
        payload = {
            "model": llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            "stream": False,
            "options": {"temperature": 0},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "")

    elif llm_provider == "anthropic":
        import anthropic

        client = anthropic.AsyncAnthropic()
        resp = await client.messages.create(
            model=llm_model,
            max_tokens=512,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": question}],
        )
        return resp.content[0].text if resp.content else ""

    elif llm_provider == "openai":
        import openai

        client = openai.AsyncOpenAI()
        resp = await client.chat.completions.create(
            model=llm_model,
            temperature=0,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
        )
        return resp.choices[0].message.content or ""

    else:
        raise ValueError(f"Unknown LLM provider: {llm_provider}")


# ============================================================================
# MedQA Evaluator
# ============================================================================

@dataclass
class MedQAConditionResult:
    """Results for a single evaluation condition."""

    condition: str
    total: int = 0
    correct: int = 0
    accuracy: float = 0.0
    step1_correct: int = 0
    step1_total: int = 0
    step1_accuracy: float = 0.0
    step23_correct: int = 0
    step23_total: int = 0
    step23_accuracy: float = 0.0
    per_question: list[dict[str, Any]] = field(default_factory=list)
    latency_s: float = 0.0


@dataclass
class MedQAResult:
    """Results of a MedQA evaluation run."""

    total_questions: int = 0
    evaluated_questions: int = 0
    llm_model: str = ""

    # Per-condition results
    conditions: dict[str, MedQAConditionResult] = field(default_factory=dict)

    duration_s: float = 0.0

    def to_markdown(self) -> str:
        lines = [
            "## MedQA-USMLE Results",
            f"Model: {self.llm_model} | Evaluated: {self.evaluated_questions}/{self.total_questions}",
            "",
            "| Condition | Overall | Step 1 | Step 2&3 |",
            "|---|---|---|---|",
        ]

        for cid, cr in self.conditions.items():
            lines.append(
                f"| {cr.condition} | {cr.accuracy:.1%} ({cr.correct}/{cr.total}) "
                f"| {cr.step1_accuracy:.1%} ({cr.step1_correct}/{cr.step1_total}) "
                f"| {cr.step23_accuracy:.1%} ({cr.step23_correct}/{cr.step23_total}) |"
            )

        # Published baselines
        lines.extend(["", "### Published Baselines", "| Model | Accuracy |", "|---|---|"])
        for name, acc in PUBLISHED_BASELINES.items():
            lines.append(f"| {name} | {acc:.1%} |")

        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        conditions_json = {}
        for cid, cr in self.conditions.items():
            conditions_json[cid] = {
                "condition": cr.condition,
                "total": cr.total,
                "correct": cr.correct,
                "accuracy": cr.accuracy,
                "step1_accuracy": cr.step1_accuracy,
                "step1_correct": cr.step1_correct,
                "step1_total": cr.step1_total,
                "step23_accuracy": cr.step23_accuracy,
                "step23_correct": cr.step23_correct,
                "step23_total": cr.step23_total,
                "latency_s": cr.latency_s,
                "per_question": cr.per_question[:20],  # sample
            }

        return {
            "benchmark": "MedQA-USMLE-4-options",
            "total_questions": self.total_questions,
            "evaluated_questions": self.evaluated_questions,
            "llm_model": self.llm_model,
            "duration_s": self.duration_s,
            "conditions": conditions_json,
            "published_baselines": PUBLISHED_BASELINES,
        }


class MedQAEvaluator:
    """Evaluates MedQA-USMLE benchmark.

    Unlike EHRNoteQA, MedQA is NOT patient-specific — it tests general
    medical knowledge. We evaluate in two modes:
      1. LLM-alone: standard MCQ answering
      2. Ontology-augmented: extract medical concepts from question,
         look up OMOP relationships, provide as additional context

    Usage:
        evaluator = MedQAEvaluator()
        evaluator.load("data/benchmarks/medqa_test.jsonl")
        result = await evaluator.run(llm_model="gemma3:27b", llm_provider="ollama")
    """

    def __init__(self) -> None:
        self._items: list[MedQAItem] = []
        self._questions: list[QAQuestion] = []

    @property
    def total_questions(self) -> int:
        return len(self._questions)

    def load(self, path: str | Path, split: str = "test") -> None:
        """Load MedQA dataset from JSONL file."""
        self._items = load_medqa(path)
        self._questions = medqa_to_qa_questions(self._items, split=split)

    def load_multiple(self, paths: list[str | Path]) -> None:
        """Load multiple JSONL files (e.g., train + dev + test)."""
        for path in paths:
            split = Path(path).stem  # e.g., "test", "train", "dev"
            items = load_medqa(path)
            self._items.extend(items)
            self._questions.extend(medqa_to_qa_questions(items, split=split))

    def get_subset(
        self,
        exam_level: str | None = None,
        limit: int | None = None,
    ) -> list[QAQuestion]:
        """Get a filtered subset of questions."""
        questions = self._questions

        if exam_level:
            questions = [
                q for q in questions
                if q.metadata.get("exam_level") == exam_level
            ]

        if limit:
            questions = questions[:limit]

        return questions

    def _load_checkpoint(self, checkpoint_path: str, condition: str) -> dict[str, dict]:
        """Load checkpoint file and return dict of question_id -> result for a condition."""
        completed: dict[str, dict] = {}
        try:
            with open(checkpoint_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    if entry.get("condition") == condition:
                        completed[entry["question_id"]] = entry
        except FileNotFoundError:
            pass
        return completed

    def _append_checkpoint(self, checkpoint_path: str, entry: dict) -> None:
        """Append a single result entry to the checkpoint JSONL file."""
        with open(checkpoint_path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    async def run(
        self,
        llm_model: str = "claude-sonnet-4-5-20250929",
        llm_provider: str = "anthropic",
        question_limit: int | None = None,
        ollama_base_url: str = "http://localhost:11434",
        include_ontology_condition: bool = False,
        batch_size: int = 10,
        checkpoint_path: str | None = None,
    ) -> MedQAResult:
        """Run MedQA evaluation with optional checkpoint/resume support.

        Args:
            llm_model: LLM to use.
            llm_provider: Provider (anthropic/openai/ollama).
            question_limit: Limit total questions for faster iteration.
            ollama_base_url: Ollama server URL.
            include_ontology_condition: Also run with OMOP ontology context.
            batch_size: Log progress every N questions.
            checkpoint_path: Path to JSONL checkpoint file for resume support.
                If set, each question result is saved incrementally and
                already-completed questions are skipped on resume.

        Returns:
            MedQAResult with accuracy metrics and baseline comparisons.
        """
        t0 = time.perf_counter()

        questions = self._questions
        if question_limit:
            questions = questions[:question_limit]

        if not questions:
            logger.warning("No MedQA questions to evaluate")
            return MedQAResult(total_questions=len(self._questions))

        logger.info(
            "Running MedQA: %d questions (model=%s, provider=%s)",
            len(questions), llm_model, llm_provider,
        )

        conditions_to_run = ["llm_alone"]
        if include_ontology_condition:
            conditions_to_run.append("ontology_augmented")

        all_results: dict[str, MedQAConditionResult] = {}

        for condition in conditions_to_run:
            logger.info("--- MedQA Condition: %s ---", condition)
            cond_t0 = time.perf_counter()

            # Load checkpoint for resume
            checkpoint: dict[str, dict] = {}
            if checkpoint_path:
                checkpoint = self._load_checkpoint(checkpoint_path, condition)
                if checkpoint:
                    logger.info("  Resuming: %d questions already completed", len(checkpoint))

            system_prompt = MCQ_SYSTEM_PROMPT
            correct = 0
            total = 0
            step1_correct = 0
            step1_total = 0
            step23_correct = 0
            step23_total = 0
            per_question: list[dict[str, Any]] = []
            skipped = 0

            for i, q in enumerate(questions):
                total += 1
                exam_level = q.metadata.get("exam_level", "unknown")

                # Check checkpoint — skip if already completed successfully
                cached = checkpoint.get(q.question_id)
                if cached and not cached.get("error"):
                    predicted = cached.get("predicted")
                    is_correct = cached.get("correct", False)
                    skipped += 1
                else:
                    cached = None  # Force re-evaluation on error entries

                if cached is None:
                    try:
                        prompt = q.question
                        if condition == "ontology_augmented":
                            ontology_ctx = await self._get_ontology_context(q.question)
                            if ontology_ctx:
                                prompt = (
                                    f"Relevant medical ontology context:\n{ontology_ctx}\n\n"
                                    f"Question:\n{q.question}"
                                )

                        response = await _call_llm(
                            question=prompt,
                            system_prompt=system_prompt,
                            llm_model=llm_model,
                            llm_provider=llm_provider,
                            ollama_base_url=ollama_base_url,
                        )

                        predicted = extract_mcq_answer(response)
                        is_correct = predicted is not None and predicted == q.expected_answer

                        entry = {
                            "condition": condition,
                            "question_id": q.question_id,
                            "predicted": predicted,
                            "expected": q.expected_answer,
                            "correct": is_correct,
                            "exam_level": exam_level,
                            "response_preview": response[:100] if response else "",
                        }

                        if checkpoint_path:
                            self._append_checkpoint(checkpoint_path, entry)

                    except Exception as exc:
                        logger.warning("Error on %s: %s", q.question_id, exc)
                        predicted = None
                        is_correct = False

                        entry = {
                            "condition": condition,
                            "question_id": q.question_id,
                            "predicted": None,
                            "expected": q.expected_answer,
                            "correct": False,
                            "error": str(exc),
                        }
                        if checkpoint_path:
                            self._append_checkpoint(checkpoint_path, entry)

                if is_correct:
                    correct += 1
                if exam_level == "step1":
                    step1_total += 1
                    if is_correct:
                        step1_correct += 1
                elif exam_level in ("step2&3", "step2_3"):
                    step23_total += 1
                    if is_correct:
                        step23_correct += 1

                per_question.append({
                    "question_id": q.question_id,
                    "predicted": predicted,
                    "expected": q.expected_answer,
                    "correct": is_correct,
                    "exam_level": exam_level,
                })

                if (i + 1) % batch_size == 0:
                    logger.info(
                        "  Progress: %d/%d (%.1f%% correct so far, %d resumed)",
                        i + 1, len(questions), correct / total * 100 if total else 0, skipped,
                    )

            cond_latency = time.perf_counter() - cond_t0

            all_results[condition] = MedQAConditionResult(
                condition=condition,
                total=total,
                correct=correct,
                accuracy=correct / total if total > 0 else 0.0,
                step1_correct=step1_correct,
                step1_total=step1_total,
                step1_accuracy=step1_correct / step1_total if step1_total > 0 else 0.0,
                step23_correct=step23_correct,
                step23_total=step23_total,
                step23_accuracy=step23_correct / step23_total if step23_total > 0 else 0.0,
                per_question=per_question,
                latency_s=cond_latency,
            )

            logger.info(
                "  %s: accuracy=%.1f%% (%d/%d), step1=%.1f%%, step2&3=%.1f%%, time=%.1fs (resumed %d)",
                condition,
                all_results[condition].accuracy * 100,
                correct, total,
                all_results[condition].step1_accuracy * 100,
                all_results[condition].step23_accuracy * 100,
                cond_latency,
                skipped,
            )

        duration = time.perf_counter() - t0

        return MedQAResult(
            total_questions=len(self._questions),
            evaluated_questions=len(questions),
            llm_model=llm_model,
            conditions=all_results,
            duration_s=duration,
        )

    async def _get_ontology_context(self, question_text: str) -> str | None:
        """Extract medical concepts from the question and look up OMOP relationships.

        This provides ontology-grounded context to the LLM — demonstrating
        whether structured medical knowledge improves general QA performance.
        """
        try:
            from app.services.graph_augmented_rag import GraphAugmentedRAGService

            rag = GraphAugmentedRAGService()
            # Extract concepts from the question text
            concepts = await rag.extract_concepts(question_text)

            if not concepts:
                return None

            # Build ontology context string from extracted concepts
            lines = []
            for concept in concepts[:5]:  # Limit to top 5 concepts
                name = concept.get("concept_name", concept.get("name", ""))
                domain = concept.get("domain", "")
                concept_id = concept.get("concept_id", "")
                if name:
                    line = f"- {name}"
                    if domain:
                        line += f" (domain: {domain})"
                    if concept_id:
                        line += f" [OMOP:{concept_id}]"
                    lines.append(line)

            return "\n".join(lines) if lines else None

        except Exception as exc:
            logger.debug("Ontology context extraction failed: %s", exc)
            return None
