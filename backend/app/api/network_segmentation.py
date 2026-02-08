"""Network Segmentation API endpoints (CISO-5).

Exposes network zone definitions, traffic policies, zero-trust validation,
firewall rule generation, topology mapping, and HIPAA compliance audit.

Endpoints:
    GET  /security/network/zones                  - All network zones
    GET  /security/network/zones/{zone}            - Zone detail with rules
    GET  /security/network/policies                - All traffic policies
    POST /security/network/validate-traffic        - Check if traffic is allowed
    GET  /security/network/firewall-rules          - Generated firewall rules
    GET  /security/network/topology                - Service-to-zone mapping
    GET  /security/network/audit                   - Network compliance audit
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.network_segmentation import (
    ComplianceAuditReport,
    FirewallFormat,
    FirewallRuleSet,
    NetworkTopology,
    NetworkZone,
    PolicyListResponse,
    TrafficValidationRequest,
    TrafficValidationResponse,
    ZoneDetailResponse,
    ZoneListResponse,
)
from app.services.network_segmentation_service import (
    get_network_segmentation_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security/network", tags=["Network Segmentation"])


# ---------------------------------------------------------------------------
# Zones
# ---------------------------------------------------------------------------


@router.get(
    "/zones",
    response_model=ZoneListResponse,
    summary="List all network zones",
    description=(
        "Returns all defined network zones (DMZ, APPLICATION, DATA, "
        "MANAGEMENT) with their CIDR ranges, security levels, and "
        "allowed traffic directions."
    ),
)
async def list_zones() -> ZoneListResponse:
    """Return all network zone definitions."""
    svc = get_network_segmentation_service()
    return svc.get_zones()


@router.get(
    "/zones/{zone}",
    response_model=ZoneDetailResponse,
    summary="Get zone detail",
    description=(
        "Returns detailed information about a specific network zone, "
        "including all inbound/outbound traffic policies and the "
        "number of services deployed in the zone."
    ),
)
async def get_zone(zone: NetworkZone) -> ZoneDetailResponse:
    """Return detailed information for a single zone."""
    svc = get_network_segmentation_service()
    try:
        return svc.get_zone(zone)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone '{zone}' not found",
        )


# ---------------------------------------------------------------------------
# Traffic Policies
# ---------------------------------------------------------------------------


@router.get(
    "/policies",
    response_model=PolicyListResponse,
    summary="List all traffic policies",
    description=(
        "Returns all inter-zone traffic policies including allowed "
        "protocols, ports, encryption/authentication requirements, "
        "and logging levels."
    ),
)
async def list_policies() -> PolicyListResponse:
    """Return all traffic policies."""
    svc = get_network_segmentation_service()
    return svc.get_policies()


# ---------------------------------------------------------------------------
# Traffic Validation
# ---------------------------------------------------------------------------


@router.post(
    "/validate-traffic",
    response_model=TrafficValidationResponse,
    summary="Validate traffic flow",
    description=(
        "Zero-trust traffic validation: checks whether a specific "
        "source zone, destination zone, protocol, and port combination "
        "is allowed by current policies. Returns ALLOW/DENY with the "
        "matching policy and required security controls."
    ),
)
async def validate_traffic(
    request: TrafficValidationRequest,
) -> TrafficValidationResponse:
    """Validate whether a specific traffic flow is allowed."""
    svc = get_network_segmentation_service()
    return svc.validate_traffic(request)


# ---------------------------------------------------------------------------
# Firewall Rules
# ---------------------------------------------------------------------------


@router.get(
    "/firewall-rules",
    response_model=FirewallRuleSet,
    summary="Generate firewall rules",
    description=(
        "Generates iptables or nftables firewall rules from the "
        "current zone policies. Includes a default DENY rule for "
        "all unmatched traffic."
    ),
)
async def get_firewall_rules(
    format: FirewallFormat = Query(
        FirewallFormat.IPTABLES,
        description="Output format: iptables or nftables",
    ),
) -> FirewallRuleSet:
    """Generate firewall rules from zone policies."""
    svc = get_network_segmentation_service()
    return svc.generate_firewall_rules(fmt=format)


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------


@router.get(
    "/topology",
    response_model=NetworkTopology,
    summary="Get network topology",
    description=(
        "Returns the service-to-zone topology mapping showing which "
        "services run in which network zones, along with their ports, "
        "protocols, and data classification levels."
    ),
)
async def get_topology() -> NetworkTopology:
    """Return the service-to-zone topology mapping."""
    svc = get_network_segmentation_service()
    return svc.get_topology()


# ---------------------------------------------------------------------------
# Compliance Audit
# ---------------------------------------------------------------------------


@router.get(
    "/audit",
    response_model=ComplianceAuditReport,
    summary="Run network compliance audit",
    description=(
        "Runs a comprehensive HIPAA network isolation compliance audit "
        "evaluating DMZ-to-DATA isolation, encryption in transit, "
        "authentication requirements, audit logging, monitoring, and "
        "default deny policies. Returns a score (0-100), PASS/WARN/FAIL "
        "results for each check, and remediation recommendations."
    ),
)
async def run_audit() -> ComplianceAuditReport:
    """Run HIPAA network compliance audit."""
    svc = get_network_segmentation_service()
    return svc.run_compliance_audit()
