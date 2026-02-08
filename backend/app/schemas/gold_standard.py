"""Schemas for Gold Standard Dataset Management.

Provides structured types for managing curated gold standard datasets
used to evaluate NLP extraction, OMOP mapping, trial screening accuracy,
and assertion detection.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GoldStandardDomain(str, Enum):
    """Domain types for gold standard datasets."""

    NLP_EXTRACTION = "nlp_extraction"
    OMOP_MAPPING = "omop_mapping"
    TRIAL_SCREENING = "trial_screening"
    ASSERTION_DETECTION = "assertion_detection"


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------


class GoldStandardDataset(BaseModel):
    """A versioned gold standard dataset with annotations."""

    id: str = Field(..., description="Unique dataset identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Dataset name")
    domain: GoldStandardDomain = Field(..., description="Evaluation domain")
    description: str = Field(default="", description="Human-readable description")
    version: str = Field(
        default="1.0.0", min_length=1, max_length=64, description="Dataset version"
    )
    annotation_count: int = Field(default=0, description="Number of annotations")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )


class Annotation(BaseModel):
    """A single gold standard annotation pairing input with expected output."""

    id: str = Field(..., description="Unique annotation identifier")
    dataset_id: str = Field(..., description="Parent dataset identifier")
    input_data: dict[str, Any] = Field(
        ..., description="Input data (e.g., clinical text, term)"
    )
    expected_output: dict[str, Any] = Field(
        ..., description="Expected output (e.g., extracted mentions, concept IDs)"
    )
    annotator_id: str = Field(
        default="system", description="Identifier of the annotator"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional annotation metadata"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )


# ---------------------------------------------------------------------------
# Evaluation models
# ---------------------------------------------------------------------------


class Prediction(BaseModel):
    """A prediction to compare against a gold standard annotation."""

    annotation_id: str = Field(
        ..., description="ID of the gold standard annotation being evaluated"
    )
    predicted_output: dict[str, Any] = Field(
        ..., description="Predicted output to compare against expected"
    )


class PerClassMetric(BaseModel):
    """Precision, recall, and F1 for a single class."""

    class_name: str = Field(..., description="Class/category name")
    precision: float = Field(..., ge=0.0, le=1.0, description="Precision score")
    recall: float = Field(..., ge=0.0, le=1.0, description="Recall score")
    f1: float = Field(..., ge=0.0, le=1.0, description="F1 score")
    support: int = Field(..., ge=0, description="Number of samples in this class")


class EvaluationResult(BaseModel):
    """Result of evaluating predictions against a gold standard dataset."""

    dataset_id: str = Field(..., description="Dataset that was evaluated against")
    total: int = Field(..., ge=0, description="Total number of annotations evaluated")
    correct: int = Field(..., ge=0, description="Number of correct predictions")
    incorrect: int = Field(..., ge=0, description="Number of incorrect predictions")
    accuracy: float = Field(..., ge=0.0, le=1.0, description="Overall accuracy")
    per_class_metrics: list[PerClassMetric] = Field(
        default_factory=list, description="Per-class precision/recall/F1"
    )
    confusion_data: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Confusion matrix as {actual: {predicted: count}}",
    )


# ---------------------------------------------------------------------------
# Request / response schemas for the API layer
# ---------------------------------------------------------------------------


class CreateDatasetRequest(BaseModel):
    """Request body for creating a gold standard dataset."""

    name: str = Field(..., min_length=1, max_length=255, description="Dataset name")
    domain: GoldStandardDomain = Field(..., description="Evaluation domain")
    description: str = Field(default="", description="Human-readable description")
    version: str = Field(default="1.0.0", description="Dataset version")


class AddAnnotationRequest(BaseModel):
    """Request body for adding an annotation to a dataset."""

    input_data: dict[str, Any] = Field(..., description="Input data")
    expected_output: dict[str, Any] = Field(..., description="Expected output")
    annotator_id: str = Field(default="system", description="Annotator identifier")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class EvaluateRequest(BaseModel):
    """Request body for evaluating predictions against gold standard."""

    predictions: list[Prediction] = Field(
        ..., min_length=1, description="Predictions to evaluate"
    )


class DatasetListResponse(BaseModel):
    """Response for listing gold standard datasets."""

    total: int = Field(..., description="Total number of datasets")
    datasets: list[GoldStandardDataset] = Field(
        ..., description="List of datasets"
    )


class DatasetWithAnnotations(BaseModel):
    """A dataset together with all of its annotations."""

    dataset: GoldStandardDataset = Field(..., description="Dataset metadata")
    annotations: list[Annotation] = Field(
        default_factory=list, description="All annotations in the dataset"
    )


class InterAnnotatorAgreement(BaseModel):
    """Inter-annotator agreement metrics for a dataset."""

    dataset_id: str = Field(..., description="Dataset identifier")
    annotator_count: int = Field(..., description="Number of distinct annotators")
    annotators: list[str] = Field(..., description="List of annotator IDs")
    pairwise_agreement: float = Field(
        ..., ge=0.0, le=1.0, description="Average pairwise agreement rate"
    )
    cohens_kappa: float = Field(
        ..., description="Cohen's kappa (or Fleiss' kappa for >2 annotators)"
    )
