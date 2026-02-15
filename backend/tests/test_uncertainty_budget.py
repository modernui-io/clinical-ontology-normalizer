"""Tests for P2-007 (Uncertainty taxonomy) and P2-019 (API budget/timeout).

Covers:
- Uncertainty reason catalog completeness
- classify_uncertainty logic for various scenarios
- QueryBudget defaults and env-var overrides
- BudgetTracker phase tracking and enforcement
- BudgetExceeded exception semantics
"""

from __future__ import annotations

import os
import time

import pytest

from app.schemas.uncertainty_taxonomy import (
    REASON_CATALOG,
    UncertaintyCategory,
    UncertaintyReason,
    classify_uncertainty,
    get_uncertainty_reason,
)
from app.core.api_budget import (
    BudgetExceeded,
    BudgetTracker,
    QueryBudget,
)


# ============================================================================
# P2-007: Uncertainty Taxonomy
# ============================================================================


class TestReasonCatalog:
    """REASON_CATALOG should be consistent and complete."""

    def test_all_codes_match_keys(self):
        for key, reason in REASON_CATALOG.items():
            assert reason.code == key, f"Key {key} != reason.code {reason.code}"

    def test_codes_follow_format(self):
        for code in REASON_CATALOG:
            assert code.startswith("UC-"), f"Code {code} missing UC- prefix"
            assert len(code) == 6, f"Code {code} is not 6 chars"

    def test_all_categories_represented(self):
        categories_used = {r.category for r in REASON_CATALOG.values()}
        # At minimum these categories should have at least one code
        expected = {
            UncertaintyCategory.INSUFFICIENT_EVIDENCE,
            UncertaintyCategory.LOW_CONFIDENCE,
            UncertaintyCategory.DEPENDENCY_UNAVAILABLE,
            UncertaintyCategory.MODEL_LIMITATION,
        }
        assert expected.issubset(categories_used)

    def test_severity_values_valid(self):
        for reason in REASON_CATALOG.values():
            assert reason.severity in ("info", "warning", "error")

    def test_catalog_has_minimum_entries(self):
        assert len(REASON_CATALOG) >= 8


class TestGetUncertaintyReason:
    def test_known_code(self):
        reason = get_uncertainty_reason("UC-001")
        assert reason is not None
        assert reason.code == "UC-001"
        assert reason.category == UncertaintyCategory.INSUFFICIENT_EVIDENCE

    def test_unknown_code_returns_none(self):
        assert get_uncertainty_reason("UC-999") is None

    def test_empty_code(self):
        assert get_uncertainty_reason("") is None


class TestClassifyUncertainty:
    """classify_uncertainty should return the right codes for each scenario."""

    def test_healthy_query_returns_empty(self):
        codes = classify_uncertainty(
            confidence=0.85,
            evidence_count=5,
            kg_node_count=3,
            dependency_state={"kg_available": True, "documents_available": True, "llm_available": True},
            fallback_used=False,
        )
        assert codes == []

    def test_no_evidence_returns_uc001(self):
        codes = classify_uncertainty(
            confidence=0.85,
            evidence_count=0,
            kg_node_count=3,
        )
        assert "UC-001" in codes

    def test_no_kg_nodes_returns_uc002(self):
        codes = classify_uncertainty(
            confidence=0.85,
            evidence_count=5,
            kg_node_count=0,
        )
        assert "UC-002" in codes

    def test_very_low_confidence_returns_uc003(self):
        codes = classify_uncertainty(
            confidence=0.1,
            evidence_count=5,
            kg_node_count=3,
        )
        assert "UC-003" in codes
        # Should NOT also have UC-010 (moderate)
        assert "UC-010" not in codes

    def test_moderate_confidence_returns_uc010(self):
        codes = classify_uncertainty(
            confidence=0.4,
            evidence_count=5,
            kg_node_count=3,
        )
        assert "UC-010" in codes
        assert "UC-003" not in codes

    def test_kg_unavailable_returns_uc007(self):
        codes = classify_uncertainty(
            confidence=0.85,
            evidence_count=5,
            kg_node_count=3,
            dependency_state={"kg_available": False, "documents_available": True},
        )
        assert "UC-007" in codes

    def test_docs_unavailable_returns_uc008(self):
        codes = classify_uncertainty(
            confidence=0.85,
            evidence_count=5,
            kg_node_count=3,
            dependency_state={"kg_available": True, "documents_available": False},
        )
        assert "UC-008" in codes

    def test_fallback_returns_uc006(self):
        codes = classify_uncertainty(
            confidence=0.85,
            evidence_count=5,
            kg_node_count=3,
            fallback_used=True,
        )
        assert "UC-006" in codes

    def test_multiple_issues_returns_multiple_codes(self):
        codes = classify_uncertainty(
            confidence=0.1,
            evidence_count=0,
            kg_node_count=0,
            dependency_state={"kg_available": False, "documents_available": False},
            fallback_used=True,
        )
        assert "UC-001" in codes
        assert "UC-002" in codes
        assert "UC-003" in codes
        assert "UC-007" in codes
        assert "UC-008" in codes
        assert "UC-006" in codes

    def test_none_dependency_state_treated_as_available(self):
        codes = classify_uncertainty(
            confidence=0.85,
            evidence_count=5,
            kg_node_count=3,
            dependency_state=None,
        )
        assert "UC-007" not in codes
        assert "UC-008" not in codes


# ============================================================================
# P2-019: API Budget / Timeout Policies
# ============================================================================


class TestQueryBudget:
    def test_defaults(self):
        budget = QueryBudget()
        assert budget.max_total_seconds == 30.0
        assert budget.max_llm_seconds == 15.0
        assert budget.max_kg_seconds == 10.0
        assert budget.max_doc_retrieval_seconds == 5.0

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("QUERY_BUDGET_TOTAL_SECONDS", "60")
        monkeypatch.setenv("QUERY_BUDGET_LLM_SECONDS", "25")
        monkeypatch.setenv("QUERY_BUDGET_KG_SECONDS", "20")
        monkeypatch.setenv("QUERY_BUDGET_DOC_SECONDS", "8")
        budget = QueryBudget()
        assert budget.max_total_seconds == 60.0
        assert budget.max_llm_seconds == 25.0
        assert budget.max_kg_seconds == 20.0
        assert budget.max_doc_retrieval_seconds == 8.0

    def test_invalid_env_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("QUERY_BUDGET_TOTAL_SECONDS", "not_a_number")
        budget = QueryBudget()
        assert budget.max_total_seconds == 30.0

    def test_limit_for_phases(self):
        budget = QueryBudget()
        assert budget.limit_for("llm") == 15.0
        assert budget.limit_for("kg") == 10.0
        assert budget.limit_for("doc_retrieval") == 5.0

    def test_custom_limits(self):
        budget = QueryBudget(
            max_total_seconds=10,
            max_llm_seconds=5,
            max_kg_seconds=3,
            max_doc_retrieval_seconds=2,
        )
        assert budget.limit_for("llm") == 5.0
        assert budget.limit_for("kg") == 3.0
        assert budget.limit_for("doc_retrieval") == 2.0


class TestBudgetExceeded:
    def test_exception_fields(self):
        exc = BudgetExceeded("llm", 16.5, 15.0)
        assert exc.phase == "llm"
        assert exc.elapsed == 16.5
        assert exc.limit == 15.0
        assert "llm" in str(exc)
        assert "16.50" in str(exc)

    def test_is_exception(self):
        exc = BudgetExceeded("total", 31.0, 30.0)
        assert isinstance(exc, Exception)


class TestBudgetTracker:
    def test_phase_tracking_under_budget(self):
        budget = QueryBudget(max_total_seconds=30, max_llm_seconds=15, max_kg_seconds=10, max_doc_retrieval_seconds=5)
        tracker = BudgetTracker(budget)

        tracker.start_phase("llm")
        time.sleep(0.01)
        tracker.end_phase("llm")  # should not raise

        summary = tracker.get_summary()
        assert "llm_ms" in summary
        assert summary["llm_ms"] >= 5  # at least 5ms
        assert "total_ms" in summary

    def test_phase_exceeded_raises(self):
        budget = QueryBudget(
            max_total_seconds=30,
            max_llm_seconds=0.01,  # 10ms limit
            max_kg_seconds=10,
            max_doc_retrieval_seconds=5,
        )
        tracker = BudgetTracker(budget)

        tracker.start_phase("llm")
        time.sleep(0.05)  # 50ms > 10ms limit
        with pytest.raises(BudgetExceeded) as exc_info:
            tracker.end_phase("llm")
        assert exc_info.value.phase == "llm"

    def test_total_budget_exceeded_raises(self):
        budget = QueryBudget(
            max_total_seconds=0.01,  # 10ms total
            max_llm_seconds=15,
            max_kg_seconds=10,
            max_doc_retrieval_seconds=5,
        )
        tracker = BudgetTracker(budget)

        time.sleep(0.05)  # exceed total budget
        tracker.start_phase("llm")
        time.sleep(0.01)
        with pytest.raises(BudgetExceeded) as exc_info:
            tracker.end_phase("llm")
        assert exc_info.value.phase == "total"

    def test_end_phase_without_start_is_noop(self):
        tracker = BudgetTracker()
        tracker.end_phase("llm")  # should not raise
        summary = tracker.get_summary()
        assert "llm_ms" not in summary

    def test_get_summary_all_phases(self):
        budget = QueryBudget(max_total_seconds=30, max_llm_seconds=15, max_kg_seconds=10, max_doc_retrieval_seconds=5)
        tracker = BudgetTracker(budget)

        for phase in ("llm", "kg", "doc_retrieval"):
            tracker.start_phase(phase)
            time.sleep(0.005)
            tracker.end_phase(phase)

        summary = tracker.get_summary()
        assert "llm_ms" in summary
        assert "kg_ms" in summary
        assert "doc_retrieval_ms" in summary
        assert "total_ms" in summary
        assert all(v >= 0 for v in summary.values())

    def test_default_budget_used_when_none(self):
        tracker = BudgetTracker(budget=None)
        assert tracker.budget.max_total_seconds == 30.0

    def test_total_elapsed(self):
        tracker = BudgetTracker()
        time.sleep(0.02)
        assert tracker.total_elapsed() >= 0.015


class TestUncertaintyReasonModel:
    """Validate UncertaintyReason Pydantic model constraints."""

    def test_valid_reason(self):
        reason = UncertaintyReason(
            category=UncertaintyCategory.LOW_CONFIDENCE,
            code="UC-099",
            description="Test reason",
            severity="warning",
        )
        assert reason.code == "UC-099"

    def test_invalid_code_pattern(self):
        with pytest.raises(Exception):
            UncertaintyReason(
                category=UncertaintyCategory.LOW_CONFIDENCE,
                code="BAD-CODE",
                description="Bad",
                severity="warning",
            )

    def test_invalid_severity(self):
        with pytest.raises(Exception):
            UncertaintyReason(
                category=UncertaintyCategory.LOW_CONFIDENCE,
                code="UC-099",
                description="Bad",
                severity="critical",  # not allowed
            )
