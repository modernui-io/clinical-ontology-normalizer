"""SQLAlchemy models for provenance tracking and reasoning traces.

Provides full traceability from clinical answers back to source documents,
extraction methods, and reasoning steps used to generate them.

Models:
- ProvenanceRecord: Links extracted entities to their source documents and methods
- ReasoningTrace: Records each step of the hybrid query reasoning pipeline
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExtractionMethodDB(str, Enum):
    """Methods used to extract clinical entities."""

    NLP_RULE_BASED = "nlp_rule_based"
    NLP_LLM = "nlp_llm"
    NLP_ENSEMBLE = "nlp_ensemble"
    MANUAL = "manual"
    FHIR_IMPORT = "fhir_import"
    CSV_IMPORT = "csv_import"
    HL7_IMPORT = "hl7_import"


class ConfidenceLevelDB(str, Enum):
    """Qualitative confidence levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class ReasoningStepType(str, Enum):
    """Types of reasoning steps in the hybrid query pipeline."""

    KG_RETRIEVAL = "kg_retrieval"
    GRAPH_RAG_RETRIEVAL = "graph_rag_retrieval"  # Multi-hop graph traversal
    RAG_SEARCH = "rag_search"
    ORCHESTRATOR_CONSENSUS = "orchestrator_consensus"  # Multi-agent MDT deliberation
    LLM_INFERENCE = "llm_inference"
    GUIDELINE_MATCH = "guideline_match"
    POLICY_CHECK = "policy_check"


class ProvenanceRecord(Base):
    """Tracks the origin and extraction details of clinical entities.

    Links KG nodes, clinical facts, and other entities back to their
    source documents, extraction methods, and confidence assessments.
    """

    __tablename__ = "provenance_records"

    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    extraction_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    confidence_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
    )
    confidence_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    source_document_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        index=True,
    )
    source_section: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    source_span_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    source_span_end: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    extraction_model: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    extraction_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    verified_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        default=None,
    )

    __table_args__ = (
        Index("ix_provenance_entity", "entity_type", "entity_id"),
        Index("ix_provenance_patient_entity", "patient_id", "entity_type"),
        Index("ix_provenance_source_doc", "source_document_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProvenanceRecord(id={self.id}, entity_type={self.entity_type}, "
            f"entity_id={self.entity_id}, method={self.extraction_method})>"
        )


class ReasoningTrace(Base):
    """Records each step of the hybrid query reasoning pipeline.

    Tracks KG retrieval, RAG search, LLM inference, guideline matching,
    and policy checking steps with timing, confidence, and metadata.
    """

    __tablename__ = "reasoning_traces"

    query_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    step_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    input_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    output_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    confidence_contribution: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        default=None,
    )

    __table_args__ = (
        Index("ix_reasoning_query_step", "query_id", "step_order"),
        Index("ix_reasoning_patient", "patient_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ReasoningTrace(id={self.id}, query_id={self.query_id}, "
            f"step={self.step_order}, type={self.step_type})>"
        )
