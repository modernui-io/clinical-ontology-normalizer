"""SQLAlchemy models for Document and StructuredResource."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class TSVECTOR(TypeDecorator):
    """TSVECTOR type that falls back to Text on non-PostgreSQL backends (e.g. SQLite in tests)."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_TSVECTOR())
        return dialect.type_descriptor(Text())
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, SoftDeleteMixin
from app.schemas.base import ConsentStatus, JobStatus, ResourceType

if TYPE_CHECKING:
    from app.models.clinical_value import ClinicalValue
    from app.models.mention import Mention


class Document(SoftDeleteMixin, Base):
    """Clinical document containing unstructured text.

    VP-Compliance: Inherits SoftDeleteMixin for audit trail and data recovery.

    Represents a clinical note (progress note, discharge summary, etc.)
    that will be processed through the NLP pipeline to extract mentions.

    Multi-tenancy: owner_id links to the user who uploaded the document.
    When auth is enabled, queries are scoped to the owner. Admins see all.
    """

    __tablename__ = "documents"

    patient_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="User who uploaded this document (for multi-tenancy scoping)",
    )
    note_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # PHI Encryption: encrypted version of document text
    text_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Fernet-encrypted document text for HIPAA compliance",
    )
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",  # Column name in database
        JSONB,
        nullable=False,
        default=dict,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=JobStatus.QUEUED,
        index=True,
    )
    job_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # P1-027: Residency and consent metadata
    residency_country: Mapped[str | None] = mapped_column(
        String(2),  # ISO 3166-1 alpha-2
        nullable=True,
        doc="ISO 3166-1 alpha-2 country code for patient residency (e.g. AU)",
    )
    consent_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        doc="Consent status: obtained | pending | declined | not_required",
    )
    consent_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Date consent was obtained or last updated",
    )
    consent_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="URI or ID linking to the external consent record",
    )

    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
    )

    @property
    def text_decrypted(self) -> str:
        """Get decrypted text, falling back to plaintext if not encrypted."""
        if self.text_encrypted:
            try:
                from app.core.phi_encryption import decrypt_phi
                return decrypt_phi(self.text_encrypted)
            except Exception:
                pass
        return self.text

    # Relationships
    clinical_values: Mapped[list["ClinicalValue"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    mentions: Mapped[list["Mention"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, patient_id={self.patient_id}, note_type={self.note_type}, status={self.status})>"


class StructuredResource(SoftDeleteMixin, Base):
    """Structured clinical resource (FHIR bundle, CSV data).

    VP-Compliance: Inherits SoftDeleteMixin for audit trail and data recovery.

    Represents structured clinical data that will be processed
    to extract clinical facts directly without NLP.
    """

    __tablename__ = "structured_resources"

    patient_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[ResourceType] = mapped_column(
        Enum(ResourceType, name="resource_type", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",  # Column name in database
        JSONB,
        nullable=False,
        default=dict,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=JobStatus.QUEUED,
        index=True,
    )
    job_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<StructuredResource(id={self.id}, patient_id={self.patient_id}, resource_type={self.resource_type}, status={self.status})>"
