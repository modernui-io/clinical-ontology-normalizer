"""Tests for NeurIPS 2026 experiment runner and QA evaluation."""

from __future__ import annotations

import pytest

from app.services.experiment_runner import EXPERIMENT_DEFINITIONS
from app.services.qa_evaluation import (
    ASSERTION_QUESTIONS,
    RAG_QUESTIONS,
    TEMPORAL_QUESTIONS,
    QAEvaluationService,
    QAQuestion,
    QAResult,
)


# ============================================================================
# Experiment Definitions
# ============================================================================


class TestExperimentDefinitions:
    def test_all_six_experiments_defined(self):
        assert len(EXPERIMENT_DEFINITIONS) == 6
        expected_keys = {
            "exp1_pipeline_eval",
            "exp2_assertion_ablation",
            "exp3_temporal_ablation",
            "exp4_graphrag_comparison",
            "exp5_benchmark",
            "exp6_scalability",
        }
        assert set(EXPERIMENT_DEFINITIONS.keys()) == expected_keys

    def test_experiment_fields_present(self):
        for key, defn in EXPERIMENT_DEFINITIONS.items():
            assert "name" in defn, f"{key} missing 'name'"
            assert "description" in defn, f"{key} missing 'description'"
            assert "hypothesis" in defn, f"{key} missing 'hypothesis'"
            assert "config" in defn, f"{key} missing 'config'"
            assert "tags" in defn, f"{key} missing 'tags'"
            assert "datasets" in defn, f"{key} missing 'datasets'"
            assert "metric_categories" in defn, f"{key} missing 'metric_categories'"

    def test_configs_are_valid(self):
        from app.schemas.research import ExperimentConfig

        for key, defn in EXPERIMENT_DEFINITIONS.items():
            config = ExperimentConfig(**defn["config"])
            assert isinstance(config.assertion_aware, bool)
            assert config.nlp_method in ("rule_based", "ml", "ensemble")

    def test_ablation_experiments_have_conditions(self):
        assert "conditions" in EXPERIMENT_DEFINITIONS["exp2_assertion_ablation"]
        assert len(EXPERIMENT_DEFINITIONS["exp2_assertion_ablation"]["conditions"]) == 3

        assert "conditions" in EXPERIMENT_DEFINITIONS["exp3_temporal_ablation"]
        assert len(EXPERIMENT_DEFINITIONS["exp3_temporal_ablation"]["conditions"]) == 3

        assert "conditions" in EXPERIMENT_DEFINITIONS["exp4_graphrag_comparison"]
        assert len(EXPERIMENT_DEFINITIONS["exp4_graphrag_comparison"]["conditions"]) == 4

    def test_neurips2026_tag_present(self):
        for key, defn in EXPERIMENT_DEFINITIONS.items():
            assert "neurips2026" in defn["tags"], f"{key} missing neurips2026 tag"

    def test_exp2_is_key_result(self):
        assert "key_result" in EXPERIMENT_DEFINITIONS["exp2_assertion_ablation"]["tags"]


# ============================================================================
# Ablation Mode Mappings
# ============================================================================


class TestAblationConditionModes:
    """Test that ExperimentRunner maps conditions to correct GraphRAG modes."""

    def test_assertion_condition_modes(self):
        from app.services.experiment_runner import ExperimentRunner
        assert ExperimentRunner.ASSERTION_CONDITION_TO_MODE == {
            "no_assertion": "none",
            "assertion_extracted_only": "extracted_only",
            "full_epistemic": "full",
        }

    def test_temporal_condition_modes(self):
        from app.services.experiment_runner import ExperimentRunner
        assert ExperimentRunner.TEMPORAL_CONDITION_TO_MODE == {
            "no_temporal": "no_temporal",
            "timestamps_only": "timestamps_only",
            "full_bitemporal": "full_bitemporal",
        }

    def test_retrieval_condition_modes(self):
        from app.services.experiment_runner import ExperimentRunner
        assert ExperimentRunner.RETRIEVAL_CONDITION_TO_MODE == {
            "doc_only": "doc_only",
            "graph_only": "graph_only",
            "graph_plus_doc": "graph_plus_doc",
            "graph_plus_doc_plus_guidelines": "graph_plus_doc_plus_guidelines",
        }

    def test_assertion_modes_cover_all_conditions(self):
        from app.services.experiment_runner import ExperimentRunner
        conditions = EXPERIMENT_DEFINITIONS["exp2_assertion_ablation"]["conditions"]
        for cond in conditions:
            assert cond in ExperimentRunner.ASSERTION_CONDITION_TO_MODE, f"Missing mode for {cond}"

    def test_temporal_modes_cover_all_conditions(self):
        from app.services.experiment_runner import ExperimentRunner
        conditions = EXPERIMENT_DEFINITIONS["exp3_temporal_ablation"]["conditions"]
        for cond in conditions:
            assert cond in ExperimentRunner.TEMPORAL_CONDITION_TO_MODE, f"Missing mode for {cond}"

    def test_retrieval_modes_cover_all_conditions(self):
        from app.services.experiment_runner import ExperimentRunner
        conditions = EXPERIMENT_DEFINITIONS["exp4_graphrag_comparison"]["conditions"]
        for cond in conditions:
            assert cond in ExperimentRunner.RETRIEVAL_CONDITION_TO_MODE, f"Missing mode for {cond}"


# ============================================================================
# QA Question Sets
# ============================================================================


class TestAssertionQuestions:
    def test_question_count(self):
        assert len(ASSERTION_QUESTIONS) == 50

    def test_question_categories(self):
        categories = {q.category for q in ASSERTION_QUESTIONS}
        expected = {"negation", "uncertainty", "family_history", "temporal_status", "conditional"}
        assert categories == expected

    def test_category_distribution(self):
        counts = {}
        for q in ASSERTION_QUESTIONS:
            counts[q.category] = counts.get(q.category, 0) + 1

        assert counts["negation"] == 15
        assert counts["uncertainty"] == 10
        assert counts["family_history"] == 10
        assert counts["temporal_status"] == 10
        assert counts["conditional"] == 5

    def test_all_assertion_sensitive(self):
        for q in ASSERTION_QUESTIONS:
            assert q.assertion_sensitive is True, f"Question {q.question_id} not marked assertion_sensitive"

    def test_unique_question_ids(self):
        ids = [q.question_id for q in ASSERTION_QUESTIONS]
        assert len(ids) == len(set(ids))

    def test_questions_have_expected_answers(self):
        for q in ASSERTION_QUESTIONS:
            assert q.expected_answer, f"Question {q.question_id} missing expected_answer"
            assert len(q.expected_answer) > 10, f"Question {q.question_id} expected_answer too short"

    def test_questions_have_context(self):
        for q in ASSERTION_QUESTIONS:
            assert q.clinical_context, f"Question {q.question_id} missing clinical_context"


class TestTemporalQuestions:
    def test_question_count(self):
        assert len(TEMPORAL_QUESTIONS) >= 25  # At least representative subset

    def test_question_categories(self):
        categories = {q.category for q in TEMPORAL_QUESTIONS}
        expected = {"current_state", "historical", "sequence", "duration", "change"}
        assert categories == expected

    def test_all_temporal_sensitive(self):
        for q in TEMPORAL_QUESTIONS:
            assert q.temporal_sensitive is True

    def test_unique_question_ids(self):
        ids = [q.question_id for q in TEMPORAL_QUESTIONS]
        assert len(ids) == len(set(ids))


class TestRAGQuestions:
    def test_question_count(self):
        assert len(RAG_QUESTIONS) >= 20  # Representative subset (5 per category)

    def test_question_categories(self):
        categories = {q.category for q in RAG_QUESTIONS}
        expected = {"single_hop", "multi_hop", "reasoning", "guideline_sensitive"}
        assert categories == expected

    def test_unique_question_ids(self):
        ids = [q.question_id for q in RAG_QUESTIONS]
        assert len(ids) == len(set(ids))


# ============================================================================
# QA Evaluation Service
# ============================================================================


class TestQAEvaluationService:
    @pytest.fixture
    def service(self):
        return QAEvaluationService()

    def test_get_assertion_questions(self, service):
        questions = service.get_assertion_questions()
        assert len(questions) == 50

    def test_get_temporal_questions(self, service):
        questions = service.get_temporal_questions()
        assert len(questions) >= 25

    def test_get_rag_questions(self, service):
        questions = service.get_rag_questions()
        assert len(questions) >= 20

    def test_filter_by_category(self, service):
        questions = service.get_assertion_questions()
        negation = service.get_questions_by_category(questions, "negation")
        assert len(negation) == 15
        assert all(q.category == "negation" for q in negation)


class TestQAScoring:
    @pytest.fixture
    def service(self):
        return QAEvaluationService()

    def test_negation_correct(self, service):
        q = QAQuestion(
            question_id="test_neg",
            question="Does the patient have diabetes?",
            category="negation",
            expected_answer="No — patient denies diabetes.",
            assertion_sensitive=True,
        )
        result = service.score_answer(q, "No, the patient does not have diabetes.", "full_epistemic")
        assert result.correct is True
        assert result.score == 1.0

    def test_negation_false_positive(self, service):
        q = QAQuestion(
            question_id="test_neg_fp",
            question="Does the patient have diabetes?",
            category="negation",
            expected_answer="No — patient denies diabetes.",
            assertion_sensitive=True,
        )
        result = service.score_answer(q, "Yes, the patient has diabetes.", "no_assertion")
        assert result.correct is False
        assert result.score == 0.0

    def test_uncertainty_correct(self, service):
        q = QAQuestion(
            question_id="test_unc",
            question="Is pneumonia confirmed?",
            category="uncertainty",
            expected_answer="Not confirmed — possible pneumonia.",
            assertion_sensitive=True,
        )
        result = service.score_answer(q, "Possible pneumonia, pending confirmation.", "full_epistemic")
        assert result.correct is True

    def test_uncertainty_missed(self, service):
        q = QAQuestion(
            question_id="test_unc_miss",
            question="Is pneumonia confirmed?",
            category="uncertainty",
            expected_answer="Not confirmed — possible pneumonia.",
            assertion_sensitive=True,
        )
        result = service.score_answer(q, "Yes, the patient has pneumonia.", "no_assertion")
        assert result.correct is False

    def test_family_history_correct(self, service):
        q = QAQuestion(
            question_id="test_fh",
            question="Does the patient have breast cancer?",
            category="family_history",
            expected_answer="No — family history only.",
            assertion_sensitive=True,
        )
        result = service.score_answer(q, "Family history of breast cancer in mother, but patient is clear.", "full_epistemic")
        assert result.correct is True

    def test_conditional_correct(self, service):
        q = QAQuestion(
            question_id="test_cond",
            question="Should the patient receive metformin?",
            category="conditional",
            expected_answer="Only if renal function is adequate.",
            assertion_sensitive=True,
        )
        result = service.score_answer(q, "Metformin should be considered if eGFR remains above 30.", "full_epistemic")
        assert result.correct is True

    def test_temporal_status_correct(self, service):
        q = QAQuestion(
            question_id="test_ts",
            question="Is the patient currently on warfarin?",
            category="temporal_status",
            expected_answer="No — warfarin was discontinued. Now on apixaban.",
            assertion_sensitive=True,
        )
        result = service.score_answer(q, "Warfarin was previously prescribed but has been discontinued.", "full_epistemic")
        assert result.correct is True


class TestQAEvaluationReport:
    @pytest.fixture
    def service(self):
        return QAEvaluationService()

    def test_evaluate_question_set(self, service):
        questions = [
            QAQuestion(
                question_id="q1", question="Q1?", category="negation",
                expected_answer="No", assertion_sensitive=True,
            ),
            QAQuestion(
                question_id="q2", question="Q2?", category="negation",
                expected_answer="No", assertion_sensitive=True,
            ),
        ]
        answers = {"q1": "No, negative.", "q2": "Yes, positive."}
        report = service.evaluate_question_set(questions, answers, "full_epistemic", "Test")

        assert report.total_questions == 2
        assert report.correct == 1
        assert report.accuracy == 0.5

    def test_clinical_safety_score(self, service):
        results = [
            QAResult(question_id="q1", predicted_answer="No", expected_answer="No",
                     correct=True, score=1.0, category="negation", condition="full"),
            QAResult(question_id="q2", predicted_answer="Yes", expected_answer="No",
                     correct=False, score=0.0, category="negation", condition="no_assertion"),
        ]
        safety_score = service.compute_clinical_safety_score(results)
        # q1 correct (weight 2.0, +2.0), q2 incorrect negation (weight 2.0, -2.0)
        # total_weight = 4.0, score = 0.0
        assert safety_score == 0.0

    def test_clinical_safety_score_all_correct(self, service):
        results = [
            QAResult(question_id="q1", predicted_answer="No", expected_answer="No",
                     correct=True, score=1.0, category="negation", condition="full"),
            QAResult(question_id="q2", predicted_answer="uncertain", expected_answer="uncertain",
                     correct=True, score=1.0, category="uncertainty", condition="full"),
        ]
        safety_score = service.compute_clinical_safety_score(results)
        assert safety_score == 1.0
