"""Pydantic schemas for Requirements Traceability Matrix (VP-Quality-3).

Defines data contracts for requirements tracking, trace links between
requirements/design/code/tests/validation, coverage analysis, gap reports,
and impact analysis.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class RequirementCategory(str, Enum):
    """Category classification for requirements."""

    FUNCTIONAL = "FUNCTIONAL"
    NON_FUNCTIONAL = "NON_FUNCTIONAL"
    REGULATORY = "REGULATORY"
    SECURITY = "SECURITY"


class RequirementPriority(str, Enum):
    """Priority level for requirements."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class RequirementStatus(str, Enum):
    """Lifecycle status for requirements."""

    DEFINED = "DEFINED"
    DESIGNED = "DESIGNED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    VALIDATED = "VALIDATED"


class TraceLevelKind(str, Enum):
    """Types of trace link levels."""

    DESIGN = "DESIGN"
    CODE = "CODE"
    TEST = "TEST"
    VALIDATION = "VALIDATION"


class CoverageLevel(str, Enum):
    """Coverage classification for a requirement."""

    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    IMPLEMENTED_UNTESTED = "IMPLEMENTED_UNTESTED"
    TESTED_UNVALIDATED = "TESTED_UNVALIDATED"
    FULLY_COVERED = "FULLY_COVERED"


# ---------------------------------------------------------------------------
# Trace Link Schemas
# ---------------------------------------------------------------------------


class TraceLink(BaseModel):
    """A single trace link reference."""

    ref: str = Field(..., description="Reference path or identifier")
    description: str = Field(default="", description="Description of what this reference covers")
    verified: bool = Field(default=False, description="Whether this link has been verified")
    verified_at: datetime | None = Field(default=None, description="When link was verified")


class TraceLinks(BaseModel):
    """All trace links for a requirement across the four levels."""

    design_refs: list[TraceLink] = Field(default_factory=list, description="Design document references")
    code_refs: list[TraceLink] = Field(default_factory=list, description="Source code file references")
    test_refs: list[TraceLink] = Field(default_factory=list, description="Test file/function references")
    validation_refs: list[TraceLink] = Field(default_factory=list, description="Validation evidence references")


# ---------------------------------------------------------------------------
# Requirement Schemas
# ---------------------------------------------------------------------------


class RequirementBase(BaseModel):
    """Base fields for a requirement."""

    title: str = Field(..., min_length=1, max_length=500, description="Requirement title")
    description: str = Field(..., min_length=1, description="Detailed requirement description")
    category: RequirementCategory = Field(..., description="Requirement category")
    priority: RequirementPriority = Field(..., description="Priority level")
    source: str = Field(default="", description="Stakeholder or regulation source")


class RequirementCreate(RequirementBase):
    """Schema for creating a new requirement."""

    id: str | None = Field(default=None, description="Optional custom ID (auto-generated if not provided)")
    status: RequirementStatus = Field(default=RequirementStatus.DEFINED, description="Initial status")
    trace_links: TraceLinks | None = Field(default=None, description="Initial trace links")


class RequirementUpdate(BaseModel):
    """Schema for updating an existing requirement."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, min_length=1)
    category: RequirementCategory | None = None
    priority: RequirementPriority | None = None
    status: RequirementStatus | None = None
    source: str | None = None
    trace_links: TraceLinks | None = None


class RequirementResponse(RequirementBase):
    """Full requirement record with trace links and metadata."""

    id: str = Field(..., description="Unique requirement identifier")
    status: RequirementStatus = Field(..., description="Current lifecycle status")
    trace_links: TraceLinks = Field(default_factory=TraceLinks, description="All trace links")
    coverage_level: CoverageLevel = Field(..., description="Computed coverage level")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class RequirementListResponse(BaseModel):
    """Paginated list of requirements."""

    requirements: list[RequirementResponse] = Field(default_factory=list)
    total: int = Field(default=0, description="Total number of requirements")
    page: int = Field(default=1)
    page_size: int = Field(default=50)


# ---------------------------------------------------------------------------
# Coverage Analysis Schemas
# ---------------------------------------------------------------------------


class CoverageSummary(BaseModel):
    """Summary statistics for requirement coverage."""

    total_requirements: int = Field(default=0)
    fully_covered: int = Field(default=0)
    tested_unvalidated: int = Field(default=0)
    implemented_untested: int = Field(default=0)
    not_implemented: int = Field(default=0)
    coverage_percentage: float = Field(default=0.0, description="Percent fully covered")

    # Breakdowns by category
    by_category: dict[str, dict[str, int]] = Field(default_factory=dict)
    # Breakdowns by priority
    by_priority: dict[str, dict[str, int]] = Field(default_factory=dict)


class CoverageReport(BaseModel):
    """Full coverage analysis report."""

    summary: CoverageSummary = Field(default_factory=CoverageSummary)
    requirements: list[RequirementResponse] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now())


# ---------------------------------------------------------------------------
# Gap Analysis Schemas
# ---------------------------------------------------------------------------


class GapItem(BaseModel):
    """A single gap identified in traceability."""

    requirement_id: str = Field(..., description="Requirement with the gap")
    requirement_title: str = Field(default="")
    category: RequirementCategory = Field(...)
    priority: RequirementPriority = Field(...)
    missing_levels: list[TraceLevelKind] = Field(default_factory=list, description="Trace levels that are missing")
    coverage_level: CoverageLevel = Field(...)
    recommendation: str = Field(default="", description="Recommended action to close the gap")


class GapReport(BaseModel):
    """Gap analysis report with all identified gaps."""

    gaps: list[GapItem] = Field(default_factory=list)
    total_gaps: int = Field(default=0)
    critical_gaps: int = Field(default=0, description="P1 requirements with gaps")
    generated_at: datetime = Field(default_factory=lambda: datetime.now())


# ---------------------------------------------------------------------------
# Impact Analysis Schemas
# ---------------------------------------------------------------------------


class ImpactAnalysisRequest(BaseModel):
    """Request payload for impact analysis."""

    changed_files: list[str] = Field(..., min_length=1, description="List of changed file paths")
    change_description: str = Field(default="", description="Description of the change")


class AffectedRequirement(BaseModel):
    """A requirement affected by a code change."""

    requirement_id: str = Field(...)
    requirement_title: str = Field(default="")
    category: RequirementCategory = Field(...)
    priority: RequirementPriority = Field(...)
    status: RequirementStatus = Field(...)
    matched_code_refs: list[str] = Field(default_factory=list, description="Code refs that match changed files")
    matched_test_refs: list[str] = Field(default_factory=list, description="Test refs that match changed files")
    risk_level: str = Field(default="LOW", description="Risk classification: LOW, MEDIUM, HIGH, CRITICAL")


class ImpactAnalysisResponse(BaseModel):
    """Result of impact analysis for code changes."""

    changed_files: list[str] = Field(default_factory=list)
    affected_requirements: list[AffectedRequirement] = Field(default_factory=list)
    total_affected: int = Field(default=0)
    risk_summary: dict[str, int] = Field(default_factory=dict, description="Count by risk level")
    recommendations: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now())


# ---------------------------------------------------------------------------
# Traceability Matrix Schemas
# ---------------------------------------------------------------------------


class MatrixRow(BaseModel):
    """A single row in the traceability matrix."""

    requirement_id: str = Field(...)
    requirement_title: str = Field(default="")
    category: RequirementCategory = Field(...)
    priority: RequirementPriority = Field(...)
    status: RequirementStatus = Field(...)
    design_count: int = Field(default=0)
    code_count: int = Field(default=0)
    test_count: int = Field(default=0)
    validation_count: int = Field(default=0)
    coverage_level: CoverageLevel = Field(...)
    design_refs: list[str] = Field(default_factory=list)
    code_refs: list[str] = Field(default_factory=list)
    test_refs: list[str] = Field(default_factory=list)
    validation_refs: list[str] = Field(default_factory=list)


class TraceabilityMatrix(BaseModel):
    """Full traceability matrix with all requirements."""

    rows: list[MatrixRow] = Field(default_factory=list)
    summary: CoverageSummary = Field(default_factory=CoverageSummary)
    generated_at: datetime = Field(default_factory=lambda: datetime.now())
