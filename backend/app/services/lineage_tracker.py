"""Pipeline lineage tracker service.

P2-022: Tracks structured data lineage end-to-end as data flows through
the clinical normalizer pipeline (ingestion -> extraction -> mapping ->
fact_building -> kg_build -> query).

Usage:
    tracker = LineageTracker(source_system="epic_ehr", source_id="doc-123")
    tracker.add_step("ingestion", "document_processing", "raw_text", "document")
    tracker.add_step("extraction", "nlp_rule_based", "document", "mentions")
    ...
    lineage = tracker.get_lineage()
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.schemas.data_lineage import (
    DataLineage,
    LineageQueryResponse,
    LineageStep,
    PipelineStepName,
)

logger = logging.getLogger(__name__)

# In-memory lineage store keyed by (source_system, source_id) or fact_id.
# In production this would be backed by the database; this provides a
# lightweight in-process tracker for pipeline runs.
_lineage_store: dict[str, DataLineage] = {}


class LineageTracker:
    """Accumulates pipeline steps as data flows through the system.

    Each tracker instance corresponds to one piece of data (document,
    fact, etc.) moving through the pipeline. Steps are appended in order.

    Args:
        source_system: Identifier for the originating system.
        source_id: Identifier for the source record.
        patient_id: Optional patient identifier.
        document_id: Optional document identifier.
    """

    def __init__(
        self,
        source_system: str,
        source_id: str,
        *,
        patient_id: str | None = None,
        document_id: str | None = None,
    ) -> None:
        self._lineage = DataLineage(
            source_system=source_system,
            source_id=source_id,
            patient_id=patient_id,
            document_id=document_id,
        )
        self._step_start_time: float | None = None

    def start_step(self) -> None:
        """Mark the start of a step for duration tracking."""
        self._step_start_time = time.monotonic()

    def add_step(
        self,
        step_name: str | PipelineStepName,
        service_name: str,
        input_type: str,
        output_type: str,
        *,
        version: str = "1.0.0",
        metadata: dict[str, Any] | None = None,
        record_count: int | None = None,
    ) -> LineageStep:
        """Add a completed pipeline step to the lineage chain.

        Args:
            step_name: Pipeline step (must be a valid PipelineStepName).
            service_name: Name of the service that executed the step.
            input_type: Type/format of the input data.
            output_type: Type/format of the output data.
            version: Version of the service/algorithm.
            metadata: Optional step-specific metadata.
            record_count: Optional count of records processed.

        Returns:
            The created LineageStep.
        """
        if isinstance(step_name, str):
            step_name = PipelineStepName(step_name)

        duration_ms = None
        if self._step_start_time is not None:
            duration_ms = (time.monotonic() - self._step_start_time) * 1000
            self._step_start_time = None

        step = LineageStep(
            step_name=step_name,
            input_type=input_type,
            output_type=output_type,
            service_name=service_name,
            version=version,
            metadata=metadata or {},
            duration_ms=duration_ms,
            record_count=record_count,
        )

        self._lineage.steps.append(step)

        logger.debug(
            "Lineage step added: %s via %s (%s -> %s)",
            step_name.value,
            service_name,
            input_type,
            output_type,
        )

        return step

    def set_fact_id(self, fact_id: str) -> None:
        """Associate the lineage chain with a resulting ClinicalFact."""
        self._lineage.fact_id = fact_id

    def complete(self) -> DataLineage:
        """Mark the lineage chain as complete and store it.

        Returns:
            The completed DataLineage.
        """
        from datetime import datetime, timezone

        self._lineage.completed_at = datetime.now(timezone.utc)

        # Store by multiple keys for lookup flexibility
        key = f"{self._lineage.source_system}:{self._lineage.source_id}"
        _lineage_store[key] = self._lineage

        if self._lineage.fact_id:
            _lineage_store[f"fact:{self._lineage.fact_id}"] = self._lineage

        if self._lineage.document_id:
            _lineage_store[f"doc:{self._lineage.document_id}"] = self._lineage

        logger.info(
            "Lineage complete: %s -> %d steps, duration=%s ms",
            key,
            len(self._lineage.steps),
            self._lineage.total_duration_ms,
        )

        return self._lineage

    def get_lineage(self) -> DataLineage:
        """Get the current state of the lineage chain.

        Returns:
            The DataLineage (may be incomplete if pipeline is still running).
        """
        return self._lineage

    @property
    def step_count(self) -> int:
        """Number of steps recorded so far."""
        return len(self._lineage.steps)

    @property
    def is_complete(self) -> bool:
        """Whether the lineage chain has been marked complete."""
        return self._lineage.completed_at is not None


def get_lineage(fact_id: str) -> LineageQueryResponse | None:
    """Retrieve the full lineage chain for a ClinicalFact.

    Args:
        fact_id: The ClinicalFact identifier.

    Returns:
        LineageQueryResponse with the lineage chain and any warnings,
        or None if no lineage is found.
    """
    key = f"fact:{fact_id}"
    lineage = _lineage_store.get(key)

    if lineage is None:
        return None

    warnings: list[str] = []

    # Check for completeness
    if not lineage.is_complete:
        warnings.append(
            f"Lineage chain is incomplete: reached {lineage.steps[-1].step_name.value if lineage.steps else 'no steps'}"
        )

    # Check for expected step ordering
    expected_order = [
        PipelineStepName.INGESTION,
        PipelineStepName.EXTRACTION,
        PipelineStepName.MAPPING,
        PipelineStepName.FACT_BUILDING,
        PipelineStepName.KG_BUILD,
        PipelineStepName.QUERY,
    ]
    actual_steps = [s.step_name for s in lineage.steps]
    for i, step in enumerate(actual_steps):
        if step in expected_order:
            expected_idx = expected_order.index(step)
            if i > 0 and actual_steps[i - 1] in expected_order:
                prev_expected_idx = expected_order.index(actual_steps[i - 1])
                if expected_idx < prev_expected_idx:
                    warnings.append(
                        f"Step ordering anomaly: {step.value} appears after {actual_steps[i-1].value}"
                    )

    return LineageQueryResponse(lineage=lineage, warnings=warnings)


def get_lineage_by_document(document_id: str) -> LineageQueryResponse | None:
    """Retrieve lineage chain for a document.

    Args:
        document_id: The document identifier.

    Returns:
        LineageQueryResponse or None.
    """
    key = f"doc:{document_id}"
    lineage = _lineage_store.get(key)

    if lineage is None:
        return None

    return LineageQueryResponse(lineage=lineage, warnings=[])


def clear_store() -> None:
    """Clear the in-memory lineage store (for testing)."""
    _lineage_store.clear()
