"""Tests for Answer Template Service (P3-004)."""

import pytest

from app.services.answer_template_service import (
    QuestionClass,
    FormattedAnswer,
    AnswerTemplate,
    format_answer,
    get_template,
    _confidence_band,
)


class TestQuestionClassEnum:
    """Verify QuestionClass enum values."""

    def test_all_classes_defined(self):
        expected = {
            "medication_query",
            "condition_query",
            "lab_query",
            "procedure_query",
            "general_query",
            "differential_diagnosis",
        }
        assert {qc.value for qc in QuestionClass} == expected


class TestConfidenceBands:
    """Verify confidence band mapping."""

    def test_high_confidence(self):
        assert _confidence_band(0.95) == "high"
        assert _confidence_band(0.80) == "high"

    def test_medium_confidence(self):
        assert _confidence_band(0.65) == "medium"
        assert _confidence_band(0.50) == "medium"

    def test_low_confidence(self):
        assert _confidence_band(0.3) == "low"
        assert _confidence_band(0.0) == "low"


class TestGetTemplate:
    """Verify template retrieval."""

    def test_each_class_has_template(self):
        for qc in QuestionClass:
            t = get_template(qc)
            assert isinstance(t, AnswerTemplate)
            assert t.question_class == qc

    def test_templates_have_all_confidence_bands(self):
        for qc in QuestionClass:
            t = get_template(qc)
            for band in ("high", "medium", "low"):
                assert band in t.confidence_bands


class TestFormatAnswer:
    """Verify answer formatting."""

    def test_basic_medication_query(self):
        result = format_answer(
            QuestionClass.MEDICATION_QUERY,
            raw_answer="Warfarin requires INR monitoring.",
            confidence=0.9,
        )
        assert isinstance(result, FormattedAnswer)
        assert "Medication Review:" in result.summary
        assert result.confidence == 0.9
        assert "high" in result.confidence_note.lower()

    def test_low_confidence_note(self):
        result = format_answer(
            QuestionClass.GENERAL_QUERY,
            raw_answer="Unclear finding.",
            confidence=0.2,
        )
        assert "low" in result.confidence_note.lower()
        assert "20%" in result.confidence_note

    def test_evidence_uses_custom_text(self):
        result = format_answer(
            QuestionClass.LAB_QUERY,
            raw_answer="Potassium is elevated.",
            evidence="Serum K+ 6.1 mEq/L exceeds normal range (3.5-5.0).",
            confidence=0.85,
        )
        assert "6.1" in result.evidence

    def test_confidence_clamped(self):
        result = format_answer(
            QuestionClass.GENERAL_QUERY,
            raw_answer="test",
            confidence=1.5,
        )
        assert result.confidence == 1.0

        result2 = format_answer(
            QuestionClass.GENERAL_QUERY,
            raw_answer="test",
            confidence=-0.3,
        )
        assert result2.confidence == 0.0

    def test_to_dict(self):
        result = format_answer(
            QuestionClass.CONDITION_QUERY,
            raw_answer="Diabetes management.",
            confidence=0.7,
        )
        d = result.to_dict()
        assert d["question_class"] == "condition_query"
        assert "summary" in d
        assert "evidence" in d
        assert d["confidence"] == 0.7

    def test_to_text_has_section_headers(self):
        result = format_answer(
            QuestionClass.DIFFERENTIAL_DIAGNOSIS,
            raw_answer="Consider PE vs pneumonia.",
            confidence=0.6,
        )
        text = result.to_text()
        assert "## Summary" in text
        assert "## Evidence" in text
        assert "## Confidence" in text
        assert "## Limitations" in text
        assert "## Recommended Next Steps" in text

    def test_all_question_classes_produce_valid_output(self):
        for qc in QuestionClass:
            result = format_answer(qc, raw_answer="Test answer.", confidence=0.5)
            assert result.summary
            assert result.evidence
            assert result.confidence_note
            assert result.limitations
            assert result.next_steps
