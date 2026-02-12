"""Pydantic schemas for Safety Signal Detection (Pharmacovigilance).

Manages safety signal detection operations: signal identification from multiple
sources (spontaneous reports, clinical trials, literature, registries, real-world
data), disproportionality analysis (PRR, ROR, BCPNN, MGPS, EBGM), signal
evaluation with causality assessment, lifecycle management (new -> under_evaluation
-> confirmed/refuted -> closed), and signal detection metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SignalStatus(str, Enum):
    """Lifecycle status of a safety signal."""

    NEW = "new"
    UNDER_EVALUATION = "under_evaluation"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    CLOSED = "closed"


class SignalSource(str, Enum):
    """Source from which a safety signal was detected."""

    SPONTANEOUS_REPORTS = "spontaneous_reports"
    CLINICAL_TRIAL = "clinical_trial"
    LITERATURE = "literature"
    REGISTRY = "registry"
    REAL_WORLD_DATA = "real_world_data"


class SignalPriority(str, Enum):
    """Priority classification for a safety signal."""

    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DisproportionalityMethod(str, Enum):
    """Statistical method used for disproportionality analysis."""

    PRR = "prr"
    ROR = "ror"
    BCPNN = "bcpnn"
    MGPS = "mgps"
    EBGM = "ebgm"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class SafetySignal(BaseModel):
    """A detected safety signal requiring pharmacovigilance evaluation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique signal identifier")
    signal_number: str = Field(..., description="Human-readable signal reference number")
    title: str = Field(..., description="Short descriptive title for the signal")
    description: str = Field(..., description="Detailed description of the safety signal")
    status: SignalStatus = Field(
        default=SignalStatus.NEW, description="Current lifecycle status"
    )
    priority: SignalPriority = Field(..., description="Priority classification")
    source: SignalSource = Field(..., description="Detection source")
    detected_date: datetime = Field(..., description="Date the signal was first detected")
    evaluation_start_date: datetime | None = Field(
        None, description="Date evaluation began"
    )
    confirmed_date: datetime | None = Field(
        None, description="Date the signal was confirmed"
    )
    closed_date: datetime | None = Field(None, description="Date the signal was closed")
    drug_name: str = Field(..., description="Name of the drug associated with the signal")
    trial_ids: list[str] = Field(
        default_factory=list,
        description="Clinical trial identifiers linked to this signal",
    )
    preferred_term: str = Field(
        ..., description="MedDRA preferred term for the adverse event"
    )
    soc: str = Field(..., description="MedDRA System Organ Class")
    observed_count: int = Field(
        ge=0, description="Observed number of adverse event reports"
    )
    expected_count: float = Field(
        ge=0.0, description="Expected number of reports based on background rate"
    )
    disproportionality_score: float = Field(
        ge=0.0,
        description="Computed disproportionality score (e.g., PRR, ROR, EBGM value)",
    )
    method_used: DisproportionalityMethod = Field(
        ..., description="Statistical method used for disproportionality analysis"
    )
    reporter: str = Field(
        ..., description="Person or system that reported / detected the signal"
    )
    assigned_evaluator: str | None = Field(
        None, description="Evaluator assigned to assess the signal"
    )
    regulatory_impact: str | None = Field(
        None,
        description="Assessment of potential regulatory impact (e.g., label change, REMS)",
    )
    action_taken: str | None = Field(
        None,
        description="Action taken in response to the signal (e.g., study paused, SUSAR filed)",
    )


class SignalEvaluation(BaseModel):
    """An evaluation record for a safety signal."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique evaluation identifier")
    signal_id: str = Field(..., description="Associated signal identifier")
    evaluator: str = Field(..., description="Name of the evaluator")
    evaluation_date: datetime = Field(..., description="Date of the evaluation")
    conclusion: str = Field(..., description="Evaluation conclusion summary")
    supporting_evidence: str = Field(
        ..., description="Evidence supporting the conclusion"
    )
    recommendation: str = Field(
        ..., description="Recommended next steps or actions"
    )
    causality_assessment: str = Field(
        ...,
        description="Causality assessment (e.g., certain, probable, possible, unlikely, unrelated)",
    )


class SignalMetrics(BaseModel):
    """Aggregated safety signal detection metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_signals: int = Field(ge=0, description="Total number of signals")
    signals_by_status: dict[str, int] = Field(
        default_factory=dict, description="Signal counts by lifecycle status"
    )
    signals_by_priority: dict[str, int] = Field(
        default_factory=dict, description="Signal counts by priority level"
    )
    signals_by_source: dict[str, int] = Field(
        default_factory=dict, description="Signal counts by detection source"
    )
    avg_disproportionality_score: float = Field(
        ge=0.0, description="Average disproportionality score across all signals"
    )
    total_evaluations: int = Field(ge=0, description="Total evaluation records")
    confirmed_signals: int = Field(ge=0, description="Number of confirmed signals")
    refuted_signals: int = Field(ge=0, description="Number of refuted signals")
    open_signals: int = Field(
        ge=0,
        description="Number of signals in new or under_evaluation status",
    )
    urgent_signals: int = Field(ge=0, description="Number of urgent priority signals")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SignalCreate(BaseModel):
    """Request to create a new safety signal."""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., description="Signal title")
    description: str = Field(..., description="Detailed description")
    priority: SignalPriority = Field(..., description="Priority classification")
    source: SignalSource = Field(..., description="Detection source")
    drug_name: str = Field(..., description="Drug name")
    trial_ids: list[str] = Field(
        default_factory=list, description="Linked trial identifiers"
    )
    preferred_term: str = Field(..., description="MedDRA preferred term")
    soc: str = Field(..., description="MedDRA System Organ Class")
    observed_count: int = Field(ge=0, description="Observed report count")
    expected_count: float = Field(ge=0.0, description="Expected report count")
    disproportionality_score: float = Field(
        ge=0.0, description="Disproportionality score"
    )
    method_used: DisproportionalityMethod = Field(
        ..., description="Statistical method used"
    )
    reporter: str = Field(..., description="Reporter name or system")
    assigned_evaluator: str | None = Field(None, description="Assigned evaluator")


class SignalUpdate(BaseModel):
    """Request to update an existing safety signal."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(None, description="Signal title")
    description: str | None = Field(None, description="Detailed description")
    priority: SignalPriority | None = Field(None, description="Priority classification")
    drug_name: str | None = Field(None, description="Drug name")
    trial_ids: list[str] | None = Field(None, description="Linked trial identifiers")
    preferred_term: str | None = Field(None, description="MedDRA preferred term")
    soc: str | None = Field(None, description="MedDRA System Organ Class")
    observed_count: int | None = Field(None, ge=0, description="Observed report count")
    expected_count: float | None = Field(
        None, ge=0.0, description="Expected report count"
    )
    disproportionality_score: float | None = Field(
        None, ge=0.0, description="Disproportionality score"
    )
    method_used: DisproportionalityMethod | None = Field(
        None, description="Statistical method used"
    )
    assigned_evaluator: str | None = Field(None, description="Assigned evaluator")
    regulatory_impact: str | None = Field(None, description="Regulatory impact assessment")
    action_taken: str | None = Field(None, description="Action taken")


class SignalEvaluationCreate(BaseModel):
    """Request to create an evaluation for a safety signal."""

    model_config = ConfigDict(from_attributes=True)

    evaluator: str = Field(..., description="Evaluator name")
    conclusion: str = Field(..., description="Evaluation conclusion")
    supporting_evidence: str = Field(..., description="Supporting evidence")
    recommendation: str = Field(..., description="Recommended next steps")
    causality_assessment: str = Field(..., description="Causality assessment")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SignalListResponse(BaseModel):
    """List of safety signals."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SafetySignal] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SignalEvaluationListResponse(BaseModel):
    """List of signal evaluations."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SignalEvaluation] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
