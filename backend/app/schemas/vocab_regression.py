"""Pydantic schemas for vocabulary update regression testing.

Dir-CI-3.5: Vocabulary Update Regression Testing - schemas for capturing
vocabulary mapping baselines, detecting changes between vocabulary versions,
and assessing the impact of vocabulary updates on clinical trial eligibility.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    """Type of vocabulary mapping change detected."""

    ID_CHANGED = "id_changed"
    DEPRECATED = "deprecated"
    DOMAIN_CHANGED = "domain_changed"
    NEW_MAPPING = "new_mapping"
    CONFIDENCE_CHANGED = "confidence_changed"
    NAME_CHANGED = "name_changed"


class RiskLevel(str, Enum):
    """Risk level of a vocabulary change."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VocabMapping(BaseModel):
    """A single term-to-concept vocabulary mapping entry."""

    term: str = Field(..., description="Source clinical term text")
    concept_id: int = Field(..., description="OMOP concept ID")
    concept_name: str = Field(..., description="OMOP concept name")
    domain_id: str = Field(..., description="OMOP domain (Condition, Drug, Measurement, etc.)")
    vocabulary_id: str = Field(..., description="Source vocabulary (SNOMED, RxNorm, LOINC, etc.)")
    standard_concept: str | None = Field(
        None, description="Standard concept flag: 'S' for standard, 'C' for classification, None for non-standard"
    )
    concept_class_id: str | None = Field(
        None, description="Concept class within the vocabulary"
    )
    confidence: float = Field(
        1.0, description="Mapping confidence score (0.0-1.0)"
    )


class VocabBaseline(BaseModel):
    """A snapshot of vocabulary mappings at a point in time."""

    name: str = Field(..., description="Unique baseline name (e.g. 'v5.0-2026-01')")
    version: str = Field(..., description="Vocabulary version identifier")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the baseline was captured",
    )
    mappings: list[VocabMapping] = Field(
        default_factory=list, description="List of term-to-concept mappings"
    )
    total_count: int = Field(0, description="Total number of mappings in the baseline")
    description: str = Field("", description="Optional description of the baseline")

    def model_post_init(self, __context: object) -> None:
        """Set total_count from mappings if not explicitly provided."""
        if self.total_count == 0 and self.mappings:
            object.__setattr__(self, "total_count", len(self.mappings))


class VocabChange(BaseModel):
    """A detected change between baseline and current vocabulary mappings."""

    term: str = Field(..., description="Clinical term that changed")
    change_type: ChangeType = Field(..., description="Type of change detected")
    old_value: str | None = Field(None, description="Previous value (baseline)")
    new_value: str | None = Field(None, description="Current value (new vocabulary)")
    old_concept_id: int | None = Field(None, description="Previous concept ID")
    new_concept_id: int | None = Field(None, description="New concept ID")
    domain_id: str = Field("", description="Domain of the affected concept")
    risk_level: RiskLevel = Field(
        RiskLevel.LOW, description="Risk level: high, medium, or low"
    )
    detail: str = Field("", description="Human-readable description of the change")


class VocabRegressionReport(BaseModel):
    """Report comparing current vocabulary against a baseline."""

    baseline_name: str = Field(..., description="Name of the baseline compared against")
    baseline_version: str = Field("", description="Vocabulary version of the baseline")
    current_version: str = Field("", description="Current vocabulary version being tested")
    comparison_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the comparison was performed",
    )
    total_checked: int = Field(0, description="Total number of mappings checked")
    unchanged: int = Field(0, description="Number of mappings that are identical")
    changed: int = Field(0, description="Number of mappings with changes")
    changes: list[VocabChange] = Field(
        default_factory=list, description="Detailed list of changes"
    )
    high_risk_changes: int = Field(
        0, description="Number of high-risk changes"
    )
    medium_risk_changes: int = Field(
        0, description="Number of medium-risk changes"
    )
    low_risk_changes: int = Field(
        0, description="Number of low-risk changes"
    )
    new_mappings: int = Field(
        0, description="Number of new mappings available"
    )
    deprecated_mappings: int = Field(
        0, description="Number of deprecated concept mappings"
    )
    trial_impacting_changes: list[VocabChange] = Field(
        default_factory=list,
        description="Changes that affect active trial eligibility criteria",
    )

    @property
    def has_breaking_changes(self) -> bool:
        """Check if the report contains any high-risk changes."""
        return self.high_risk_changes > 0

    @property
    def change_rate_pct(self) -> float:
        """Calculate the percentage of mappings that changed."""
        if self.total_checked == 0:
            return 0.0
        return round(self.changed / self.total_checked * 100.0, 2)


class VocabUpdatePreview(BaseModel):
    """Preview of vocabulary update impact before applying."""

    baseline_name: str = Field(..., description="Baseline being compared")
    total_mappings: int = Field(0, description="Total mappings in the baseline")
    affected_mappings: int = Field(0, description="Mappings affected by the update")
    breaking_changes: int = Field(0, description="High-risk changes that may break eligibility")
    safe_changes: int = Field(0, description="Low/medium-risk changes")
    recommendation: str = Field(
        "", description="Recommendation: 'safe_to_apply', 'review_required', 'block_update'"
    )
    report: VocabRegressionReport | None = Field(
        None, description="Full regression report for detailed review"
    )
