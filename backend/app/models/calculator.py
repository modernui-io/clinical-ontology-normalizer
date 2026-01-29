"""SQLAlchemy models for Custom Clinical Calculators.

Models for user-defined calculators that extend the built-in clinical calculators:
- CustomCalculator: Definition of a custom calculator
- CalculatorInput: Input parameter definition
- CalculatorResult: Result from executing a calculator
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InputType(str, Enum):
    """Type of calculator input."""

    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    SELECT = "select"  # Dropdown selection
    RADIO = "radio"  # Radio button options


class OutputType(str, Enum):
    """Type of calculator output."""

    NUMBER = "number"
    INTEGER = "integer"
    PERCENTAGE = "percentage"
    CATEGORY = "category"  # Risk level, classification, etc.
    SCORE = "score"


class CustomCalculator(Base):
    """User-defined clinical calculator.

    Allows users to create custom calculators with a formula DSL
    that supports safe arithmetic, conditional logic, and lookup tables.

    Example:
        BMI with categories:
        - formula: "weight / (height / 100) ^ 2"
        - Lookup table for classification

        Medication dosing:
        - formula: "if(egfr < 30, dose * 0.5, if(egfr < 60, dose * 0.75, dose))"
    """

    __tablename__ = "custom_calculators"

    # Basic information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Formula using safe DSL
    formula: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Output configuration
    output_type: Mapped[OutputType] = mapped_column(
        SQLEnum(OutputType, name="calculator_output_type", create_constraint=True,
                values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=OutputType.NUMBER,
    )
    output_unit: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Interpretation configuration (JSONB for lookup tables)
    # Format: [{"min": 0, "max": 18.5, "label": "Underweight", "risk_level": "moderate"}, ...]
    interpretation_rules: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Input definitions stored as JSONB array
    # Format: [{"name": "weight", "type": "number", "label": "Weight", "unit": "kg", ...}, ...]
    inputs: Mapped[list[dict]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    # Recommendations configuration (JSONB)
    # Format: {"underweight": ["Recommendation 1", ...], "normal": [...], ...}
    recommendations: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # References (citations, guidelines)
    references: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Metadata
    created_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Category/tags for organization
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    tags: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    results: Mapped[list["CalculatorResult"]] = relationship(
        back_populates="calculator",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<CustomCalculator(id={self.id}, name={self.name}, is_builtin={self.is_builtin})>"


class CalculatorResult(Base):
    """Result from executing a calculator.

    Stores the computed result along with inputs for audit trail
    and patient record keeping.
    """

    __tablename__ = "calculator_results"

    # Link to calculator
    calculator_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("custom_calculators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    calculator_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Patient context (optional)
    patient_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Input values used
    inputs: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    # Computed result
    result: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    result_unit: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Interpretation
    risk_level: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    interpretation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Recommendations generated
    recommendations: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Computed components (intermediate values)
    components: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Execution metadata
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    calculated_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    execution_time_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Relationships
    calculator: Mapped["CustomCalculator"] = relationship(
        back_populates="results",
    )

    def __repr__(self) -> str:
        return f"<CalculatorResult(id={self.id}, calculator={self.calculator_name}, result={self.result})>"
