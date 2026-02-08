"""Pydantic schemas for Clinical Validation Study Design.

CMO-1.4: Clinical Validation Study Design

A validation study compares the system's automated screening results against
a gold-standard clinical review (board-certified physician) to measure
screening accuracy.  This is critical for regulatory compliance and for
establishing confidence in the system's screening pipeline.

Key metrics:
- Sensitivity (true positive rate): system says eligible, gold standard agrees
- Specificity (true negative rate): system says ineligible, gold standard agrees
- PPV: of those system says eligible, % actually eligible
- NPV: of those system says ineligible, % actually ineligible
- Cohen's Kappa: inter-rater agreement beyond chance
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ScreeningResult(str, enum.Enum):
    """Possible screening outcomes."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"


class StudyStatus(str, enum.Enum):
    """Lifecycle status of a validation study."""

    DESIGN = "DESIGN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"


class StudyMethodology(str, enum.Enum):
    """Study design methodology."""

    RETROSPECTIVE_CHART_REVIEW = "RETROSPECTIVE_CHART_REVIEW"
    PROSPECTIVE_PARALLEL = "PROSPECTIVE_PARALLEL"
    CROSS_SECTIONAL = "CROSS_SECTIONAL"


# ==============================================================================
# Core schemas
# ==============================================================================


class ValidationStudyCreate(BaseModel):
    """Request body for creating a new validation study."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Human-readable study name",
    )
    description: str = Field(
        "",
        max_length=5000,
        description="Detailed study description and objectives",
    )
    trial_id: str = Field(
        ...,
        min_length=1,
        description="ID of the clinical trial being validated",
    )
    sample_size: int = Field(
        ...,
        gt=0,
        description="Target sample size (number of cases to review)",
    )
    methodology: StudyMethodology = Field(
        default=StudyMethodology.RETROSPECTIVE_CHART_REVIEW,
        description="Study design methodology",
    )


class ValidationStudy(BaseModel):
    """A clinical validation study record."""

    id: str = Field(description="Unique study identifier")
    name: str
    description: str = ""
    trial_id: str
    sample_size: int
    methodology: StudyMethodology
    status: StudyStatus = StudyStatus.DESIGN
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    case_count: int = Field(
        default=0,
        description="Number of cases added so far",
    )


class StudyCaseCreate(BaseModel):
    """Request body for adding a case to a validation study."""

    patient_id: str = Field(..., min_length=1)
    system_result: ScreeningResult = Field(
        ...,
        description="The system's screening determination",
    )
    gold_standard_result: ScreeningResult = Field(
        ...,
        description="The gold-standard clinical reviewer's determination",
    )
    reviewer_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the board-certified physician reviewer",
    )
    notes: str = Field(
        "",
        max_length=5000,
        description="Optional reviewer notes",
    )


class StudyCase(BaseModel):
    """A single case in a validation study."""

    id: str
    study_id: str
    patient_id: str
    system_result: ScreeningResult
    gold_standard_result: ScreeningResult
    reviewer_id: str
    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    notes: str = ""


# ==============================================================================
# Metrics schemas
# ==============================================================================


class ConfusionMatrix(BaseModel):
    """2x2 confusion matrix for binary classification."""

    true_positive: int = Field(
        ge=0,
        description="System=ELIGIBLE, Gold=ELIGIBLE (correct positive)",
    )
    true_negative: int = Field(
        ge=0,
        description="System=INELIGIBLE, Gold=INELIGIBLE (correct negative)",
    )
    false_positive: int = Field(
        ge=0,
        description="System=ELIGIBLE, Gold=INELIGIBLE (type I error)",
    )
    false_negative: int = Field(
        ge=0,
        description="System=INELIGIBLE, Gold=ELIGIBLE (type II error -- worst for screening)",
    )

    @property
    def total(self) -> int:
        return self.true_positive + self.true_negative + self.false_positive + self.false_negative


class ConfidenceInterval(BaseModel):
    """95% confidence interval for a metric."""

    lower: float
    upper: float
    confidence_level: float = 0.95


class ValidationMetrics(BaseModel):
    """Full set of validation metrics computed from study cases."""

    sensitivity: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="True positive rate: TP / (TP + FN). Most critical for screening.",
    )
    specificity: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="True negative rate: TN / (TN + FP)",
    )
    ppv: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Positive predictive value: TP / (TP + FP)",
    )
    npv: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Negative predictive value: TN / (TN + FN)",
    )
    accuracy: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Overall accuracy: (TP + TN) / total",
    )
    f1_score: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Harmonic mean of precision (PPV) and recall (sensitivity)",
    )
    cohens_kappa: float | None = Field(
        None,
        ge=-1.0,
        le=1.0,
        description="Cohen's Kappa: inter-rater agreement beyond chance. "
        "1.0 = perfect, 0 = chance, <0 = worse than chance",
    )
    confusion_matrix: ConfusionMatrix
    total_cases: int = Field(ge=0)
    sensitivity_ci: ConfidenceInterval | None = None
    specificity_ci: ConfidenceInterval | None = None


# ==============================================================================
# Report schema
# ==============================================================================


class StudyReport(BaseModel):
    """Full validation study report with metrics and study metadata."""

    study: ValidationStudy
    metrics: ValidationMetrics | None = Field(
        None,
        description="None if no cases have been added yet",
    )
    sample_size_achieved: int = Field(
        ge=0,
        description="Actual number of cases reviewed",
    )
    completion_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="sample_size_achieved / target sample_size",
    )
    meets_sensitivity_target: bool | None = Field(
        None,
        description="True if sensitivity >= 0.95 (clinical target)",
    )
    meets_specificity_target: bool | None = Field(
        None,
        description="True if specificity >= 0.85 (clinical target)",
    )
