"""Pydantic schemas for HITRUST CSF v11 Roadmap (CISO-13).

Defines HITRUST Common Security Framework control categories, maturity
levels, evidence management, readiness scoring, and certification
roadmap models for the clinical trial patient recruitment platform.

CISO-13: HITRUST CSF Roadmap
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HITRUSTCategory(int, Enum):
    """HITRUST CSF v11 Control Categories (0-13)."""

    INFORMATION_SECURITY_MANAGEMENT = 0
    ACCESS_CONTROL = 1
    HUMAN_RESOURCES_SECURITY = 2
    RISK_MANAGEMENT = 3
    SECURITY_POLICY = 4
    ORGANIZATION_OF_INFORMATION_SECURITY = 5
    COMPLIANCE = 6
    ASSET_MANAGEMENT = 7
    PHYSICAL_AND_ENVIRONMENTAL_SECURITY = 8
    COMMUNICATIONS_AND_OPERATIONS_MANAGEMENT = 9
    INFORMATION_SYSTEMS_ACQUISITION_DEVELOPMENT_MAINTENANCE = 10
    INFORMATION_SECURITY_INCIDENT_MANAGEMENT = 11
    BUSINESS_CONTINUITY_MANAGEMENT = 12
    PRIVACY_PRACTICES = 13


class MaturityLevel(str, Enum):
    """HITRUST CSF control maturity levels."""

    NOT_STARTED = "NOT_STARTED"
    POLICY = "POLICY"             # Documented
    PROCEDURE = "PROCEDURE"       # Implemented procedures
    IMPLEMENTED = "IMPLEMENTED"   # Operational
    MEASURED = "MEASURED"         # Monitored
    MANAGED = "MANAGED"           # Continuously improved


class RoadmapPhase(str, Enum):
    """Certification roadmap phases."""

    PHASE_1 = "PHASE_1"  # Quick wins
    PHASE_2 = "PHASE_2"  # Foundational
    PHASE_3 = "PHASE_3"  # Advanced
    PHASE_4 = "PHASE_4"  # Certification


class EvidenceType(str, Enum):
    """Type of evidence attached to a HITRUST control."""

    DOCUMENT = "DOCUMENT"
    TEST = "TEST"
    CONFIGURATION = "CONFIGURATION"
    SCREENSHOT = "SCREENSHOT"
    LOG = "LOG"
    POLICY = "POLICY"
    CODE = "CODE"
    AUDIT_REPORT = "AUDIT_REPORT"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class EvidenceAttachment(BaseModel):
    """Evidence attached to a HITRUST control."""

    id: str = Field(..., description="Unique evidence identifier")
    control_id: str = Field(..., description="Associated control ID")
    evidence_type: EvidenceType = Field(..., description="Type of evidence")
    title: str = Field(..., description="Evidence title")
    description: str = Field(default="", description="Evidence description")
    file_reference: str = Field(..., description="Path or URL to evidence file")
    collected_at: datetime = Field(..., description="When evidence was collected")
    collected_by: str = Field(default="system", description="Who collected the evidence")


class EvidenceCreate(BaseModel):
    """Request to attach evidence to a control."""

    control_id: str = Field(..., description="Control ID to attach evidence to")
    evidence_type: EvidenceType = Field(..., description="Type of evidence")
    title: str = Field(..., description="Evidence title")
    description: str = Field(default="", description="Evidence description")
    file_reference: str = Field(..., description="Path or URL to evidence file")


# ---------------------------------------------------------------------------
# HITRUST Control
# ---------------------------------------------------------------------------


class HITRUSTControl(BaseModel):
    """A single HITRUST CSF control mapping."""

    id: str = Field(..., description="Control ID (e.g. 01.a, 09.ab)")
    category: HITRUSTCategory = Field(..., description="HITRUST Control Category (0-13)")
    title: str = Field(..., description="Control title")
    description: str = Field(..., description="Detailed control description")
    maturity_level: MaturityLevel = Field(..., description="Current maturity level")
    target_maturity: MaturityLevel = Field(
        default=MaturityLevel.MANAGED, description="Target maturity level"
    )
    platform_control: str = Field(
        default="", description="Reference to existing platform control/feature"
    )
    file_reference: str = Field(
        default="", description="File or feature that implements this control"
    )
    evidence: list[EvidenceAttachment] = Field(
        default_factory=list, description="Attached evidence"
    )
    gap_description: str = Field(
        default="", description="Description of gap if not fully mature"
    )
    remediation_plan: str = Field(
        default="", description="What needs to be done for gaps"
    )
    roadmap_phase: RoadmapPhase = Field(
        default=RoadmapPhase.PHASE_2, description="Which certification phase addresses this"
    )
    effort_hours: int = Field(
        default=0, description="Estimated remediation effort in hours"
    )
    notes: str = Field(default="", description="Additional notes")
    last_assessed: datetime | None = Field(
        default=None, description="Last assessment date"
    )
    assessed_by: str = Field(default="", description="Who last assessed this control")


class HITRUSTControlUpdate(BaseModel):
    """Request to update a HITRUST control."""

    maturity_level: MaturityLevel | None = Field(default=None, description="New maturity level")
    target_maturity: MaturityLevel | None = Field(default=None, description="Updated target maturity")
    platform_control: str | None = Field(
        default=None, description="Updated platform control reference"
    )
    file_reference: str | None = Field(
        default=None, description="Updated file reference"
    )
    gap_description: str | None = Field(
        default=None, description="Updated gap description"
    )
    remediation_plan: str | None = Field(
        default=None, description="Updated remediation plan"
    )
    roadmap_phase: RoadmapPhase | None = Field(
        default=None, description="Updated roadmap phase"
    )
    effort_hours: int | None = Field(
        default=None, description="Updated effort estimate"
    )
    notes: str | None = Field(default=None, description="Updated notes")
    assessed_by: str | None = Field(default=None, description="Assessor name")


# ---------------------------------------------------------------------------
# Readiness Score
# ---------------------------------------------------------------------------


class CategoryReadiness(BaseModel):
    """Readiness score for a single HITRUST category."""

    category: HITRUSTCategory = Field(..., description="HITRUST Control Category")
    category_name: str = Field(..., description="Human-readable category name")
    total_controls: int = Field(..., description="Total controls in category")
    maturity_distribution: dict[str, int] = Field(
        ..., description="Count per maturity level"
    )
    average_maturity_score: float = Field(
        ..., description="Average maturity score (0-5 scale)"
    )
    readiness_percentage: float = Field(
        ..., description="Readiness percentage (0-100)"
    )


class ReadinessScore(BaseModel):
    """Overall HITRUST certification readiness scores."""

    overall_percentage: float = Field(
        ..., description="Overall readiness percentage"
    )
    overall_maturity_score: float = Field(
        ..., description="Overall average maturity score (0-5)"
    )
    categories: list[CategoryReadiness] = Field(
        ..., description="Per-category readiness"
    )
    total_controls: int = Field(..., description="Total controls assessed")
    maturity_distribution: dict[str, int] = Field(
        ..., description="Overall count per maturity level"
    )
    estimated_effort_to_certification: int = Field(
        ..., description="Estimated total hours to reach certification"
    )
    assessed_at: datetime = Field(..., description="Assessment timestamp")


# ---------------------------------------------------------------------------
# Category Summary
# ---------------------------------------------------------------------------


class CategorySummary(BaseModel):
    """Summary of a single HITRUST category."""

    category: HITRUSTCategory = Field(..., description="Category number")
    category_name: str = Field(..., description="Human-readable category name")
    total_controls: int = Field(..., description="Number of controls in category")
    average_maturity_score: float = Field(
        ..., description="Average maturity score (0-5)"
    )
    readiness_percentage: float = Field(
        ..., description="Readiness percentage (0-100)"
    )
    top_gaps: list[str] = Field(
        ..., description="Top control IDs with gaps"
    )


# ---------------------------------------------------------------------------
# Roadmap
# ---------------------------------------------------------------------------


class RoadmapItem(BaseModel):
    """A single item in the certification roadmap."""

    control_id: str = Field(..., description="Control that needs work")
    category: HITRUSTCategory = Field(..., description="HITRUST Category")
    title: str = Field(..., description="Control title")
    current_maturity: MaturityLevel = Field(..., description="Current maturity level")
    target_maturity: MaturityLevel = Field(..., description="Target maturity level")
    effort_hours: int = Field(..., description="Estimated effort in hours")
    remediation_plan: str = Field(..., description="What needs to be done")


class RoadmapPhaseDetail(BaseModel):
    """Detail for a single roadmap phase."""

    phase: RoadmapPhase = Field(..., description="Roadmap phase")
    phase_name: str = Field(..., description="Human-readable phase name")
    description: str = Field(..., description="Phase description")
    estimated_duration_weeks: int = Field(
        ..., description="Estimated duration in weeks"
    )
    total_effort_hours: int = Field(
        ..., description="Total effort in hours for this phase"
    )
    items: list[RoadmapItem] = Field(
        ..., description="Controls to address in this phase"
    )


class CertificationRoadmap(BaseModel):
    """Complete HITRUST certification roadmap."""

    title: str = Field(
        default="HITRUST CSF v11 Certification Roadmap",
        description="Roadmap title",
    )
    overall_readiness: ReadinessScore = Field(
        ..., description="Current readiness assessment"
    )
    phases: list[RoadmapPhaseDetail] = Field(
        ..., description="Phased certification roadmap"
    )
    total_effort_hours: int = Field(
        ..., description="Total effort across all phases"
    )
    estimated_total_weeks: int = Field(
        ..., description="Estimated total duration in weeks"
    )
    generated_at: datetime = Field(..., description="Report generation timestamp")
    generated_by: str = Field(
        default="HITRUSTComplianceService", description="Report generator"
    )
