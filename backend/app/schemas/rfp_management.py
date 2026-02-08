"""Schemas for RFP Response Template and Competitive Positioning.

Partnership-1: Provides structured schemas for generating RFP responses,
competitive positioning matrices, capability catalogs, and case studies
for clinical trial patient recruitment partnerships.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MaturityLevel(str, Enum):
    """Feature maturity level."""

    PRODUCTION = "production"
    PILOT = "pilot"
    SCAFFOLD = "scaffold"
    PLANNED = "planned"


class DifferentiationScore(str, Enum):
    """Competitive differentiation score."""

    LEADING = "LEADING"
    COMPETITIVE = "COMPETITIVE"
    DEVELOPING = "DEVELOPING"
    GAP = "GAP"


class PricingTier(str, Enum):
    """Platform pricing tier."""

    STARTER = "Starter"
    PROFESSIONAL = "Professional"
    ENTERPRISE = "Enterprise"


class CaseStudyTherapeuticArea(str, Enum):
    """Therapeutic area for case studies."""

    OPHTHALMOLOGY = "Ophthalmology"
    DERMATOLOGY = "Dermatology"
    ONCOLOGY = "Oncology"


# ---------------------------------------------------------------------------
# Capability models
# ---------------------------------------------------------------------------


class PlatformCapability(BaseModel):
    """Single platform capability with maturity classification."""

    id: str = Field(..., description="Unique capability identifier")
    name: str = Field(..., description="Human-readable capability name")
    category: str = Field(..., description="Capability category")
    description: str = Field(..., description="Detailed description")
    maturity: MaturityLevel = Field(..., description="Current maturity level")
    key_features: list[str] = Field(
        default_factory=list, description="Key feature list"
    )
    standards: list[str] = Field(
        default_factory=list,
        description="Applicable standards (FHIR, OMOP, etc.)",
    )


class CapabilityCatalogResponse(BaseModel):
    """Full platform capability catalog."""

    total_capabilities: int = 0
    by_maturity: dict[str, int] = Field(
        default_factory=dict,
        description="Count of capabilities per maturity level",
    )
    capabilities: list[PlatformCapability] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Competitive positioning
# ---------------------------------------------------------------------------


class CompetitorScore(BaseModel):
    """Score for a single competitor in one category."""

    competitor: str
    score: DifferentiationScore
    notes: str = ""


class CompetitiveCategory(BaseModel):
    """One row of the competitive positioning matrix."""

    category: str = Field(..., description="Evaluation category")
    our_score: DifferentiationScore
    our_evidence: str = Field("", description="Evidence / proof point")
    competitors: list[CompetitorScore] = Field(default_factory=list)


class CompetitiveMatrixResponse(BaseModel):
    """Full competitive positioning matrix."""

    generated_at: datetime
    platform_name: str = "Clinical Ontology Normalizer"
    categories: list[CompetitiveCategory] = Field(default_factory=list)
    summary: str = ""
    key_differentiators: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# RFP template sections
# ---------------------------------------------------------------------------


class RFPTemplateSection(BaseModel):
    """One section of an RFP response template."""

    section_id: str = Field(..., description="Section identifier slug")
    title: str
    content: str = Field(..., description="Pre-populated section content")
    key_points: list[str] = Field(
        default_factory=list,
        description="Bullet-point highlights",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Supporting evidence / metrics",
    )


class RFPTemplateListResponse(BaseModel):
    """List of available RFP template sections."""

    total_sections: int = 0
    sections: list[RFPTemplateSection] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Case studies
# ---------------------------------------------------------------------------


class CaseStudyMetric(BaseModel):
    """A single metric from a case study."""

    metric: str
    value: str
    context: str = ""


class CaseStudy(BaseModel):
    """Clinical trial case study template."""

    id: str
    title: str
    therapeutic_area: CaseStudyTherapeuticArea
    drug_name: str
    indication: str
    challenge: str = Field(..., description="Problem / challenge addressed")
    solution: str = Field(..., description="Platform solution applied")
    results: list[CaseStudyMetric] = Field(default_factory=list)
    timeline: str = ""
    testimonial: str = ""


class CaseStudyListResponse(BaseModel):
    """List of case studies."""

    total: int = 0
    case_studies: list[CaseStudy] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# RFP generation
# ---------------------------------------------------------------------------


class RFPGenerateRequest(BaseModel):
    """Request to generate a customized RFP response."""

    sponsor_name: str = Field(..., description="Pharma sponsor name")
    therapeutic_area: str = Field("", description="Therapeutic focus area")
    trial_phase: str = Field("", description="Trial phase (I, II, III, IV)")
    requirements: list[str] = Field(
        default_factory=list,
        description="Specific requirements from the RFP",
    )
    sections: list[str] = Field(
        default_factory=list,
        description="Section IDs to include (empty = all)",
    )
    include_case_studies: bool = Field(
        True, description="Include relevant case studies"
    )
    include_competitive_matrix: bool = Field(
        True, description="Include competitive positioning"
    )
    include_pricing: bool = Field(
        True, description="Include pricing section"
    )


class RFPGeneratedResponse(BaseModel):
    """Generated RFP response."""

    generated_at: datetime
    sponsor_name: str
    therapeutic_area: str = ""
    trial_phase: str = ""
    sections: list[RFPTemplateSection] = Field(default_factory=list)
    matched_capabilities: list[PlatformCapability] = Field(
        default_factory=list
    )
    case_studies: list[CaseStudy] = Field(default_factory=list)
    competitive_matrix: CompetitiveMatrixResponse | None = None
    requirement_coverage: float = Field(
        0.0,
        description="Fraction of requirements matched to capabilities",
    )


# ---------------------------------------------------------------------------
# Requirement matching
# ---------------------------------------------------------------------------


class RequirementMatch(BaseModel):
    """Mapping from a requirement string to matched capabilities."""

    requirement: str
    matched: bool = False
    matched_capabilities: list[PlatformCapability] = Field(
        default_factory=list
    )
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Match confidence"
    )
    gap_notes: str = Field(
        "",
        description="Notes if the requirement cannot be fully met",
    )


class RequirementMatchRequest(BaseModel):
    """Request to match a list of requirements to platform capabilities."""

    requirements: list[str] = Field(
        ..., min_length=1, description="Requirements to match"
    )


class RequirementMatchResponse(BaseModel):
    """Results of matching requirements to capabilities."""

    total_requirements: int = 0
    matched_count: int = 0
    partial_count: int = 0
    gap_count: int = 0
    coverage_score: float = Field(
        0.0, description="Overall coverage 0.0-1.0"
    )
    matches: list[RequirementMatch] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


class PricingTierDetail(BaseModel):
    """Detail for one pricing tier."""

    tier: PricingTier
    name: str
    monthly_price: str = Field(
        ..., description="Price string (e.g. '$5,000/mo')"
    )
    annual_price: str = ""
    included_patients: str = ""
    features: list[str] = Field(default_factory=list)
    support_level: str = ""
    recommended_for: str = ""
