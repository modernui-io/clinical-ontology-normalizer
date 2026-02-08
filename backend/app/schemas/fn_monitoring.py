"""Pydantic schemas for False Negative monitoring in clinical trial screening.

CMO-6: False Negative Monitoring

A false negative occurs when a patient IS eligible for a clinical trial but
the screening system says they are NOT eligible.  This is worse than a false
positive because the patient misses a potentially life-saving trial.

This module defines the data contracts for:
- Recording screening outcomes
- Flagging potential false negatives (clinician review)
- Aggregated FN reports per trial
- Unknown-criteria analysis (data completeness gaps)
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class FNFlagCreate(BaseModel):
    """Request body for flagging a potential false negative."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description=(
            "Why the clinician believes this patient should have been "
            "flagged as eligible. E.g., 'Patient has confirmed AD diagnosis "
            "in external records not yet imported.'"
        ),
    )
    flagged_by: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Identifier of the clinician who flagged the false negative",
    )


class FNFlag(BaseModel):
    """A recorded false-negative flag from a clinician."""

    trial_id: str
    patient_id: str
    reason: str
    flagged_by: str
    flagged_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MissReason(BaseModel):
    """A reason that appears in FN flags, with its occurrence count."""

    reason: str
    count: int


class UnknownCriteriaAnalysis(BaseModel):
    """Analysis of a single criterion that evaluates to UNKNOWN frequently.

    Criteria that are UNKNOWN most often indicate data completeness gaps --
    the system cannot evaluate a criterion because the patient's record
    lacks data in the relevant clinical domain.
    """

    criterion_description: str = Field(
        description="Human-readable name/description of the criterion",
    )
    unknown_count: int = Field(
        ge=0,
        description="Number of screenings where this criterion evaluated to UNKNOWN",
    )
    total_evaluations: int = Field(
        ge=0,
        description="Total number of times this criterion was evaluated",
    )
    unknown_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of evaluations resulting in UNKNOWN (0.0 to 1.0)",
    )


class FNReport(BaseModel):
    """Aggregated false-negative monitoring report for a trial.

    Provides visibility into screening quality and potential missed matches.
    """

    trial_id: str
    total_screened: int = Field(
        ge=0,
        description="Total unique patients screened for this trial",
    )
    total_flagged: int = Field(
        ge=0,
        description="Total unique patients flagged as potential false negatives",
    )
    fn_rate: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "False negative rate = flagged_fn / total_screened. "
            "A rate above 0.05 (5%) warrants investigation."
        ),
    )
    top_miss_reasons: list[MissReason] = Field(
        default_factory=list,
        description="Most common reasons given when flagging false negatives, ordered by frequency",
    )
    unknown_criteria_gaps: list[UnknownCriteriaAnalysis] = Field(
        default_factory=list,
        description=(
            "Criteria that evaluate to UNKNOWN most often, indicating "
            "data completeness gaps. Ordered by unknown_rate descending."
        ),
    )
