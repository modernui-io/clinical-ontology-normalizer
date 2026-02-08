"""SQLAlchemy models for Clinical Trial management.

Supports clinical trial definition, patient eligibility tracking,
and enrollment management for the trial recruitment workflow.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, SoftDeleteMixin


class TrialPhase(str, Enum):
    """Clinical trial phase."""

    PHASE_1 = "phase_1"
    PHASE_1_2 = "phase_1_2"
    PHASE_2 = "phase_2"
    PHASE_2_3 = "phase_2_3"
    PHASE_3 = "phase_3"
    PHASE_3_4 = "phase_3_4"
    PHASE_4 = "phase_4"
    NOT_APPLICABLE = "not_applicable"


class TrialStatus(str, Enum):
    """Clinical trial recruitment status."""

    DRAFT = "draft"
    RECRUITING = "recruiting"
    ACTIVE_NOT_RECRUITING = "active_not_recruiting"
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    WITHDRAWN = "withdrawn"


class EnrollmentStatus(str, Enum):
    """Patient enrollment status within a trial."""

    CANDIDATE = "candidate"
    SCREENED = "screened"
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    ENROLLED = "enrolled"
    ACTIVE = "active"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"
    SCREEN_FAILED = "screen_failed"


class Trial(SoftDeleteMixin, Base):
    """A clinical trial with eligibility criteria and enrollment tracking.

    Eligibility criteria are modeled as a cohort definition (JSON) using
    the same criterion types as the CohortService: demographics, conditions,
    drugs, procedures, measurements, and visits with boolean logic.
    """

    __tablename__ = "trials"

    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    nct_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
        index=True,
    )
    protocol_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    sponsor: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    phase: Mapped[TrialPhase] = mapped_column(
        SAEnum(TrialPhase, name="trial_phase", create_constraint=True, create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TrialPhase.PHASE_3,
    )
    status: Mapped[TrialStatus] = mapped_column(
        SAEnum(TrialStatus, name="trial_status", create_constraint=True, create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TrialStatus.DRAFT,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    therapeutic_area: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    indication_codes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    inclusion_criteria: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    exclusion_criteria: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    enrollment_target: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
    )
    site_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    enrollments = relationship(
        "TrialEnrollment",
        back_populates="trial",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_trials_sponsor", "sponsor"),
        Index("ix_trials_phase_status", "phase", "status"),
        Index("ix_trials_therapeutic_area", "therapeutic_area"),
    )

    def __repr__(self) -> str:
        return f"<Trial(id={self.id}, name={self.name}, nct={self.nct_number}, status={self.status})>"

    @property
    def enrolled_count(self) -> int:
        """Count of currently enrolled patients (requires loaded relationship)."""
        if not self.enrollments:
            return 0
        return sum(
            1 for e in self.enrollments
            if e.enrollment_status in (EnrollmentStatus.ENROLLED, EnrollmentStatus.ACTIVE)
        )

    @property
    def enrollment_progress(self) -> float:
        """Percentage of enrollment target met."""
        if self.enrollment_target <= 0:
            return 0.0
        return min(100.0, (self.enrolled_count / self.enrollment_target) * 100)


class TrialEnrollment(Base):
    """Tracks a patient's enrollment status in a clinical trial.

    Records the full lifecycle from candidate identification through
    screening, eligibility determination, and enrollment.
    """

    __tablename__ = "trial_enrollments"

    trial_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("trials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    enrollment_status: Mapped[EnrollmentStatus] = mapped_column(
        SAEnum(EnrollmentStatus, name="enrollment_status", create_constraint=True, create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=EnrollmentStatus.CANDIDATE,
        index=True,
    )
    match_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    criteria_met: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    criteria_failed: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    screening_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    enrollment_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    withdrawal_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    withdrawal_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    site_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    trial = relationship("Trial", back_populates="enrollments")

    __table_args__ = (
        Index("ix_trial_enrollments_trial_patient", "trial_id", "patient_id", unique=True),
        Index("ix_trial_enrollments_trial_status", "trial_id", "enrollment_status"),
        Index("ix_trial_enrollments_patient_status", "patient_id", "enrollment_status"),
    )

    def __repr__(self) -> str:
        return f"<TrialEnrollment(trial={self.trial_id}, patient={self.patient_id}, status={self.enrollment_status})>"
