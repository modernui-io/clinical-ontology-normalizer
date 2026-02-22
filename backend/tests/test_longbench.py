"""Tests for the Longitudinal Clinical Benchmark (LongBench) harness.

Tests cover:
- Schema construction and scoring
- Cohort serialization round-trip
- Condition config completeness
- Analyzer aggregation logic
"""

from __future__ import annotations

import json

import pytest

from app.services.longbench_schemas import (
    ConditionID,
    ConditionTierScore,
    CriterionResult,
    CriterionType,
    CriterionWeight,
    LongBenchCohort,
    LongBenchCriterion,
    LongBenchQuestion,
    LongBenchReport,
    LongBenchResult,
    LongitudinalTier,
    PatientCohortEntry,
    QuestionDomain,
)
from app.services.longbench_cohort import (
    TIER_BOUNDS,
    cohort_from_json,
    cohort_to_json,
)
from app.services.longbench_runner import (
    CONDITION_CONFIGS,
    LongBenchAnalyzer,
)


# ============================================================================
# Schema tests
# ============================================================================


class TestLongBenchSchemas:
    """Test data structure construction and scoring."""

    def test_criterion_numeric_weight(self):
        c1 = LongBenchCriterion(
            criterion_id="c1", text="t", criterion_type=CriterionType.EXPERIENCER,
            weight=CriterionWeight.CRITICAL,
        )
        c2 = LongBenchCriterion(
            criterion_id="c2", text="t", criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        )
        c3 = LongBenchCriterion(
            criterion_id="c3", text="t", criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.NICE,
        )
        assert c1.numeric_weight == 2.0
        assert c2.numeric_weight == 1.0
        assert c3.numeric_weight == 0.5

    def test_question_max_score(self):
        criteria = [
            LongBenchCriterion(
                criterion_id="c1", text="t",
                criterion_type=CriterionType.EXPERIENCER,
                weight=CriterionWeight.CRITICAL,
            ),
            LongBenchCriterion(
                criterion_id="c2", text="t",
                criterion_type=CriterionType.ASSERTION,
                weight=CriterionWeight.IMPORTANT,
            ),
        ]
        q = LongBenchQuestion(
            question_id="q1", patient_id="P001",
            question_text="Does the patient have X?",
            domain=QuestionDomain.PROBLEM_LIST,
            tier=LongitudinalTier.B,
            criteria=criteria,
        )
        assert q.max_score == 3.0  # 2.0 + 1.0

    def test_result_compute_scores_all_satisfied(self):
        criteria = [
            LongBenchCriterion(
                criterion_id="c1", text="t",
                criterion_type=CriterionType.EXPERIENCER,
                weight=CriterionWeight.CRITICAL,
            ),
            LongBenchCriterion(
                criterion_id="c2", text="t",
                criterion_type=CriterionType.ASSERTION,
                weight=CriterionWeight.IMPORTANT,
            ),
        ]
        result = LongBenchResult(
            question_id="q1", patient_id="P001",
            condition=ConditionID.B3, tier=LongitudinalTier.B,
            domain=QuestionDomain.PROBLEM_LIST,
            predicted_answer="answer",
            criterion_results=[
                CriterionResult(criterion_id="c1", satisfied=True),
                CriterionResult(criterion_id="c2", satisfied=True),
            ],
        )
        result.compute_scores(criteria)
        assert result.raw_score == 3.0
        assert result.max_score == 3.0
        assert result.normalized_score == 1.0

    def test_result_compute_scores_partial(self):
        criteria = [
            LongBenchCriterion(
                criterion_id="c1", text="t",
                criterion_type=CriterionType.EXPERIENCER,
                weight=CriterionWeight.CRITICAL,
            ),
            LongBenchCriterion(
                criterion_id="c2", text="t",
                criterion_type=CriterionType.ASSERTION,
                weight=CriterionWeight.IMPORTANT,
            ),
        ]
        result = LongBenchResult(
            question_id="q1", patient_id="P001",
            condition=ConditionID.B2, tier=LongitudinalTier.A,
            domain=QuestionDomain.FAMILY_HISTORY,
            predicted_answer="answer",
            criterion_results=[
                CriterionResult(criterion_id="c1", satisfied=True),
                CriterionResult(criterion_id="c2", satisfied=False),
            ],
        )
        result.compute_scores(criteria)
        assert result.raw_score == 2.0   # Only critical satisfied
        assert result.max_score == 3.0
        assert abs(result.normalized_score - 2 / 3) < 0.01

    def test_result_compute_scores_empty(self):
        result = LongBenchResult(
            question_id="q1", patient_id="P001",
            condition=ConditionID.B0, tier=LongitudinalTier.C,
            domain=QuestionDomain.RISK_ASSESSMENT,
            predicted_answer="",
        )
        result.compute_scores([])
        assert result.normalized_score == 0.0


# ============================================================================
# Cohort serialization tests
# ============================================================================


class TestCohortSerialization:
    """Test JSON round-trip for cohort data."""

    def _make_cohort(self) -> LongBenchCohort:
        patients = [
            PatientCohortEntry(
                patient_id="P001", tier=LongitudinalTier.A,
                encounter_count=2, total_note_length=5000,
                has_family_history=True,
            ),
            PatientCohortEntry(
                patient_id="P002", tier=LongitudinalTier.C,
                encounter_count=20, total_note_length=50000,
            ),
        ]
        criteria = [
            LongBenchCriterion(
                criterion_id="q1_c0", text="Correctly identifies family history",
                criterion_type=CriterionType.EXPERIENCER,
                weight=CriterionWeight.CRITICAL,
                evidence_source="Discharge summary #1",
            ),
            LongBenchCriterion(
                criterion_id="q1_c1", text="Does not attribute to patient",
                criterion_type=CriterionType.ASSERTION,
                weight=CriterionWeight.IMPORTANT,
            ),
        ]
        questions = [
            LongBenchQuestion(
                question_id="q1", patient_id="P001",
                question_text="What family history is documented?",
                domain=QuestionDomain.FAMILY_HISTORY,
                tier=LongitudinalTier.A,
                criteria=criteria,
                encounter_count=2,
                generated_by="template",
            ),
        ]
        return LongBenchCohort(
            cohort_id="test_cohort",
            patients=patients,
            questions=questions,
            version="1.0.0",
            metadata={"test": True},
        )

    def test_round_trip(self):
        original = self._make_cohort()
        data = cohort_to_json(original)
        restored = cohort_from_json(data)

        assert restored.cohort_id == original.cohort_id
        assert len(restored.patients) == 2
        assert len(restored.questions) == 1
        assert restored.patients[0].patient_id == "P001"
        assert restored.patients[0].tier == LongitudinalTier.A
        assert restored.patients[1].encounter_count == 20
        assert restored.questions[0].criteria[0].criterion_type == CriterionType.EXPERIENCER
        assert restored.questions[0].criteria[0].weight == CriterionWeight.CRITICAL

    def test_json_serializable(self):
        cohort = self._make_cohort()
        data = cohort_to_json(cohort)
        # Should be JSON-serializable
        json_str = json.dumps(data)
        assert len(json_str) > 0
        # Should round-trip through JSON
        parsed = json.loads(json_str)
        assert parsed["cohort_id"] == "test_cohort"

    def test_tier_summary(self):
        cohort = self._make_cohort()
        summary = cohort.tier_summary
        assert summary["A"]["patients"] == 1
        assert summary["A"]["questions"] == 1
        assert summary["C"]["patients"] == 1
        assert summary["C"]["questions"] == 0  # No tier C questions


# ============================================================================
# Condition config tests
# ============================================================================


class TestConditionConfigs:
    """Verify all conditions are properly configured."""

    def test_all_conditions_have_configs(self):
        for cond in ConditionID:
            assert cond in CONDITION_CONFIGS, f"Missing config for {cond}"

    def test_b0_has_no_patient_data(self):
        cfg = CONDITION_CONFIGS[ConditionID.B0]
        assert cfg["no_patient_data"] is True

    def test_b1_is_latest_only(self):
        cfg = CONDITION_CONFIGS[ConditionID.B1]
        assert cfg["raw_note_only"] is True
        assert cfg["latest_only"] is True

    def test_b2_is_doc_rag(self):
        cfg = CONDITION_CONFIGS[ConditionID.B2]
        assert cfg["retrieval_mode"] == "doc_only"
        assert cfg["assertion_mode"] == "none"

    def test_b3_is_kg_rag(self):
        cfg = CONDITION_CONFIGS[ConditionID.B3]
        assert cfg["retrieval_mode"] == "graph_plus_doc"
        assert cfg["assertion_mode"] == "full"
        assert cfg["temporal_mode"] == "full_bitemporal"

    def test_b4_is_full_system(self):
        cfg = CONDITION_CONFIGS[ConditionID.B4]
        assert cfg["retrieval_mode"] == "graph_plus_doc_plus_guidelines"
        assert cfg["assertion_mode"] == "full"
        assert cfg["temporal_mode"] == "full_bitemporal"
        assert cfg["calculator_enabled"] is True
        assert cfg["guidelines_enabled"] is True


# ============================================================================
# Tier bounds tests
# ============================================================================


class TestTierBounds:
    """Verify tier encounter boundaries."""

    def test_tier_a_bounds(self):
        lo, hi = TIER_BOUNDS[LongitudinalTier.A]
        assert lo == 1
        assert hi == 2

    def test_tier_b_bounds(self):
        lo, hi = TIER_BOUNDS[LongitudinalTier.B]
        assert lo == 5
        assert hi == 10

    def test_tier_c_bounds(self):
        lo, hi = TIER_BOUNDS[LongitudinalTier.C]
        assert lo == 15

    def test_tiers_non_overlapping(self):
        _, a_hi = TIER_BOUNDS[LongitudinalTier.A]
        b_lo, b_hi = TIER_BOUNDS[LongitudinalTier.B]
        c_lo, _ = TIER_BOUNDS[LongitudinalTier.C]
        assert a_hi < b_lo  # Gap between A and B is intentional
        assert b_hi < c_lo  # Gap between B and C is intentional


# ============================================================================
# Analyzer tests
# ============================================================================


class TestLongBenchAnalyzer:
    """Test aggregate analysis computation."""

    def _make_results(self) -> tuple[list[LongBenchResult], list[LongBenchQuestion]]:
        """Create sample results for analysis."""
        criteria = [
            LongBenchCriterion(
                criterion_id="c1", text="experiencer check",
                criterion_type=CriterionType.EXPERIENCER,
                weight=CriterionWeight.CRITICAL,
            ),
            LongBenchCriterion(
                criterion_id="c2", text="assertion check",
                criterion_type=CriterionType.ASSERTION,
                weight=CriterionWeight.IMPORTANT,
            ),
        ]

        questions = [
            LongBenchQuestion(
                question_id=f"q{i}", patient_id=f"P{i:03d}",
                question_text="Test?",
                domain=QuestionDomain.FAMILY_HISTORY,
                tier=tier,
                criteria=criteria,
            )
            for i, tier in enumerate([
                LongitudinalTier.A, LongitudinalTier.A,
                LongitudinalTier.C, LongitudinalTier.C,
            ])
        ]

        results = []
        # B0: poor on experiencer across all tiers
        for q in questions:
            r = LongBenchResult(
                question_id=q.question_id, patient_id=q.patient_id,
                condition=ConditionID.B0, tier=q.tier,
                domain=q.domain, predicted_answer="guess",
                criterion_results=[
                    CriterionResult(criterion_id="c1", satisfied=False),
                    CriterionResult(criterion_id="c2", satisfied=False),
                ],
            )
            r.compute_scores(criteria)
            results.append(r)

        # B3: good on experiencer, especially in tier C
        for qi, q in enumerate(questions):
            exp_satisfied = q.tier == LongitudinalTier.C  # Only good with longitudinal data
            r = LongBenchResult(
                question_id=q.question_id, patient_id=q.patient_id,
                condition=ConditionID.B3, tier=q.tier,
                domain=q.domain, predicted_answer="precise answer",
                criterion_results=[
                    CriterionResult(criterion_id="c1", satisfied=exp_satisfied),
                    CriterionResult(criterion_id="c2", satisfied=True),
                ],
            )
            r.compute_scores(criteria)
            results.append(r)

        return results, questions

    def test_compute_condition_tier_scores(self):
        results, questions = self._make_results()
        scores = LongBenchAnalyzer.compute_condition_tier_scores(results, questions)

        # Should have 4 cells: B0xA, B0xC, B3xA, B3xC
        assert len(scores) == 4

        # Find B0 tier A
        b0_a = next(
            s for s in scores
            if s.condition == ConditionID.B0 and s.tier == LongitudinalTier.A
        )
        assert b0_a.mean_score == 0.0  # All criteria failed

        # Find B3 tier C — should be higher than B3 tier A
        b3_c = next(
            s for s in scores
            if s.condition == ConditionID.B3 and s.tier == LongitudinalTier.C
        )
        b3_a = next(
            s for s in scores
            if s.condition == ConditionID.B3 and s.tier == LongitudinalTier.A
        )
        assert b3_c.mean_score > b3_a.mean_score  # Longitudinal advantage!

    def test_markdown_table(self):
        results, questions = self._make_results()
        scores = LongBenchAnalyzer.compute_condition_tier_scores(results, questions)
        table = LongBenchAnalyzer.to_markdown_table(scores)
        assert "Tier A" in table
        assert "Tier C" in table
        assert "LLM Alone" in table
        assert "KG-RAG" in table

    def test_criterion_type_table(self):
        results, questions = self._make_results()
        scores = LongBenchAnalyzer.compute_condition_tier_scores(results, questions)
        table = LongBenchAnalyzer.to_criterion_type_table(scores)
        assert "experiencer" in table
        assert "assertion" in table

    def test_report_to_json(self):
        results, questions = self._make_results()
        report = LongBenchReport(
            cohort_id="test",
            results=results,
            total_questions=4,
            total_criteria=8,
        )
        report.condition_tier_scores = (
            LongBenchAnalyzer.compute_condition_tier_scores(results, questions)
        )

        data = LongBenchAnalyzer.report_to_json(report)
        assert data["cohort_id"] == "test"
        assert len(data["results"]) == 8  # 4 questions x 2 conditions
        assert len(data["condition_tier_scores"]) == 4
        # Should be JSON-serializable
        json_str = json.dumps(data)
        assert len(json_str) > 0
