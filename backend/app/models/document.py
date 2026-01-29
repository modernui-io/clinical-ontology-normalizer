"""SQLAlchemy models for Document and StructuredResource."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, SoftDeleteMixin
from app.schemas.base import JobStatus, ResourceType

if TYPE_CHECKING:
    from app.models.clinical_value import ClinicalValue


class Document(SoftDeleteMixin, Base):
    """Clinical document containing unstructured text.

    VP-Compliance: Inherits SoftDeleteMixin for audit trail and data recovery.

    Represents a clinical note (progress note, discharge summary, etc.)
    that will be processed through the NLP pipeline to extract mentions.
    """

    __tablename__ = "documents"

    patient_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    note_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(
        Text,
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

    # Relationships
    clinical_values: Mapped[list["ClinicalValue"]] = relationship(
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
