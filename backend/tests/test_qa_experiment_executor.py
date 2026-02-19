"""Tests for QA experiment executor."""

from __future__ import annotations

import pytest

from app.services.qa_experiment_executor import (
    CLINICAL_QA_SYSTEM_PROMPT,
    QAExperimentExecutor,
    QARunConfig,
    print_ablation_table,
)
from app.services.qa_evaluation import (
    ASSERTION_QUESTIONS,
    QAEvaluationReport,
    QAEvaluationService,
    QAQuestion,
    QAResult,
)


class TestQARunConfig:
    def test_default_config(self):
        config = QARunConfig(patient_id="P001", condition="full_epistemic")
        assert config.assertion_mode == "full"
        assert config.temporal_mode == "full_bitemporal"
        assert config.retrieval_mode == "graph_plus_doc"
        assert config.llm_model == "claude-sonnet-4-5-20250929"

    def test_assertion_ablation_configs(self):
        configs = {
            "no_assertion": QARunConfig(
                patient_id="P001", condition="no_assertion", assertion_mode="none",
            ),
            "extracted_only": QARunConfig(
                patient_id="P001", condition="assertion_extracted_only",
                assertion_mode="extracted_only",
            ),
            "full": QARunConfig(
                patient_id="P001", condition="full_epistemic", assertion_mode="full",
            ),
        }
        assert configs["no_assertion"].assertion_mode == "none"
        assert configs["extracted_only"].assertion_mode == "extracted_only"
        assert configs["full"].assertion_mode == "full"

    def test_temporal_ablation_configs(self):
        configs = {
            "no_temporal": QARunConfig(
                patient_id="P001", condition="no_temporal",
                temporal_mode="no_temporal",
            ),
            "timestamps_only": QARunConfig(
                patient_id="P001", condition="timestamps_only",
                temporal_mode="timestamps_only",
            ),
            "full_bitemporal": QARunConfig(
                patient_id="P001", condition="full_bitemporal",
                temporal_mode="full_bitemporal",
            ),
        }
        assert configs["no_temporal"].temporal_mode == "no_temporal"
        assert configs["timestamps_only"].temporal_mode == "timestamps_only"
        assert configs["full_bitemporal"].temporal_mode == "full_bitemporal"

    def test_retrieval_mode_configs(self):
        for mode in ("doc_only", "graph_only", "graph_plus_doc", "graph_plus_doc_plus_guidelines"):
            config = QARunConfig(
                patient_id="P001", condition=mode, retrieval_mode=mode,
            )
            assert config.retrieval_mode == mode


class TestSystemPrompt:
    def test_system_prompt_covers_assertion_types(self):
        prompt = CLINICAL_QA_SYSTEM_PROMPT
        assert "NEGATED" in prompt
        assert "UNCERTAINTY" in prompt
        assert "FAMILY HISTORY" in prompt
        assert "HISTORICAL" in prompt
        assert "CONDITIONAL" in prompt

    def test_system_prompt_covers_temporal(self):
        assert "temporal" in CLINICAL_QA_SYSTEM_PROMPT.lower()
        assert "most recent" in CLINICAL_QA_SYSTEM_PROMPT.lower()


class TestExecutorInit:
    def test_executor_creates_services(self):
        executor = QAExperimentExecutor()
        assert executor.qa_service is not None
        assert isinstance(executor.qa_service, QAEvaluationService)


class TestPrintAblationTable:
    def test_formats_table(self):
        reports = {
            "no_assertion": QAEvaluationReport(
                experiment_name="test",
                condition="no_assertion",
                total_questions=10,
                correct=6,
                accuracy=0.6,
                category_accuracies={"negation": 0.4, "uncertainty": 0.8},
            ),
            "full_epistemic": QAEvaluationReport(
                experiment_name="test",
                condition="full_epistemic",
                total_questions=10,
                correct=9,
                accuracy=0.9,
                category_accuracies={"negation": 0.9, "uncertainty": 0.9},
            ),
        }
        table = print_ablation_table(reports)
        assert "no_assertion" in table
        assert "full_epistemic" in table
        assert "60.0%" in table
        assert "90.0%" in table

    def test_empty_reports(self):
        table = print_ablation_table({})
        # Should produce header rows at minimum
        assert "Condition" in table

    def test_includes_safety_score(self):
        results = [
            QAResult(
                question_id="q1", predicted_answer="No", expected_answer="No",
                correct=True, score=1.0, category="negation", condition="full",
            ),
        ]
        reports = {
            "full": QAEvaluationReport(
                experiment_name="test",
                condition="full",
                total_questions=1,
                correct=1,
                accuracy=1.0,
                category_accuracies={"negation": 1.0},
                results=results,
            ),
        }
        table = print_ablation_table(reports)
        assert "Safety" in table
        assert "1.000" in table


class TestConditionCoverage:
    """Verify all experiment conditions map to valid config values."""

    def test_assertion_conditions(self):
        condition_to_mode = {
            "no_assertion": "none",
            "assertion_extracted_only": "extracted_only",
            "full_epistemic": "full",
        }
        for cond, mode in condition_to_mode.items():
            config = QARunConfig(
                patient_id="P001", condition=cond, assertion_mode=mode,
            )
            assert config.assertion_mode == mode

    def test_temporal_conditions(self):
        condition_to_mode = {
            "no_temporal": "no_temporal",
            "timestamps_only": "timestamps_only",
            "full_bitemporal": "full_bitemporal",
        }
        for cond, mode in condition_to_mode.items():
            config = QARunConfig(
                patient_id="P001", condition=cond, temporal_mode=mode,
            )
            assert config.temporal_mode == mode

    def test_retrieval_conditions(self):
        condition_to_mode = {
            "doc_only": "doc_only",
            "graph_only": "graph_only",
            "graph_plus_doc": "graph_plus_doc",
            "graph_plus_doc_plus_guidelines": "graph_plus_doc_plus_guidelines",
        }
        for cond, mode in condition_to_mode.items():
            config = QARunConfig(
                patient_id="P001", condition=cond, retrieval_mode=mode,
            )
            assert config.retrieval_mode == mode


class TestQuestionSetCompleteness:
    """Verify question sets are complete for experiments."""

    def test_assertion_questions_cover_all_categories(self):
        categories = {q.category for q in ASSERTION_QUESTIONS}
        assert "negation" in categories
        assert "uncertainty" in categories
        assert "family_history" in categories
        assert "temporal_status" in categories
        assert "conditional" in categories

    def test_assertion_questions_all_have_clinical_context(self):
        for q in ASSERTION_QUESTIONS:
            assert q.clinical_context, f"{q.question_id} missing clinical_context"

    def test_total_llm_calls_per_patient(self):
        """Document expected LLM call count for cost estimation."""
        exp2_calls = len(ASSERTION_QUESTIONS) * 3  # 3 conditions
        assert exp2_calls == 150

        from app.services.qa_evaluation import TEMPORAL_QUESTIONS, RAG_QUESTIONS
        exp3_calls = len(TEMPORAL_QUESTIONS) * 3
        exp4_calls = len(RAG_QUESTIONS) * 4  # 4 conditions

        total = exp2_calls + exp3_calls + exp4_calls
        # Sanity check: total should be reasonable for a single patient
        assert total < 1000, f"Total LLM calls {total} seems too high"
