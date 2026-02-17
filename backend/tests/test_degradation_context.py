"""Tests for Phase 1 Safety Envelope: DegradationContext and DegradationMetadata."""

from __future__ import annotations

import asyncio

import pytest

from app.core.degradation_context import DegradationContext
from app.schemas.degradation import DegradationMetadata


class TestDegradationMetadata:
    """Unit tests for DegradationMetadata schema."""

    def test_default_values(self):
        meta = DegradationMetadata()
        assert meta.degraded is False
        assert meta.degraded_components == []
        assert meta.fallback_used is False
        assert meta.warnings == []
        assert meta.trace_id is None

    def test_degraded_state(self):
        meta = DegradationMetadata(
            degraded=True,
            degraded_components=["neo4j_sync"],
            fallback_used=True,
            warnings=["neo4j_sync: ConnectionError: connection refused"],
            trace_id="req-abc123",
        )
        assert meta.degraded is True
        assert "neo4j_sync" in meta.degraded_components
        assert meta.fallback_used is True
        assert len(meta.warnings) == 1

    def test_serialization_round_trip(self):
        meta = DegradationMetadata(
            degraded=True,
            degraded_components=["guideline_rag", "neo4j_sync"],
            fallback_used=True,
            warnings=["guideline_rag: FileNotFoundError: fixture missing"],
        )
        data = meta.model_dump()
        restored = DegradationMetadata(**data)
        assert restored == meta

    def test_json_serialization(self):
        meta = DegradationMetadata(degraded=True, degraded_components=["test"])
        json_str = meta.model_dump_json()
        assert '"degraded":true' in json_str or '"degraded": true' in json_str


class TestDegradationContext:
    """Unit tests for DegradationContext ContextVar accumulator."""

    def setup_method(self):
        DegradationContext.reset()

    def test_initial_snapshot_clean(self):
        snapshot = DegradationContext.snapshot()
        assert snapshot.degraded is False
        assert snapshot.degraded_components == []
        assert snapshot.fallback_used is False
        assert snapshot.warnings == []

    def test_record_single_failure(self):
        error = ValueError("test error")
        DegradationContext.record_stage_failure("test_component", error, None)

        snapshot = DegradationContext.snapshot()
        assert snapshot.degraded is True
        assert snapshot.degraded_components == ["test_component"]
        assert snapshot.fallback_used is True
        assert len(snapshot.warnings) == 1
        assert "test_component" in snapshot.warnings[0]
        assert "ValueError" in snapshot.warnings[0]

    def test_accumulate_multiple_failures(self):
        DegradationContext.record_stage_failure("comp_a", ValueError("err1"), [])
        DegradationContext.record_stage_failure("comp_b", RuntimeError("err2"), {})
        DegradationContext.record_stage_failure("comp_c", ConnectionError("err3"), None)

        snapshot = DegradationContext.snapshot()
        assert snapshot.degraded is True
        assert len(snapshot.degraded_components) == 3
        assert snapshot.degraded_components == ["comp_a", "comp_b", "comp_c"]
        assert len(snapshot.warnings) == 3

    def test_reset_clears_state(self):
        DegradationContext.record_stage_failure("comp", ValueError("err"), None)
        assert DegradationContext.snapshot().degraded is True

        DegradationContext.reset()
        snapshot = DegradationContext.snapshot()
        assert snapshot.degraded is False
        assert snapshot.degraded_components == []

    def test_snapshot_is_copy(self):
        """Snapshot returns copies, not references to mutable ContextVar lists."""
        DegradationContext.record_stage_failure("comp", ValueError("err"), None)
        snap1 = DegradationContext.snapshot()

        # Mutating the snapshot should not affect the context
        snap1.degraded_components.append("injected")

        snap2 = DegradationContext.snapshot()
        assert "injected" not in snap2.degraded_components

    def test_contextvar_isolation(self):
        """Different asyncio tasks should have isolated degradation state."""
        results = {}

        async def task_a():
            DegradationContext.reset()
            DegradationContext.record_stage_failure("task_a_comp", ValueError("a"), None)
            await asyncio.sleep(0.01)
            results["a"] = DegradationContext.snapshot()

        async def task_b():
            DegradationContext.reset()
            await asyncio.sleep(0.01)
            results["b"] = DegradationContext.snapshot()

        async def run():
            await asyncio.gather(task_a(), task_b())

        asyncio.run(run())

        assert results["a"].degraded is True
        assert results["a"].degraded_components == ["task_a_comp"]
        assert results["b"].degraded is False
        assert results["b"].degraded_components == []
