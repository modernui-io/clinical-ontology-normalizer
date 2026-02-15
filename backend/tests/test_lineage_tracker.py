"""P2-022: Tests for structured data lineage tracker.

Tests cover:
- LineageStep schema validation
- DataLineage schema and properties
- LineageTracker accumulation of steps
- get_lineage() fact-based retrieval
- Step ordering and completeness checks
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from app.schemas.data_lineage import (
    DataLineage,
    LineageQueryResponse,
    LineageStep,
    PipelineStepName,
)
from app.services.lineage_tracker import (
    LineageTracker,
    clear_store,
    get_lineage,
    get_lineage_by_document,
)


@pytest.fixture(autouse=True)
def _clean_store():
    """Clear the in-memory lineage store before each test."""
    clear_store()
    yield
    clear_store()


# ===========================================================================
# 1. Schema Tests: LineageStep
# ===========================================================================


class TestLineageStepSchema:
    """Test LineageStep Pydantic schema."""

    def test_minimal_step(self) -> None:
        """LineageStep can be created with required fields."""
        step = LineageStep(
            step_name=PipelineStepName.INGESTION,
            input_type="raw_text",
            output_type="document",
            service_name="document_processing",
        )
        assert step.step_name == PipelineStepName.INGESTION
        assert step.version == "1.0.0"
        assert step.metadata == {}

    def test_step_with_all_fields(self) -> None:
        """LineageStep with all optional fields."""
        step = LineageStep(
            step_name=PipelineStepName.EXTRACTION,
            input_type="document",
            output_type="mentions",
            service_name="nlp_rule_based",
            version="2.1.0",
            metadata={"model": "biobert"},
            duration_ms=123.45,
            record_count=42,
        )
        assert step.version == "2.1.0"
        assert step.metadata["model"] == "biobert"
        assert step.duration_ms == 123.45
        assert step.record_count == 42

    def test_step_timestamp_auto_populated(self) -> None:
        """LineageStep timestamp is auto-populated if not set."""
        step = LineageStep(
            step_name=PipelineStepName.MAPPING,
            input_type="mentions",
            output_type="omop_concepts",
            service_name="clinical_ontology_mapper",
        )
        assert isinstance(step.timestamp, datetime)

    def test_invalid_step_name_rejected(self) -> None:
        """Invalid step name raises validation error."""
        with pytest.raises(Exception):
            LineageStep(
                step_name="invalid_step",
                input_type="a",
                output_type="b",
                service_name="svc",
            )


# ===========================================================================
# 2. Schema Tests: DataLineage
# ===========================================================================


class TestDataLineageSchema:
    """Test DataLineage Pydantic schema."""

    def test_minimal_lineage(self) -> None:
        """DataLineage with required fields only."""
        lineage = DataLineage(
            source_system="epic_ehr",
            source_id="doc-001",
        )
        assert lineage.source_system == "epic_ehr"
        assert lineage.steps == []
        assert lineage.is_complete is False

    def test_lineage_is_complete_property(self) -> None:
        """is_complete returns True when last step is QUERY."""
        lineage = DataLineage(
            source_system="test",
            source_id="id-1",
            steps=[
                LineageStep(
                    step_name=PipelineStepName.QUERY,
                    input_type="kg_query",
                    output_type="answer",
                    service_name="graph_rag",
                ),
            ],
        )
        assert lineage.is_complete is True

    def test_lineage_total_duration(self) -> None:
        """total_duration_ms sums all step durations."""
        lineage = DataLineage(
            source_system="test",
            source_id="id-1",
            steps=[
                LineageStep(
                    step_name=PipelineStepName.INGESTION,
                    input_type="a",
                    output_type="b",
                    service_name="svc",
                    duration_ms=100.0,
                ),
                LineageStep(
                    step_name=PipelineStepName.EXTRACTION,
                    input_type="b",
                    output_type="c",
                    service_name="svc",
                    duration_ms=200.0,
                ),
            ],
        )
        assert lineage.total_duration_ms == 300.0

    def test_lineage_step_names(self) -> None:
        """step_names returns ordered list of step name strings."""
        lineage = DataLineage(
            source_system="test",
            source_id="id-1",
            steps=[
                LineageStep(
                    step_name=PipelineStepName.INGESTION,
                    input_type="a",
                    output_type="b",
                    service_name="svc",
                ),
                LineageStep(
                    step_name=PipelineStepName.EXTRACTION,
                    input_type="b",
                    output_type="c",
                    service_name="svc",
                ),
            ],
        )
        assert lineage.step_names == ["ingestion", "extraction"]


# ===========================================================================
# 3. LineageTracker Tests
# ===========================================================================


class TestLineageTracker:
    """Test LineageTracker accumulation and lifecycle."""

    def test_tracker_adds_steps(self) -> None:
        """LineageTracker accumulates steps in order."""
        tracker = LineageTracker(source_system="ehr", source_id="d-1")
        tracker.add_step("ingestion", "doc_proc", "raw_text", "document")
        tracker.add_step("extraction", "nlp", "document", "mentions")

        lineage = tracker.get_lineage()
        assert tracker.step_count == 2
        assert lineage.steps[0].step_name == PipelineStepName.INGESTION
        assert lineage.steps[1].step_name == PipelineStepName.EXTRACTION

    def test_tracker_records_duration(self) -> None:
        """LineageTracker records duration when start_step() is called."""
        tracker = LineageTracker(source_system="ehr", source_id="d-2")
        tracker.start_step()
        time.sleep(0.01)  # 10ms
        step = tracker.add_step("ingestion", "svc", "a", "b")
        assert step.duration_ms is not None
        assert step.duration_ms > 0

    def test_tracker_no_duration_without_start(self) -> None:
        """Duration is None when start_step() was not called."""
        tracker = LineageTracker(source_system="ehr", source_id="d-3")
        step = tracker.add_step("ingestion", "svc", "a", "b")
        assert step.duration_ms is None

    def test_tracker_set_fact_id(self) -> None:
        """set_fact_id associates the lineage with a ClinicalFact."""
        tracker = LineageTracker(source_system="ehr", source_id="d-4")
        tracker.set_fact_id("fact-abc-123")
        assert tracker.get_lineage().fact_id == "fact-abc-123"

    def test_tracker_complete(self) -> None:
        """complete() marks the lineage as finished and stores it."""
        tracker = LineageTracker(source_system="ehr", source_id="d-5")
        tracker.add_step("ingestion", "svc", "a", "b")
        tracker.set_fact_id("fact-xyz")
        lineage = tracker.complete()

        assert tracker.is_complete is True
        assert lineage.completed_at is not None

    def test_tracker_stores_by_fact_id(self) -> None:
        """Completed lineage is retrievable by fact_id."""
        tracker = LineageTracker(source_system="ehr", source_id="d-6")
        tracker.add_step("ingestion", "svc", "a", "b")
        tracker.set_fact_id("fact-lookup-test")
        tracker.complete()

        result = get_lineage("fact-lookup-test")
        assert result is not None
        assert result.lineage.source_id == "d-6"

    def test_tracker_stores_by_document_id(self) -> None:
        """Completed lineage is retrievable by document_id."""
        tracker = LineageTracker(
            source_system="ehr",
            source_id="d-7",
            document_id="doc-lookup-test",
        )
        tracker.add_step("ingestion", "svc", "a", "b")
        tracker.complete()

        result = get_lineage_by_document("doc-lookup-test")
        assert result is not None
        assert result.lineage.source_id == "d-7"


# ===========================================================================
# 4. get_lineage() Tests
# ===========================================================================


class TestGetLineage:
    """Test get_lineage retrieval and warnings."""

    def test_get_lineage_returns_none_for_unknown(self) -> None:
        """get_lineage returns None when fact_id is not found."""
        result = get_lineage("nonexistent-fact")
        assert result is None

    def test_get_lineage_warns_on_incomplete(self) -> None:
        """get_lineage warns when the chain is incomplete."""
        tracker = LineageTracker(source_system="ehr", source_id="d-8")
        tracker.add_step("ingestion", "svc", "a", "b")
        tracker.set_fact_id("fact-incomplete")
        tracker.complete()

        result = get_lineage("fact-incomplete")
        assert result is not None
        assert any("incomplete" in w.lower() for w in result.warnings)

    def test_get_lineage_no_warnings_for_complete(self) -> None:
        """get_lineage has no ordering warnings when steps are in order."""
        tracker = LineageTracker(source_system="ehr", source_id="d-9")
        tracker.add_step("ingestion", "svc", "a", "b")
        tracker.add_step("extraction", "svc", "b", "c")
        tracker.add_step("mapping", "svc", "c", "d")
        tracker.add_step("fact_building", "svc", "d", "e")
        tracker.add_step("kg_build", "svc", "e", "f")
        tracker.add_step("query", "svc", "f", "g")
        tracker.set_fact_id("fact-complete")
        tracker.complete()

        result = get_lineage("fact-complete")
        assert result is not None
        assert result.lineage.is_complete is True
        # No ordering anomaly warnings expected
        ordering_warnings = [w for w in result.warnings if "ordering" in w.lower()]
        assert len(ordering_warnings) == 0


# ===========================================================================
# 5. PipelineStepName Enum Tests
# ===========================================================================


class TestPipelineStepNameEnum:
    """Test PipelineStepName enum values."""

    def test_all_expected_steps_exist(self) -> None:
        """All standard pipeline steps are defined."""
        expected = {"ingestion", "extraction", "mapping", "fact_building", "kg_build", "query"}
        actual = {s.value for s in PipelineStepName}
        assert actual == expected

    def test_step_names_are_strings(self) -> None:
        """PipelineStepName values are strings."""
        for step in PipelineStepName:
            assert isinstance(step.value, str)
