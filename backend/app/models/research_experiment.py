"""SQLAlchemy models for research experiment tracking."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    pass


class ExperimentStatus(str, enum.Enum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class ExperimentRunStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MetricCategory(str, enum.Enum):
    NLP = "nlp"
    MAPPING = "mapping"
    ASSERTION = "assertion"
    KG = "kg"
    RAG = "rag"
    TIMING = "timing"


class ResearchExperiment(Base):
    """A research experiment for the NeurIPS paper."""

    __tablename__ = "research_experiments"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(ExperimentStatus, name="experiment_status", create_type=False,
             values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        server_default="draft",
    )
    summary_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    runs: Mapped[list[ResearchExperimentRun]] = relationship(
        "ResearchExperimentRun", back_populates="experiment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_research_experiments_status", "status"),
        Index("ix_research_experiments_created_by", "created_by"),
    )


class ResearchExperimentRun(Base):
    """A single run within an experiment (e.g., one MIMIC batch import + processing)."""

    __tablename__ = "research_experiment_runs"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("research_experiments.id", ondelete="CASCADE"), nullable=False
    )
    mimic_batch_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    run_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    document_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    patient_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    status: Mapped[ExperimentRunStatus] = mapped_column(
        Enum(ExperimentRunStatus, name="experiment_run_status", create_type=False,
             values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        server_default="pending",
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    experiment: Mapped[ResearchExperiment] = relationship(
        "ResearchExperiment", back_populates="runs"
    )
    metrics: Mapped[list[ResearchExperimentMetric]] = relationship(
        "ResearchExperimentMetric", back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_research_runs_experiment_id", "experiment_id"),
        Index("ix_research_runs_status", "status"),
    )


class ResearchExperimentMetric(Base):
    """A single metric recorded for an experiment run."""

    __tablename__ = "research_experiment_metrics"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("research_experiment_runs.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[MetricCategory] = mapped_column(
        Enum(MetricCategory, name="metric_category", create_type=False,
             values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped[ResearchExperimentRun] = relationship(
        "ResearchExperimentRun", back_populates="metrics"
    )

    __table_args__ = (
        Index("ix_research_metrics_run_id", "run_id"),
        Index("ix_research_metrics_category", "category"),
        Index("ix_research_metrics_run_category", "run_id", "category"),
    )
