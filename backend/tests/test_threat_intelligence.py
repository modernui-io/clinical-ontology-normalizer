"""Tests for Threat Intelligence & DLP Policies (CISO-13).

Tests verify:
- Pre-populated seed data (10 indicators, 4 feeds, 6 alerts, 8 DLP policies,
  12 violations, 5 trainings)
- Threat indicator CRUD: create, read, update, delete, list with filters
- IOC search by value (exact and substring)
- Threat feed management: create, read, update, delete
- Threat alert management: create, read, list with filters
- Alert acknowledge and mitigate workflows
- DLP policy CRUD: create, read, update, delete
- DLP policy enable/disable toggling
- DLP violation tracking and resolution
- Security awareness training management
- Threat metrics aggregation (by category, severity, active threats, MITRE)
- DLP metrics aggregation (by channel, policy type, blocked vs logged)
- Training compliance rate calculation
- Pagination support
- Edge cases (not found, invalid IDs)
- API endpoint integration tests via ASGI test client
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.threat_intelligence import (
    DLPAction,
    DLPChannel,
    DLPPolicyType,
    IOCType,
    ThreatCategory,
    ThreatSeverity,
    ThreatStatus,
)
from app.services.threat_intelligence_service import (
    ThreatIntelligenceService,
    get_threat_intelligence_service,
    reset_threat_intelligence_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the singleton service before and after each test."""
    reset_threat_intelligence_service()
    yield
    reset_threat_intelligence_service()


@pytest.fixture
def service() -> ThreatIntelligenceService:
    return get_threat_intelligence_service()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


API_PREFIX = "/api/v1/threat-intelligence"


# ============================================================================
# Seed Data Verification Tests
# ============================================================================


class TestSeedData:
    """Tests verifying seed data is properly initialized."""

    def test_seed_indicators_count(self, service: ThreatIntelligenceService):
        items, total = service.list_indicators()
        assert total == 10

    def test_seed_feeds_count(self, service: ThreatIntelligenceService):
        feeds = service.list_feeds()
        assert len(feeds) == 4

    def test_seed_alerts_count(self, service: ThreatIntelligenceService):
        alerts = service.list_alerts()
        assert len(alerts) == 6

    def test_seed_dlp_policies_count(self, service: ThreatIntelligenceService):
        policies = service.list_dlp_policies()
        assert len(policies) == 8

    def test_seed_violations_count(self, service: ThreatIntelligenceService):
        items, total = service.list_violations()
        assert total == 12

    def test_seed_trainings_count(self, service: ThreatIntelligenceService):
        trainings = service.list_trainings()
        assert len(trainings) == 5

    def test_seed_indicator_has_mitre_techniques(self, service: ThreatIntelligenceService):
        ind = service.get_indicator("ioc-001")
        assert ind is not None
        assert len(ind.mitre_techniques) > 0
        assert "T1071.001" in ind.mitre_techniques

    def test_seed_indicator_categories(self, service: ThreatIntelligenceService):
        items, _ = service.list_indicators()
        categories = {i.threat_category for i in items}
        assert ThreatCategory.APT in categories
        assert ThreatCategory.PHISHING in categories
        assert ThreatCategory.RANSOMWARE in categories

    def test_seed_dlp_policy_has_patterns(self, service: ThreatIntelligenceService):
        policy = service.get_dlp_policy("dlp-001")
        assert policy is not None
        assert len(policy.patterns) == 3
        assert policy.patterns[0].pattern_name == "SSN Pattern"

    def test_seed_feed_providers(self, service: ThreatIntelligenceService):
        feeds = service.list_feeds()
        providers = {f.provider for f in feeds}
        assert "AT&T Cybersecurity" in providers
        assert "CISA" in providers


# ============================================================================
# Indicator CRUD Tests
# ============================================================================


class TestIndicatorCRUD:
    """Tests for indicator create, read, update, delete operations."""

    def test_create_indicator(self, service: ThreatIntelligenceService):
        ind = service.create_indicator(
            ioc_type=IOCType.IP_ADDRESS,
            value="10.20.30.40",
            threat_category=ThreatCategory.APT,
            severity=ThreatSeverity.HIGH,
            description="Test indicator",
            source="unit-test",
            confidence_score=75.0,
        )
        assert ind.id.startswith("ioc-")
        assert ind.value == "10.20.30.40"
        assert ind.status == ThreatStatus.NEW

    def test_get_indicator(self, service: ThreatIntelligenceService):
        ind = service.get_indicator("ioc-001")
        assert ind is not None
        assert ind.value == "185.220.101.42"

    def test_get_indicator_not_found(self, service: ThreatIntelligenceService):
        assert service.get_indicator("ioc-nonexistent") is None

    def test_update_indicator_severity(self, service: ThreatIntelligenceService):
        updated = service.update_indicator("ioc-001", severity=ThreatSeverity.MEDIUM)
        assert updated is not None
        assert updated.severity == ThreatSeverity.MEDIUM

    def test_update_indicator_status(self, service: ThreatIntelligenceService):
        updated = service.update_indicator("ioc-002", status=ThreatStatus.CONFIRMED)
        assert updated is not None
        assert updated.status == ThreatStatus.CONFIRMED

    def test_update_indicator_confidence(self, service: ThreatIntelligenceService):
        updated = service.update_indicator("ioc-001", confidence_score=50.0)
        assert updated is not None
        assert updated.confidence_score == 50.0

    def test_update_indicator_description(self, service: ThreatIntelligenceService):
        updated = service.update_indicator("ioc-001", description="Updated description")
        assert updated is not None
        assert updated.description == "Updated description"

    def test_update_indicator_campaigns(self, service: ThreatIntelligenceService):
        updated = service.update_indicator("ioc-001", related_campaigns=["NewCampaign"])
        assert updated is not None
        assert "NewCampaign" in updated.related_campaigns

    def test_update_indicator_mitre(self, service: ThreatIntelligenceService):
        updated = service.update_indicator("ioc-001", mitre_techniques=["T1234"])
        assert updated is not None
        assert "T1234" in updated.mitre_techniques

    def test_update_indicator_not_found(self, service: ThreatIntelligenceService):
        assert service.update_indicator("ioc-nonexistent", severity=ThreatSeverity.LOW) is None

    def test_delete_indicator(self, service: ThreatIntelligenceService):
        assert service.delete_indicator("ioc-010") is True
        assert service.get_indicator("ioc-010") is None

    def test_delete_indicator_not_found(self, service: ThreatIntelligenceService):
        assert service.delete_indicator("ioc-nonexistent") is False

    def test_create_indicator_with_campaigns(self, service: ThreatIntelligenceService):
        ind = service.create_indicator(
            ioc_type=IOCType.DOMAIN,
            value="test.evil.com",
            threat_category=ThreatCategory.PHISHING,
            severity=ThreatSeverity.HIGH,
            related_campaigns=["Campaign-X"],
            mitre_techniques=["T1566.001"],
        )
        assert ind.related_campaigns == ["Campaign-X"]
        assert ind.mitre_techniques == ["T1566.001"]


# ============================================================================
# Indicator Search & Filter Tests
# ============================================================================


class TestIndicatorSearchFilter:
    """Tests for indicator searching and filtering."""

    def test_search_by_value_exact(self, service: ThreatIntelligenceService):
        results = service.search_indicator_by_value("185.220.101.42")
        assert len(results) == 1
        assert results[0].id == "ioc-001"

    def test_search_by_value_substring(self, service: ThreatIntelligenceService):
        results = service.search_indicator_by_value("evil.com")
        assert len(results) >= 1

    def test_search_by_value_case_insensitive(self, service: ThreatIntelligenceService):
        results = service.search_indicator_by_value("PHARMA-UPDATE")
        assert len(results) >= 1

    def test_search_no_results(self, service: ThreatIntelligenceService):
        results = service.search_indicator_by_value("nonexistent.domain.xyz")
        assert len(results) == 0

    def test_filter_by_ioc_type(self, service: ThreatIntelligenceService):
        items, total = service.list_indicators(ioc_type=IOCType.IP_ADDRESS)
        assert total >= 3
        assert all(i.ioc_type == IOCType.IP_ADDRESS for i in items)

    def test_filter_by_category(self, service: ThreatIntelligenceService):
        items, total = service.list_indicators(threat_category=ThreatCategory.APT)
        assert total >= 1
        assert all(i.threat_category == ThreatCategory.APT for i in items)

    def test_filter_by_severity(self, service: ThreatIntelligenceService):
        items, total = service.list_indicators(severity=ThreatSeverity.CRITICAL)
        assert total >= 3
        assert all(i.severity == ThreatSeverity.CRITICAL for i in items)

    def test_filter_by_status(self, service: ThreatIntelligenceService):
        items, total = service.list_indicators(status=ThreatStatus.CONFIRMED)
        assert total >= 2
        assert all(i.status == ThreatStatus.CONFIRMED for i in items)

    def test_filter_combined(self, service: ThreatIntelligenceService):
        items, total = service.list_indicators(
            ioc_type=IOCType.IP_ADDRESS,
            severity=ThreatSeverity.CRITICAL,
        )
        assert all(
            i.ioc_type == IOCType.IP_ADDRESS and i.severity == ThreatSeverity.CRITICAL
            for i in items
        )

    def test_pagination(self, service: ThreatIntelligenceService):
        items, total = service.list_indicators(limit=3, offset=0)
        assert len(items) == 3
        assert total == 10

    def test_pagination_offset(self, service: ThreatIntelligenceService):
        items, total = service.list_indicators(limit=5, offset=8)
        assert len(items) == 2
        assert total == 10


# ============================================================================
# Feed Management Tests
# ============================================================================


class TestFeedManagement:
    """Tests for threat feed CRUD operations."""

    def test_list_feeds(self, service: ThreatIntelligenceService):
        feeds = service.list_feeds()
        assert len(feeds) == 4

    def test_get_feed(self, service: ThreatIntelligenceService):
        feed = service.get_feed("feed-001")
        assert feed is not None
        assert feed.name == "AlienVault OTX"

    def test_get_feed_not_found(self, service: ThreatIntelligenceService):
        assert service.get_feed("feed-nonexistent") is None

    def test_create_feed(self, service: ThreatIntelligenceService):
        feed = service.create_feed(
            name="Test Feed",
            provider="Test Provider",
            url="https://test.example.com/feed",
            feed_type="JSON",
            update_frequency_hours=12,
        )
        assert feed.id.startswith("feed-")
        assert feed.name == "Test Feed"
        assert feed.indicators_count == 0

    def test_update_feed_name(self, service: ThreatIntelligenceService):
        updated = service.update_feed("feed-001", name="Updated OTX")
        assert updated is not None
        assert updated.name == "Updated OTX"

    def test_update_feed_enabled(self, service: ThreatIntelligenceService):
        updated = service.update_feed("feed-004", enabled=True)
        assert updated is not None
        assert updated.enabled is True

    def test_update_feed_frequency(self, service: ThreatIntelligenceService):
        updated = service.update_feed("feed-001", update_frequency_hours=2)
        assert updated is not None
        assert updated.update_frequency_hours == 2

    def test_update_feed_not_found(self, service: ThreatIntelligenceService):
        assert service.update_feed("feed-nonexistent", name="x") is None

    def test_delete_feed(self, service: ThreatIntelligenceService):
        assert service.delete_feed("feed-004") is True
        assert service.get_feed("feed-004") is None

    def test_delete_feed_not_found(self, service: ThreatIntelligenceService):
        assert service.delete_feed("feed-nonexistent") is False


# ============================================================================
# Alert Management Tests
# ============================================================================


class TestAlertManagement:
    """Tests for threat alert operations."""

    def test_list_alerts(self, service: ThreatIntelligenceService):
        alerts = service.list_alerts()
        assert len(alerts) == 6

    def test_list_alerts_filter_severity(self, service: ThreatIntelligenceService):
        alerts = service.list_alerts(severity=ThreatSeverity.CRITICAL)
        assert all(a.severity == ThreatSeverity.CRITICAL for a in alerts)
        assert len(alerts) >= 2

    def test_list_alerts_filter_category(self, service: ThreatIntelligenceService):
        alerts = service.list_alerts(category=ThreatCategory.APT)
        assert len(alerts) >= 1
        assert all(a.category == ThreatCategory.APT for a in alerts)

    def test_list_alerts_filter_acknowledged(self, service: ThreatIntelligenceService):
        unack = service.list_alerts(acknowledged=False)
        assert all(not a.acknowledged for a in unack)
        assert len(unack) >= 3

    def test_get_alert(self, service: ThreatIntelligenceService):
        alert = service.get_alert("alert-001")
        assert alert is not None
        assert alert.title == "APT28 C2 Communication Detected"

    def test_get_alert_not_found(self, service: ThreatIntelligenceService):
        assert service.get_alert("alert-nonexistent") is None

    def test_create_alert(self, service: ThreatIntelligenceService):
        alert = service.create_alert(
            title="Test Alert",
            severity=ThreatSeverity.HIGH,
            category=ThreatCategory.PHISHING,
            description="Test alert for unit testing",
            indicators=["ioc-002"],
            affected_systems=["test-system"],
            detection_method="unit-test",
        )
        assert alert.id.startswith("alert-")
        assert alert.acknowledged is False
        assert alert.mitigated is False

    def test_acknowledge_alert(self, service: ThreatIntelligenceService):
        result = service.acknowledge_alert("alert-001", "test-analyst")
        assert result is not None
        assert result.acknowledged is True
        assert result.acknowledged_by == "test-analyst"

    def test_acknowledge_alert_not_found(self, service: ThreatIntelligenceService):
        assert service.acknowledge_alert("alert-nonexistent", "user") is None

    def test_mitigate_alert(self, service: ThreatIntelligenceService):
        result = service.mitigate_alert("alert-001")
        assert result is not None
        assert result.mitigated is True

    def test_mitigate_alert_not_found(self, service: ThreatIntelligenceService):
        assert service.mitigate_alert("alert-nonexistent") is None

    def test_alert_has_indicators(self, service: ThreatIntelligenceService):
        alert = service.get_alert("alert-001")
        assert alert is not None
        assert "ioc-001" in alert.indicators

    def test_alert_has_affected_systems(self, service: ThreatIntelligenceService):
        alert = service.get_alert("alert-001")
        assert alert is not None
        assert len(alert.affected_systems) >= 1


# ============================================================================
# DLP Policy CRUD Tests
# ============================================================================


class TestDLPPolicyCRUD:
    """Tests for DLP policy CRUD operations."""

    def test_list_policies(self, service: ThreatIntelligenceService):
        policies = service.list_dlp_policies()
        assert len(policies) == 8

    def test_list_policies_filter_type(self, service: ThreatIntelligenceService):
        policies = service.list_dlp_policies(policy_type=DLPPolicyType.PHI_DETECTION)
        assert len(policies) >= 2
        assert all(p.policy_type == DLPPolicyType.PHI_DETECTION for p in policies)

    def test_list_policies_filter_enabled(self, service: ThreatIntelligenceService):
        disabled = service.list_dlp_policies(enabled=False)
        assert len(disabled) >= 1
        assert all(not p.enabled for p in disabled)

    def test_get_policy(self, service: ThreatIntelligenceService):
        policy = service.get_dlp_policy("dlp-001")
        assert policy is not None
        assert policy.name == "PHI Detection - Patient Records"

    def test_get_policy_not_found(self, service: ThreatIntelligenceService):
        assert service.get_dlp_policy("dlp-nonexistent") is None

    def test_create_policy(self, service: ThreatIntelligenceService):
        policy = service.create_dlp_policy(
            name="Test Policy",
            policy_type=DLPPolicyType.PII_DETECTION,
            description="Test policy for unit testing",
            channels=[DLPChannel.EMAIL],
            action=DLPAction.ALERT,
        )
        assert policy.id.startswith("dlp-")
        assert policy.name == "Test Policy"
        assert policy.violation_count_30d == 0

    def test_update_policy_name(self, service: ThreatIntelligenceService):
        updated = service.update_dlp_policy("dlp-001", name="Updated PHI Policy")
        assert updated is not None
        assert updated.name == "Updated PHI Policy"

    def test_update_policy_action(self, service: ThreatIntelligenceService):
        updated = service.update_dlp_policy("dlp-002", action=DLPAction.BLOCK)
        assert updated is not None
        assert updated.action == DLPAction.BLOCK

    def test_update_policy_channels(self, service: ThreatIntelligenceService):
        updated = service.update_dlp_policy(
            "dlp-001",
            channels=[DLPChannel.EMAIL, DLPChannel.API_ENDPOINT],
        )
        assert updated is not None
        assert len(updated.channels) == 2

    def test_update_policy_sensitivity(self, service: ThreatIntelligenceService):
        updated = service.update_dlp_policy("dlp-001", sensitivity_threshold=0.95)
        assert updated is not None
        assert updated.sensitivity_threshold == 0.95

    def test_update_policy_exceptions(self, service: ThreatIntelligenceService):
        updated = service.update_dlp_policy(
            "dlp-001", exceptions=["user1@test.com", "user2@test.com"]
        )
        assert updated is not None
        assert len(updated.exceptions) == 2

    def test_update_policy_not_found(self, service: ThreatIntelligenceService):
        assert service.update_dlp_policy("dlp-nonexistent", name="x") is None

    def test_delete_policy(self, service: ThreatIntelligenceService):
        assert service.delete_dlp_policy("dlp-008") is True
        assert service.get_dlp_policy("dlp-008") is None

    def test_delete_policy_not_found(self, service: ThreatIntelligenceService):
        assert service.delete_dlp_policy("dlp-nonexistent") is False

    def test_enable_policy(self, service: ThreatIntelligenceService):
        result = service.enable_dlp_policy("dlp-008")
        assert result is not None
        assert result.enabled is True

    def test_disable_policy(self, service: ThreatIntelligenceService):
        result = service.disable_dlp_policy("dlp-001")
        assert result is not None
        assert result.enabled is False

    def test_enable_not_found(self, service: ThreatIntelligenceService):
        assert service.enable_dlp_policy("dlp-nonexistent") is None

    def test_disable_not_found(self, service: ThreatIntelligenceService):
        assert service.disable_dlp_policy("dlp-nonexistent") is None

    def test_policy_patterns_structure(self, service: ThreatIntelligenceService):
        policy = service.get_dlp_policy("dlp-003")
        assert policy is not None
        assert len(policy.patterns) == 3
        for p in policy.patterns:
            assert p.pattern_name != ""
            assert p.regex_pattern != ""


# ============================================================================
# DLP Violation Tests
# ============================================================================


class TestDLPViolations:
    """Tests for DLP violation tracking and resolution."""

    def test_list_violations(self, service: ThreatIntelligenceService):
        items, total = service.list_violations()
        assert total == 12

    def test_list_violations_filter_policy(self, service: ThreatIntelligenceService):
        items, total = service.list_violations(policy_id="dlp-001")
        assert total >= 2
        assert all(v.policy_id == "dlp-001" for v in items)

    def test_list_violations_filter_channel(self, service: ThreatIntelligenceService):
        items, total = service.list_violations(channel=DLPChannel.EMAIL)
        assert total >= 3
        assert all(v.channel == DLPChannel.EMAIL for v in items)

    def test_list_violations_filter_resolved(self, service: ThreatIntelligenceService):
        items, total = service.list_violations(resolved=False)
        assert all(not v.resolved for v in items)

    def test_list_violations_pagination(self, service: ThreatIntelligenceService):
        items, total = service.list_violations(limit=5, offset=0)
        assert len(items) == 5
        assert total == 12

    def test_get_violation(self, service: ThreatIntelligenceService):
        v = service.get_violation("viol-001")
        assert v is not None
        assert v.policy_id == "dlp-001"

    def test_get_violation_not_found(self, service: ThreatIntelligenceService):
        assert service.get_violation("viol-nonexistent") is None

    def test_create_violation(self, service: ThreatIntelligenceService):
        v = service.create_violation(
            policy_id="dlp-001",
            channel=DLPChannel.EMAIL,
            user_id="test-user",
            content_summary="Test violation",
            data_classification="PHI",
            action_taken=DLPAction.BLOCK,
        )
        assert v is not None
        assert v.id.startswith("viol-")
        assert v.resolved is False

    def test_create_violation_invalid_policy(self, service: ThreatIntelligenceService):
        v = service.create_violation(
            policy_id="dlp-nonexistent",
            channel=DLPChannel.EMAIL,
            action_taken=DLPAction.BLOCK,
        )
        assert v is None

    def test_create_violation_updates_policy_count(self, service: ThreatIntelligenceService):
        policy_before = service.get_dlp_policy("dlp-001")
        assert policy_before is not None
        count_before = policy_before.violation_count_30d

        service.create_violation(
            policy_id="dlp-001",
            channel=DLPChannel.EMAIL,
            action_taken=DLPAction.BLOCK,
        )

        policy_after = service.get_dlp_policy("dlp-001")
        assert policy_after is not None
        assert policy_after.violation_count_30d == count_before + 1

    def test_resolve_violation(self, service: ThreatIntelligenceService):
        result = service.resolve_violation(
            "viol-001", resolution_notes="Issue addressed"
        )
        assert result is not None
        assert result.resolved is True
        assert result.resolution_notes == "Issue addressed"

    def test_resolve_violation_not_found(self, service: ThreatIntelligenceService):
        assert service.resolve_violation(
            "viol-nonexistent", resolution_notes="test"
        ) is None


# ============================================================================
# Training Management Tests
# ============================================================================


class TestTrainingManagement:
    """Tests for security awareness training management."""

    def test_list_trainings(self, service: ThreatIntelligenceService):
        trainings = service.list_trainings()
        assert len(trainings) == 5

    def test_get_training(self, service: ThreatIntelligenceService):
        t = service.get_training("train-001")
        assert t is not None
        assert t.name == "Annual HIPAA Security Training"

    def test_get_training_not_found(self, service: ThreatIntelligenceService):
        assert service.get_training("train-nonexistent") is None

    def test_create_training(self, service: ThreatIntelligenceService):
        t = service.create_training(
            name="Test Training",
            training_type="Awareness",
            description="Test training program",
            required_for_roles=["all"],
            total_assigned=100,
        )
        assert t.id.startswith("train-")
        assert t.total_completed == 0
        assert t.pass_rate == 0.0

    def test_update_training_completed(self, service: ThreatIntelligenceService):
        result = service.update_training("train-001", total_completed=200)
        assert result is not None
        assert result.total_completed == 200

    def test_update_training_pass_rate(self, service: ThreatIntelligenceService):
        result = service.update_training("train-001", pass_rate=98.5)
        assert result is not None
        assert result.pass_rate == 98.5

    def test_update_training_phishing_rate(self, service: ThreatIntelligenceService):
        result = service.update_training(
            "train-002", phishing_simulation_click_rate=5.0
        )
        assert result is not None
        assert result.phishing_simulation_click_rate == 5.0

    def test_update_training_not_found(self, service: ThreatIntelligenceService):
        assert service.update_training("train-nonexistent", total_completed=1) is None


# ============================================================================
# Metrics Tests
# ============================================================================


class TestMetrics:
    """Tests for threat, DLP, and training metrics aggregation."""

    def test_threat_metrics_total(self, service: ThreatIntelligenceService):
        metrics = service.get_threat_metrics()
        assert metrics.total_indicators == 10

    def test_threat_metrics_by_category(self, service: ThreatIntelligenceService):
        metrics = service.get_threat_metrics()
        assert len(metrics.indicators_by_category) > 0
        assert "APT" in metrics.indicators_by_category

    def test_threat_metrics_by_severity(self, service: ThreatIntelligenceService):
        metrics = service.get_threat_metrics()
        assert "CRITICAL" in metrics.indicators_by_severity
        assert metrics.indicators_by_severity["CRITICAL"] >= 3

    def test_threat_metrics_active_threats(self, service: ThreatIntelligenceService):
        metrics = service.get_threat_metrics()
        # NEW and UNDER_INVESTIGATION statuses
        assert metrics.active_threats >= 4

    def test_threat_metrics_mitre_coverage(self, service: ThreatIntelligenceService):
        metrics = service.get_threat_metrics()
        assert len(metrics.mitre_technique_coverage) > 0
        assert "T1071.001" in metrics.mitre_technique_coverage

    def test_threat_metrics_feeds(self, service: ThreatIntelligenceService):
        metrics = service.get_threat_metrics()
        assert metrics.total_feeds == 4
        assert metrics.active_feeds == 3  # feed-004 is disabled

    def test_threat_metrics_alerts(self, service: ThreatIntelligenceService):
        metrics = service.get_threat_metrics()
        assert metrics.total_alerts == 6
        assert metrics.unacknowledged_alerts >= 3

    def test_threat_metrics_confidence(self, service: ThreatIntelligenceService):
        metrics = service.get_threat_metrics()
        assert metrics.mean_confidence_score > 0

    def test_dlp_metrics_total(self, service: ThreatIntelligenceService):
        metrics = service.get_dlp_metrics()
        assert metrics.total_policies == 8
        assert metrics.active_policies == 7

    def test_dlp_metrics_violations_by_channel(self, service: ThreatIntelligenceService):
        metrics = service.get_dlp_metrics()
        assert len(metrics.violations_by_channel) > 0
        assert "EMAIL" in metrics.violations_by_channel

    def test_dlp_metrics_violations_by_policy_type(self, service: ThreatIntelligenceService):
        metrics = service.get_dlp_metrics()
        assert len(metrics.violations_by_policy_type) > 0

    def test_dlp_metrics_blocked_count(self, service: ThreatIntelligenceService):
        metrics = service.get_dlp_metrics()
        assert metrics.blocked_count >= 4

    def test_dlp_metrics_resolved_unresolved(self, service: ThreatIntelligenceService):
        metrics = service.get_dlp_metrics()
        assert metrics.resolved_count + metrics.unresolved_count == 12

    def test_training_compliance_total(self, service: ThreatIntelligenceService):
        compliance = service.get_training_compliance()
        assert compliance.total_trainings == 5

    def test_training_compliance_completion_rate(self, service: ThreatIntelligenceService):
        compliance = service.get_training_compliance()
        assert compliance.overall_completion_rate > 0
        assert compliance.overall_completion_rate <= 100

    def test_training_compliance_pass_rate(self, service: ThreatIntelligenceService):
        compliance = service.get_training_compliance()
        assert compliance.overall_pass_rate > 0

    def test_training_compliance_phishing(self, service: ThreatIntelligenceService):
        compliance = service.get_training_compliance()
        assert compliance.avg_phishing_click_rate > 0

    def test_training_compliance_overdue(self, service: ThreatIntelligenceService):
        compliance = service.get_training_compliance()
        # train-004 has deadline in the past with incomplete assignment
        assert compliance.overdue_trainings >= 1


# ============================================================================
# API Endpoint Integration Tests
# ============================================================================


@pytest.mark.anyio
class TestIndicatorAPI:
    """API integration tests for indicator endpoints."""

    async def test_list_indicators_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/indicators")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    async def test_list_indicators_filter_severity(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/indicators", params={"severity": "CRITICAL"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["severity"] == "CRITICAL"

    async def test_list_indicators_pagination(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/indicators", params={"limit": 3, "offset": 0}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["total"] == 10

    async def test_search_indicators_api(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/indicators/search", params={"value": "185.220"}
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_indicator_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/indicators/ioc-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ioc-001"

    async def test_get_indicator_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/indicators/ioc-nonexistent")
        assert resp.status_code == 404

    async def test_create_indicator_api(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/indicators",
            json={
                "ioc_type": "IP_ADDRESS",
                "value": "1.2.3.4",
                "threat_category": "APT",
                "severity": "HIGH",
                "description": "API test indicator",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["value"] == "1.2.3.4"
        assert data["status"] == "NEW"

    async def test_update_indicator_api(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/indicators/ioc-001",
            json={"severity": "MEDIUM", "description": "Updated via API"},
        )
        assert resp.status_code == 200
        assert resp.json()["severity"] == "MEDIUM"

    async def test_update_indicator_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/indicators/ioc-nonexistent",
            json={"severity": "LOW"},
        )
        assert resp.status_code == 404

    async def test_delete_indicator_api(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/indicators/ioc-010")
        assert resp.status_code == 204

    async def test_delete_indicator_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/indicators/ioc-nonexistent")
        assert resp.status_code == 404


@pytest.mark.anyio
class TestFeedAPI:
    """API integration tests for feed endpoints."""

    async def test_list_feeds_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/feeds")
        assert resp.status_code == 200
        assert len(resp.json()) == 4

    async def test_get_feed_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/feeds/feed-001")
        assert resp.status_code == 200
        assert resp.json()["name"] == "AlienVault OTX"

    async def test_get_feed_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/feeds/feed-nonexistent")
        assert resp.status_code == 404

    async def test_create_feed_api(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/feeds",
            json={
                "name": "API Test Feed",
                "provider": "Test Provider",
                "url": "https://test.com/feed",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "API Test Feed"

    async def test_update_feed_api(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/feeds/feed-001",
            json={"name": "Updated Feed Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Feed Name"

    async def test_delete_feed_api(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/feeds/feed-004")
        assert resp.status_code == 204


@pytest.mark.anyio
class TestAlertAPI:
    """API integration tests for alert endpoints."""

    async def test_list_alerts_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    async def test_list_alerts_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/alerts", params={"severity": "CRITICAL"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["severity"] == "CRITICAL"

    async def test_get_alert_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts/alert-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "alert-001"

    async def test_get_alert_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts/alert-nonexistent")
        assert resp.status_code == 404

    async def test_create_alert_api(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/alerts",
            json={
                "title": "API Test Alert",
                "severity": "HIGH",
                "category": "PHISHING",
                "description": "Test alert from API",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["acknowledged"] is False

    async def test_acknowledge_alert_api(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/alerts/alert-001/acknowledge",
            params={"acknowledged_by": "api-user"},
        )
        assert resp.status_code == 200
        assert resp.json()["acknowledged"] is True

    async def test_acknowledge_alert_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/alerts/alert-nonexistent/acknowledge",
            params={"acknowledged_by": "api-user"},
        )
        assert resp.status_code == 404

    async def test_mitigate_alert_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/alerts/alert-001/mitigate")
        assert resp.status_code == 200
        assert resp.json()["mitigated"] is True

    async def test_mitigate_alert_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/alerts/alert-nonexistent/mitigate"
        )
        assert resp.status_code == 404


@pytest.mark.anyio
class TestDLPPolicyAPI:
    """API integration tests for DLP policy endpoints."""

    async def test_list_policies_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dlp/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    async def test_list_policies_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dlp/policies",
            params={"policy_type": "PHI_DETECTION"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["policy_type"] == "PHI_DETECTION"

    async def test_list_policies_filter_enabled(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dlp/policies", params={"enabled": False}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["enabled"] is False

    async def test_get_policy_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dlp/policies/dlp-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "dlp-001"

    async def test_get_policy_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dlp/policies/dlp-nonexistent")
        assert resp.status_code == 404

    async def test_create_policy_api(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/dlp/policies",
            json={
                "name": "API Test Policy",
                "policy_type": "PII_DETECTION",
                "channels": ["EMAIL"],
                "action": "ALERT",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "API Test Policy"

    async def test_update_policy_api(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dlp/policies/dlp-001",
            json={"name": "Updated PHI Policy", "action": "QUARANTINE"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated PHI Policy"
        assert resp.json()["action"] == "QUARANTINE"

    async def test_delete_policy_api(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dlp/policies/dlp-008")
        assert resp.status_code == 204

    async def test_enable_policy_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/dlp/policies/dlp-008/enable")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    async def test_disable_policy_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/dlp/policies/dlp-001/disable")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    async def test_enable_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/dlp/policies/dlp-nonexistent/enable"
        )
        assert resp.status_code == 404

    async def test_disable_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/dlp/policies/dlp-nonexistent/disable"
        )
        assert resp.status_code == 404


@pytest.mark.anyio
class TestDLPViolationAPI:
    """API integration tests for DLP violation endpoints."""

    async def test_list_violations_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dlp/violations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    async def test_list_violations_filter_policy(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dlp/violations", params={"policy_id": "dlp-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["policy_id"] == "dlp-001"

    async def test_list_violations_filter_channel(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dlp/violations", params={"channel": "EMAIL"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["channel"] == "EMAIL"

    async def test_list_violations_filter_resolved(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dlp/violations", params={"resolved": False}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["resolved"] is False

    async def test_get_violation_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dlp/violations/viol-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "viol-001"

    async def test_get_violation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dlp/violations/viol-nonexistent")
        assert resp.status_code == 404

    async def test_resolve_violation_api(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/dlp/violations/viol-001/resolve",
            json={"resolution_notes": "Resolved via API test"},
        )
        assert resp.status_code == 200
        assert resp.json()["resolved"] is True
        assert resp.json()["resolution_notes"] == "Resolved via API test"

    async def test_resolve_violation_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/dlp/violations/viol-nonexistent/resolve",
            json={"resolution_notes": "test"},
        )
        assert resp.status_code == 404


@pytest.mark.anyio
class TestTrainingAPI:
    """API integration tests for training endpoints."""

    async def test_list_trainings_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    async def test_get_training_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training/train-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "train-001"

    async def test_get_training_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training/train-nonexistent")
        assert resp.status_code == 404

    async def test_create_training_api(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/training",
            params={
                "name": "API Test Training",
                "training_type": "Awareness",
                "description": "Created via API",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "API Test Training"

    async def test_update_training_api(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/training/train-001",
            params={"total_completed": 230, "pass_rate": 96.0},
        )
        assert resp.status_code == 200
        assert resp.json()["total_completed"] == 230

    async def test_update_training_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/training/train-nonexistent",
            params={"total_completed": 1},
        )
        assert resp.status_code == 404


@pytest.mark.anyio
class TestMetricsAPI:
    """API integration tests for metrics endpoints."""

    async def test_threat_metrics_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics/threats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_indicators"] == 10
        assert "indicators_by_category" in data
        assert "mitre_technique_coverage" in data

    async def test_dlp_metrics_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics/dlp")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_policies"] == 8
        assert "violations_by_channel" in data

    async def test_training_metrics_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics/training")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trainings"] == 5
        assert "overall_completion_rate" in data
        assert "avg_phishing_click_rate" in data
