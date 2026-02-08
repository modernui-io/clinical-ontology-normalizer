"""SQLAlchemy models for extracted clinical values."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum as SAEnum
from sqlalchemy import BigInteger, ForeignKey, Integer, String, Float, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.vocabulary import Concept


class ValueType(str, Enum):
    """Type of clinical value."""

    LAB_RESULT = "lab_result"
    VITAL_SIGN = "vital_sign"
    MEDICATION_DOSE = "medication_dose"
    MEASUREMENT = "measurement"
    SCORE = "score"


class ClinicalValue(Base):
    """Extracted clinical value with numeric data.

    Represents quantitative clinical data extracted from notes:
    - Lab results: HbA1c 7.2%, Creatinine 1.8 mg/dL
    - Vital signs: BP 145/92, HR 88, Temp 101.2F
    - Medication doses: Metformin 1000mg BID
    - Measurements: EF 35%, BMI 32
    """

    __tablename__ = "clinical_values"

    # Source document
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Patient for easy querying
    patient_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # Value type
    value_type: Mapped[ValueType] = mapped_column(
        SAEnum(ValueType, name="value_type", create_constraint=True, create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )

    # The extracted text span
    text: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # Position in document
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)

    # The name/label of what was measured
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # Numeric value (primary)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Secondary value for ranges (e.g., BP systolic/diastolic)
    value_secondary: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Unit of measurement
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Normalized unit (standard form)
    unit_normalized: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # For medications: frequency
    frequency: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # For medications: route
    route: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Linked OMOP concept (for the measurement type)
    omop_concept_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )

    # Interpretation (normal, high, low, critical)
    interpretation: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Reference range if available
    reference_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_high: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Section where found
    section: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Extraction confidence
    confidence: Mapped[float] = mapped_column(Float, default=0.8)

    # Additional metadata
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
    )

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="clinical_values")

    def __repr__(self) -> str:
        return f"<ClinicalValue({self.name}={self.value} {self.unit})>"

    @property
    def display_value(self) -> str:
        """Human-readable value string."""
        if self.value is None:
            return self.text

        if self.value_secondary is not None:
            # Range value like BP
            return f"{int(self.value)}/{int(self.value_secondary)}"

        # Format based on value magnitude
        if self.value == int(self.value):
            val_str = str(int(self.value))
        else:
            val_str = f"{self.value:.2f}".rstrip('0').rstrip('.')

        if self.unit:
            return f"{val_str} {self.unit}"
        return val_str

    @property
    def is_abnormal(self) -> bool:
        """Check if value is outside reference range."""
        if self.value is None:
            return False
        if self.reference_low is not None and self.value < self.reference_low:
            return True
        if self.reference_high is not None and self.value > self.reference_high:
            return True
        return False
