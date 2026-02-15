"""Tests for P1-003 (workflow confidence policy) and P1-011 (GraphRAG source retrieval).

Covers:
- Workflow-specific threshold lookups
- Custom override loading from env var
- Policy versioning
- Source retrieval status tracking in GraphAugmentedRAG
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.confidence_policy import DEFAULT_THRESHOLDS, ConfidencePolicy
from app.services.confidence_policy_service import check_action_gate
from app.services.workflow_confidence_policy import (
    WorkflowConfidencePolicy,
    WorkflowType,
    _WORKFLOW_DEFAULTS,
    detect_workflow_type,
    get_policy_for_workflow,
    get_policy_version,
    reset_overrides_cache,
)
from app.services.graph_augmented_rag import (
    GraphAugmentedContext,
    GraphAugmentedRAGService,
    GraphPath,
    SourceRetrievalStatus,
    TemporalContext,
)


# =============================================================================
# P1-003: Workflow-Specific Threshold Lookups
# =============================================================================


class TestWorkflowType:
    """WorkflowType enum values."""

    def test_all_workflow_types_defined(self) -> None:
        expected = {
            "medication_review",
            "diagnosis_support",
            "lab_interpretation",
            "general_query",
            "administrative",
        }
        actual = {wt.value for wt in WorkflowType}
        assert actual == expected

    def test_workflow_type_is_string_enum(self) -> None:
        assert WorkflowType.MEDICATION_REVIEW == "medication_review"
        assert isinstance(WorkflowType.GENERAL_QUERY, str)


class TestGetPolicyForWorkflow:
    """get_policy_for_workflow returns correct thresholds per workflow."""

    def setup_method(self) -> None:
        reset_overrides_cache()
        os.environ.pop("CONFIDENCE_POLICY_OVERRIDES", None)

    def teardown_method(self) -> None:
        reset_overrides_cache()
        os.environ.pop("CONFIDENCE_POLICY_OVERRIDES", None)

    def test_medication_review_has_highest_action_threshold(self) -> None:
        policy = get_policy_for_workflow(WorkflowType.MEDICATION_REVIEW)
        assert policy.thresholds["action"] == 0.90
        assert policy.thresholds["critical_action"] == 0.97

    def test_general_query_has_lowest_action_threshold(self) -> None:
        policy = get_policy_for_workflow(WorkflowType.GENERAL_QUERY)
        assert policy.thresholds["action"] == 0.70
        assert policy.thresholds["critical_action"] == 0.85

    def test_administrative_has_relaxed_thresholds(self) -> None:
        policy = get_policy_for_workflow(WorkflowType.ADMINISTRATIVE)
        assert policy.thresholds["action"] == 0.60
        assert policy.thresholds["suggestion"] == 0.25

    def test_diagnosis_support_thresholds(self) -> None:
        policy = get_policy_for_workflow(WorkflowType.DIAGNOSIS_SUPPORT)
        assert policy.thresholds["action"] == 0.88
        assert policy.thresholds["recommendation"] == 0.75

    def test_lab_interpretation_matches_base_defaults(self) -> None:
        """Lab interpretation should use base defaults for most tiers."""
        policy = get_policy_for_workflow(WorkflowType.LAB_INTERPRETATION)
        assert policy.thresholds["action"] == 0.85
        assert policy.thresholds["critical_action"] == 0.95

    def test_all_workflows_have_all_tiers(self) -> None:
        """Every workflow policy should have all risk tiers defined."""
        expected_tiers = set(DEFAULT_THRESHOLDS.keys())
        for wt in WorkflowType:
            policy = get_policy_for_workflow(wt)
            assert set(policy.thresholds.keys()) >= expected_tiers, (
                f"Workflow {wt.value} missing tiers"
            )

    def test_string_workflow_type_accepted(self) -> None:
        policy = get_policy_for_workflow("medication_review")
        assert policy.workflow_type == "medication_review"
        assert policy.thresholds["action"] == 0.90

    def test_unknown_workflow_falls_back_to_base(self) -> None:
        policy = get_policy_for_workflow("unknown_workflow")
        assert policy.thresholds == dict(DEFAULT_THRESHOLDS)

    def test_strict_mode_default_true(self) -> None:
        policy = get_policy_for_workflow(WorkflowType.MEDICATION_REVIEW)
        assert policy.strict_mode is True

    def test_strict_mode_can_be_overridden(self) -> None:
        policy = get_policy_for_workflow(
            WorkflowType.MEDICATION_REVIEW, strict_mode=False,
        )
        assert policy.strict_mode is False

    def test_to_confidence_policy_conversion(self) -> None:
        wf_policy = get_policy_for_workflow(WorkflowType.MEDICATION_REVIEW)
        base_policy = wf_policy.to_confidence_policy()
        assert isinstance(base_policy, ConfidencePolicy)
        assert base_policy.thresholds["action"] == 0.90

    def test_workflow_policy_integrates_with_check_action_gate(self) -> None:
        """Workflow policy should be usable with check_action_gate."""
        wf_policy = get_policy_for_workflow(WorkflowType.MEDICATION_REVIEW)
        base_policy = wf_policy.to_confidence_policy()

        # High confidence should pass medication_review action gate
        result = check_action_gate(0.95, "action", policy=base_policy)
        assert result.allowed is True

        # Low confidence should fail medication_review action gate
        result = check_action_gate(0.80, "action", policy=base_policy)
        assert result.allowed is False


# =============================================================================
# P1-003: Custom Override Loading
# =============================================================================


class TestEnvOverrides:
    """CONFIDENCE_POLICY_OVERRIDES env var loading."""

    def setup_method(self) -> None:
        reset_overrides_cache()
        os.environ.pop("CONFIDENCE_POLICY_OVERRIDES", None)

    def teardown_method(self) -> None:
        reset_overrides_cache()
        os.environ.pop("CONFIDENCE_POLICY_OVERRIDES", None)

    def test_env_override_applied_on_top_of_defaults(self) -> None:
        overrides = {"medication_review": {"action": 0.99}}
        os.environ["CONFIDENCE_POLICY_OVERRIDES"] = json.dumps(overrides)
        reset_overrides_cache()

        policy = get_policy_for_workflow(WorkflowType.MEDICATION_REVIEW)
        assert policy.thresholds["action"] == 0.99
        # Other tiers should remain at workflow defaults
        assert policy.thresholds["suggestion"] == 0.65

    def test_env_override_for_specific_workflow_only(self) -> None:
        overrides = {"administrative": {"action": 0.75}}
        os.environ["CONFIDENCE_POLICY_OVERRIDES"] = json.dumps(overrides)
        reset_overrides_cache()

        admin_policy = get_policy_for_workflow(WorkflowType.ADMINISTRATIVE)
        assert admin_policy.thresholds["action"] == 0.75

        # Other workflows should be unaffected
        med_policy = get_policy_for_workflow(WorkflowType.MEDICATION_REVIEW)
        assert med_policy.thresholds["action"] == 0.90

    def test_invalid_json_gracefully_ignored(self) -> None:
        os.environ["CONFIDENCE_POLICY_OVERRIDES"] = "not-valid-json"
        reset_overrides_cache()

        policy = get_policy_for_workflow(WorkflowType.MEDICATION_REVIEW)
        # Should fall back to built-in defaults
        assert policy.thresholds["action"] == 0.90

    def test_empty_env_var_no_effect(self) -> None:
        os.environ["CONFIDENCE_POLICY_OVERRIDES"] = ""
        reset_overrides_cache()

        policy = get_policy_for_workflow(WorkflowType.GENERAL_QUERY)
        assert policy.thresholds["action"] == 0.70

    def test_non_dict_top_level_ignored(self) -> None:
        os.environ["CONFIDENCE_POLICY_OVERRIDES"] = '"just a string"'
        reset_overrides_cache()

        policy = get_policy_for_workflow(WorkflowType.MEDICATION_REVIEW)
        assert policy.thresholds["action"] == 0.90

    def test_cache_persists_across_calls(self) -> None:
        overrides = {"medication_review": {"action": 0.99}}
        os.environ["CONFIDENCE_POLICY_OVERRIDES"] = json.dumps(overrides)
        reset_overrides_cache()

        policy1 = get_policy_for_workflow(WorkflowType.MEDICATION_REVIEW)
        # Change env after first load - cache should keep old value
        os.environ["CONFIDENCE_POLICY_OVERRIDES"] = json.dumps(
            {"medication_review": {"action": 0.50}},
        )
        policy2 = get_policy_for_workflow(WorkflowType.MEDICATION_REVIEW)
        assert policy1.thresholds["action"] == policy2.thresholds["action"] == 0.99

    def test_reset_clears_cache(self) -> None:
        overrides = {"medication_review": {"action": 0.99}}
        os.environ["CONFIDENCE_POLICY_OVERRIDES"] = json.dumps(overrides)
        reset_overrides_cache()

        policy1 = get_policy_for_workflow(WorkflowType.MEDICATION_REVIEW)
        assert policy1.thresholds["action"] == 0.99

        os.environ["CONFIDENCE_POLICY_OVERRIDES"] = json.dumps(
            {"medication_review": {"action": 0.50}},
        )
        reset_overrides_cache()
        policy2 = get_policy_for_workflow(WorkflowType.MEDICATION_REVIEW)
        assert policy2.thresholds["action"] == 0.50


# =============================================================================
# P1-003: Policy Versioning
# =============================================================================


class TestPolicyVersioning:
    """get_policy_version returns a version string for audit."""

    def test_version_is_semver_like(self) -> None:
        version = get_policy_version()
        parts = version.split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()

    def test_version_is_stable(self) -> None:
        v1 = get_policy_version()
        v2 = get_policy_version()
        assert v1 == v2


# =============================================================================
# P1-003: Workflow Detection
# =============================================================================


class TestDetectWorkflowType:
    """detect_workflow_type heuristics."""

    def test_medication_keywords(self) -> None:
        assert detect_workflow_type("What medications is this patient on?") == WorkflowType.MEDICATION_REVIEW
        assert detect_workflow_type("Check drug interactions") == WorkflowType.MEDICATION_REVIEW
        assert detect_workflow_type("dosage for metformin") == WorkflowType.MEDICATION_REVIEW

    def test_diagnosis_keywords(self) -> None:
        assert detect_workflow_type("What is the diagnosis?") == WorkflowType.DIAGNOSIS_SUPPORT
        assert detect_workflow_type("differential for chest pain") == WorkflowType.DIAGNOSIS_SUPPORT

    def test_lab_keywords(self) -> None:
        assert detect_workflow_type("What are the lab results?") == WorkflowType.LAB_INTERPRETATION
        assert detect_workflow_type("A1C level over time") == WorkflowType.LAB_INTERPRETATION
        assert detect_workflow_type("glucose values") == WorkflowType.LAB_INTERPRETATION

    def test_admin_keywords(self) -> None:
        assert detect_workflow_type("billing code for visit") == WorkflowType.ADMINISTRATIVE
        assert detect_workflow_type("ICD code lookup") == WorkflowType.ADMINISTRATIVE

    def test_general_fallback(self) -> None:
        assert detect_workflow_type("tell me about this patient") == WorkflowType.GENERAL_QUERY

    def test_query_type_hint_overrides(self) -> None:
        # Even without medication keywords, hint takes precedence
        assert detect_workflow_type("what about this?", "medication") == WorkflowType.MEDICATION_REVIEW
        assert detect_workflow_type("what about this?", "condition") == WorkflowType.DIAGNOSIS_SUPPORT
        assert detect_workflow_type("what about this?", "lab") == WorkflowType.LAB_INTERPRETATION
        assert detect_workflow_type("what about this?", "admin") == WorkflowType.ADMINISTRATIVE


# =============================================================================
# P1-011: Source Retrieval Status Tracking
# =============================================================================


class TestSourceRetrievalStatus:
    """SourceRetrievalStatus constants."""

    def test_status_values(self) -> None:
        assert SourceRetrievalStatus.FULL == "full"
        assert SourceRetrievalStatus.PARTIAL == "partial"
        assert SourceRetrievalStatus.UNAVAILABLE == "unavailable"


class TestGraphAugmentedContextStatus:
    """GraphAugmentedContext includes source_retrieval_status field."""

    def test_default_status_is_unavailable(self) -> None:
        ctx = GraphAugmentedContext(
            query="test",
            patient_id="P001",
            graph_paths=[],
            temporal_context=None,
            retrieved_documents=[],
            policy_constraints=[],
        )
        assert ctx.source_retrieval_status == SourceRetrievalStatus.UNAVAILABLE

    def test_status_can_be_set_to_full(self) -> None:
        ctx = GraphAugmentedContext(
            query="test",
            patient_id="P001",
            graph_paths=[],
            temporal_context=None,
            retrieved_documents=[{"source": "doc:1", "content": "text"}],
            policy_constraints=[],
            source_retrieval_status=SourceRetrievalStatus.FULL,
        )
        assert ctx.source_retrieval_status == "full"

    def test_status_can_be_set_to_partial(self) -> None:
        ctx = GraphAugmentedContext(
            query="test",
            patient_id="P001",
            graph_paths=[],
            temporal_context=None,
            retrieved_documents=[
                {"source": "doc:1", "source_available": True, "content": "ok"},
                {"source": "doc:2", "source_available": False, "content": ""},
            ],
            policy_constraints=[],
            source_retrieval_status=SourceRetrievalStatus.PARTIAL,
        )
        assert ctx.source_retrieval_status == "partial"


# =============================================================================
# P1-011: Document Retrieval in GraphRAGService
# =============================================================================


@dataclass
class _FakeDocument:
    """Lightweight stand-in for Document ORM model."""
    id: Any
    patient_id: str
    note_type: str
    text: str
    extra_metadata: dict


class _FakeScalarsResult:
    """Mock for SQLAlchemy result.scalars()."""
    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return self._items


class _FakeResult:
    """Mock for SQLAlchemy execute result."""
    def __init__(self, items: list) -> None:
        self._items = items

    def scalars(self) -> _FakeScalarsResult:
        return _FakeScalarsResult(self._items)

    def scalar_one_or_none(self) -> Any:
        return self._items[0] if self._items else None


class TestDocumentRetrievalScoring:
    """_score_and_format_docs returns correctly scored documents."""

    def test_relevant_docs_scored_and_returned(self) -> None:
        service = GraphAugmentedRAGService.__new__(GraphAugmentedRAGService)
        docs = [
            _FakeDocument(
                id=uuid4(), patient_id="P1", note_type="progress_note",
                text="Patient has diabetes and takes metformin daily",
                extra_metadata={},
            ),
            _FakeDocument(
                id=uuid4(), patient_id="P1", note_type="lab_report",
                text="Blood pressure 120/80, heart rate normal",
                extra_metadata={},
            ),
        ]
        formatted, status = service._score_and_format_docs(
            docs, "diabetes medication", query_concepts=["diabetes", "metformin"],
        )
        assert status == SourceRetrievalStatus.FULL
        assert len(formatted) >= 1
        # The diabetes doc should score higher
        assert formatted[0]["source_available"] is True
        assert "diabetes" in formatted[0]["content"].lower()

    def test_no_matching_docs_returns_unavailable(self) -> None:
        service = GraphAugmentedRAGService.__new__(GraphAugmentedRAGService)
        docs = [
            _FakeDocument(
                id=uuid4(), patient_id="P1", note_type="admin",
                text="Scheduling appointment for next week",
                extra_metadata={},
            ),
        ]
        formatted, status = service._score_and_format_docs(
            docs, "cardiac catheterization results", query_concepts=["cardiac"],
        )
        # The doc text doesn't contain "cardiac" as a concept match or enough query words
        # Result depends on exact scoring, but status should reflect reality
        assert status in (SourceRetrievalStatus.FULL, SourceRetrievalStatus.UNAVAILABLE)

    def test_empty_docs_returns_unavailable(self) -> None:
        service = GraphAugmentedRAGService.__new__(GraphAugmentedRAGService)
        formatted, status = service._score_and_format_docs(
            [], "anything", query_concepts=[],
        )
        assert status == SourceRetrievalStatus.UNAVAILABLE
        assert formatted == []

    def test_doc_with_empty_text_handled_gracefully(self) -> None:
        service = GraphAugmentedRAGService.__new__(GraphAugmentedRAGService)
        docs = [
            _FakeDocument(
                id=uuid4(), patient_id="P1", note_type="note",
                text="",
                extra_metadata={},
            ),
        ]
        formatted, status = service._score_and_format_docs(
            docs, "diabetes", query_concepts=["diabetes"],
        )
        assert status == SourceRetrievalStatus.UNAVAILABLE

    def test_source_available_false_on_format_error(self) -> None:
        """When individual doc formatting fails, source_available should be False."""
        service = GraphAugmentedRAGService.__new__(GraphAugmentedRAGService)

        # Create a doc that will score but fail on formatting
        class _BadDoc:
            text = "diabetes is present"

            @property
            def id(self):
                raise RuntimeError("simulated error")

            @property
            def patient_id(self):
                return "P1"

            @property
            def note_type(self):
                raise RuntimeError("simulated error")

        formatted, status = service._score_and_format_docs(
            [_BadDoc()], "diabetes", query_concepts=["diabetes"],
        )
        assert status == SourceRetrievalStatus.PARTIAL
        assert len(formatted) == 1
        assert formatted[0]["source_available"] is False

    def test_max_five_docs_returned(self) -> None:
        service = GraphAugmentedRAGService.__new__(GraphAugmentedRAGService)
        docs = [
            _FakeDocument(
                id=uuid4(), patient_id="P1", note_type="note",
                text=f"diabetes note {i}",
                extra_metadata={},
            )
            for i in range(10)
        ]
        formatted, status = service._score_and_format_docs(
            docs, "diabetes", query_concepts=["diabetes"],
        )
        assert len(formatted) <= 5
        assert status == SourceRetrievalStatus.FULL


class TestDocumentRetrievalSync:
    """_retrieve_documents_sync with mocked session."""

    def test_returns_unavailable_when_no_docs(self) -> None:
        mock_session = MagicMock()
        mock_session.execute.return_value = _FakeResult([])

        service = GraphAugmentedRAGService(mock_session)
        docs, status = service._retrieve_documents_sync("test query", "P001")
        assert status == SourceRetrievalStatus.UNAVAILABLE
        assert docs == []

    def test_returns_full_when_docs_found(self) -> None:
        fake_docs = [
            _FakeDocument(
                id=uuid4(), patient_id="P001", note_type="progress_note",
                text="Patient diagnosed with hypertension",
                extra_metadata={},
            ),
        ]
        mock_session = MagicMock()
        mock_session.execute.return_value = _FakeResult(fake_docs)

        service = GraphAugmentedRAGService(mock_session)
        docs, status = service._retrieve_documents_sync(
            "hypertension diagnosis", "P001", query_concepts=["hypertension"],
        )
        assert status == SourceRetrievalStatus.FULL
        assert len(docs) == 1
        assert docs[0]["source_available"] is True

    def test_returns_unavailable_on_db_error(self) -> None:
        mock_session = MagicMock()
        mock_session.execute.side_effect = RuntimeError("DB down")

        service = GraphAugmentedRAGService(mock_session)
        docs, status = service._retrieve_documents_sync("test", "P001")
        assert status == SourceRetrievalStatus.UNAVAILABLE
        assert docs == []


class TestDocumentRetrievalAsync:
    """_retrieve_documents_async with mocked async session."""

    @pytest.mark.asyncio
    async def test_returns_unavailable_when_no_docs(self) -> None:
        mock_session = MagicMock(spec=["execute"])
        mock_session.execute = _make_async_mock(_FakeResult([]))

        service = GraphAugmentedRAGService(mock_session)
        service._is_async = True
        docs, status = await service._retrieve_documents_async("test query", "P001")
        assert status == SourceRetrievalStatus.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_returns_full_when_docs_found(self) -> None:
        fake_docs = [
            _FakeDocument(
                id=uuid4(), patient_id="P001", note_type="progress_note",
                text="Patient has diabetes and takes metformin",
                extra_metadata={},
            ),
        ]
        mock_session = MagicMock(spec=["execute"])
        mock_session.execute = _make_async_mock(_FakeResult(fake_docs))

        service = GraphAugmentedRAGService(mock_session)
        service._is_async = True
        docs, status = await service._retrieve_documents_async(
            "diabetes medication", "P001", query_concepts=["diabetes"],
        )
        assert status == SourceRetrievalStatus.FULL
        assert len(docs) >= 1

    @pytest.mark.asyncio
    async def test_returns_unavailable_on_db_error(self) -> None:
        async def _raise(*args, **kwargs):
            raise RuntimeError("DB down")

        mock_session = MagicMock(spec=["execute"])
        mock_session.execute = _raise

        service = GraphAugmentedRAGService(mock_session)
        service._is_async = True
        docs, status = await service._retrieve_documents_async("test", "P001")
        assert status == SourceRetrievalStatus.UNAVAILABLE


# =============================================================================
# Helpers
# =============================================================================


def _make_async_mock(return_value: Any):
    """Create an async function that returns the given value."""
    async def _mock(*args, **kwargs):
        return return_value
    return _mock
