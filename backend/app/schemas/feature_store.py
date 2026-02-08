"""Schemas for Feature Store Service.

Provides structured types for managing ML features used in
clinical trial patient screening pipelines.  Includes feature
definitions, computation results, statistics, importance tracking,
and versioning metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class FeatureDataType(str, Enum):
    """Data type of a feature value."""

    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    TEXT = "text"
    TIMESTAMP = "timestamp"


class FeatureDomain(str, Enum):
    """Clinical domain a feature belongs to."""

    CONDITION = "condition"
    MEDICATION = "medication"
    LAB = "lab"
    DEMOGRAPHIC = "demographic"
    PROCEDURE = "procedure"
    OBSERVATION = "observation"
    SCREENING = "screening"
    ENGAGEMENT = "engagement"
    GEOGRAPHIC = "geographic"
    INSURANCE = "insurance"
    COMORBIDITY = "comorbidity"


class TrendDirection(str, Enum):
    """Direction of a lab value trend."""

    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


class MissingReason(str, Enum):
    """Reason a feature value is missing."""

    NO_DATA = "no_data"
    INSUFFICIENT_HISTORY = "insufficient_history"
    COMPUTATION_ERROR = "computation_error"
    NOT_APPLICABLE = "not_applicable"
    PATIENT_NOT_FOUND = "patient_not_found"


# ---------------------------------------------------------------------------
# Feature Definition schemas
# ---------------------------------------------------------------------------


class FeatureDefinitionBase(BaseModel):
    """Base fields for a feature definition."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique feature name (snake_case)",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Human-readable description of the feature",
    )
    data_type: FeatureDataType = Field(
        ..., description="Data type of the feature value"
    )
    domain: FeatureDomain = Field(
        ..., description="Clinical domain this feature belongs to"
    )
    computation_logic: str = Field(
        default="",
        max_length=2000,
        description="Description of how the feature is computed",
    )
    freshness_requirements: str = Field(
        default="on_demand",
        max_length=255,
        description="How often this feature should be refreshed (e.g. 'daily', 'on_demand')",
    )
    source_tables: list[str] = Field(
        default_factory=list,
        description="Database tables or data sources used to compute this feature",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Arbitrary tags for filtering / grouping",
    )


class FeatureDefinitionCreate(FeatureDefinitionBase):
    """Request body for registering a new feature definition."""

    pass


class FeatureDefinitionUpdate(BaseModel):
    """Request body for updating a feature definition (partial)."""

    description: str | None = Field(None, max_length=1000)
    data_type: FeatureDataType | None = None
    domain: FeatureDomain | None = None
    computation_logic: str | None = Field(None, max_length=2000)
    freshness_requirements: str | None = Field(None, max_length=255)
    source_tables: list[str] | None = None
    tags: list[str] | None = None


class FeatureDefinitionResponse(FeatureDefinitionBase):
    """Response schema for a feature definition."""

    id: str = Field(..., description="Unique feature definition ID")
    version: int = Field(..., description="Current version number")
    is_builtin: bool = Field(
        ..., description="Whether this is a pre-defined built-in feature"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last-updated timestamp")


class FeatureDefinitionListResponse(BaseModel):
    """Paginated list of feature definitions."""

    total: int = Field(..., description="Total number of feature definitions")
    features: list[FeatureDefinitionResponse] = Field(
        ..., description="Feature definitions"
    )


# ---------------------------------------------------------------------------
# Feature Computation schemas
# ---------------------------------------------------------------------------


class ComputedFeatureValue(BaseModel):
    """A single computed feature value for a patient."""

    feature_name: str = Field(..., description="Feature name")
    value: Any = Field(None, description="Computed value (None if missing)")
    data_type: FeatureDataType = Field(..., description="Data type of the value")
    is_missing: bool = Field(
        False, description="Whether the value could not be computed"
    )
    missing_reason: MissingReason | None = Field(
        None, description="Reason the value is missing"
    )
    computation_time_ms: float = Field(
        ..., description="Time taken to compute this feature (milliseconds)"
    )
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the value was computed",
    )


class FeatureVectorResponse(BaseModel):
    """Complete feature vector for a patient."""

    patient_id: str = Field(..., description="Patient identifier")
    features: dict[str, Any] = Field(
        ..., description="Feature name -> value mapping"
    )
    feature_details: list[ComputedFeatureValue] = Field(
        ..., description="Detailed computation results per feature"
    )
    total_computation_time_ms: float = Field(
        ..., description="Total computation time (milliseconds)"
    )
    missing_count: int = Field(
        ..., description="Number of features that could not be computed"
    )
    computed_count: int = Field(
        ..., description="Number of features successfully computed"
    )
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the vector was computed",
    )


class BatchComputeRequest(BaseModel):
    """Request body for batch feature computation."""

    patient_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Patient IDs to compute features for",
    )
    feature_names: list[str] | None = Field(
        None,
        description="Specific features to compute; if None compute all",
    )


class BatchComputeResponse(BaseModel):
    """Response for batch feature computation."""

    results: list[FeatureVectorResponse] = Field(
        ..., description="Feature vectors per patient"
    )
    total_patients: int = Field(..., description="Number of patients processed")
    total_computation_time_ms: float = Field(
        ..., description="Total time for batch computation"
    )
    errors: dict[str, str] = Field(
        default_factory=dict,
        description="Patient ID -> error message for failed computations",
    )


# ---------------------------------------------------------------------------
# Feature Statistics schemas
# ---------------------------------------------------------------------------


class FeatureStatistics(BaseModel):
    """Descriptive statistics for a single feature."""

    feature_name: str = Field(..., description="Feature name")
    data_type: FeatureDataType = Field(..., description="Feature data type")
    sample_count: int = Field(..., description="Number of samples used")
    null_count: int = Field(..., description="Number of null values")
    null_rate: float = Field(..., description="Fraction of null values")
    # Numeric stats (only populated for NUMERIC features)
    min_value: float | None = Field(None, description="Minimum value")
    max_value: float | None = Field(None, description="Maximum value")
    mean_value: float | None = Field(None, description="Mean value")
    std_value: float | None = Field(None, description="Standard deviation")
    median_value: float | None = Field(None, description="Median value")
    # Categorical / boolean stats
    distribution: dict[str, int] | None = Field(
        None, description="Value -> count for categorical/boolean features"
    )
    unique_count: int | None = Field(
        None, description="Number of distinct values"
    )


class FeatureStatisticsListResponse(BaseModel):
    """Response for feature statistics."""

    total: int = Field(..., description="Number of features with statistics")
    statistics: list[FeatureStatistics] = Field(
        ..., description="Per-feature statistics"
    )
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When statistics were last computed",
    )


# ---------------------------------------------------------------------------
# Feature Importance schemas
# ---------------------------------------------------------------------------


class FeatureImportance(BaseModel):
    """Importance score for a single feature."""

    feature_name: str = Field(..., description="Feature name")
    importance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Importance score (0-1, higher = more important)",
    )
    rank: int = Field(..., ge=1, description="Rank among all features")
    domain: FeatureDomain = Field(..., description="Feature domain")
    description: str = Field(..., description="Feature description")
    usage_count: int = Field(
        0, description="Number of times this feature was used in screening"
    )


class FeatureImportanceListResponse(BaseModel):
    """Response for feature importance ranking."""

    total: int = Field(..., description="Total number of ranked features")
    importance: list[FeatureImportance] = Field(
        ..., description="Features ranked by importance"
    )
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When importance was last computed",
    )


# ---------------------------------------------------------------------------
# Feature Version schemas
# ---------------------------------------------------------------------------


class FeatureVersion(BaseModel):
    """A version snapshot of a feature definition."""

    version: int = Field(..., description="Version number")
    changed_at: datetime = Field(..., description="When this version was created")
    changes: dict[str, Any] = Field(
        ..., description="Fields that changed in this version"
    )
    changed_by: str = Field(
        default="system", description="Who made the change"
    )


class FeatureVersionHistory(BaseModel):
    """Version history for a feature."""

    feature_name: str = Field(..., description="Feature name")
    current_version: int = Field(..., description="Current version number")
    versions: list[FeatureVersion] = Field(
        ..., description="Version history (newest first)"
    )
