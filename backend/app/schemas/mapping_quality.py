"""Pydantic schemas for mapping quality metrics.

CTO-4: OMOP Mapping Quality - schemas for coverage dashboard,
confidence distribution, unmapped term analysis, and domain coverage.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConfidenceBucket(BaseModel):
    """A bucket in the confidence score distribution histogram."""

    range_label: str = Field(..., description="Bucket label (e.g. '0.0-0.1')")
    count: int = Field(..., description="Number of mappings in this bucket")
    percentage: float = Field(..., description="Percentage of total mappings")


class DomainCoverage(BaseModel):
    """Mapping coverage statistics for a single OMOP domain."""

    domain: str = Field(..., description="OMOP domain name (e.g. condition, drug)")
    total_mentions: int = Field(..., description="Total mentions in this domain")
    mapped_mentions: int = Field(..., description="Mentions with at least one concept candidate")
    coverage_pct: float = Field(..., description="Percentage of mentions that are mapped")
    avg_confidence: float = Field(..., description="Average confidence score of best candidates")


class SourceDistribution(BaseModel):
    """Distribution of mapping sources (exact, fuzzy, ML, manual)."""

    source: str = Field(..., description="Mapping method/source name")
    count: int = Field(..., description="Number of mappings from this source")
    percentage: float = Field(..., description="Percentage of total mappings")


class UnmappedTerm(BaseModel):
    """A term that failed to map to any OMOP concept."""

    term_text: str = Field(..., description="The unmapped mention text")
    frequency: int = Field(..., description="Number of times this term appears")
    domain: str | None = Field(None, description="Inferred domain, if available")
    suggested_concepts: list[str] = Field(
        default_factory=list,
        description="Suggested OMOP concepts for manual review",
    )


class MappingQualityReport(BaseModel):
    """Overall mapping quality report with coverage and distribution metrics."""

    total_mentions: int = Field(..., description="Total number of mentions analyzed")
    mapped_mentions: int = Field(..., description="Mentions with at least one concept candidate")
    overall_coverage: float = Field(..., description="Overall mapping coverage percentage")
    ambiguity_rate: float = Field(
        ..., description="Percentage of mentions with >1 candidate (needs review)"
    )
    domain_coverage: list[DomainCoverage] = Field(
        default_factory=list, description="Per-domain coverage breakdown"
    )
    confidence_distribution: list[ConfidenceBucket] = Field(
        default_factory=list, description="Histogram of confidence scores"
    )
    source_distribution: list[SourceDistribution] = Field(
        default_factory=list, description="Breakdown by mapping method/source"
    )


class MappingTrendPoint(BaseModel):
    """A single data point in a mapping quality trend."""

    date: str = Field(..., description="Date in ISO format (YYYY-MM-DD)")
    coverage_pct: float = Field(..., description="Coverage percentage on this date")
    total_mentions: int = Field(..., description="Total mentions as of this date")
    mapped_mentions: int = Field(..., description="Mapped mentions as of this date")
    avg_confidence: float = Field(..., description="Average confidence on this date")


class MappingTrendReport(BaseModel):
    """Mapping quality metrics over time."""

    period_days: int = Field(..., description="Number of days in the trend period")
    data_points: list[MappingTrendPoint] = Field(
        default_factory=list, description="Daily trend data points"
    )
