"""SQLAlchemy models for institutional policy management.

Provides storage for institutional policies, their sections,
and linkage to alert rules for automated compliance checking.

Models:
- Policy: Institutional policy document with versioning
- PolicySection: Individual sections with embeddings for RAG search
- PolicyAlertRule: Links policy sections to clinical alert rules
"""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PolicyStatus(str, Enum):
    """Status lifecycle for policies."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class Policy(Base):
    """Institutional policy document with versioning.

    Stores the full policy text, metadata, and status for lifecycle management.
    Content is hashed for integrity verification and deduplication.
    """

    __tablename__ = "policies"

    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    source_organization: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    effective_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    uploaded_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        index=True,
    )
    content_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
    )
    file_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        default=None,
    )

    # Relationships
    sections = relationship(
        "PolicySection",
        back_populates="policy",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_policies_status_name", "status", "name"),
    )

    def __repr__(self) -> str:
        return f"<Policy(id={self.id}, name='{self.name}', version='{self.version}', status='{self.status}')>"


class PolicySection(Base):
    """Individual section of a policy document.

    Each section is independently searchable via embedding-based RAG.
    Sections are tagged with conditions and measurements they apply to.
    """

    __tablename__ = "policy_sections"

    policy_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    content_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    applies_to_conditions: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    applies_to_measurements: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    keywords: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float),
        nullable=True,
    )

    # Relationships
    policy = relationship("Policy", back_populates="sections")
    alert_rule_mappings = relationship(
        "PolicyAlertRule",
        back_populates="policy_section",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_policy_sections_policy", "policy_id"),
    )

    def __repr__(self) -> str:
        return f"<PolicySection(id={self.id}, policy_id={self.policy_id}, title='{self.title}')>"


class PolicyAlertRule(Base):
    """Links policy sections to clinical alert rules.

    Tracks which alert rules are derived from or supported by
    specific policy sections, with confidence scores.
    """

    __tablename__ = "policy_alert_rules"

    policy_section_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("policy_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_rule_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    mapping_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    mapping_rationale: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    policy_section = relationship("PolicySection", back_populates="alert_rule_mappings")

    __table_args__ = (
        Index("ix_policy_alert_rules_section_rule", "policy_section_id", "alert_rule_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<PolicyAlertRule(id={self.id}, section={self.policy_section_id}, "
            f"rule={self.alert_rule_id}, confidence={self.mapping_confidence})>"
        )
