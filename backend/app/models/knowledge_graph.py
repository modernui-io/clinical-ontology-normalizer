"""SQLAlchemy models for KGNode and KGEdge.

Includes temporal fields for bi-temporal knowledge graph queries:
- temporal_valid_from/to: When the relationship is valid in real world
- temporal_order: Allen's interval algebra relationship (BEFORE, DURING, AFTER, etc.)
- temporal_confidence: Confidence in the temporal assertions
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, CheckConstraint, DateTime, JSON, Enum, Float, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, SoftDeleteMixin
from app.schemas.knowledge_graph import EdgeType, NodeType


class KGNode(SoftDeleteMixin, Base):
    """Knowledge graph node representing an entity.

    VP-Compliance: Inherits SoftDeleteMixin for audit trail and data recovery.

    Nodes can be:
    - Patient nodes (central node for each patient, patient_id set)
    - Shared concept nodes (conditions, drugs, etc., patient_id=NULL, shared across patients)

    Shared concept nodes have patient_id=NULL and are deduplicated by
    (node_type, omop_concept_id). Patient-specific relationships are
    expressed through KGEdge which always carries patient_id.
    """

    __tablename__ = "kg_nodes"

    patient_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    # PHI Encryption: deterministic-encrypted patient_id for queryability
    patient_id_encrypted: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        index=True,
        doc="AES-SIV encrypted patient_id for HIPAA compliance",
    )
    node_type: Mapped[NodeType] = mapped_column(
        Enum(NodeType, name="node_type", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    omop_concept_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )
    label: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    properties: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    # Vector embedding for semantic search (384 dimensions for MiniLM)
    embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float),
        nullable=True,
    )

    # Relationships for edges
    outgoing_edges = relationship(
        "KGEdge",
        foreign_keys="KGEdge.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "KGEdge",
        foreign_keys="KGEdge.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<KGNode(id={self.id}, type={self.node_type}, label='{self.label}')>"

    # VP-Performance-1: Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_kg_nodes_patient_type", "patient_id", "node_type"),
        Index("ix_kg_nodes_patient_concept", "patient_id", "omop_concept_id"),
        Index("ix_kg_nodes_type_concept", "node_type", "omop_concept_id"),
        # Partial unique index for shared concept dedup
        Index(
            "ix_kg_nodes_global_concept",
            "node_type",
            "omop_concept_id",
            unique=True,
            postgresql_where=text(
                "patient_id IS NULL AND omop_concept_id IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
        # Index for querying shared nodes
        Index(
            "ix_kg_nodes_shared",
            "node_type",
            postgresql_where=text("patient_id IS NULL"),
        ),
        # Patient nodes must have patient_id
        CheckConstraint(
            "(node_type = 'patient' AND patient_id IS NOT NULL) OR (node_type != 'patient')",
            name="ck_patient_node_has_pid",
        ),
    )

    @property
    def is_patient_node(self) -> bool:
        """Check if this is a patient node."""
        return bool(self.node_type == NodeType.PATIENT)

    @property
    def is_shared_concept(self) -> bool:
        """Check if this is a shared concept node (patient_id is NULL)."""
        return self.patient_id is None


class KGEdge(SoftDeleteMixin, Base):
    """Knowledge graph edge representing a relationship.

    VP-Compliance: Inherits SoftDeleteMixin for audit trail and data recovery.

    Edges connect nodes with typed relationships:
    - has_condition: Patient → Condition
    - takes_drug: Patient → Drug
    - has_measurement: Patient → Measurement
    - condition_treated_by: Condition → Drug

    Temporal fields enable bi-temporal queries:
    - temporal_valid_from/to: When relationship is valid in real world
    - temporal_order: Allen's interval algebra relationship
    - temporal_confidence: Confidence in temporal assertions
    """

    __tablename__ = "kg_edges"

    patient_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    # PHI Encryption: deterministic-encrypted patient_id for queryability
    patient_id_encrypted: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        index=True,
        doc="AES-SIV encrypted patient_id for HIPAA compliance",
    )
    source_node_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("kg_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("kg_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edge_type: Mapped[EdgeType] = mapped_column(
        Enum(EdgeType, name="edge_type", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    fact_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("clinical_facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    properties: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # ==========================================================================
    # Bi-Temporal Fields
    # ==========================================================================
    # There are two temporal dimensions:
    #
    # 1. VALID TIME (Event Time): When the clinical event actually happened
    #    - event_date: Point in time when this happened (e.g., "diagnosed on 2023-03-15")
    #    - valid_from/valid_to: Period when this was true (e.g., "on medication from Jan-June 2023")
    #
    # 2. TRANSACTION TIME (Record Time): When we learned about it
    #    - recorded_at: When this was recorded in the source system
    #    - created_at: When this edge was created in our KG (inherited from Base)
    #    - source_document_date: Date of the source document
    #
    # 3. TEMPORAL ASSERTION: Conceptual time (from NLP extraction)
    #    - temporality: CURRENT, PAST, FUTURE (e.g., "history of diabetes" = PAST)
    # ==========================================================================

    # Valid Time: When the clinical event/relationship was true in the real world
    event_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="When this clinical event occurred (point in time)",
    )
    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="When this relationship became true (start of validity period)",
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="When this relationship ceased to be true (null = ongoing)",
    )

    # Transaction Time: When we learned about this / provenance
    recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When this was recorded in the source system",
    )
    source_document_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Date of the source document (e.g., note date, lab report date)",
    )

    # Temporal Assertion: Conceptual time from NLP
    temporality: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Temporal assertion: current, past, future (from NLP extraction)",
    )

    # Temporal Ordering: Allen's interval algebra relationship
    temporal_order: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Temporal ordering vs related events: before, after, during, concurrent",
    )

    # Confidence in temporal information
    temporal_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Confidence in temporal assertions (0-1)",
    )

    # Relationships
    source_node = relationship(
        "KGNode",
        foreign_keys=[source_node_id],
        back_populates="outgoing_edges",
    )
    target_node = relationship(
        "KGNode",
        foreign_keys=[target_node_id],
        back_populates="incoming_edges",
    )
    fact = relationship("ClinicalFact")

    # Indexes for temporal queries and VP-Performance-1: Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_kg_edges_valid_range", "valid_from", "valid_to"),
        Index("ix_kg_edges_patient_valid", "patient_id", "valid_from"),
        # event_date index already created by index=True on column definition
        # VP-Performance-1: Additional composite indexes for common query patterns
        Index("ix_kg_edges_patient_type", "patient_id", "edge_type"),
        Index("ix_kg_edges_source_type", "source_node_id", "edge_type"),
        Index("ix_kg_edges_target_type", "target_node_id", "edge_type"),
        Index("ix_kg_edges_source_patient", "source_node_id", "patient_id"),
    )

    def __repr__(self) -> str:
        return f"<KGEdge(id={self.id}, type={self.edge_type}, {self.source_node_id} → {self.target_node_id})>"

    @property
    def is_currently_valid(self) -> bool:
        """Check if this edge is currently valid (no end date or end date in future)."""
        if self.valid_to is None:
            return True
        return self.valid_to > datetime.now(timezone.utc)

    @property
    def has_temporal_bounds(self) -> bool:
        """Check if this edge has any temporal information."""
        return self.valid_from is not None or self.valid_to is not None or self.event_date is not None

    @property
    def is_historical(self) -> bool:
        """Check if this is a historical fact (in the past)."""
        return self.temporality == "past"

    @property
    def effective_date(self) -> datetime | None:
        """Get the most specific date for this edge (event_date or valid_from)."""
        return self.event_date or self.valid_from
