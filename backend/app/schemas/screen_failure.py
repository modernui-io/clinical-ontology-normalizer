"""Pydantic schemas for Screen Failure Analytics (VP-Product-3).

Tracks and reports on why patients fail trial screening to help sites
optimise recruitment strategies.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ScreeningOutcome(str, Enum):
    """Possible outcomes of a patient screening."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    PENDING = "pending"
    ERROR = "error"


class CriterionType(str, Enum):
    """High-level category for a screening criterion."""

    CONDITION = "condition"
    MEASUREMENT = "measurement"
    DEMOGRAPHIC = "demographic"
    DRUG = "drug"
    PROCEDURE = "procedure"
    OBSERVATION = "observation"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Core record
# ---------------------------------------------------------------------------

class FailingCriterion(BaseModel):
    """A single criterion that a patient failed."""

    criterion_name: str = Field(..., description="Human-readable name of the failing criterion")
    criterion_type: CriterionType = Field(
        default=CriterionType.OTHER,
        description="Category of the criterion (condition/measurement/demographic/...)",
    )
    details: str | None = Field(None, description="Optional explanation of why it failed")


class ScreeningRecord(BaseModel):
    """Record of a single patient screening outcome."""

    id: str = Field(..., description="Unique record identifier")
    trial_id: str = Field(..., description="Trial that was screened against")
    patient_id: str = Field(..., description="Patient who was screened")
    outcome: ScreeningOutcome = Field(..., description="Screening outcome")
    failing_criteria: list[FailingCriterion] = Field(
        default_factory=list,
        description="Criteria the patient failed (empty for eligible patients)",
    )
    match_score: float | None = Field(None, ge=0.0, le=1.0, description="Overall match score")
    timestamp: datetime = Field(..., description="When the screening occurred")
    metadata: dict | None = Field(None, description="Arbitrary extra metadata")


# ---------------------------------------------------------------------------
# Analytics report
# ---------------------------------------------------------------------------

class TopFailingCriterion(BaseModel):
    """A criterion ranked by how many patients it rejects."""

    criterion_name: str
    criterion_type: CriterionType
    failure_count: int = Field(ge=0)
    failure_rate: float = Field(ge=0.0, le=1.0, description="Fraction of screened patients failing this criterion")


class FailureByType(BaseModel):
    """Failure distribution grouped by criterion type."""

    criterion_type: CriterionType
    failure_count: int = Field(ge=0)
    percentage: float = Field(ge=0.0, le=100.0, description="Percentage of total failures")


class DailyTrend(BaseModel):
    """Failure rate for a single day or week."""

    date: str = Field(..., description="ISO date string (YYYY-MM-DD)")
    screened: int = Field(ge=0)
    failed: int = Field(ge=0)
    failure_rate: float = Field(ge=0.0, le=1.0)


class FailureAnalyticsReport(BaseModel):
    """Aggregated screen-failure analytics for a trial."""

    trial_id: str
    date_from: datetime | None = None
    date_to: datetime | None = None
    total_screened: int = Field(ge=0)
    total_eligible: int = Field(ge=0)
    total_ineligible: int = Field(ge=0)
    total_pending: int = Field(ge=0)
    total_error: int = Field(ge=0)
    failure_rate: float = Field(ge=0.0, le=1.0, description="Ineligible / total screened")
    top_failing_criteria: list[TopFailingCriterion] = Field(default_factory=list)
    failure_by_type: list[FailureByType] = Field(default_factory=list)
    daily_trend: list[DailyTrend] = Field(default_factory=list)
    near_miss_count: int = Field(
        ge=0,
        default=0,
        description="Patients failing by exactly 1 criterion",
    )


# ---------------------------------------------------------------------------
# Recruitment funnel
# ---------------------------------------------------------------------------

class FunnelStage(BaseModel):
    """A single stage of the recruitment funnel."""

    name: str = Field(..., description="Stage name")
    count: int = Field(ge=0)
    conversion_rate: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Fraction converting from previous stage (None for first stage)",
    )


class RecruitmentFunnel(BaseModel):
    """End-to-end recruitment funnel for a trial."""

    trial_id: str
    stages: list[FunnelStage] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Criteria difficulty
# ---------------------------------------------------------------------------

class CriteriaDifficulty(BaseModel):
    """Per-criterion pass rate indicating how hard each criterion is."""

    criterion_name: str
    criterion_type: CriterionType
    pass_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0, default=0)
    pass_rate: float = Field(ge=0.0, le=1.0, description="pass_count / (pass_count + fail_count)")


class CriteriaDifficultyReport(BaseModel):
    """All criteria difficulty scores for a trial."""

    trial_id: str
    criteria: list[CriteriaDifficulty] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Near-miss patients
# ---------------------------------------------------------------------------

class NearMissPatient(BaseModel):
    """A patient who almost qualified -- failed by 1-2 criteria."""

    patient_id: str
    failing_criteria: list[FailingCriterion] = Field(
        default_factory=list,
        description="The 1-2 criteria that blocked eligibility",
    )
    match_score: float | None = Field(None, ge=0.0, le=1.0)
    num_failing: int = Field(ge=1, description="Number of failing criteria")


class NearMissReport(BaseModel):
    """Near-miss patients for a trial."""

    trial_id: str
    max_failures: int = Field(ge=1, description="Maximum failing criteria to qualify as near miss")
    patients: list[NearMissPatient] = Field(default_factory=list)
    total: int = Field(ge=0, default=0)
