"""SQLAlchemy models for clinical trial sites/locations."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, SoftDeleteMixin


class Site(SoftDeleteMixin, Base):
    """Clinical trial site representing a physical location.

    VP-Compliance: Inherits SoftDeleteMixin for audit trail and data recovery.

    Sites are physical locations (hospitals, clinics) where patients are
    screened and enrolled in clinical trials. Each patient is assigned to
    exactly one site.
    """

    __tablename__ = "sites"

    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )
    site_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
    )
    organization: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    city: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default="US",
    )

    # Relationships
    patient_assignments = relationship(
        "PatientSiteAssignment",
        back_populates="site",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Site(id={self.id}, name='{self.name}', code={self.site_code})>"


class PatientSiteAssignment(Base):
    """Maps a patient to a site.

    A patient belongs to exactly one site. This is a separate table
    (rather than a column on KGNode) to keep the site concept decoupled
    from the knowledge graph.
    """

    __tablename__ = "patient_site_assignments"

    patient_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    site_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    site = relationship("Site", back_populates="patient_assignments")

    __table_args__ = (
        Index("ix_patient_site_unique", "patient_id", "site_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<PatientSiteAssignment(patient={self.patient_id}, site={self.site_id})>"
