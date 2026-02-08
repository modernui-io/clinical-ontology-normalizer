"""Network Segmentation Service (CISO-5).

Defines a 4-tier network zone architecture and enforces traffic policies
for HIPAA-compliant clinical trial infrastructure:

- DMZ:         Load balancer, WAF, public endpoints
- APPLICATION: FastAPI backend, Next.js frontend, background workers
- DATA:        PostgreSQL, Redis, Neo4j
- MANAGEMENT:  Monitoring, logging, admin tools

Provides:
- Zone definitions with CIDR/VLAN assignments
- Inter-zone traffic policies (20+ rules)
- Zero-trust traffic validation
- iptables / nftables firewall rule generation
- Service-to-zone topology mapping
- HIPAA network isolation compliance audit
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from app.schemas.network_segmentation import (
    ComplianceAuditReport,
    ComplianceCheck,
    ComplianceStatus,
    FirewallFormat,
    FirewallRule,
    FirewallRuleSet,
    LoggingLevel,
    NetworkTopology,
    NetworkZone,
    PolicyListResponse,
    Protocol,
    RuleAction,
    ServiceMapping,
    TrafficDirection,
    TrafficPolicy,
    TrafficValidationRequest,
    TrafficValidationResponse,
    ZoneDefinition,
    ZoneDetailResponse,
    ZoneListResponse,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Zone Definitions
# ============================================================================

ZONE_DEFINITIONS: dict[NetworkZone, ZoneDefinition] = {
    NetworkZone.DMZ: ZoneDefinition(
        zone=NetworkZone.DMZ,
        name="Demilitarized Zone",
        description=(
            "Internet-facing zone hosting load balancers, WAF, and public "
            "API gateway. All external traffic terminates here before "
            "being proxied to the application tier."
        ),
        cidr_range="10.0.1.0/24",
        vlan_id=100,
        security_level=30,
        services=["load_balancer", "waf", "api_gateway", "cdn_edge"],
        allowed_inbound_zones=[],
        allowed_outbound_zones=[NetworkZone.APPLICATION],
        requires_encryption=True,
        requires_authentication=False,
        monitoring_enabled=True,
    ),
    NetworkZone.APPLICATION: ZoneDefinition(
        zone=NetworkZone.APPLICATION,
        name="Application Zone",
        description=(
            "Core application tier hosting FastAPI backend, Next.js "
            "frontend, and background workers. Receives traffic from DMZ "
            "and connects to data stores in the DATA zone."
        ),
        cidr_range="10.0.2.0/24",
        vlan_id=200,
        security_level=60,
        services=[
            "fastapi_backend",
            "nextjs_frontend",
            "celery_workers",
            "nlp_pipeline",
        ],
        allowed_inbound_zones=[NetworkZone.DMZ, NetworkZone.MANAGEMENT],
        allowed_outbound_zones=[NetworkZone.DATA],
        requires_encryption=True,
        requires_authentication=True,
        monitoring_enabled=True,
    ),
    NetworkZone.DATA: ZoneDefinition(
        zone=NetworkZone.DATA,
        name="Data Zone",
        description=(
            "Highly restricted zone hosting databases and data stores. "
            "Contains PHI/PII and clinical trial data. No outbound "
            "traffic allowed. Only APPLICATION zone may connect."
        ),
        cidr_range="10.0.3.0/24",
        vlan_id=300,
        security_level=95,
        services=["postgresql", "redis", "neo4j", "data_backup"],
        allowed_inbound_zones=[NetworkZone.APPLICATION, NetworkZone.MANAGEMENT],
        allowed_outbound_zones=[],
        requires_encryption=True,
        requires_authentication=True,
        monitoring_enabled=True,
    ),
    NetworkZone.MANAGEMENT: ZoneDefinition(
        zone=NetworkZone.MANAGEMENT,
        name="Management Zone",
        description=(
            "Operations zone for monitoring, logging, and administration. "
            "Has read-only access to all zones for health checks and "
            "metrics collection. Tightly access-controlled."
        ),
        cidr_range="10.0.4.0/24",
        vlan_id=400,
        security_level=80,
        services=[
            "prometheus",
            "grafana",
            "elk_stack",
            "admin_console",
            "alertmanager",
        ],
        allowed_inbound_zones=[],
        allowed_outbound_zones=[
            NetworkZone.DMZ,
            NetworkZone.APPLICATION,
            NetworkZone.DATA,
        ],
        requires_encryption=True,
        requires_authentication=True,
        monitoring_enabled=True,
    ),
}


# ============================================================================
# Traffic Policies (20+ rules)
# ============================================================================

def _build_default_policies() -> list[TrafficPolicy]:
    """Build the default set of 24 traffic policies."""
    return [
        # --- DMZ -> APPLICATION ---
        TrafficPolicy(
            policy_id="POL-001",
            name="DMZ to APP HTTPS",
            source_zone=NetworkZone.DMZ,
            destination_zone=NetworkZone.APPLICATION,
            allowed_protocols=[Protocol.HTTPS],
            allowed_ports=[443],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=False,
            encryption_required=True,
            logging_level=LoggingLevel.DETAILED,
            description="Allow HTTPS traffic from DMZ to application servers",
            hipaa_relevant=True,
        ),
        TrafficPolicy(
            policy_id="POL-002",
            name="DMZ to APP Health Check",
            source_zone=NetworkZone.DMZ,
            destination_zone=NetworkZone.APPLICATION,
            allowed_protocols=[Protocol.TCP],
            allowed_ports=[8000],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=False,
            encryption_required=True,
            logging_level=LoggingLevel.BASIC,
            description="Allow health check probes from load balancer to backend",
            hipaa_relevant=False,
        ),
        # --- APPLICATION -> DATA ---
        TrafficPolicy(
            policy_id="POL-003",
            name="APP to PostgreSQL",
            source_zone=NetworkZone.APPLICATION,
            destination_zone=NetworkZone.DATA,
            allowed_protocols=[Protocol.TCP],
            allowed_ports=[5432],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.FULL,
            description="Allow application to connect to PostgreSQL",
            hipaa_relevant=True,
        ),
        TrafficPolicy(
            policy_id="POL-004",
            name="APP to Redis",
            source_zone=NetworkZone.APPLICATION,
            destination_zone=NetworkZone.DATA,
            allowed_protocols=[Protocol.TCP],
            allowed_ports=[6379],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.DETAILED,
            description="Allow application to connect to Redis cache/queue",
            hipaa_relevant=True,
        ),
        TrafficPolicy(
            policy_id="POL-005",
            name="APP to Neo4j Bolt",
            source_zone=NetworkZone.APPLICATION,
            destination_zone=NetworkZone.DATA,
            allowed_protocols=[Protocol.TCP],
            allowed_ports=[7687],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.DETAILED,
            description="Allow application to connect to Neo4j via Bolt protocol",
            hipaa_relevant=True,
        ),
        # --- BLOCK: DMZ -> DATA (critical security rule) ---
        TrafficPolicy(
            policy_id="POL-006",
            name="DENY DMZ to DATA",
            source_zone=NetworkZone.DMZ,
            destination_zone=NetworkZone.DATA,
            allowed_protocols=[],
            allowed_ports=[],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.FULL,
            description="Block all direct traffic from DMZ to DATA zone",
            enabled=True,
            hipaa_relevant=True,
        ),
        # --- BLOCK: DATA outbound ---
        TrafficPolicy(
            policy_id="POL-007",
            name="DENY DATA Outbound",
            source_zone=NetworkZone.DATA,
            destination_zone=NetworkZone.DMZ,
            allowed_protocols=[],
            allowed_ports=[],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.FULL,
            description="Block all outbound traffic from DATA zone to DMZ",
            hipaa_relevant=True,
        ),
        TrafficPolicy(
            policy_id="POL-008",
            name="DENY DATA to APP",
            source_zone=NetworkZone.DATA,
            destination_zone=NetworkZone.APPLICATION,
            allowed_protocols=[],
            allowed_ports=[],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.FULL,
            description="Block all outbound traffic from DATA zone to APPLICATION",
            hipaa_relevant=True,
        ),
        # --- MANAGEMENT -> all zones ---
        TrafficPolicy(
            policy_id="POL-009",
            name="MGMT to DMZ Monitoring",
            source_zone=NetworkZone.MANAGEMENT,
            destination_zone=NetworkZone.DMZ,
            allowed_protocols=[Protocol.TCP, Protocol.ICMP],
            allowed_ports=[443, 9090, 9100],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.BASIC,
            description="Allow management to monitor DMZ services",
            hipaa_relevant=False,
        ),
        TrafficPolicy(
            policy_id="POL-010",
            name="MGMT to APP Monitoring",
            source_zone=NetworkZone.MANAGEMENT,
            destination_zone=NetworkZone.APPLICATION,
            allowed_protocols=[Protocol.TCP, Protocol.ICMP],
            allowed_ports=[8000, 9090, 9100, 3000],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.BASIC,
            description="Allow management to monitor application services",
            hipaa_relevant=False,
        ),
        TrafficPolicy(
            policy_id="POL-011",
            name="MGMT to DATA Monitoring",
            source_zone=NetworkZone.MANAGEMENT,
            destination_zone=NetworkZone.DATA,
            allowed_protocols=[Protocol.TCP],
            allowed_ports=[5432, 6379, 7687, 9100],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.DETAILED,
            description="Allow management to monitor data stores",
            hipaa_relevant=True,
        ),
        # --- Intra-zone policies ---
        TrafficPolicy(
            policy_id="POL-012",
            name="APP Internal Communication",
            source_zone=NetworkZone.APPLICATION,
            destination_zone=NetworkZone.APPLICATION,
            allowed_protocols=[Protocol.TCP],
            allowed_ports=[8000, 3000, 5555],
            direction=TrafficDirection.BOTH,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.BASIC,
            description="Allow internal communication between application services",
            hipaa_relevant=False,
        ),
        TrafficPolicy(
            policy_id="POL-013",
            name="MGMT Internal Communication",
            source_zone=NetworkZone.MANAGEMENT,
            destination_zone=NetworkZone.MANAGEMENT,
            allowed_protocols=[Protocol.TCP],
            allowed_ports=[9090, 9093, 5601, 9200, 3000],
            direction=TrafficDirection.BOTH,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.BASIC,
            description="Allow internal communication between management services",
            hipaa_relevant=False,
        ),
        # --- Additional security policies ---
        TrafficPolicy(
            policy_id="POL-014",
            name="DENY DMZ to MGMT",
            source_zone=NetworkZone.DMZ,
            destination_zone=NetworkZone.MANAGEMENT,
            allowed_protocols=[],
            allowed_ports=[],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.FULL,
            description="Block all direct traffic from DMZ to MANAGEMENT zone",
            hipaa_relevant=True,
        ),
        TrafficPolicy(
            policy_id="POL-015",
            name="DENY DATA to MGMT",
            source_zone=NetworkZone.DATA,
            destination_zone=NetworkZone.MANAGEMENT,
            allowed_protocols=[],
            allowed_ports=[],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.FULL,
            description="Block all outbound traffic from DATA to MANAGEMENT",
            hipaa_relevant=True,
        ),
        TrafficPolicy(
            policy_id="POL-016",
            name="DMZ TLS Termination",
            source_zone=NetworkZone.DMZ,
            destination_zone=NetworkZone.DMZ,
            allowed_protocols=[Protocol.TLS, Protocol.HTTPS],
            allowed_ports=[443, 8443],
            direction=TrafficDirection.INBOUND,
            authentication_required=False,
            encryption_required=True,
            logging_level=LoggingLevel.DETAILED,
            description="Allow external TLS connections to DMZ",
            hipaa_relevant=True,
        ),
        TrafficPolicy(
            policy_id="POL-017",
            name="APP to APP Celery",
            source_zone=NetworkZone.APPLICATION,
            destination_zone=NetworkZone.APPLICATION,
            allowed_protocols=[Protocol.TCP],
            allowed_ports=[5555, 6379],
            direction=TrafficDirection.BOTH,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.BASIC,
            description="Allow Celery worker communication within APP zone",
            hipaa_relevant=False,
        ),
        TrafficPolicy(
            policy_id="POL-018",
            name="MGMT Syslog Collection",
            source_zone=NetworkZone.MANAGEMENT,
            destination_zone=NetworkZone.APPLICATION,
            allowed_protocols=[Protocol.UDP, Protocol.TCP],
            allowed_ports=[514, 5044],
            direction=TrafficDirection.INBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.DETAILED,
            description="Allow log shipping from APP to MANAGEMENT (ELK)",
            hipaa_relevant=True,
        ),
        TrafficPolicy(
            policy_id="POL-019",
            name="DENY APP to DMZ",
            source_zone=NetworkZone.APPLICATION,
            destination_zone=NetworkZone.DMZ,
            allowed_protocols=[],
            allowed_ports=[],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.FULL,
            description="Block outbound from APPLICATION to DMZ (no reverse proxy)",
            hipaa_relevant=True,
        ),
        TrafficPolicy(
            policy_id="POL-020",
            name="DENY APP to MGMT",
            source_zone=NetworkZone.APPLICATION,
            destination_zone=NetworkZone.MANAGEMENT,
            allowed_protocols=[],
            allowed_ports=[],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.FULL,
            description="Block direct outbound from APPLICATION to MANAGEMENT",
            hipaa_relevant=True,
        ),
        TrafficPolicy(
            policy_id="POL-021",
            name="DATA Replication",
            source_zone=NetworkZone.DATA,
            destination_zone=NetworkZone.DATA,
            allowed_protocols=[Protocol.TCP],
            allowed_ports=[5432, 6379, 7687],
            direction=TrafficDirection.BOTH,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.DETAILED,
            description="Allow database replication within DATA zone",
            hipaa_relevant=True,
        ),
        TrafficPolicy(
            policy_id="POL-022",
            name="MGMT SSH Access",
            source_zone=NetworkZone.MANAGEMENT,
            destination_zone=NetworkZone.APPLICATION,
            allowed_protocols=[Protocol.TCP],
            allowed_ports=[22],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.FULL,
            description="Allow SSH from MANAGEMENT to APPLICATION for admin access",
            hipaa_relevant=False,
        ),
        TrafficPolicy(
            policy_id="POL-023",
            name="MGMT SSH to DATA",
            source_zone=NetworkZone.MANAGEMENT,
            destination_zone=NetworkZone.DATA,
            allowed_protocols=[Protocol.TCP],
            allowed_ports=[22],
            direction=TrafficDirection.OUTBOUND,
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.FULL,
            description="Allow SSH from MANAGEMENT to DATA for database admin",
            hipaa_relevant=True,
        ),
        TrafficPolicy(
            policy_id="POL-024",
            name="DMZ Rate Limiting",
            source_zone=NetworkZone.DMZ,
            destination_zone=NetworkZone.DMZ,
            allowed_protocols=[Protocol.TCP],
            allowed_ports=[80, 443],
            direction=TrafficDirection.INBOUND,
            authentication_required=False,
            encryption_required=True,
            logging_level=LoggingLevel.DETAILED,
            description="Rate-limited external HTTP/HTTPS access to DMZ",
            hipaa_relevant=False,
        ),
    ]


DEFAULT_POLICIES = _build_default_policies()


# ============================================================================
# Service Topology
# ============================================================================

DEFAULT_SERVICE_MAPPINGS: list[ServiceMapping] = [
    ServiceMapping(
        service_name="nginx_load_balancer",
        zone=NetworkZone.DMZ,
        port=443,
        protocol=Protocol.HTTPS,
        description="Nginx reverse proxy and load balancer",
        requires_external_access=True,
        data_classification="public",
    ),
    ServiceMapping(
        service_name="waf",
        zone=NetworkZone.DMZ,
        port=443,
        protocol=Protocol.HTTPS,
        description="Web Application Firewall",
        requires_external_access=True,
        data_classification="public",
    ),
    ServiceMapping(
        service_name="fastapi_backend",
        zone=NetworkZone.APPLICATION,
        port=8000,
        protocol=Protocol.TCP,
        description="FastAPI clinical ontology normalizer backend",
        requires_external_access=False,
        data_classification="phi",
    ),
    ServiceMapping(
        service_name="nextjs_frontend",
        zone=NetworkZone.APPLICATION,
        port=3000,
        protocol=Protocol.TCP,
        description="Next.js frontend application",
        requires_external_access=False,
        data_classification="internal",
    ),
    ServiceMapping(
        service_name="celery_worker",
        zone=NetworkZone.APPLICATION,
        port=5555,
        protocol=Protocol.TCP,
        description="Celery background task workers",
        requires_external_access=False,
        data_classification="phi",
    ),
    ServiceMapping(
        service_name="nlp_pipeline",
        zone=NetworkZone.APPLICATION,
        port=8001,
        protocol=Protocol.TCP,
        description="NLP extraction and entity recognition pipeline",
        requires_external_access=False,
        data_classification="phi",
    ),
    ServiceMapping(
        service_name="postgresql",
        zone=NetworkZone.DATA,
        port=5432,
        protocol=Protocol.TCP,
        description="PostgreSQL primary database (OMOP CDM)",
        requires_external_access=False,
        data_classification="phi",
    ),
    ServiceMapping(
        service_name="redis",
        zone=NetworkZone.DATA,
        port=6379,
        protocol=Protocol.TCP,
        description="Redis cache and job queue",
        requires_external_access=False,
        data_classification="phi",
    ),
    ServiceMapping(
        service_name="neo4j",
        zone=NetworkZone.DATA,
        port=7687,
        protocol=Protocol.TCP,
        description="Neo4j knowledge graph database",
        requires_external_access=False,
        data_classification="phi",
    ),
    ServiceMapping(
        service_name="prometheus",
        zone=NetworkZone.MANAGEMENT,
        port=9090,
        protocol=Protocol.TCP,
        description="Prometheus metrics collection",
        requires_external_access=False,
        data_classification="internal",
    ),
    ServiceMapping(
        service_name="grafana",
        zone=NetworkZone.MANAGEMENT,
        port=3000,
        protocol=Protocol.TCP,
        description="Grafana monitoring dashboards",
        requires_external_access=False,
        data_classification="internal",
    ),
    ServiceMapping(
        service_name="elasticsearch",
        zone=NetworkZone.MANAGEMENT,
        port=9200,
        protocol=Protocol.TCP,
        description="Elasticsearch log storage",
        requires_external_access=False,
        data_classification="internal",
    ),
    ServiceMapping(
        service_name="kibana",
        zone=NetworkZone.MANAGEMENT,
        port=5601,
        protocol=Protocol.TCP,
        description="Kibana log visualization",
        requires_external_access=False,
        data_classification="internal",
    ),
    ServiceMapping(
        service_name="alertmanager",
        zone=NetworkZone.MANAGEMENT,
        port=9093,
        protocol=Protocol.TCP,
        description="Prometheus Alertmanager",
        requires_external_access=False,
        data_classification="internal",
    ),
]


# ============================================================================
# HIPAA Compliance Checks
# ============================================================================

HIPAA_COMPLIANCE_CHECKS: list[dict] = [
    {
        "check_id": "HIPAA-NET-001",
        "name": "DMZ-to-DATA isolation",
        "description": "Verify no direct path from DMZ to DATA zone exists",
        "category": "Network Isolation",
        "hipaa_reference": "45 CFR 164.312(e)(1) - Transmission Security",
        "severity": "critical",
    },
    {
        "check_id": "HIPAA-NET-002",
        "name": "DATA zone outbound restriction",
        "description": "Verify DATA zone has no outbound traffic to untrusted zones",
        "category": "Network Isolation",
        "hipaa_reference": "45 CFR 164.312(a)(1) - Access Control",
        "severity": "critical",
    },
    {
        "check_id": "HIPAA-NET-003",
        "name": "Encryption in transit",
        "description": "Verify all zones handling PHI require encryption",
        "category": "Encryption",
        "hipaa_reference": "45 CFR 164.312(e)(2)(ii) - Encryption",
        "severity": "critical",
    },
    {
        "check_id": "HIPAA-NET-004",
        "name": "Authentication on PHI access",
        "description": "Verify authentication required for PHI-containing zones",
        "category": "Access Control",
        "hipaa_reference": "45 CFR 164.312(d) - Person Authentication",
        "severity": "critical",
    },
    {
        "check_id": "HIPAA-NET-005",
        "name": "Audit logging enabled",
        "description": "Verify HIPAA-relevant traffic policies have detailed logging",
        "category": "Audit Controls",
        "hipaa_reference": "45 CFR 164.312(b) - Audit Controls",
        "severity": "high",
    },
    {
        "check_id": "HIPAA-NET-006",
        "name": "Network monitoring active",
        "description": "Verify all zones have network monitoring enabled",
        "category": "Monitoring",
        "hipaa_reference": "45 CFR 164.308(a)(1)(ii)(D) - Information System Activity Review",
        "severity": "high",
    },
    {
        "check_id": "HIPAA-NET-007",
        "name": "Minimum necessary access",
        "description": "Verify policies follow minimum necessary principle (specific ports only)",
        "category": "Access Control",
        "hipaa_reference": "45 CFR 164.502(b) - Minimum Necessary",
        "severity": "high",
    },
    {
        "check_id": "HIPAA-NET-008",
        "name": "DATA zone authentication",
        "description": "Verify DATA zone requires authentication for all access",
        "category": "Access Control",
        "hipaa_reference": "45 CFR 164.312(d) - Person Authentication",
        "severity": "critical",
    },
    {
        "check_id": "HIPAA-NET-009",
        "name": "Management zone isolation",
        "description": "Verify MANAGEMENT zone is not accessible from DMZ",
        "category": "Network Isolation",
        "hipaa_reference": "45 CFR 164.312(a)(1) - Access Control",
        "severity": "high",
    },
    {
        "check_id": "HIPAA-NET-010",
        "name": "Default deny policy",
        "description": "Verify default firewall policy is DENY for all unmatched traffic",
        "category": "Firewall",
        "hipaa_reference": "45 CFR 164.312(e)(1) - Transmission Security",
        "severity": "critical",
    },
    {
        "check_id": "HIPAA-NET-011",
        "name": "PHI data classification",
        "description": "Verify services handling PHI are classified and in appropriate zones",
        "category": "Data Classification",
        "hipaa_reference": "45 CFR 164.312(a)(2)(iv) - Encryption and Decryption",
        "severity": "high",
    },
    {
        "check_id": "HIPAA-NET-012",
        "name": "Zone VLAN separation",
        "description": "Verify each zone uses a distinct VLAN for network-level isolation",
        "category": "Network Isolation",
        "hipaa_reference": "45 CFR 164.312(e)(1) - Transmission Security",
        "severity": "medium",
    },
]


# ============================================================================
# Service
# ============================================================================


class NetworkSegmentationService:
    """Service managing network zone segmentation and traffic policies.

    Implements a 4-tier network architecture for HIPAA-compliant
    clinical trial infrastructure with zero-trust validation.
    """

    def __init__(self) -> None:
        self._zones: dict[NetworkZone, ZoneDefinition] = dict(ZONE_DEFINITIONS)
        self._policies: list[TrafficPolicy] = list(DEFAULT_POLICIES)
        self._service_mappings: list[ServiceMapping] = list(DEFAULT_SERVICE_MAPPINGS)
        logger.info(
            "NetworkSegmentationService initialized: %d zones, %d policies, %d services",
            len(self._zones),
            len(self._policies),
            len(self._service_mappings),
        )

    # ------------------------------------------------------------------
    # Zone operations
    # ------------------------------------------------------------------

    def get_zones(self) -> ZoneListResponse:
        """Return all network zone definitions."""
        zones = list(self._zones.values())
        return ZoneListResponse(
            zones=zones,
            total_zones=len(zones),
            timestamp=datetime.now(timezone.utc),
        )

    def get_zone(self, zone: NetworkZone) -> ZoneDetailResponse:
        """Return detailed info for a single zone including its policies."""
        zone_def = self._zones[zone]
        inbound = [
            p for p in self._policies
            if p.destination_zone == zone and p.source_zone != zone
        ]
        outbound = [
            p for p in self._policies
            if p.source_zone == zone and p.destination_zone != zone
        ]
        services_in_zone = [
            s for s in self._service_mappings if s.zone == zone
        ]
        return ZoneDetailResponse(
            zone=zone_def,
            inbound_policies=inbound,
            outbound_policies=outbound,
            service_count=len(services_in_zone),
            timestamp=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Policy operations
    # ------------------------------------------------------------------

    def get_policies(self) -> PolicyListResponse:
        """Return all traffic policies."""
        return PolicyListResponse(
            policies=self._policies,
            total_policies=len(self._policies),
            timestamp=datetime.now(timezone.utc),
        )

    def get_policies_for_zone(self, zone: NetworkZone) -> list[TrafficPolicy]:
        """Return all policies involving a specific zone."""
        return [
            p for p in self._policies
            if p.source_zone == zone or p.destination_zone == zone
        ]

    # ------------------------------------------------------------------
    # Zero-trust traffic validation
    # ------------------------------------------------------------------

    def validate_traffic(
        self, request: TrafficValidationRequest
    ) -> TrafficValidationResponse:
        """Check whether a specific traffic flow is allowed.

        Implements zero-trust validation: traffic is denied unless an
        explicit ALLOW policy exists with matching zone, protocol, and port.
        """
        now = datetime.now(timezone.utc)

        # Look for a matching allow policy
        for policy in self._policies:
            if not policy.enabled:
                continue
            if (
                policy.source_zone == request.source_zone
                and policy.destination_zone == request.destination_zone
            ):
                # A deny policy (empty ports/protocols) blocks traffic
                if not policy.allowed_ports and not policy.allowed_protocols:
                    return TrafficValidationResponse(
                        allowed=False,
                        source_zone=request.source_zone,
                        destination_zone=request.destination_zone,
                        protocol=request.protocol,
                        port=request.port,
                        matching_policy=policy.policy_id,
                        reason=(
                            f"Traffic blocked by explicit deny policy: "
                            f"{policy.name} ({policy.policy_id})"
                        ),
                        authentication_required=policy.authentication_required,
                        encryption_required=policy.encryption_required,
                        logging_level=policy.logging_level,
                        timestamp=now,
                    )

                # Check protocol and port match
                if (
                    request.protocol in policy.allowed_protocols
                    and request.port in policy.allowed_ports
                ):
                    return TrafficValidationResponse(
                        allowed=True,
                        source_zone=request.source_zone,
                        destination_zone=request.destination_zone,
                        protocol=request.protocol,
                        port=request.port,
                        matching_policy=policy.policy_id,
                        reason=(
                            f"Traffic allowed by policy: "
                            f"{policy.name} ({policy.policy_id})"
                        ),
                        authentication_required=policy.authentication_required,
                        encryption_required=policy.encryption_required,
                        logging_level=policy.logging_level,
                        timestamp=now,
                    )

        # Default deny
        return TrafficValidationResponse(
            allowed=False,
            source_zone=request.source_zone,
            destination_zone=request.destination_zone,
            protocol=request.protocol,
            port=request.port,
            matching_policy=None,
            reason=(
                "Traffic denied: no matching allow policy found "
                "(default deny)"
            ),
            authentication_required=True,
            encryption_required=True,
            logging_level=LoggingLevel.FULL,
            timestamp=now,
        )

    # ------------------------------------------------------------------
    # Firewall rule generation
    # ------------------------------------------------------------------

    def generate_firewall_rules(
        self,
        fmt: FirewallFormat = FirewallFormat.IPTABLES,
    ) -> FirewallRuleSet:
        """Generate firewall rules from current zone policies.

        Produces iptables or nftables syntax rules for all defined
        policies, with a default DENY policy for unmatched traffic.
        """
        rules: list[FirewallRule] = []
        raw_rules: list[str] = []
        order = 0

        for policy in self._policies:
            if not policy.enabled:
                continue

            src_cidr = self._zones[policy.source_zone].cidr_range
            dst_cidr = self._zones[policy.destination_zone].cidr_range

            # Deny policies (empty ports)
            if not policy.allowed_ports:
                order += 1
                rule = FirewallRule(
                    rule_id=f"FW-{order:04d}",
                    chain="FORWARD",
                    source=src_cidr,
                    destination=dst_cidr,
                    protocol="all",
                    port=0,
                    action=RuleAction.DENY,
                    comment=policy.description,
                    logging_enabled=policy.logging_level != LoggingLevel.NONE,
                    order=order,
                )
                rules.append(rule)
                if fmt == FirewallFormat.IPTABLES:
                    raw = (
                        f"iptables -A FORWARD -s {src_cidr} -d {dst_cidr} "
                        f"-j DROP -m comment --comment \"{policy.name}\""
                    )
                else:
                    raw = (
                        f"nft add rule inet filter forward "
                        f"ip saddr {src_cidr} ip daddr {dst_cidr} drop "
                        f"comment \"{policy.name}\""
                    )
                raw_rules.append(raw)
                continue

            for port in policy.allowed_ports:
                for proto in policy.allowed_protocols:
                    order += 1
                    proto_str = "tcp" if proto in (
                        Protocol.TCP, Protocol.HTTPS, Protocol.TLS
                    ) else proto.value.lower()

                    rule = FirewallRule(
                        rule_id=f"FW-{order:04d}",
                        chain="FORWARD",
                        source=src_cidr,
                        destination=dst_cidr,
                        protocol=proto_str,
                        port=port,
                        action=RuleAction.ALLOW,
                        comment=policy.description,
                        logging_enabled=policy.logging_level != LoggingLevel.NONE,
                        order=order,
                    )
                    rules.append(rule)

                    if fmt == FirewallFormat.IPTABLES:
                        raw = (
                            f"iptables -A FORWARD -s {src_cidr} -d {dst_cidr} "
                            f"-p {proto_str} --dport {port} "
                            f"-j ACCEPT -m comment --comment \"{policy.name}\""
                        )
                    else:
                        raw = (
                            f"nft add rule inet filter forward "
                            f"ip saddr {src_cidr} ip daddr {dst_cidr} "
                            f"{proto_str} dport {port} accept "
                            f"comment \"{policy.name}\""
                        )
                    raw_rules.append(raw)

        # Default deny rule at the end
        order += 1
        default_deny = FirewallRule(
            rule_id=f"FW-{order:04d}",
            chain="FORWARD",
            source="0.0.0.0/0",
            destination="0.0.0.0/0",
            protocol="all",
            port=0,
            action=RuleAction.DENY,
            comment="Default deny - drop all unmatched traffic",
            logging_enabled=True,
            order=order,
        )
        rules.append(default_deny)
        if fmt == FirewallFormat.IPTABLES:
            raw_rules.append(
                "iptables -A FORWARD -j DROP "
                "-m comment --comment \"Default deny\""
            )
        else:
            raw_rules.append(
                "nft add rule inet filter forward drop "
                "comment \"Default deny\""
            )

        return FirewallRuleSet(
            format=fmt,
            rules=rules,
            total_rules=len(rules),
            generated_at=datetime.now(timezone.utc),
            raw_rules=raw_rules,
            default_policy=RuleAction.DENY,
        )

    # ------------------------------------------------------------------
    # Topology
    # ------------------------------------------------------------------

    def get_topology(self) -> NetworkTopology:
        """Return the service-to-zone topology mapping."""
        zones_used = sorted(
            set(s.zone for s in self._service_mappings),
            key=lambda z: z.value,
        )
        return NetworkTopology(
            services=self._service_mappings,
            total_services=len(self._service_mappings),
            zones_utilized=zones_used,
            timestamp=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Compliance audit
    # ------------------------------------------------------------------

    def run_compliance_audit(self) -> ComplianceAuditReport:
        """Run a HIPAA network isolation compliance audit.

        Evaluates all defined compliance checks against the current zone
        configuration and traffic policies.
        """
        now = datetime.now(timezone.utc)
        audit_id = hashlib.sha256(
            now.isoformat().encode()
        ).hexdigest()[:12]

        checks: list[ComplianceCheck] = []

        for check_def in HIPAA_COMPLIANCE_CHECKS:
            result = self._evaluate_check(check_def["check_id"])
            checks.append(
                ComplianceCheck(
                    check_id=check_def["check_id"],
                    name=check_def["name"],
                    description=check_def["description"],
                    status=result["status"],
                    category=check_def["category"],
                    finding=result["finding"],
                    recommendation=result["recommendation"],
                    hipaa_reference=check_def["hipaa_reference"],
                    severity=check_def["severity"],
                )
            )

        passed = sum(1 for c in checks if c.status == ComplianceStatus.PASS)
        warnings = sum(1 for c in checks if c.status == ComplianceStatus.WARN)
        failed = sum(1 for c in checks if c.status == ComplianceStatus.FAIL)
        total = len(checks)

        # Score: PASS=100%, WARN=50%, FAIL=0%
        score = int(((passed * 100) + (warnings * 50)) / total) if total else 0

        if failed > 0:
            overall = ComplianceStatus.FAIL
        elif warnings > 0:
            overall = ComplianceStatus.WARN
        else:
            overall = ComplianceStatus.PASS

        recommendations = [
            c.recommendation for c in checks
            if c.status != ComplianceStatus.PASS and c.recommendation
        ]

        return ComplianceAuditReport(
            audit_id=audit_id,
            timestamp=now,
            overall_score=score,
            overall_status=overall,
            total_checks=total,
            passed_checks=passed,
            warning_checks=warnings,
            failed_checks=failed,
            checks=checks,
            hipaa_compliant=failed == 0,
            recommendations=recommendations,
            zones_audited=list(self._zones.keys()),
        )

    def _evaluate_check(self, check_id: str) -> dict:
        """Evaluate a single compliance check against current config."""

        if check_id == "HIPAA-NET-001":
            # DMZ-to-DATA isolation
            dmz_to_data = [
                p for p in self._policies
                if p.source_zone == NetworkZone.DMZ
                and p.destination_zone == NetworkZone.DATA
            ]
            has_deny = any(
                not p.allowed_ports and not p.allowed_protocols
                for p in dmz_to_data
            )
            has_allow = any(
                p.allowed_ports and p.allowed_protocols
                for p in dmz_to_data
            )
            if has_deny and not has_allow:
                return {
                    "status": ComplianceStatus.PASS,
                    "finding": "DMZ-to-DATA traffic is explicitly denied with no allow rules",
                    "recommendation": "",
                }
            return {
                "status": ComplianceStatus.FAIL,
                "finding": "DMZ has a path to DATA zone — critical isolation failure",
                "recommendation": "Add explicit DENY rule for DMZ-to-DATA and remove any allow rules",
            }

        if check_id == "HIPAA-NET-002":
            # DATA outbound restriction
            data_outbound = [
                p for p in self._policies
                if p.source_zone == NetworkZone.DATA
                and p.destination_zone != NetworkZone.DATA
                and p.allowed_ports  # has allow rules
            ]
            if not data_outbound:
                return {
                    "status": ComplianceStatus.PASS,
                    "finding": "DATA zone has no outbound allow rules to external zones",
                    "recommendation": "",
                }
            return {
                "status": ComplianceStatus.FAIL,
                "finding": f"DATA zone has {len(data_outbound)} outbound allow policies",
                "recommendation": "Remove all outbound allow rules from DATA zone",
            }

        if check_id == "HIPAA-NET-003":
            # Encryption in transit
            phi_zones = [NetworkZone.APPLICATION, NetworkZone.DATA]
            unencrypted = [
                p for p in self._policies
                if (
                    p.source_zone in phi_zones
                    or p.destination_zone in phi_zones
                )
                and not p.encryption_required
                and p.allowed_ports  # only check allow rules
            ]
            if not unencrypted:
                return {
                    "status": ComplianceStatus.PASS,
                    "finding": "All PHI zone traffic requires encryption",
                    "recommendation": "",
                }
            return {
                "status": ComplianceStatus.FAIL,
                "finding": f"{len(unencrypted)} policies touching PHI zones lack encryption",
                "recommendation": "Enable encryption_required on all PHI zone policies",
            }

        if check_id == "HIPAA-NET-004":
            # Authentication on PHI access
            data_zone = self._zones[NetworkZone.DATA]
            app_zone = self._zones[NetworkZone.APPLICATION]
            if data_zone.requires_authentication and app_zone.requires_authentication:
                return {
                    "status": ComplianceStatus.PASS,
                    "finding": "PHI zones require authentication for all access",
                    "recommendation": "",
                }
            return {
                "status": ComplianceStatus.FAIL,
                "finding": "PHI zones missing authentication requirement",
                "recommendation": "Set requires_authentication=True on all PHI zones",
            }

        if check_id == "HIPAA-NET-005":
            # Audit logging
            hipaa_policies = [p for p in self._policies if p.hipaa_relevant]
            weak_logging = [
                p for p in hipaa_policies
                if p.logging_level in (LoggingLevel.NONE, LoggingLevel.BASIC)
                and p.allowed_ports  # only check allow rules
            ]
            if not weak_logging:
                return {
                    "status": ComplianceStatus.PASS,
                    "finding": "All HIPAA-relevant policies have DETAILED or FULL logging",
                    "recommendation": "",
                }
            return {
                "status": ComplianceStatus.WARN,
                "finding": f"{len(weak_logging)} HIPAA-relevant policies have insufficient logging",
                "recommendation": "Upgrade logging to DETAILED or FULL on all HIPAA-relevant policies",
            }

        if check_id == "HIPAA-NET-006":
            # Network monitoring
            unmonitored = [
                z for z in self._zones.values() if not z.monitoring_enabled
            ]
            if not unmonitored:
                return {
                    "status": ComplianceStatus.PASS,
                    "finding": "All zones have network monitoring enabled",
                    "recommendation": "",
                }
            zone_names = ", ".join(z.zone.value for z in unmonitored)
            return {
                "status": ComplianceStatus.WARN,
                "finding": f"Zones without monitoring: {zone_names}",
                "recommendation": "Enable monitoring on all network zones",
            }

        if check_id == "HIPAA-NET-007":
            # Minimum necessary (no wildcard ports)
            wildcard_policies = [
                p for p in self._policies
                if p.allowed_ports and len(p.allowed_ports) > 10
            ]
            if not wildcard_policies:
                return {
                    "status": ComplianceStatus.PASS,
                    "finding": "All policies specify limited port sets (minimum necessary)",
                    "recommendation": "",
                }
            return {
                "status": ComplianceStatus.WARN,
                "finding": f"{len(wildcard_policies)} policies have overly broad port ranges",
                "recommendation": "Restrict port ranges to only necessary ports",
            }

        if check_id == "HIPAA-NET-008":
            # DATA zone authentication
            data_zone = self._zones[NetworkZone.DATA]
            data_inbound = [
                p for p in self._policies
                if p.destination_zone == NetworkZone.DATA
                and p.allowed_ports
                and not p.authentication_required
            ]
            if data_zone.requires_authentication and not data_inbound:
                return {
                    "status": ComplianceStatus.PASS,
                    "finding": "DATA zone requires authentication for all inbound traffic",
                    "recommendation": "",
                }
            return {
                "status": ComplianceStatus.FAIL,
                "finding": "DATA zone has inbound policies without authentication",
                "recommendation": "Require authentication on all DATA zone inbound policies",
            }

        if check_id == "HIPAA-NET-009":
            # MANAGEMENT zone isolation from DMZ
            dmz_to_mgmt = [
                p for p in self._policies
                if p.source_zone == NetworkZone.DMZ
                and p.destination_zone == NetworkZone.MANAGEMENT
            ]
            has_deny = any(
                not p.allowed_ports and not p.allowed_protocols
                for p in dmz_to_mgmt
            )
            has_allow = any(
                p.allowed_ports and p.allowed_protocols
                for p in dmz_to_mgmt
            )
            if has_deny and not has_allow:
                return {
                    "status": ComplianceStatus.PASS,
                    "finding": "MANAGEMENT zone is isolated from DMZ",
                    "recommendation": "",
                }
            if not has_allow:
                return {
                    "status": ComplianceStatus.PASS,
                    "finding": "No allow rules from DMZ to MANAGEMENT (default deny)",
                    "recommendation": "",
                }
            return {
                "status": ComplianceStatus.FAIL,
                "finding": "DMZ can reach MANAGEMENT zone",
                "recommendation": "Add explicit DENY rule from DMZ to MANAGEMENT",
            }

        if check_id == "HIPAA-NET-010":
            # Default deny policy
            # Our firewall generation always adds a default deny
            return {
                "status": ComplianceStatus.PASS,
                "finding": "Default DENY policy is enforced for all unmatched traffic",
                "recommendation": "",
            }

        if check_id == "HIPAA-NET-011":
            # PHI data classification
            phi_services = [
                s for s in self._service_mappings
                if s.data_classification == "phi"
            ]
            misplaced = [
                s for s in phi_services if s.zone == NetworkZone.DMZ
            ]
            if not misplaced:
                return {
                    "status": ComplianceStatus.PASS,
                    "finding": "All PHI services are deployed in appropriate zones (not in DMZ)",
                    "recommendation": "",
                }
            names = ", ".join(s.service_name for s in misplaced)
            return {
                "status": ComplianceStatus.FAIL,
                "finding": f"PHI services in DMZ: {names}",
                "recommendation": "Move PHI services out of DMZ to APPLICATION or DATA zone",
            }

        if check_id == "HIPAA-NET-012":
            # VLAN separation
            vlans = [z.vlan_id for z in self._zones.values()]
            if len(vlans) == len(set(vlans)):
                return {
                    "status": ComplianceStatus.PASS,
                    "finding": "Each zone has a unique VLAN ID for proper network isolation",
                    "recommendation": "",
                }
            return {
                "status": ComplianceStatus.WARN,
                "finding": "Some zones share VLAN IDs, reducing isolation",
                "recommendation": "Assign unique VLAN IDs to each network zone",
            }

        # Unknown check — default pass
        return {
            "status": ComplianceStatus.PASS,
            "finding": "Check not implemented",
            "recommendation": "",
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return service statistics."""
        return {
            "zones": len(self._zones),
            "policies": len(self._policies),
            "services": len(self._service_mappings),
            "hipaa_checks": len(HIPAA_COMPLIANCE_CHECKS),
        }


# ============================================================================
# Singleton
# ============================================================================

_service: Optional[NetworkSegmentationService] = None


def get_network_segmentation_service() -> NetworkSegmentationService:
    """Return the singleton NetworkSegmentationService instance."""
    global _service
    if _service is None:
        _service = NetworkSegmentationService()
    return _service
