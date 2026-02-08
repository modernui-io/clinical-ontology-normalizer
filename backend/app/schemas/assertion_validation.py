"""Schemas for assertion validation framework.

Provides Pydantic models for golden dataset test cases, validation results,
per-category and per-difficulty metrics, disagreement records, and the
overall validation report.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AssertionExpected(str, Enum):
    """Expected assertion values used in the golden dataset.

    Maps to ``app.schemas.base.Assertion`` but includes all categories the
    validation framework needs to distinguish.
    """

    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    POSSIBLE = "POSSIBLE"
    HYPOTHETICAL = "HYPOTHETICAL"
    FAMILY_HISTORY = "FAMILY_HISTORY"
    CONDITIONAL = "CONDITIONAL"


class TestCaseCategory(str, Enum):
    """Category tags for golden dataset test cases."""

    NEGATION = "negation"
    FAMILY_HISTORY = "family_history"
    HYPOTHETICAL = "hypothetical"
    UNCERTAINTY = "uncertainty"
    DOUBLE_NEGATION = "double_negation"
    SECTION_CONTEXT = "section_context"
    TEMPORAL = "temporal"


class TestCaseDifficulty(str, Enum):
    """Difficulty ratings for golden dataset test cases."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AssertionTestCase(BaseModel):
    """A single test case from the golden assertion dataset."""

    id: int = Field(..., description="Unique identifier for the test case")
    text: str = Field(..., description="Clinical sentence or paragraph")
    mention_text: str = Field(..., description="The specific mention span")
    mention_start: int = Field(..., ge=0, description="Character offset of the mention start")
    expected_assertion: AssertionExpected = Field(
        ..., description="Expected assertion classification"
    )
    category: TestCaseCategory = Field(
        ..., description="Category tag for the test case"
    )
    difficulty: TestCaseDifficulty = Field(
        ..., description="Difficulty rating"
    )


class AssertionSingleResult(BaseModel):
    """Result of assertion classification for a single mention."""

    predicted_assertion: str = Field(
        ..., description="Predicted assertion value"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Classification confidence"
    )
    trigger_text: str | None = Field(
        None, description="Trigger pattern that matched"
    )
    trigger_distance: int | None = Field(
        None, description="Token distance from trigger to mention"
    )


class CategoryMetrics(BaseModel):
    """Accuracy, precision, recall, and F1 for a single category."""

    category: str = Field(..., description="Category name")
    total: int = Field(..., ge=0, description="Total test cases in this category")
    correct: int = Field(..., ge=0, description="Correctly classified count")
    accuracy: float = Field(..., ge=0.0, le=1.0, description="Accuracy")
    precision: float = Field(
        ..., ge=0.0, le=1.0, description="Precision (positive predictive value)"
    )
    recall: float = Field(
        ..., ge=0.0, le=1.0, description="Recall (sensitivity)")
    f1: float = Field(..., ge=0.0, le=1.0, description="F1 score")


class DifficultyMetrics(BaseModel):
    """Accuracy metrics grouped by difficulty level."""

    difficulty: str = Field(..., description="Difficulty level")
    total: int = Field(..., ge=0, description="Total test cases at this difficulty")
    correct: int = Field(..., ge=0, description="Correctly classified count")
    accuracy: float = Field(..., ge=0.0, le=1.0, description="Accuracy")


class DisagreementRecord(BaseModel):
    """A test case where predicted and expected assertions disagree."""

    test_case: AssertionTestCase = Field(
        ..., description="The original test case"
    )
    predicted_assertion: str = Field(
        ..., description="What the classifier predicted"
    )
    expected_assertion: str = Field(
        ..., description="What was expected"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Classifier confidence"
    )
    trigger_text: str | None = Field(
        None, description="Trigger that fired (if any)"
    )


class AssertionValidationReport(BaseModel):
    """Comprehensive validation report comparing classifier vs golden dataset."""

    total_cases: int = Field(..., ge=0, description="Total test cases evaluated")
    overall_correct: int = Field(..., ge=0, description="Total correct predictions")
    overall_accuracy: float = Field(
        ..., ge=0.0, le=1.0, description="Overall accuracy"
    )
    category_metrics: list[CategoryMetrics] = Field(
        default_factory=list, description="Per-category metrics"
    )
    difficulty_metrics: list[DifficultyMetrics] = Field(
        default_factory=list, description="Per-difficulty metrics"
    )
    disagreements: list[DisagreementRecord] = Field(
        default_factory=list, description="Cases where classifier disagreed"
    )
    assertion_accuracy: dict[str, float] = Field(
        default_factory=dict,
        description="Accuracy per expected assertion type",
    )
