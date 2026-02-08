"""Tests for Network Segmentation Policy (CISO-5).

Tests cover:
- Zone definitions: all 4 zones present, properties correct
- Traffic policies: 20+ rules, correct zone pairs
- Zero-trust validation: allow/deny scenarios
- Firewall rule generation: iptables and nftables
- Service topology: service-to-zone mapping
- HIPAA compliance audit: all checks pass
- API endpoint responses
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.schemas.network_segmentation import (
    ComplianceStatus,
    FirewallFormat,
    LoggingLevel,
    NetworkZone,
    Protocol,
    RuleAction,
    TrafficDirection,
    TrafficValidationRequest,
)
from app.services.network_segmentation_service import (
    DEFAULT_POLICIES,
    DEFAULT_SERVICE_MAPPINGS,
    HIPAA_COMPLIANCE_CHECKS,
    ZONE_DEFINITIONS,
    NetworkSegmentationService,
    get_network_segmentation_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def service() -> NetworkSegmentationService:
    """Fresh service instance for each test."""
    return NetworkSegmentationService()


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""
    from app.main import app
    return TestClient(app)


# ============================================================================
# Zone Definition Tests
# ============================================================================


class TestZoneDefinitions:
    """Tests for network zone definitions."""

    def test_all_four_zones_defined(self, service: NetworkSegmentationService) -> None:
        """Verify all 4 network zones exist."""
        zones = service.get_zones()
        assert zones.total_zones == 4
        zone_ids = {z.zone for z in zones.zones}
        assert zone_ids == {
            NetworkZone.DMZ,
            NetworkZone.APPLICATION,
            NetworkZone.DATA,
            NetworkZone.MANAGEMENT,
        }

    def test_dmz_zone_properties(self, service: NetworkSegmentationService) -> None:
        """DMZ zone has correct properties."""
        detail = service.get_zone(NetworkZone.DMZ)
        zone = detail.zone
        assert zone.zone == NetworkZone.DMZ
        assert zone.cidr_range == "10.0.1.0/24"
        assert zone.vlan_id == 100
        assert zone.security_level == 30
        assert zone.monitoring_enabled is True
        assert "load_balancer" in zone.services

    def test_application_zone_properties(self, service: NetworkSegmentationService) -> None:
        """APPLICATION zone has correct properties."""
        detail = service.get_zone(NetworkZone.APPLICATION)
        zone = detail.zone
        assert zone.zone == NetworkZone.APPLICATION
        assert zone.cidr_range == "10.0.2.0/24"
        assert zone.vlan_id == 200
        assert zone.security_level == 60
        assert zone.requires_authentication is True
        assert "fastapi_backend" in zone.services

    def test_data_zone_properties(self, service: NetworkSegmentationService) -> None:
        """DATA zone is highest security with no outbound."""
        detail = service.get_zone(NetworkZone.DATA)
        zone = detail.zone
        assert zone.zone == NetworkZone.DATA
        assert zone.cidr_range == "10.0.3.0/24"
        assert zone.vlan_id == 300
        assert zone.security_level == 95
        assert zone.requires_encryption is True
        assert zone.requires_authentication is True
        assert zone.allowed_outbound_zones == []
        assert "postgresql" in zone.services

    def test_management_zone_properties(self, service: NetworkSegmentationService) -> None:
        """MANAGEMENT zone can reach all other zones for monitoring."""
        detail = service.get_zone(NetworkZone.MANAGEMENT)
        zone = detail.zone
        assert zone.zone == NetworkZone.MANAGEMENT
        assert zone.vlan_id == 400
        assert NetworkZone.DMZ in zone.allowed_outbound_zones
        assert NetworkZone.APPLICATION in zone.allowed_outbound_zones
        assert NetworkZone.DATA in zone.allowed_outbound_zones
        assert "prometheus" in zone.services

    def test_unique_vlan_ids(self, service: NetworkSegmentationService) -> None:
        """All zones have unique VLAN IDs."""
        zones = service.get_zones()
        vlans = [z.vlan_id for z in zones.zones]
        assert len(vlans) == len(set(vlans))

    def test_unique_cidr_ranges(self, service: NetworkSegmentationService) -> None:
        """All zones have unique CIDR ranges."""
        zones = service.get_zones()
        cidrs = [z.cidr_range for z in zones.zones]
        assert len(cidrs) == len(set(cidrs))

    def test_zone_detail_includes_policies(self, service: NetworkSegmentationService) -> None:
        """Zone detail response includes associated policies."""
        detail = service.get_zone(NetworkZone.APPLICATION)
        assert len(detail.inbound_policies) > 0
        assert len(detail.outbound_policies) > 0
        assert detail.service_count > 0

    def test_zone_detail_timestamp(self, service: NetworkSegmentationService) -> None:
        """Zone detail includes a timestamp."""
        detail = service.get_zone(NetworkZone.DMZ)
        assert detail.timestamp is not None


# ============================================================================
# Traffic Policy Tests
# ============================================================================


class TestTrafficPolicies:
    """Tests for traffic policies."""

    def test_minimum_20_policies(self, service: NetworkSegmentationService) -> None:
        """At least 20 traffic policies are defined."""
        policies = service.get_policies()
        assert policies.total_policies >= 20

    def test_dmz_to_app_https_only(self, service: NetworkSegmentationService) -> None:
        """DMZ to APP allows only HTTPS/443."""
        policies = service.get_policies()
        dmz_to_app_https = [
            p for p in policies.policies
            if p.policy_id == "POL-001"
        ]
        assert len(dmz_to_app_https) == 1
        pol = dmz_to_app_https[0]
        assert pol.source_zone == NetworkZone.DMZ
        assert pol.destination_zone == NetworkZone.APPLICATION
        assert Protocol.HTTPS in pol.allowed_protocols
        assert 443 in pol.allowed_ports

    def test_app_to_postgresql(self, service: NetworkSegmentationService) -> None:
        """APP to DATA allows PostgreSQL/5432."""
        policies = service.get_policies()
        pg_policy = [p for p in policies.policies if p.policy_id == "POL-003"]
        assert len(pg_policy) == 1
        assert pg_policy[0].allowed_ports == [5432]
        assert pg_policy[0].authentication_required is True

    def test_app_to_redis(self, service: NetworkSegmentationService) -> None:
        """APP to DATA allows Redis/6379."""
        policies = service.get_policies()
        redis_policy = [p for p in policies.policies if p.policy_id == "POL-004"]
        assert len(redis_policy) == 1
        assert 6379 in redis_policy[0].allowed_ports

    def test_app_to_neo4j(self, service: NetworkSegmentationService) -> None:
        """APP to DATA allows Neo4j/7687."""
        policies = service.get_policies()
        neo4j_policy = [p for p in policies.policies if p.policy_id == "POL-005"]
        assert len(neo4j_policy) == 1
        assert 7687 in neo4j_policy[0].allowed_ports

    def test_dmz_to_data_denied(self, service: NetworkSegmentationService) -> None:
        """DMZ to DATA is explicitly denied (critical rule)."""
        policies = service.get_policies()
        deny = [p for p in policies.policies if p.policy_id == "POL-006"]
        assert len(deny) == 1
        assert deny[0].allowed_protocols == []
        assert deny[0].allowed_ports == []

    def test_data_outbound_denied(self, service: NetworkSegmentationService) -> None:
        """DATA zone has no outbound allow rules to external zones."""
        policies = service.get_policies()
        data_outbound_allow = [
            p for p in policies.policies
            if p.source_zone == NetworkZone.DATA
            and p.destination_zone != NetworkZone.DATA
            and p.allowed_ports  # has allow rules
        ]
        assert len(data_outbound_allow) == 0

    def test_management_can_monitor_all(self, service: NetworkSegmentationService) -> None:
        """MANAGEMENT zone has monitoring policies to all other zones."""
        policies = service.get_policies()
        mgmt_monitor = [
            p for p in policies.policies
            if p.source_zone == NetworkZone.MANAGEMENT
            and p.destination_zone != NetworkZone.MANAGEMENT
            and p.allowed_ports
        ]
        destinations = {p.destination_zone for p in mgmt_monitor}
        assert NetworkZone.DMZ in destinations
        assert NetworkZone.APPLICATION in destinations
        assert NetworkZone.DATA in destinations

    def test_all_policies_have_ids(self, service: NetworkSegmentationService) -> None:
        """All policies have unique IDs."""
        policies = service.get_policies()
        ids = [p.policy_id for p in policies.policies]
        assert len(ids) == len(set(ids))

    def test_hipaa_relevant_policies_exist(self, service: NetworkSegmentationService) -> None:
        """There are HIPAA-relevant policies."""
        policies = service.get_policies()
        hipaa = [p for p in policies.policies if p.hipaa_relevant]
        assert len(hipaa) > 0

    def test_policies_for_zone(self, service: NetworkSegmentationService) -> None:
        """get_policies_for_zone returns policies involving the zone."""
        app_policies = service.get_policies_for_zone(NetworkZone.APPLICATION)
        assert len(app_policies) > 0
        for p in app_policies:
            assert (
                p.source_zone == NetworkZone.APPLICATION
                or p.destination_zone == NetworkZone.APPLICATION
            )


# ============================================================================
# Zero-Trust Traffic Validation Tests
# ============================================================================


class TestTrafficValidation:
    """Tests for zero-trust traffic validation."""

    def test_allow_dmz_to_app_https(self, service: NetworkSegmentationService) -> None:
        """HTTPS/443 from DMZ to APP is allowed."""
        req = TrafficValidationRequest(
            source_zone=NetworkZone.DMZ,
            destination_zone=NetworkZone.APPLICATION,
            protocol=Protocol.HTTPS,
            port=443,
        )
        result = service.validate_traffic(req)
        assert result.allowed is True
        assert result.matching_policy is not None

    def test_deny_dmz_to_data(self, service: NetworkSegmentationService) -> None:
        """Any traffic from DMZ to DATA is denied."""
        req = TrafficValidationRequest(
            source_zone=NetworkZone.DMZ,
            destination_zone=NetworkZone.DATA,
            protocol=Protocol.TCP,
            port=5432,
        )
        result = service.validate_traffic(req)
        assert result.allowed is False

    def test_allow_app_to_postgresql(self, service: NetworkSegmentationService) -> None:
        """TCP/5432 from APP to DATA is allowed."""
        req = TrafficValidationRequest(
            source_zone=NetworkZone.APPLICATION,
            destination_zone=NetworkZone.DATA,
            protocol=Protocol.TCP,
            port=5432,
        )
        result = service.validate_traffic(req)
        assert result.allowed is True

    def test_allow_app_to_redis(self, service: NetworkSegmentationService) -> None:
        """TCP/6379 from APP to DATA is allowed."""
        req = TrafficValidationRequest(
            source_zone=NetworkZone.APPLICATION,
            destination_zone=NetworkZone.DATA,
            protocol=Protocol.TCP,
            port=6379,
        )
        result = service.validate_traffic(req)
        assert result.allowed is True

    def test_allow_app_to_neo4j(self, service: NetworkSegmentationService) -> None:
        """TCP/7687 from APP to DATA is allowed."""
        req = TrafficValidationRequest(
            source_zone=NetworkZone.APPLICATION,
            destination_zone=NetworkZone.DATA,
            protocol=Protocol.TCP,
            port=7687,
        )
        result = service.validate_traffic(req)
        assert result.allowed is True

    def test_deny_app_to_data_wrong_port(self, service: NetworkSegmentationService) -> None:
        """TCP/3306 from APP to DATA is denied (MySQL not allowed)."""
        req = TrafficValidationRequest(
            source_zone=NetworkZone.APPLICATION,
            destination_zone=NetworkZone.DATA,
            protocol=Protocol.TCP,
            port=3306,
        )
        result = service.validate_traffic(req)
        assert result.allowed is False

    def test_deny_data_outbound(self, service: NetworkSegmentationService) -> None:
        """DATA zone cannot reach DMZ."""
        req = TrafficValidationRequest(
            source_zone=NetworkZone.DATA,
            destination_zone=NetworkZone.DMZ,
            protocol=Protocol.TCP,
            port=443,
        )
        result = service.validate_traffic(req)
        assert result.allowed is False

    def test_deny_data_to_app(self, service: NetworkSegmentationService) -> None:
        """DATA zone cannot reach APPLICATION."""
        req = TrafficValidationRequest(
            source_zone=NetworkZone.DATA,
            destination_zone=NetworkZone.APPLICATION,
            protocol=Protocol.TCP,
            port=8000,
        )
        result = service.validate_traffic(req)
        assert result.allowed is False

    def test_default_deny_unknown_traffic(self, service: NetworkSegmentationService) -> None:
        """Traffic with no matching policy is denied by default."""
        req = TrafficValidationRequest(
            source_zone=NetworkZone.DMZ,
            destination_zone=NetworkZone.APPLICATION,
            protocol=Protocol.UDP,
            port=9999,
        )
        result = service.validate_traffic(req)
        assert result.allowed is False
        assert "default deny" in result.reason.lower()

    def test_validation_returns_security_requirements(
        self, service: NetworkSegmentationService
    ) -> None:
        """Allowed traffic returns security requirements."""
        req = TrafficValidationRequest(
            source_zone=NetworkZone.APPLICATION,
            destination_zone=NetworkZone.DATA,
            protocol=Protocol.TCP,
            port=5432,
        )
        result = service.validate_traffic(req)
        assert result.allowed is True
        assert result.authentication_required is True
        assert result.encryption_required is True
        assert result.logging_level == LoggingLevel.FULL

    def test_deny_dmz_to_management(self, service: NetworkSegmentationService) -> None:
        """DMZ cannot reach MANAGEMENT zone."""
        req = TrafficValidationRequest(
            source_zone=NetworkZone.DMZ,
            destination_zone=NetworkZone.MANAGEMENT,
            protocol=Protocol.TCP,
            port=9090,
        )
        result = service.validate_traffic(req)
        assert result.allowed is False

    def test_allow_management_to_app_monitoring(
        self, service: NetworkSegmentationService
    ) -> None:
        """MANAGEMENT can reach APP for monitoring on port 9090."""
        req = TrafficValidationRequest(
            source_zone=NetworkZone.MANAGEMENT,
            destination_zone=NetworkZone.APPLICATION,
            protocol=Protocol.TCP,
            port=9090,
        )
        result = service.validate_traffic(req)
        assert result.allowed is True


# ============================================================================
# Firewall Rule Generation Tests
# ============================================================================


class TestFirewallRules:
    """Tests for firewall rule generation."""

    def test_generate_iptables_rules(self, service: NetworkSegmentationService) -> None:
        """Generates iptables format rules."""
        ruleset = service.generate_firewall_rules(fmt=FirewallFormat.IPTABLES)
        assert ruleset.format == FirewallFormat.IPTABLES
        assert ruleset.total_rules > 0
        assert len(ruleset.rules) == ruleset.total_rules
        assert len(ruleset.raw_rules) > 0

    def test_generate_nftables_rules(self, service: NetworkSegmentationService) -> None:
        """Generates nftables format rules."""
        ruleset = service.generate_firewall_rules(fmt=FirewallFormat.NFTABLES)
        assert ruleset.format == FirewallFormat.NFTABLES
        assert ruleset.total_rules > 0
        # nftables rules contain "nft" command
        assert any("nft" in r for r in ruleset.raw_rules)

    def test_default_deny_rule_last(self, service: NetworkSegmentationService) -> None:
        """Last rule is always default DENY."""
        ruleset = service.generate_firewall_rules()
        last_rule = ruleset.rules[-1]
        assert last_rule.action == RuleAction.DENY
        assert last_rule.source == "0.0.0.0/0"
        assert last_rule.destination == "0.0.0.0/0"

    def test_default_policy_is_deny(self, service: NetworkSegmentationService) -> None:
        """Default firewall policy is DENY."""
        ruleset = service.generate_firewall_rules()
        assert ruleset.default_policy == RuleAction.DENY

    def test_iptables_raw_syntax(self, service: NetworkSegmentationService) -> None:
        """iptables rules use correct syntax."""
        ruleset = service.generate_firewall_rules(fmt=FirewallFormat.IPTABLES)
        for raw in ruleset.raw_rules:
            assert raw.startswith("iptables")

    def test_nftables_raw_syntax(self, service: NetworkSegmentationService) -> None:
        """nftables rules use correct syntax."""
        ruleset = service.generate_firewall_rules(fmt=FirewallFormat.NFTABLES)
        for raw in ruleset.raw_rules:
            assert raw.startswith("nft")

    def test_rules_have_comments(self, service: NetworkSegmentationService) -> None:
        """Generated rules include comments from policy descriptions."""
        ruleset = service.generate_firewall_rules()
        commented = [r for r in ruleset.rules if r.comment]
        assert len(commented) > 0

    def test_rules_ordered_sequentially(self, service: NetworkSegmentationService) -> None:
        """Rules have sequential order numbers."""
        ruleset = service.generate_firewall_rules()
        orders = [r.order for r in ruleset.rules]
        assert orders == sorted(orders)
        assert len(orders) == len(set(orders))  # unique


# ============================================================================
# Topology Tests
# ============================================================================


class TestTopology:
    """Tests for service-to-zone topology."""

    def test_topology_has_services(self, service: NetworkSegmentationService) -> None:
        """Topology contains services."""
        topo = service.get_topology()
        assert topo.total_services > 0
        assert len(topo.services) == topo.total_services

    def test_all_zones_utilized(self, service: NetworkSegmentationService) -> None:
        """All 4 zones have at least one service."""
        topo = service.get_topology()
        assert len(topo.zones_utilized) == 4

    def test_postgresql_in_data_zone(self, service: NetworkSegmentationService) -> None:
        """PostgreSQL is in DATA zone."""
        topo = service.get_topology()
        pg = [s for s in topo.services if s.service_name == "postgresql"]
        assert len(pg) == 1
        assert pg[0].zone == NetworkZone.DATA
        assert pg[0].port == 5432

    def test_fastapi_in_application_zone(self, service: NetworkSegmentationService) -> None:
        """FastAPI is in APPLICATION zone."""
        topo = service.get_topology()
        api = [s for s in topo.services if s.service_name == "fastapi_backend"]
        assert len(api) == 1
        assert api[0].zone == NetworkZone.APPLICATION

    def test_load_balancer_in_dmz(self, service: NetworkSegmentationService) -> None:
        """Load balancer is in DMZ."""
        topo = service.get_topology()
        lb = [s for s in topo.services if s.service_name == "nginx_load_balancer"]
        assert len(lb) == 1
        assert lb[0].zone == NetworkZone.DMZ
        assert lb[0].requires_external_access is True

    def test_prometheus_in_management(self, service: NetworkSegmentationService) -> None:
        """Prometheus is in MANAGEMENT zone."""
        topo = service.get_topology()
        prom = [s for s in topo.services if s.service_name == "prometheus"]
        assert len(prom) == 1
        assert prom[0].zone == NetworkZone.MANAGEMENT

    def test_phi_services_not_in_dmz(self, service: NetworkSegmentationService) -> None:
        """No PHI-classified service runs in DMZ."""
        topo = service.get_topology()
        phi_in_dmz = [
            s for s in topo.services
            if s.data_classification == "phi" and s.zone == NetworkZone.DMZ
        ]
        assert len(phi_in_dmz) == 0


# ============================================================================
# Compliance Audit Tests
# ============================================================================


class TestComplianceAudit:
    """Tests for HIPAA network compliance audit."""

    def test_audit_runs_all_checks(self, service: NetworkSegmentationService) -> None:
        """Audit evaluates all defined compliance checks."""
        report = service.run_compliance_audit()
        assert report.total_checks == len(HIPAA_COMPLIANCE_CHECKS)

    def test_audit_all_pass_with_defaults(self, service: NetworkSegmentationService) -> None:
        """Default configuration passes all compliance checks."""
        report = service.run_compliance_audit()
        assert report.overall_status == ComplianceStatus.PASS
        assert report.hipaa_compliant is True
        assert report.failed_checks == 0

    def test_audit_score_100_with_defaults(self, service: NetworkSegmentationService) -> None:
        """Default configuration scores 100."""
        report = service.run_compliance_audit()
        assert report.overall_score == 100

    def test_audit_has_id_and_timestamp(self, service: NetworkSegmentationService) -> None:
        """Audit report includes ID and timestamp."""
        report = service.run_compliance_audit()
        assert report.audit_id is not None
        assert len(report.audit_id) > 0
        assert report.timestamp is not None

    def test_audit_covers_all_zones(self, service: NetworkSegmentationService) -> None:
        """Audit covers all 4 network zones."""
        report = service.run_compliance_audit()
        assert len(report.zones_audited) == 4

    def test_dmz_data_isolation_check(self, service: NetworkSegmentationService) -> None:
        """HIPAA-NET-001: DMZ-to-DATA isolation passes."""
        report = service.run_compliance_audit()
        check = next(c for c in report.checks if c.check_id == "HIPAA-NET-001")
        assert check.status == ComplianceStatus.PASS

    def test_data_outbound_check(self, service: NetworkSegmentationService) -> None:
        """HIPAA-NET-002: DATA outbound restriction passes."""
        report = service.run_compliance_audit()
        check = next(c for c in report.checks if c.check_id == "HIPAA-NET-002")
        assert check.status == ComplianceStatus.PASS

    def test_encryption_check(self, service: NetworkSegmentationService) -> None:
        """HIPAA-NET-003: Encryption in transit passes."""
        report = service.run_compliance_audit()
        check = next(c for c in report.checks if c.check_id == "HIPAA-NET-003")
        assert check.status == ComplianceStatus.PASS

    def test_default_deny_check(self, service: NetworkSegmentationService) -> None:
        """HIPAA-NET-010: Default deny policy passes."""
        report = service.run_compliance_audit()
        check = next(c for c in report.checks if c.check_id == "HIPAA-NET-010")
        assert check.status == ComplianceStatus.PASS

    def test_checks_have_hipaa_references(self, service: NetworkSegmentationService) -> None:
        """All checks reference HIPAA regulations."""
        report = service.run_compliance_audit()
        for check in report.checks:
            assert check.hipaa_reference != ""
            assert "CFR" in check.hipaa_reference


# ============================================================================
# Service Stats Tests
# ============================================================================


class TestServiceStats:
    """Tests for service statistics."""

    def test_stats_include_counts(self, service: NetworkSegmentationService) -> None:
        """Stats report zone, policy, service, and check counts."""
        stats = service.get_stats()
        assert stats["zones"] == 4
        assert stats["policies"] >= 20
        assert stats["services"] > 0
        assert stats["hipaa_checks"] == len(HIPAA_COMPLIANCE_CHECKS)


# ============================================================================
# Singleton Tests
# ============================================================================


class TestSingleton:
    """Tests for singleton service instance."""

    def test_singleton_returns_same_instance(self) -> None:
        """get_network_segmentation_service returns the same instance."""
        svc1 = get_network_segmentation_service()
        svc2 = get_network_segmentation_service()
        assert svc1 is svc2


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestAPIEndpoints:
    """Tests for network segmentation API endpoints."""

    def test_list_zones_endpoint(self, client: TestClient) -> None:
        """GET /security/network/zones returns all zones."""
        resp = client.get("/api/v1/security/network/zones")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_zones"] == 4
        assert len(data["zones"]) == 4

    def test_get_zone_detail_endpoint(self, client: TestClient) -> None:
        """GET /security/network/zones/APPLICATION returns zone detail."""
        resp = client.get("/api/v1/security/network/zones/APPLICATION")
        assert resp.status_code == 200
        data = resp.json()
        assert data["zone"]["zone"] == "APPLICATION"
        assert data["service_count"] > 0

    def test_get_zone_detail_data(self, client: TestClient) -> None:
        """GET /security/network/zones/DATA returns DATA zone detail."""
        resp = client.get("/api/v1/security/network/zones/DATA")
        assert resp.status_code == 200
        data = resp.json()
        assert data["zone"]["zone"] == "DATA"

    def test_list_policies_endpoint(self, client: TestClient) -> None:
        """GET /security/network/policies returns all policies."""
        resp = client.get("/api/v1/security/network/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_policies"] >= 20

    def test_validate_traffic_allowed(self, client: TestClient) -> None:
        """POST /security/network/validate-traffic returns allowed."""
        resp = client.post(
            "/api/v1/security/network/validate-traffic",
            json={
                "source_zone": "APPLICATION",
                "destination_zone": "DATA",
                "protocol": "TCP",
                "port": 5432,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is True

    def test_validate_traffic_denied(self, client: TestClient) -> None:
        """POST /security/network/validate-traffic returns denied."""
        resp = client.post(
            "/api/v1/security/network/validate-traffic",
            json={
                "source_zone": "DMZ",
                "destination_zone": "DATA",
                "protocol": "TCP",
                "port": 5432,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is False

    def test_firewall_rules_endpoint(self, client: TestClient) -> None:
        """GET /security/network/firewall-rules returns rules."""
        resp = client.get("/api/v1/security/network/firewall-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rules"] > 0
        assert data["default_policy"] == "DENY"

    def test_firewall_rules_nftables(self, client: TestClient) -> None:
        """GET /security/network/firewall-rules?format=nftables works."""
        resp = client.get(
            "/api/v1/security/network/firewall-rules?format=nftables"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "nftables"

    def test_topology_endpoint(self, client: TestClient) -> None:
        """GET /security/network/topology returns topology."""
        resp = client.get("/api/v1/security/network/topology")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_services"] > 0
        assert len(data["zones_utilized"]) == 4

    def test_audit_endpoint(self, client: TestClient) -> None:
        """GET /security/network/audit returns compliance report."""
        resp = client.get("/api/v1/security/network/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] == 100
        assert data["hipaa_compliant"] is True
        assert data["total_checks"] > 0
