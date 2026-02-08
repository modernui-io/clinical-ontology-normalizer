"""Pydantic schemas for Network Segmentation Policy (CISO-5).

Provides request/response models for the network segmentation API including:
- Network zones (DMZ, APPLICATION, DATA, MANAGEMENT)
- Zone traffic policies with protocol/port/direction controls
- Zero-trust traffic validation
- Firewall rule generation (iptables/nftables)
- Service-to-zone topology mapping
- HIPAA network compliance audit
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================


class NetworkZone(str, Enum):
    """Network segmentation zones (4-tier architecture)."""

    DMZ = "DMZ"
    APPLICATION = "APPLICATION"
    DATA = "DATA"
    MANAGEMENT = "MANAGEMENT"


class Protocol(str, Enum):
    """Network protocols."""

    TCP = "TCP"
    UDP = "UDP"
    HTTPS = "HTTPS"
    TLS = "TLS"
    ICMP = "ICMP"


class TrafficDirection(str, Enum):
    """Traffic flow direction."""

    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    BOTH = "BOTH"


class LoggingLevel(str, Enum):
    """Logging verbosity for traffic policies."""

    NONE = "NONE"
    BASIC = "BASIC"
    DETAILED = "DETAILED"
    FULL = "FULL"


class ComplianceStatus(str, Enum):
    """Compliance check result status."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class FirewallFormat(str, Enum):
    """Firewall rule output format."""

    IPTABLES = "iptables"
    NFTABLES = "nftables"


class RuleAction(str, Enum):
    """Firewall rule action."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    LOG = "LOG"


# ============================================================================
# Zone Models
# ============================================================================


class ZoneDefinition(BaseModel):
    """Definition of a network zone."""

    zone: NetworkZone = Field(..., description="Zone identifier")
    name: str = Field(..., description="Human-readable zone name")
    description: str = Field(..., description="Zone purpose and scope")
    cidr_range: str = Field(..., description="CIDR range for the zone")
    vlan_id: int = Field(..., description="VLAN identifier")
    security_level: int = Field(
        ..., ge=0, le=100, description="Security level (0=lowest, 100=highest)"
    )
    services: list[str] = Field(
        default_factory=list, description="Services deployed in this zone"
    )
    allowed_inbound_zones: list[NetworkZone] = Field(
        default_factory=list,
        description="Zones allowed to send traffic to this zone",
    )
    allowed_outbound_zones: list[NetworkZone] = Field(
        default_factory=list,
        description="Zones this zone can send traffic to",
    )
    requires_encryption: bool = Field(
        True, description="Whether all traffic must be encrypted"
    )
    requires_authentication: bool = Field(
        True, description="Whether all access requires authentication"
    )
    monitoring_enabled: bool = Field(
        True, description="Whether network monitoring is active"
    )


class ZoneListResponse(BaseModel):
    """Response containing all network zones."""

    zones: list[ZoneDefinition] = Field(..., description="All defined zones")
    total_zones: int = Field(..., description="Total number of zones")
    timestamp: datetime = Field(..., description="Response timestamp")


class ZoneDetailResponse(BaseModel):
    """Detailed zone information with associated policies."""

    zone: ZoneDefinition = Field(..., description="Zone definition")
    inbound_policies: list[TrafficPolicy] = Field(
        default_factory=list, description="Policies for inbound traffic"
    )
    outbound_policies: list[TrafficPolicy] = Field(
        default_factory=list, description="Policies for outbound traffic"
    )
    service_count: int = Field(0, description="Number of services in this zone")
    timestamp: datetime = Field(..., description="Response timestamp")


# ============================================================================
# Traffic Policy Models
# ============================================================================


class TrafficPolicy(BaseModel):
    """Policy governing traffic between two zones."""

    policy_id: str = Field(..., description="Unique policy identifier")
    name: str = Field(..., description="Human-readable policy name")
    source_zone: NetworkZone = Field(..., description="Source zone")
    destination_zone: NetworkZone = Field(..., description="Destination zone")
    allowed_protocols: list[Protocol] = Field(
        ..., description="Allowed protocols"
    )
    allowed_ports: list[int] = Field(..., description="Allowed port numbers")
    direction: TrafficDirection = Field(..., description="Traffic direction")
    authentication_required: bool = Field(
        True, description="Whether authentication is required"
    )
    encryption_required: bool = Field(
        True, description="Whether encryption is required"
    )
    logging_level: LoggingLevel = Field(
        LoggingLevel.DETAILED, description="Logging verbosity"
    )
    description: str = Field("", description="Policy description")
    enabled: bool = Field(True, description="Whether policy is active")
    hipaa_relevant: bool = Field(
        False, description="Whether policy is HIPAA-relevant"
    )


class PolicyListResponse(BaseModel):
    """Response containing all traffic policies."""

    policies: list[TrafficPolicy] = Field(..., description="All traffic policies")
    total_policies: int = Field(..., description="Total number of policies")
    timestamp: datetime = Field(..., description="Response timestamp")


# ============================================================================
# Traffic Validation Models
# ============================================================================


class TrafficValidationRequest(BaseModel):
    """Request to validate whether traffic is allowed."""

    source_zone: NetworkZone = Field(..., description="Source zone")
    destination_zone: NetworkZone = Field(..., description="Destination zone")
    protocol: Protocol = Field(..., description="Protocol being used")
    port: int = Field(..., ge=1, le=65535, description="Target port number")


class TrafficValidationResponse(BaseModel):
    """Response indicating whether traffic is allowed."""

    allowed: bool = Field(..., description="Whether traffic is permitted")
    source_zone: NetworkZone = Field(..., description="Source zone evaluated")
    destination_zone: NetworkZone = Field(
        ..., description="Destination zone evaluated"
    )
    protocol: Protocol = Field(..., description="Protocol evaluated")
    port: int = Field(..., description="Port evaluated")
    matching_policy: Optional[str] = Field(
        None, description="Policy that matched (if allowed)"
    )
    reason: str = Field(..., description="Explanation of the decision")
    authentication_required: bool = Field(
        False, description="Whether auth is required for this traffic"
    )
    encryption_required: bool = Field(
        False, description="Whether encryption is required"
    )
    logging_level: LoggingLevel = Field(
        LoggingLevel.NONE, description="Required logging level"
    )
    timestamp: datetime = Field(..., description="Evaluation timestamp")


# ============================================================================
# Firewall Rule Models
# ============================================================================


class FirewallRule(BaseModel):
    """A single generated firewall rule."""

    rule_id: str = Field(..., description="Rule identifier")
    chain: str = Field(..., description="Firewall chain (INPUT/OUTPUT/FORWARD)")
    source: str = Field(..., description="Source address/CIDR")
    destination: str = Field(..., description="Destination address/CIDR")
    protocol: str = Field(..., description="Protocol")
    port: int = Field(..., description="Port number")
    action: RuleAction = Field(..., description="Rule action (ALLOW/DENY)")
    comment: str = Field("", description="Rule comment/description")
    logging_enabled: bool = Field(False, description="Whether to log matches")
    order: int = Field(0, description="Rule processing order")


class FirewallRuleSet(BaseModel):
    """Complete set of generated firewall rules."""

    format: FirewallFormat = Field(..., description="Output format")
    rules: list[FirewallRule] = Field(..., description="Generated rules")
    total_rules: int = Field(..., description="Total number of rules")
    generated_at: datetime = Field(..., description="Generation timestamp")
    raw_rules: list[str] = Field(
        default_factory=list,
        description="Raw firewall commands (iptables/nftables syntax)",
    )
    default_policy: RuleAction = Field(
        RuleAction.DENY, description="Default policy for unmatched traffic"
    )


# ============================================================================
# Topology Models
# ============================================================================


class ServiceMapping(BaseModel):
    """Mapping of a service to its network zone."""

    service_name: str = Field(..., description="Service name")
    zone: NetworkZone = Field(..., description="Zone the service runs in")
    port: int = Field(..., description="Primary service port")
    protocol: Protocol = Field(..., description="Primary protocol")
    description: str = Field("", description="Service description")
    requires_external_access: bool = Field(
        False, description="Whether service needs internet access"
    )
    data_classification: str = Field(
        "internal", description="Data sensitivity classification"
    )


class NetworkTopology(BaseModel):
    """Complete service-to-zone topology mapping."""

    services: list[ServiceMapping] = Field(
        ..., description="All service mappings"
    )
    total_services: int = Field(..., description="Total number of services")
    zones_utilized: list[NetworkZone] = Field(
        ..., description="Zones with active services"
    )
    timestamp: datetime = Field(..., description="Topology snapshot timestamp")


# ============================================================================
# Compliance Audit Models
# ============================================================================


class ComplianceCheck(BaseModel):
    """Individual compliance check result."""

    check_id: str = Field(..., description="Check identifier")
    name: str = Field(..., description="Check name")
    description: str = Field(..., description="What is being checked")
    status: ComplianceStatus = Field(..., description="Check result")
    category: str = Field(..., description="Compliance category")
    finding: str = Field("", description="Detailed finding description")
    recommendation: str = Field("", description="Remediation recommendation")
    hipaa_reference: str = Field(
        "", description="HIPAA regulation reference"
    )
    severity: str = Field("medium", description="Finding severity")


class ComplianceAuditReport(BaseModel):
    """Network compliance audit report."""

    audit_id: str = Field(..., description="Audit identifier")
    timestamp: datetime = Field(..., description="Audit timestamp")
    overall_score: int = Field(
        ..., ge=0, le=100, description="Overall compliance score"
    )
    overall_status: ComplianceStatus = Field(
        ..., description="Overall compliance status"
    )
    total_checks: int = Field(..., description="Total checks performed")
    passed_checks: int = Field(..., description="Number of passed checks")
    warning_checks: int = Field(..., description="Number of warning checks")
    failed_checks: int = Field(..., description="Number of failed checks")
    checks: list[ComplianceCheck] = Field(
        ..., description="Individual check results"
    )
    hipaa_compliant: bool = Field(
        ..., description="Whether network meets HIPAA requirements"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Top remediation recommendations",
    )
    zones_audited: list[NetworkZone] = Field(
        ..., description="Zones included in audit"
    )


# Forward reference resolution — ZoneDetailResponse references TrafficPolicy
# which is defined above, so we rebuild it.
ZoneDetailResponse.model_rebuild()
