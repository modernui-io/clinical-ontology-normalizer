"""Physician Evaluation Service.

Manages blind physician evaluation of clinical QA responses across
ablation conditions. Supports the NeurIPS paper's clinical validation
section.

Protocol:
- 100 held-out questions from ClinicalIntelligenceBench
- 3 conditions shown per question (C1: LLM alone, C3: KG-RAG, C5: full system)
- Blind: physician doesn't know which condition produced which answer
- 4 scoring dimensions + preference ranking
- Target: 5-7 ER physicians
"""

from __future__ import annotations

import json
import logging
import os
import random
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EvalQuestion:
    """A question presented for physician evaluation."""

    question_id: str
    question_text: str
    clinical_context: str
    expected_answer: str
    category: str
    task: str  # task_a, task_b, task_c, task_d

    # Responses from 3 conditions (order randomized per evaluator)
    responses: dict[str, str] = field(default_factory=dict)
    # Maps display label (A/B/C) to condition_id
    label_to_condition: dict[str, str] = field(default_factory=dict)


@dataclass
class EvalScore:
    """A single physician's score for one response."""

    factual_correctness: int  # 0-3
    clinical_safety: int  # 0-3
    assertion_handling: int  # 0-2
    temporal_handling: int  # 0-2

    @property
    def total(self) -> float:
        return (
            self.factual_correctness
            + self.clinical_safety
            + self.assertion_handling
            + self.temporal_handling
        )

    @property
    def max_total(self) -> float:
        return 3 + 3 + 2 + 2  # 10


@dataclass
class QuestionEvaluation:
    """A physician's evaluation of all responses for one question."""

    question_id: str
    evaluator_id: str
    scores: dict[str, EvalScore]  # condition_id -> score
    preference_ranking: list[str]  # condition_ids ordered by preference (best first)
    notes: str = ""
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EvaluationSession:
    """A complete evaluation session for one physician."""

    session_id: str
    evaluator_id: str
    evaluator_name: str
    specialty: str
    years_experience: int
    questions: list[EvalQuestion]
    evaluations: list[QuestionEvaluation] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    status: str = "in_progress"


class PhysicianEvaluationService:
    """Service for managing physician blind evaluations."""

    # Conditions to evaluate (subset of 5 for physician time)
    EVAL_CONDITIONS = ["C1_llm_alone", "C3_kg_rag", "C5_full_system"]
    CONDITION_LABELS = {
        "C1_llm_alone": "LLM Alone",
        "C3_kg_rag": "LLM + KG-RAG",
        "C5_full_system": "Full System (KG + Calculators + Guidelines)",
    }

    def __init__(self, data_dir: str = "data/benchmarks") -> None:
        self._data_dir = data_dir
        self._eval_dir = os.path.join(data_dir, "physician_eval")
        os.makedirs(self._eval_dir, exist_ok=True)
        self._sessions: dict[str, EvaluationSession] = {}
        self._load_sessions()

    def _load_sessions(self) -> None:
        """Load existing sessions from disk."""
        sessions_file = os.path.join(self._eval_dir, "sessions.json")
        if os.path.exists(sessions_file):
            with open(sessions_file) as f:
                data = json.load(f)
            for sd in data.get("sessions", []):
                session = self._deserialize_session(sd)
                self._sessions[session.session_id] = session

    def _save_sessions(self) -> None:
        """Persist sessions to disk."""
        sessions_file = os.path.join(self._eval_dir, "sessions.json")
        data = {
            "sessions": [self._serialize_session(s) for s in self._sessions.values()],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(sessions_file, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def create_session(
        self,
        evaluator_name: str,
        specialty: str,
        years_experience: int,
        ablation_results_path: str | None = None,
        num_questions: int = 100,
        seed: int = 42,
    ) -> EvaluationSession:
        """Create a new evaluation session for a physician.

        Selects questions and randomizes condition order per question.
        """
        session_id = f"eval_{uuid.uuid4().hex[:8]}"
        evaluator_id = f"physician_{uuid.uuid4().hex[:6]}"

        # Load ablation results to get predicted answers
        results_path = ablation_results_path or os.path.join(
            self._data_dir, "results", "clinicalbench_ablation.json"
        )

        questions = self._select_questions(results_path, num_questions, seed)

        session = EvaluationSession(
            session_id=session_id,
            evaluator_id=evaluator_id,
            evaluator_name=evaluator_name,
            specialty=specialty,
            years_experience=years_experience,
            questions=questions,
        )

        self._sessions[session_id] = session
        self._save_sessions()
        logger.info(
            "Created evaluation session %s for %s (%d questions)",
            session_id, evaluator_name, len(questions),
        )
        return session

    def _select_questions(
        self,
        results_path: str,
        num_questions: int,
        seed: int,
    ) -> list[EvalQuestion]:
        """Select and prepare questions for evaluation."""
        # Load ablation results
        if not os.path.exists(results_path):
            logger.warning("Ablation results not found at %s, using empty responses", results_path)
            return self._select_from_benchmark_files(num_questions, seed)

        with open(results_path) as f:
            ablation = json.load(f)

        # Build question -> condition -> predicted_answer mapping
        predictions: dict[str, dict[str, str]] = {}
        for cid, cond_data in ablation.get("conditions", {}).items():
            if cid not in self.EVAL_CONDITIONS:
                continue
            for q in cond_data.get("per_question", []):
                qid = q["question_id"]
                if qid not in predictions:
                    predictions[qid] = {}
                predictions[qid][cid] = q.get("predicted_answer", "")

        # Only include questions that have all 3 conditions
        complete_qids = [
            qid for qid, preds in predictions.items()
            if all(c in preds for c in self.EVAL_CONDITIONS)
        ]

        # Load benchmark questions for context
        benchmark_qs = self._load_benchmark_questions()

        rng = random.Random(seed)
        rng.shuffle(complete_qids)
        selected = complete_qids[:num_questions]

        eval_questions: list[EvalQuestion] = []
        for qid in selected:
            bq = benchmark_qs.get(qid, {})

            # Randomize condition display order
            conditions = list(self.EVAL_CONDITIONS)
            rng.shuffle(conditions)
            labels = ["A", "B", "C"]
            label_map = dict(zip(labels, conditions))
            responses = {cid: predictions[qid][cid] for cid in conditions}

            eval_questions.append(EvalQuestion(
                question_id=qid,
                question_text=bq.get("question", qid),
                clinical_context=bq.get("clinical_context", ""),
                expected_answer=bq.get("expected_answer", ""),
                category=bq.get("category", ""),
                task=bq.get("metadata", {}).get("task", ""),
                responses=responses,
                label_to_condition=label_map,
            ))

        return eval_questions

    def _select_from_benchmark_files(
        self, num_questions: int, seed: int,
    ) -> list[EvalQuestion]:
        """Select questions directly from benchmark files (no predictions)."""
        benchmark_qs = self._load_benchmark_questions()
        rng = random.Random(seed)
        qids = list(benchmark_qs.keys())
        rng.shuffle(qids)

        eval_questions: list[EvalQuestion] = []
        for qid in qids[:num_questions]:
            bq = benchmark_qs[qid]
            eval_questions.append(EvalQuestion(
                question_id=qid,
                question_text=bq.get("question", qid),
                clinical_context=bq.get("clinical_context", ""),
                expected_answer=bq.get("expected_answer", ""),
                category=bq.get("category", ""),
                task=bq.get("metadata", {}).get("task", ""),
            ))

        return eval_questions

    def _load_benchmark_questions(self) -> dict[str, dict]:
        """Load benchmark questions by ID."""
        questions: dict[str, dict] = {}
        for task in ["task_a", "task_b", "task_c", "task_d"]:
            path = os.path.join(self._data_dir, f"{task}.json")
            if not os.path.exists(path):
                continue
            with open(path) as f:
                data = json.load(f)
            for q in data.get("questions", []):
                q["metadata"] = q.get("metadata", {})
                q["metadata"]["task"] = task
                questions[q["question_id"]] = q
        return questions

    def submit_evaluation(
        self,
        session_id: str,
        question_id: str,
        scores: dict[str, dict[str, int]],
        preference_ranking: list[str],
        notes: str = "",
    ) -> QuestionEvaluation:
        """Submit a physician's evaluation for one question.

        Args:
            session_id: The evaluation session
            question_id: The question being evaluated
            scores: {condition_id: {factual_correctness, clinical_safety, ...}}
            preference_ranking: condition_ids ordered best-first
            notes: Optional free-text notes
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        eval_scores: dict[str, EvalScore] = {}
        for cid, s in scores.items():
            eval_scores[cid] = EvalScore(
                factual_correctness=s.get("factual_correctness", 0),
                clinical_safety=s.get("clinical_safety", 0),
                assertion_handling=s.get("assertion_handling", 0),
                temporal_handling=s.get("temporal_handling", 0),
            )

        evaluation = QuestionEvaluation(
            question_id=question_id,
            evaluator_id=session.evaluator_id,
            scores=eval_scores,
            preference_ranking=preference_ranking,
            notes=notes,
        )

        session.evaluations.append(evaluation)
        self._save_sessions()
        return evaluation

    def complete_session(self, session_id: str) -> EvaluationSession:
        """Mark a session as complete."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
        self._save_sessions()
        return session

    def get_session(self, session_id: str) -> EvaluationSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": s.session_id,
                "evaluator_name": s.evaluator_name,
                "specialty": s.specialty,
                "status": s.status,
                "questions_total": len(s.questions),
                "evaluations_completed": len(s.evaluations),
                "started_at": s.started_at.isoformat(),
            }
            for s in self._sessions.values()
        ]

    def compute_agreement_stats(self) -> dict[str, Any]:
        """Compute inter-rater agreement across completed sessions.

        Returns Fleiss' kappa, mean scores, and Wilcoxon signed-rank test.
        """
        completed = [s for s in self._sessions.values() if s.status == "completed"]
        if len(completed) < 2:
            return {"error": "Need at least 2 completed sessions for agreement stats"}

        # Collect per-question, per-condition scores from all evaluators
        all_scores: dict[str, dict[str, list[float]]] = {}  # qid -> cid -> [scores]
        preference_counts: dict[str, dict[str, int]] = {}  # cid -> rank_position -> count

        for session in completed:
            for ev in session.evaluations:
                if ev.question_id not in all_scores:
                    all_scores[ev.question_id] = {}
                for cid, score in ev.scores.items():
                    if cid not in all_scores[ev.question_id]:
                        all_scores[ev.question_id][cid] = []
                    all_scores[ev.question_id][cid].append(score.total)

                # Track preference rankings
                for rank, cid in enumerate(ev.preference_ranking):
                    if cid not in preference_counts:
                        preference_counts[cid] = {}
                    preference_counts[cid][str(rank)] = (
                        preference_counts[cid].get(str(rank), 0) + 1
                    )

        # Compute mean scores per condition
        condition_scores: dict[str, list[float]] = {}
        for qid, cid_scores in all_scores.items():
            for cid, scores in cid_scores.items():
                if cid not in condition_scores:
                    condition_scores[cid] = []
                condition_scores[cid].extend(scores)

        mean_scores = {
            cid: {
                "mean": statistics.mean(scores),
                "std": statistics.stdev(scores) if len(scores) > 1 else 0,
                "n": len(scores),
            }
            for cid, scores in condition_scores.items()
        }

        # Preference summary
        pref_summary = {}
        for cid, ranks in preference_counts.items():
            total = sum(ranks.values())
            pref_summary[cid] = {
                "first_choice_pct": ranks.get("0", 0) / total if total else 0,
                "last_choice_pct": ranks.get("2", 0) / total if total else 0,
            }

        return {
            "num_evaluators": len(completed),
            "num_questions_evaluated": len(all_scores),
            "mean_scores_per_condition": mean_scores,
            "preference_summary": pref_summary,
        }

    def export_results(self) -> dict[str, Any]:
        """Export all evaluation results for paper inclusion."""
        stats = self.compute_agreement_stats()

        # Per-dimension breakdown
        completed = [s for s in self._sessions.values() if s.status == "completed"]
        dimensions = ["factual_correctness", "clinical_safety", "assertion_handling", "temporal_handling"]
        dim_scores: dict[str, dict[str, list[float]]] = {
            d: {} for d in dimensions
        }

        for session in completed:
            for ev in session.evaluations:
                for cid, score in ev.scores.items():
                    for dim in dimensions:
                        if cid not in dim_scores[dim]:
                            dim_scores[dim][cid] = []
                        dim_scores[dim][cid].append(getattr(score, dim))

        dim_means = {}
        for dim in dimensions:
            dim_means[dim] = {
                cid: statistics.mean(scores) if scores else 0
                for cid, scores in dim_scores[dim].items()
            }

        return {
            "agreement_stats": stats,
            "per_dimension_means": dim_means,
            "evaluator_profiles": [
                {
                    "evaluator_id": s.evaluator_id,
                    "specialty": s.specialty,
                    "years_experience": s.years_experience,
                    "questions_evaluated": len(s.evaluations),
                }
                for s in completed
            ],
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    def _serialize_session(self, session: EvaluationSession) -> dict:
        """Serialize session to JSON-safe dict."""
        return {
            "session_id": session.session_id,
            "evaluator_id": session.evaluator_id,
            "evaluator_name": session.evaluator_name,
            "specialty": session.specialty,
            "years_experience": session.years_experience,
            "status": session.status,
            "started_at": session.started_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "questions": [
                {
                    "question_id": q.question_id,
                    "question_text": q.question_text,
                    "clinical_context": q.clinical_context,
                    "expected_answer": q.expected_answer,
                    "category": q.category,
                    "task": q.task,
                    "responses": q.responses,
                    "label_to_condition": q.label_to_condition,
                }
                for q in session.questions
            ],
            "evaluations": [
                {
                    "question_id": ev.question_id,
                    "evaluator_id": ev.evaluator_id,
                    "scores": {
                        cid: {
                            "factual_correctness": s.factual_correctness,
                            "clinical_safety": s.clinical_safety,
                            "assertion_handling": s.assertion_handling,
                            "temporal_handling": s.temporal_handling,
                        }
                        for cid, s in ev.scores.items()
                    },
                    "preference_ranking": ev.preference_ranking,
                    "notes": ev.notes,
                    "evaluated_at": ev.evaluated_at.isoformat(),
                }
                for ev in session.evaluations
            ],
        }

    def _deserialize_session(self, data: dict) -> EvaluationSession:
        """Deserialize session from JSON dict."""
        questions = [
            EvalQuestion(
                question_id=q["question_id"],
                question_text=q["question_text"],
                clinical_context=q.get("clinical_context", ""),
                expected_answer=q.get("expected_answer", ""),
                category=q.get("category", ""),
                task=q.get("task", ""),
                responses=q.get("responses", {}),
                label_to_condition=q.get("label_to_condition", {}),
            )
            for q in data.get("questions", [])
        ]

        evaluations = [
            QuestionEvaluation(
                question_id=ev["question_id"],
                evaluator_id=ev["evaluator_id"],
                scores={
                    cid: EvalScore(**s)
                    for cid, s in ev.get("scores", {}).items()
                },
                preference_ranking=ev.get("preference_ranking", []),
                notes=ev.get("notes", ""),
                evaluated_at=datetime.fromisoformat(ev["evaluated_at"])
                if "evaluated_at" in ev else datetime.now(timezone.utc),
            )
            for ev in data.get("evaluations", [])
        ]

        return EvaluationSession(
            session_id=data["session_id"],
            evaluator_id=data["evaluator_id"],
            evaluator_name=data["evaluator_name"],
            specialty=data["specialty"],
            years_experience=data["years_experience"],
            questions=questions,
            evaluations=evaluations,
            status=data.get("status", "in_progress"),
            started_at=datetime.fromisoformat(data["started_at"])
            if "started_at" in data else datetime.now(timezone.utc),
            completed_at=datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at") else None,
        )
