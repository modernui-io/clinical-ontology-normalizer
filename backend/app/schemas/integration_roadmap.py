"""Schemas for EDC/CTMS Integration Roadmap (Partnership-2).

Defines data structures for integration planning, readiness assessment,
effort estimation, and data mapping between the platform and external
clinical trial systems (Medidata Rave, Veeva Vault CTMS, Oracle Siebel,
REDCap, Flatiron OncoEMR, Epic EHR).
"""

from __future__ import annotations

from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IntegrationSystem(str, Enum):
    """Target systems for integration."""

    MEDIDATA_RAVE = "medidata_rave"
    VEEVA_VAULT_CTMS = "veeva_vault_ctms"
    ORACLE_SIEBEL_CTMS = "oracle_siebel_ctms"
    REDCAP = "redcap"
    FLATIRON_ONCOEMR = "flatiron_oncoemr"
    EPIC = "epic"


class DataFlowDirection(str, Enum):
    """Direction of data exchange between systems."""

    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class AuthMethod(str, Enum):
    """Authentication method for system integration."""

    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    CERTIFICATE = "certificate"
    BASIC_AUTH = "basic_auth"


class DataFormat(str, Enum):
    """Data format for exchange between systems."""

    FHIR_R4 = "FHIR_R4"
    CDISC_ODM = "CDISC_ODM"
    HL7V2 = "HL7v2"
    CUSTOM_JSON = "CUSTOM_JSON"
    CUSTOM_XML = "CUSTOM_XML"
    CSV = "CSV"


class SyncMethod(str, Enum):
    """Synchronization method for data exchange."""

    REAL_TIME = "REAL_TIME"
    BATCH = "BATCH"
    ON_DEMAND = "ON_DEMAND"


class ReadinessStatus(str, Enum):
    """Readiness assessment status for a capability."""

    IMPLEMENTED = "IMPLEMENTED"
    PARTIAL = "PARTIAL"
    NEEDS_DEVELOPMENT = "NEEDS_DEVELOPMENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RoadmapPhase(str, Enum):
    """Phased integration delivery phases."""

    PHASE_1 = "phase_1"
    PHASE_2 = "phase_2"
    PHASE_3 = "phase_3"
    PHASE_4 = "phase_4"


class IntegrationCategory(str, Enum):
    """Category of the integration target system."""

    EDC = "EDC"
    CTMS = "CTMS"
    EHR = "EHR"
    EMR = "EMR"


class FieldMappingDirection(str, Enum):
    """Direction of field mapping."""

    SOURCE_TO_TARGET = "source_to_target"
    TARGET_TO_SOURCE = "target_to_source"
    BIDIRECTIONAL = "bidirectional"


# ---------------------------------------------------------------------------
# Integration specification models
# ---------------------------------------------------------------------------


class IntegrationPattern(BaseModel):
    """Integration pattern specification for a target system."""

    data_flow: DataFlowDirection = Field(
        ..., description="Direction of data flow"
    )
    auth_methods: list[AuthMethod] = Field(
        ..., description="Supported authentication methods"
    )
    data_formats: list[DataFormat] = Field(
        ..., description="Supported data exchange formats"
    )
    sync_methods: list[SyncMethod] = Field(
        ..., description="Available synchronization methods"
    )
    api_type: str = Field(
        ..., description="API technology (REST, SOAP, GraphQL, etc.)"
    )
    api_version: str | None = Field(
        None, description="API version if applicable"
    )


class DataDomain(BaseModel):
    """A data domain available from or to a target system."""

    name: str = Field(..., description="Domain name (e.g., study events)")
    description: str = Field(..., description="What data this domain covers")
    fhir_resource_types: list[str] = Field(
        default_factory=list,
        description="Corresponding FHIR resource types",
    )
    cdisc_domains: list[str] = Field(
        default_factory=list,
        description="Corresponding CDISC domains if applicable",
    )


class IntegrationSpec(BaseModel):
    """Full integration specification for a target system."""

    system: IntegrationSystem
    display_name: str = Field(..., description="Human-readable system name")
    vendor: str = Field(..., description="Vendor/manufacturer name")
    category: IntegrationCategory = Field(
        ..., description="System category (EDC, CTMS, EHR, EMR)"
    )
    description: str = Field(
        ..., description="System description and typical use"
    )
    pattern: IntegrationPattern = Field(
        ..., description="Integration pattern details"
    )
    data_domains: list[DataDomain] = Field(
        default_factory=list,
        description="Data domains available for exchange",
    )
    documentation_url: str | None = Field(
        None, description="Link to vendor API documentation"
    )
    typical_customers: list[str] = Field(
        default_factory=list,
        description="Types of organizations using this system",
    )


# ---------------------------------------------------------------------------
# Readiness assessment models
# ---------------------------------------------------------------------------


class CapabilityReadiness(BaseModel):
    """Readiness status for a single platform capability."""

    capability: str = Field(..., description="Capability name")
    status: ReadinessStatus = Field(..., description="Implementation status")
    description: str = Field(..., description="What this capability provides")
    coverage_pct: float = Field(
        0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of capability implemented",
    )
    gap_description: str | None = Field(
        None,
        description="Description of remaining gap if not fully implemented",
    )
    estimated_effort_weeks: float = Field(
        0.0, description="Effort to fill the gap (in engineer-weeks)"
    )


class ReadinessAssessment(BaseModel):
    """Integration readiness assessment for a target system."""

    system: IntegrationSystem
    display_name: str
    overall_readiness_pct: float = Field(
        0.0,
        ge=0.0,
        le=100.0,
        description="Overall readiness percentage",
    )
    capabilities: list[CapabilityReadiness] = Field(
        default_factory=list,
        description="Per-capability readiness breakdown",
    )
    blockers: list[str] = Field(
        default_factory=list,
        description="Blocking issues for this integration",
    )
    prerequisites: list[str] = Field(
        default_factory=list,
        description="Prerequisites that must be completed first",
    )
    recommended_phase: RoadmapPhase = Field(
        ..., description="Recommended implementation phase"
    )


# ---------------------------------------------------------------------------
# Roadmap models
# ---------------------------------------------------------------------------


class EffortEstimate(BaseModel):
    """Effort estimation for an integration."""

    system: IntegrationSystem
    display_name: str
    phase: RoadmapPhase
    total_weeks: int = Field(
        ..., description="Total calendar weeks to complete"
    )
    engineering_headcount: int = Field(
        ..., description="Number of engineers required"
    )
    engineer_weeks: int = Field(
        ..., description="Total engineer-weeks of effort"
    )
    tasks: list[str] = Field(
        default_factory=list, description="Key implementation tasks"
    )
    risks: list[str] = Field(
        default_factory=list, description="Key implementation risks"
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Dependencies on other integrations or capabilities",
    )


class RoadmapMilestone(BaseModel):
    """A milestone within a roadmap phase."""

    name: str = Field(..., description="Milestone name")
    description: str = Field(..., description="What this milestone delivers")
    target_week: int = Field(
        ..., description="Target completion (week number within phase)"
    )
    deliverables: list[str] = Field(
        default_factory=list, description="Concrete deliverables"
    )


class RoadmapPhaseDetail(BaseModel):
    """Detailed information about a roadmap phase."""

    phase: RoadmapPhase
    title: str = Field(..., description="Phase title")
    description: str = Field(..., description="Phase description")
    systems: list[IntegrationSystem] = Field(
        ..., description="Systems included in this phase"
    )
    rationale: str = Field(
        ..., description="Why these systems are in this phase"
    )
    total_weeks: int = Field(
        ..., description="Total calendar weeks for this phase"
    )
    total_engineer_weeks: int = Field(
        ..., description="Total engineer-weeks for this phase"
    )
    milestones: list[RoadmapMilestone] = Field(
        default_factory=list, description="Phase milestones"
    )
    effort_estimates: list[EffortEstimate] = Field(
        default_factory=list,
        description="Per-system effort estimates in this phase",
    )


class IntegrationRoadmap(BaseModel):
    """Complete phased integration roadmap."""

    generated_at: datetime
    total_systems: int = Field(
        ..., description="Total number of target systems"
    )
    total_weeks: int = Field(
        ..., description="Total weeks across all phases"
    )
    total_engineer_weeks: int = Field(
        ..., description="Total engineer-weeks across all phases"
    )
    phases: list[RoadmapPhaseDetail] = Field(
        default_factory=list, description="Phased delivery details"
    )


# ---------------------------------------------------------------------------
# Data mapping models
# ---------------------------------------------------------------------------


class FieldMapping(BaseModel):
    """Mapping between a platform field and a target system field."""

    platform_field: str = Field(
        ..., description="Platform schema field path"
    )
    platform_type: str = Field(
        ..., description="Platform field data type"
    )
    target_field: str = Field(
        ..., description="Target system field path"
    )
    target_type: str = Field(
        ..., description="Target system field data type"
    )
    direction: FieldMappingDirection = Field(
        ..., description="Mapping direction"
    )
    transform: str | None = Field(
        None, description="Transformation logic (if any)"
    )
    required: bool = Field(
        False, description="Whether this mapping is required"
    )
    notes: str | None = Field(None, description="Additional mapping notes")


class DataMappingTemplate(BaseModel):
    """Data mapping template between platform and a target system."""

    system: IntegrationSystem
    display_name: str
    data_domain: str = Field(
        ..., description="Data domain being mapped"
    )
    source_format: DataFormat = Field(
        ..., description="Source data format"
    )
    target_format: DataFormat = Field(
        ..., description="Target data format"
    )
    field_mappings: list[FieldMapping] = Field(
        default_factory=list, description="Individual field mappings"
    )
    unmapped_source_fields: list[str] = Field(
        default_factory=list,
        description="Source fields with no target mapping",
    )
    unmapped_target_fields: list[str] = Field(
        default_factory=list,
        description="Target fields with no source mapping",
    )
    mapping_coverage_pct: float = Field(
        0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of target fields mapped",
    )


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------


class IntegrationListResponse(BaseModel):
    """Response for listing all target integrations."""

    total: int = Field(..., description="Total number of integrations")
    integrations: list[IntegrationSpec] = Field(
        default_factory=list, description="All integration specifications"
    )


class IntegrationSummary(BaseModel):
    """Summary of overall integration status."""

    generated_at: datetime
    total_systems: int = Field(
        ..., description="Total target systems"
    )
    systems_by_category: dict[str, int] = Field(
        default_factory=dict,
        description="Count of systems by category",
    )
    average_readiness_pct: float = Field(
        0.0,
        description="Average readiness across all systems",
    )
    systems_by_phase: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Systems grouped by roadmap phase",
    )
    total_effort_weeks: int = Field(
        0, description="Total engineer-weeks across all integrations"
    )
    total_calendar_weeks: int = Field(
        0, description="Total calendar weeks to complete all phases"
    )
    highest_readiness_system: str | None = Field(
        None, description="System with highest readiness"
    )
    lowest_readiness_system: str | None = Field(
        None, description="System with lowest readiness"
    )
    implemented_capabilities: list[str] = Field(
        default_factory=list,
        description="Capabilities already implemented across the platform",
    )
    gaps_requiring_development: list[str] = Field(
        default_factory=list,
        description="Capabilities requiring development effort",
    )
