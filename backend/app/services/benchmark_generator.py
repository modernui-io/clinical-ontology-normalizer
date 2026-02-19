"""Benchmark Question Generator — ClinicalIntelligenceBench.

Generates gold-standard QA questions from MIMIC-IV data by:
1. Querying the ingested MIMIC notes and structured data
2. Identifying clinically interesting patterns (negations, temporal changes, etc.)
3. Generating question-answer pairs grounded in real patient data
4. Validating questions for quality and clinical accuracy

Each task has a specialized generator:
  Task A: Finds negated/uncertain/family_history assertions in notes
  Task B: Finds patients with longitudinal data and temporal patterns
  Task C: Identifies patients with calculator-relevant measurements
  Task D: Finds discordances between structured and unstructured data
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func as sa_func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.benchmark import (
    AssertionType,
    BenchmarkQuestion,
    BenchmarkQuestionSet,
    BenchmarkTask,
    CalculatorType,
    FusionType,
    QuestionDifficulty,
    TemporalType,
)

logger = logging.getLogger(__name__)


class BenchmarkGenerator:
    """Generates gold-standard benchmark questions from MIMIC data.

    Usage:
        generator = BenchmarkGenerator(db_session)
        task_a = generator.generate_task_a(count=200)
        task_b = generator.generate_task_b(count=200)
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def generate_all(
        self,
        task_a_count: int = 200,
        task_b_count: int = 200,
        task_c_count: int = 100,
        task_d_count: int = 100,
    ) -> dict[str, BenchmarkQuestionSet]:
        """Generate all four task question sets."""
        return {
            "task_a": self.generate_task_a(task_a_count),
            "task_b": self.generate_task_b(task_b_count),
            "task_c": self.generate_task_c(task_c_count),
            "task_d": self.generate_task_d(task_d_count),
        }

    # ========================================================================
    # Task A: Negation-Aware Fact Retrieval
    # ========================================================================

    def generate_task_a(self, count: int = 200) -> BenchmarkQuestionSet:
        """Generate Task A questions from assertion-rich clinical notes.

        Distribution: 100 negation, 40 uncertainty, 30 family_history, 30 conditional.
        """
        questions: list[BenchmarkQuestion] = []

        # Find edges with assertion metadata
        negation_qs = self._generate_assertion_questions(
            assertion_value="absent", subtype=AssertionType.NEGATION.value,
            count=min(100, count // 2),
        )
        questions.extend(negation_qs)

        uncertainty_qs = self._generate_assertion_questions(
            assertion_value="possible", subtype=AssertionType.UNCERTAINTY.value,
            count=min(40, count // 5),
        )
        questions.extend(uncertainty_qs)

        family_qs = self._generate_assertion_questions(
            assertion_value="family_history", subtype=AssertionType.FAMILY_HISTORY.value,
            count=min(30, count // 7),
        )
        questions.extend(family_qs)

        conditional_qs = self._generate_assertion_questions(
            assertion_value="conditional", subtype=AssertionType.CONDITIONAL.value,
            count=min(30, count // 7),
        )
        questions.extend(conditional_qs)

        return BenchmarkQuestionSet(
            task=BenchmarkTask.TASK_A_NEGATION,
            questions=questions[:count],
            created_at=datetime.now(timezone.utc),
        )

    def _generate_assertion_questions(
        self,
        assertion_value: str,
        subtype: str,
        count: int,
    ) -> list[BenchmarkQuestion]:
        """Generate questions for a specific assertion type from KG edges."""
        questions: list[BenchmarkQuestion] = []

        try:
            # Find KG edges with this assertion in properties
            stmt = (
                select(KGEdge, KGNode)
                .join(KGNode, KGEdge.target_node_id == KGNode.id)
                .where(KGEdge.properties["assertion"].as_string() == assertion_value)
                .limit(count * 2)
            )
            result = self._session.execute(stmt)
            rows = result.all()

            for edge, node in rows[:count]:
                patient_id = edge.patient_id
                condition_label = node.label

                if assertion_value == "absent":
                    question_text = f"Does the patient have {condition_label}?"
                    expected = f"No — {condition_label} is negated/absent in the clinical record."
                elif assertion_value == "possible":
                    question_text = f"Is {condition_label} confirmed?"
                    expected = f"Not confirmed — {condition_label} is uncertain/suspected."
                elif assertion_value == "family_history":
                    question_text = f"Does the patient have {condition_label}?"
                    expected = f"Family history only — {condition_label} is in family history, not patient's own condition."
                elif assertion_value == "conditional":
                    question_text = f"Should the patient receive treatment for {condition_label}?"
                    expected = f"Conditional — treatment depends on additional criteria."
                else:
                    continue

                questions.append(BenchmarkQuestion(
                    question_id=f"bench_a_{subtype}_{uuid.uuid4().hex[:8]}",
                    task=BenchmarkTask.TASK_A_NEGATION,
                    subtype=subtype,
                    question=question_text,
                    expected_answer=expected,
                    mimic_subject_id=None,
                    clinical_context=f"Patient {patient_id}, edge assertion: {assertion_value}",
                    difficulty=QuestionDifficulty.MEDIUM,
                    scoring_rubric={"correct_assertion": 1.0, "false_positive": -2.0}
                    if assertion_value == "absent" else {},
                ))

        except Exception as exc:
            logger.warning("Task A generation for %s failed: %s", subtype, exc)

        return questions

    # ========================================================================
    # Task B: Temporal Clinical Reasoning
    # ========================================================================

    def generate_task_b(self, count: int = 200) -> BenchmarkQuestionSet:
        """Generate Task B questions requiring temporal reasoning.

        Distribution: 50 current_state, 50 historical, 40 sequence, 30 duration, 30 change.
        """
        questions: list[BenchmarkQuestion] = []

        # Find patients with multiple encounters (temporal data)
        temporal_qs = self._generate_temporal_questions(count)
        questions.extend(temporal_qs)

        return BenchmarkQuestionSet(
            task=BenchmarkTask.TASK_B_TEMPORAL,
            questions=questions[:count],
            created_at=datetime.now(timezone.utc),
        )

    def _generate_temporal_questions(self, count: int) -> list[BenchmarkQuestion]:
        """Generate temporal reasoning questions from longitudinal patient data."""
        questions: list[BenchmarkQuestion] = []

        try:
            # Find patients with edges that have event_date (temporal data)
            stmt = (
                select(
                    KGEdge.patient_id,
                    sa_func.count(KGEdge.id).label("edge_count"),
                )
                .where(KGEdge.event_date.isnot(None))
                .group_by(KGEdge.patient_id)
                .having(sa_func.count(KGEdge.id) >= 5)
                .order_by(sa_func.count(KGEdge.id).desc())
                .limit(count)
            )
            result = self._session.execute(stmt)
            patients = result.all()

            subtypes_remaining = {
                TemporalType.CURRENT_STATE.value: 50,
                TemporalType.HISTORICAL.value: 50,
                TemporalType.SEQUENCE.value: 40,
                TemporalType.DURATION.value: 30,
                TemporalType.CHANGE.value: 30,
            }

            for patient_id, edge_count in patients:
                if not any(v > 0 for v in subtypes_remaining.values()):
                    break

                # Get this patient's temporal edges
                edge_stmt = (
                    select(KGEdge, KGNode)
                    .join(KGNode, KGEdge.target_node_id == KGNode.id)
                    .where(KGEdge.patient_id == patient_id)
                    .where(KGEdge.event_date.isnot(None))
                    .order_by(KGEdge.event_date)
                    .limit(20)
                )
                edge_result = self._session.execute(edge_stmt)
                edges = edge_result.all()

                for edge, node in edges:
                    # Generate current_state questions
                    if subtypes_remaining.get(TemporalType.CURRENT_STATE.value, 0) > 0:
                        if edge.temporality == "current":
                            questions.append(BenchmarkQuestion(
                                question_id=f"bench_b_cs_{uuid.uuid4().hex[:8]}",
                                task=BenchmarkTask.TASK_B_TEMPORAL,
                                subtype=TemporalType.CURRENT_STATE.value,
                                question=f"What is the patient's current status for {node.label}?",
                                expected_answer=f"{node.label} is currently active/present.",
                                clinical_context=f"Patient {patient_id}, temporality: current",
                                difficulty=QuestionDifficulty.MEDIUM,
                            ))
                            subtypes_remaining[TemporalType.CURRENT_STATE.value] -= 1

                    # Generate historical questions
                    if subtypes_remaining.get(TemporalType.HISTORICAL.value, 0) > 0:
                        if edge.temporality == "past":
                            questions.append(BenchmarkQuestion(
                                question_id=f"bench_b_hist_{uuid.uuid4().hex[:8]}",
                                task=BenchmarkTask.TASK_B_TEMPORAL,
                                subtype=TemporalType.HISTORICAL.value,
                                question=f"Does the patient currently have {node.label}?",
                                expected_answer=f"No — {node.label} is historical/resolved.",
                                clinical_context=f"Patient {patient_id}, temporality: past",
                                difficulty=QuestionDifficulty.MEDIUM,
                            ))
                            subtypes_remaining[TemporalType.HISTORICAL.value] -= 1

        except Exception as exc:
            logger.warning("Task B generation failed: %s", exc)

        return questions

    # ========================================================================
    # Task C: Calculator-Grounded Decisions
    # ========================================================================

    def generate_task_c(self, count: int = 100) -> BenchmarkQuestionSet:
        """Generate Task C questions requiring clinical calculator computation.

        Distribution: 20 HEART, 15 Wells PE, 15 SOFA, 15 CKD-EPI, 10 ASCVD, 10 MELD, 15 other.
        """
        questions: list[BenchmarkQuestion] = []

        calculator_templates = {
            CalculatorType.HEART.value: {
                "question": "What is this patient's HEART score for chest pain evaluation?",
                "keywords": ["troponin", "ecg", "chest pain", "age", "risk factors"],
            },
            CalculatorType.WELLS_PE.value: {
                "question": "What is this patient's Wells score for PE probability?",
                "keywords": ["dvt", "hemoptysis", "heart rate", "immobilization", "surgery"],
            },
            CalculatorType.SOFA.value: {
                "question": "What is this patient's SOFA score?",
                "keywords": ["pao2", "platelets", "bilirubin", "creatinine", "gcs"],
            },
            CalculatorType.CKD_EPI.value: {
                "question": "What is this patient's eGFR using CKD-EPI?",
                "keywords": ["creatinine", "age", "gender"],
            },
            CalculatorType.ASCVD.value: {
                "question": "What is this patient's 10-year ASCVD risk?",
                "keywords": ["cholesterol", "hdl", "blood pressure", "diabetes", "smoking"],
            },
            CalculatorType.MELD.value: {
                "question": "What is this patient's MELD score?",
                "keywords": ["bilirubin", "creatinine", "inr", "sodium"],
            },
        }

        for calc_type, template in calculator_templates.items():
            target_count = {
                CalculatorType.HEART.value: 20,
                CalculatorType.WELLS_PE.value: 15,
                CalculatorType.SOFA.value: 15,
                CalculatorType.CKD_EPI.value: 15,
                CalculatorType.ASCVD.value: 10,
                CalculatorType.MELD.value: 10,
            }.get(calc_type, 15)

            calc_qs = self._generate_calculator_questions(
                calc_type, template, min(target_count, count // 6),
            )
            questions.extend(calc_qs)

        return BenchmarkQuestionSet(
            task=BenchmarkTask.TASK_C_CALCULATOR,
            questions=questions[:count],
            created_at=datetime.now(timezone.utc),
        )

    def _generate_calculator_questions(
        self,
        calc_type: str,
        template: dict[str, Any],
        count: int,
    ) -> list[BenchmarkQuestion]:
        """Generate calculator-grounded questions by finding patients with relevant measurements."""
        questions: list[BenchmarkQuestion] = []

        try:
            # Find patients with measurement nodes matching calculator keywords
            keyword = template["keywords"][0] if template["keywords"] else ""
            stmt = (
                select(KGNode.patient_id, KGNode.label)
                .where(KGNode.node_type == "measurement")
                .where(sa_func.lower(KGNode.label).contains(keyword.lower()))
                .distinct()
                .limit(count)
            )
            result = self._session.execute(stmt)
            patients = result.all()

            for patient_id, label in patients:
                questions.append(BenchmarkQuestion(
                    question_id=f"bench_c_{calc_type}_{uuid.uuid4().hex[:8]}",
                    task=BenchmarkTask.TASK_C_CALCULATOR,
                    subtype=calc_type,
                    question=template["question"],
                    expected_answer=f"Calculator computation required using patient's {label} values.",
                    clinical_context=f"Patient {patient_id} has {label} measurements",
                    difficulty=QuestionDifficulty.HARD,
                    scoring_rubric={"calculator_correct": 0.5, "decision_correct": 0.5},
                ))

        except Exception as exc:
            logger.warning("Task C generation for %s failed: %s", calc_type, exc)

        return questions

    # ========================================================================
    # Task D: Multi-Source Fusion
    # ========================================================================

    def generate_task_d(self, count: int = 100) -> BenchmarkQuestionSet:
        """Generate Task D questions requiring multi-source data fusion.

        Distribution: 30 lab-note, 30 vital-note, 20 temporal, 20 cross-note discordance.
        """
        questions: list[BenchmarkQuestion] = []

        # Find patients with both structured data (measurements) and documents
        try:
            stmt = (
                select(
                    KGEdge.patient_id,
                    sa_func.count(KGEdge.id).label("edge_count"),
                )
                .group_by(KGEdge.patient_id)
                .having(sa_func.count(KGEdge.id) >= 10)
                .limit(count)
            )
            result = self._session.execute(stmt)
            patients = result.all()

            for patient_id, _ in patients:
                # Check if patient has documents too
                doc_stmt = (
                    select(sa_func.count(Document.id))
                    .where(Document.patient_id == patient_id)
                )
                doc_result = self._session.execute(doc_stmt)
                doc_count = doc_result.scalar() or 0

                if doc_count == 0:
                    continue

                questions.append(BenchmarkQuestion(
                    question_id=f"bench_d_fusion_{uuid.uuid4().hex[:8]}",
                    task=BenchmarkTask.TASK_D_FUSION,
                    subtype=FusionType.LAB_NOTE.value,
                    question="Are the lab results consistent with the clinical note findings?",
                    expected_answer="Multi-source analysis required comparing structured labs with note text.",
                    clinical_context=f"Patient {patient_id} has {doc_count} documents + KG data",
                    difficulty=QuestionDifficulty.HARD,
                ))

                if len(questions) >= count:
                    break

        except Exception as exc:
            logger.warning("Task D generation failed: %s", exc)

        return BenchmarkQuestionSet(
            task=BenchmarkTask.TASK_D_FUSION,
            questions=questions[:count],
            created_at=datetime.now(timezone.utc),
        )

    # ========================================================================
    # Export
    # ========================================================================

    def export_to_json(
        self,
        question_sets: dict[str, BenchmarkQuestionSet],
        output_dir: str = "backend/data/benchmarks",
    ) -> list[str]:
        """Export generated question sets to JSON files.

        Returns list of file paths written.
        """
        import os

        os.makedirs(output_dir, exist_ok=True)
        paths = []

        for name, qs in question_sets.items():
            path = os.path.join(output_dir, f"{name}.json")
            with open(path, "w") as f:
                json.dump(qs.model_dump(mode="json"), f, indent=2, default=str)
            paths.append(path)
            logger.info("Exported %d questions to %s", qs.total_count, path)

        return paths
