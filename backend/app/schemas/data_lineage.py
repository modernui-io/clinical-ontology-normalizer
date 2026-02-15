"""Structured data lineage schemas for end-to-end pipeline tracking.

P2-022: Adds structured lineage fields tracking data from source system
through ingestion, extraction, mapping, fact building, KG build, and query.

These schemas complement the existing lineage.py schemas (CDO-1) by adding
fine-grained pipeline step tracking, not just source-level provenance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PipelineStepName(str, Enum):
    """Standard pipeline steps in the clinical data flow."""

    INGESTION = "ingestion"
    EXTRACTION = "extraction"
    MAPPING = "mapping"
    FACT_BUILDING = "fact_building"
    KG_BUILD = "kg_build"
    QUERY = "query"


class LineageStep(BaseModel):
    """A single step in the data lineage chain.

    Records what happened at one stage of the pipeline, including
    which service performed the work and what types flowed in/out.
    """

    step_name: PipelineStepName = Field(
        ..., description="Standard pipeline step identifier"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this step was executed",
    )
    input_type: str = Field(
        ..., description="Type/format of the input data (e.g., 'raw_text', 'mentions', 'omop_concepts')"
    )
    output_type: str = Field(
        ..., description="Type/format of the output data (e.g., 'mentions', 'clinical_facts', 'kg_nodes')"
    )
    service_name: str = Field(
        ..., description="Fully qualified service name that executed this step"
    )
    version: str = Field(
        default="1.0.0",
        description="Version of the service/algorithm used",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Step-specific metadata (e.g., model name, config params)",
    )
    duration_ms: float | None = Field(
        None,
        ge=0,
        description="Execution duration in milliseconds",
    )
    record_count: int | None = Field(
        None,
        ge=0,
        description="Number of records processed in this step",
    )


class DataLineage(BaseModel):
    """Full lineage chain from source system to final answer.

    Captures the complete provenance of a piece of data as it flows
    through the clinical normalizer pipeline.
    """

    steps: list[LineageStep] = Field(
        default_factory=list,
        description="Ordered list of pipeline steps applied to this data",
    )
    source_system: str = Field(
        ..., description="Originating system identifier (e.g., 'epic_ehr', 'cerner', 'fhir_server')"
    )
    source_id: str = Field(
        ..., description="Identifier of the source record in the source system"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this lineage chain was created",
    )
    completed_at: datetime | None = Field(
        None,
        description="When the full pipeline completed for this data",
    )
    patient_id: str | None = Field(
        None,
        description="Patient identifier this lineage chain belongs to",
    )
    document_id: str | None = Field(
        None,
        description="Source document ID if applicable",
    )
    fact_id: str | None = Field(
        None,
        description="Resulting ClinicalFact ID if applicable",
    )

    @property
    def is_complete(self) -> bool:
        """Whether the lineage chain has reached the final step."""
        if not self.steps:
            return False
        return self.steps[-1].step_name == PipelineStepName.QUERY

    @property
    def total_duration_ms(self) -> float | None:
        """Total pipeline duration across all steps with recorded durations."""
        durations = [s.duration_ms for s in self.steps if s.duration_ms is not None]
        return sum(durations) if durations else None

    @property
    def step_names(self) -> list[str]:
        """Ordered list of step names in this lineage chain."""
        return [s.step_name.value for s in self.steps]


class LineageQueryResponse(BaseModel):
    """Response when querying lineage for a fact or document."""

    lineage: DataLineage
    warnings: list[str] = Field(
        default_factory=list,
        description="Any warnings about incomplete or anomalous lineage",
    )
