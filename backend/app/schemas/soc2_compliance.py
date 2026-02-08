"""Pydantic schemas for SOC 2 Gap Analysis (CISO-12).

Defines Trust Services Criteria controls, gap analysis reporting,
readiness scoring, and remediation planning models for the clinical
trial patient recruitment platform.

CISO-12: SOC 2 Gap Analysis
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TrustServiceCategory(str, Enum):
    """SOC 2 Trust Services Categories."""

    CC = "CC"   # Common Criteria / Security
    A = "A"     # Availability
    PI = "PI"   # Processing Integrity
    C = "C"     # Confidentiality
    P = "P"     # Privacy


class ControlStatus(str, Enum):
    """Gap status for a SOC 2 control."""

    IMPLEMENTED = "IMPLEMENTED"
    PARTIAL = "PARTIAL"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RemediationPriority(str, Enum):
    """Priority for remediation items."""

    P1 = "P1"  # Audit blocker
    P2 = "P2"  # Should fix
    P3 = "P3"  # Nice to have


class EvidenceType(str, Enum):
    """Type of evidence attached to a control."""

    DOCUMENT = "DOCUMENT"
    TEST = "TEST"
    CONFIGURATION = "CONFIGURATION"
    SCREENSHOT = "SCREENSHOT"
    LOG = "LOG"
    POLICY = "POLICY"
    CODE = "CODE"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class EvidenceAttachment(BaseModel):
    """Evidence attached to a SOC 2 control."""

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
# SOC 2 Control
# ---------------------------------------------------------------------------


class SOC2Control(BaseModel):
    """A single SOC 2 control mapping."""

    id: str = Field(..., description="Control ID (e.g. CC1.1, A1.1)")
    category: TrustServiceCategory = Field(..., description="Trust Service Category")
    criterion: str = Field(..., description="SOC 2 criterion reference")
    title: str = Field(..., description="Control title")
    description: str = Field(..., description="Detailed control description")
    status: ControlStatus = Field(..., description="Current implementation status")
    platform_control: str = Field(
        default="", description="Reference to existing platform control/feature"
    )
    file_reference: str = Field(
        default="", description="File or feature that implements this control"
    )
    evidence: list[EvidenceAttachment] = Field(
        default_factory=list, description="Attached evidence"
    )
    remediation_plan: str = Field(
        default="", description="What needs to be done for gaps"
    )
    priority: RemediationPriority = Field(
        default=RemediationPriority.P3, description="Remediation priority"
    )
    effort_hours: int = Field(
        default=0, description="Estimated remediation effort in hours"
    )
    notes: str = Field(default="", description="Additional notes")
    last_assessed: datetime | None = Field(
        default=None, description="Last assessment date"
    )
    assessed_by: str = Field(default="", description="Who last assessed this control")


class SOC2ControlUpdate(BaseModel):
    """Request to update a SOC 2 control."""

    status: ControlStatus | None = Field(default=None, description="New status")
    platform_control: str | None = Field(
        default=None, description="Updated platform control reference"
    )
    file_reference: str | None = Field(
        default=None, description="Updated file reference"
    )
    remediation_plan: str | None = Field(
        default=None, description="Updated remediation plan"
    )
    priority: RemediationPriority | None = Field(
        default=None, description="Updated priority"
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
    """Readiness score for a single Trust Service Category."""

    category: TrustServiceCategory = Field(..., description="Trust Service Category")
    category_name: str = Field(..., description="Human-readable category name")
    total_controls: int = Field(..., description="Total controls in category")
    implemented: int = Field(..., description="Fully implemented controls")
    partial: int = Field(..., description="Partially implemented controls")
    not_implemented: int = Field(..., description="Not implemented controls")
    not_applicable: int = Field(..., description="Not applicable controls")
    readiness_percentage: float = Field(
        ..., description="Readiness percentage (0-100)"
    )


class ReadinessScore(BaseModel):
    """Overall SOC 2 readiness scores."""

    overall_percentage: float = Field(
        ..., description="Overall readiness percentage"
    )
    categories: list[CategoryReadiness] = Field(
        ..., description="Per-category readiness"
    )
    total_controls: int = Field(..., description="Total controls assessed")
    total_implemented: int = Field(..., description="Total fully implemented")
    total_partial: int = Field(..., description="Total partially implemented")
    total_not_implemented: int = Field(..., description="Total not implemented")
    total_not_applicable: int = Field(..., description="Total not applicable")
    assessed_at: datetime = Field(..., description="Assessment timestamp")


# ---------------------------------------------------------------------------
# Remediation
# ---------------------------------------------------------------------------


class RemediationItem(BaseModel):
    """A single remediation action item."""

    control_id: str = Field(..., description="Control that needs remediation")
    category: TrustServiceCategory = Field(..., description="Trust Service Category")
    title: str = Field(..., description="Control title")
    current_status: ControlStatus = Field(..., description="Current status")
    priority: RemediationPriority = Field(..., description="Remediation priority")
    remediation_plan: str = Field(..., description="What needs to be done")
    effort_hours: int = Field(..., description="Estimated effort in hours")


class RemediationPlan(BaseModel):
    """Prioritized remediation plan."""

    total_items: int = Field(..., description="Total remediation items")
    p1_items: int = Field(..., description="P1 (audit blocker) items")
    p2_items: int = Field(..., description="P2 (should fix) items")
    p3_items: int = Field(..., description="P3 (nice to have) items")
    total_effort_hours: int = Field(..., description="Total estimated effort")
    items: list[RemediationItem] = Field(
        ..., description="Remediation items sorted by priority"
    )
    generated_at: datetime = Field(..., description="Report generation timestamp")


# ---------------------------------------------------------------------------
# Gap Report
# ---------------------------------------------------------------------------


class CategoryGapSummary(BaseModel):
    """Gap summary for a single Trust Service Category."""

    category: TrustServiceCategory = Field(..., description="Category")
    category_name: str = Field(..., description="Human-readable category name")
    readiness_percentage: float = Field(..., description="Readiness percentage")
    controls: list[SOC2Control] = Field(..., description="Controls in this category")
    gaps: list[SOC2Control] = Field(
        ..., description="Controls with gaps (PARTIAL or NOT_IMPLEMENTED)"
    )
    implemented_controls: list[SOC2Control] = Field(
        ..., description="Fully implemented controls"
    )


class GapReport(BaseModel):
    """Comprehensive SOC 2 gap analysis report."""

    report_id: str = Field(..., description="Unique report identifier")
    title: str = Field(
        default="SOC 2 Type II Gap Analysis Report",
        description="Report title",
    )
    executive_summary: str = Field(..., description="Executive summary")
    overall_readiness: ReadinessScore = Field(
        ..., description="Overall readiness scores"
    )
    category_analysis: list[CategoryGapSummary] = Field(
        ..., description="Per-category gap analysis"
    )
    remediation_plan: RemediationPlan = Field(
        ..., description="Prioritized remediation plan"
    )
    generated_at: datetime = Field(..., description="Report generation timestamp")
    generated_by: str = Field(
        default="SOC2ComplianceService", description="Report generator"
    )
