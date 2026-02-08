"""SQLAlchemy model for persisted trial screening results.

Captures the outcome of automated or manual patient screening against
a clinical trial's eligibility criteria. Created by the Metriport
webhook pipeline after FHIR import completes, or by bulk/manual
screening actions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OverallScreeningStatus(str, Enum):
    """Overall screening outcome."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


class ScreeningTrigger(str, Enum):
    """What triggered this screening run."""

    WEBHOOK = "webhook"
    MANUAL = "manual"
    BULK = "bulk"


class ScreeningResult(Base):
    """Persisted outcome of screening a patient against a trial.

    Each row captures a single patient-trial screening event with the
    full criterion-level breakdown stored as JSON.
    """

    __tablename__ = "screening_results"

    patient_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    trial_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
    )
    trial_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    screening_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    overall_status: Mapped[OverallScreeningStatus] = mapped_column(
        SAEnum(
            OverallScreeningStatus,
            name="overall_screening_status",
            create_constraint=True,
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    match_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    inclusion_met: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    inclusion_total: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    exclusion_triggered: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    exclusion_total: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    criterion_results: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    safety_blocked: Mapped[bool | None] = mapped_column(
        nullable=True,
        default=False,
    )
    triggered_by: Mapped[ScreeningTrigger] = mapped_column(
        SAEnum(
            ScreeningTrigger,
            name="screening_trigger",
            create_constraint=True,
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ScreeningTrigger.MANUAL,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        Index("ix_screening_results_patient_trial", "patient_id", "trial_id"),
        Index("ix_screening_results_trial_status", "trial_id", "overall_status"),
        Index("ix_screening_results_date", "screening_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<ScreeningResult(id={self.id}, patient={self.patient_id}, "
            f"trial={self.trial_id}, status={self.overall_status})>"
        )
