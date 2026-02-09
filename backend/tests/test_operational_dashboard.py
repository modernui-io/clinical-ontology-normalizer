"""Tests for Operational Dashboard & SLA Management (COO-5).

Covers:
- Seed data verification
- SLA CRUD (create, read, update, delete)
- SLA measurement recording and breach detection
- SLA compliance trending
- System health monitoring
- Trial operations summaries
- Automated process management (CRUD + trigger)
- Alert management (CRUD + acknowledge)
- Full dashboard snapshot
- Key metrics calculation
- Capacity assessment
- Filtering and pagination
- Error handling (404)
- API endpoint integration
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.operational_dashboard import (
    AlertCreateRequest,
    AlertSeverity,
    OperationalStatus,
    ProcessCreateRequest,
    ProcessStatus,
    ProcessUpdateRequest,
    SLACategory,
    SLACreateRequest,
    SLAMeasurementCreateRequest,
    SLAStatus,
    SLAUpdateRequest,
)
from app.services.operational_dashboard_service import (
    OperationalDashboardService,
    get_operational_dashboard_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

API_PREFIX = "/operational-dashboard"


@pytest.fixture(autouse=True)
def clean_service():
    """Ensure a fresh service for every test (with seed data)."""
    svc = get_operational_dashboard_service()
    svc.clear()
    yield svc
    svc.clear()


@pytest.fixture
def svc(clean_service) -> OperationalDashboardService:
    """Shorthand for the clean service."""
    return clean_service


@pytest.fixture
async def api_client():
    """Async client for API tests (no DB needed -- service is in-memory)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test/api/v1",
    ) as ac:
        yield ac


# ===========================================================================
# 1. Seed Data Verification
# ===========================================================================


class TestSeedData:
    """Verify pre-populated data is present after clear() (re-populate)."""

    def test_seed_sla_definitions_count(self, svc: OperationalDashboardService):
        result = svc.list_slas()
        assert result.total == 8

    def test_seed_sla_all_have_ids(self, svc: OperationalDashboardService):
        result = svc.list_slas()
        for sla in result.items:
            assert sla.id.startswith("SLA-")

    def test_seed_sla_categories_present(self, svc: OperationalDashboardService):
        result = svc.list_slas()
        categories = {s.category for s in result.items}
        assert SLACategory.API_UPTIME in categories
        assert SLACategory.NLP_TURNAROUND in categories
        assert SLACategory.DATA_FRESHNESS in categories
        assert SLACategory.SCREENING_ACCURACY in categories
        assert SLACategory.RESPONSE_TIME in categories
        assert SLACategory.COMPLIANCE_REPORTING in categories

    def test_seed_sla_measurements_exist(self, svc: OperationalDashboardService):
        stats = svc.get_stats()
        assert stats["sla_measurements"] >= 30

    def test_seed_trial_summaries_count(self, svc: OperationalDashboardService):
        summaries = svc.get_trial_summaries()
        assert len(summaries) == 3

    def test_seed_trial_names(self, svc: OperationalDashboardService):
        summaries = svc.get_trial_summaries()
        names = {s.trial_name for s in summaries}
        assert any("EYLEA" in n for n in names)
        assert any("Dupixent" in n for n in names)
        assert any("Libtayo" in n for n in names)

    def test_seed_system_health_count(self, svc: OperationalDashboardService):
        health = svc.get_system_health()
        assert len(health) == 6

    def test_seed_system_health_services(self, svc: OperationalDashboardService):
        health = svc.get_system_health()
        names = {h.service_name for h in health}
        assert "API Gateway" in names
        assert "NLP Pipeline" in names
        assert "Database (PostgreSQL)" in names

    def test_seed_automated_processes_count(self, svc: OperationalDashboardService):
        result = svc.list_processes()
        assert result.total == 8

    def test_seed_processes_have_ids(self, svc: OperationalDashboardService):
        result = svc.list_processes()
        for p in result.items:
            assert p.id.startswith("PROC-")

    def test_seed_alerts_count(self, svc: OperationalDashboardService):
        alerts = svc.list_alerts()
        assert len(alerts) == 5

    def test_seed_alerts_have_ids(self, svc: OperationalDashboardService):
        alerts = svc.list_alerts()
        for a in alerts:
            assert a.id.startswith("ALERT-")

    def test_seed_breached_sla_exists(self, svc: OperationalDashboardService):
        breached = svc.detect_breaches()
        assert len(breached) >= 1

    def test_seed_at_risk_sla_exists(self, svc: OperationalDashboardService):
        slas = svc.list_slas()
        at_risk = [s for s in slas.items if s.status == SLAStatus.AT_RISK]
        assert len(at_risk) >= 1

    def test_seed_stats(self, svc: OperationalDashboardService):
        stats = svc.get_stats()
        assert stats["sla_definitions"] == 8
        assert stats["trial_summaries"] == 3
        assert stats["system_health_entries"] == 6
        assert stats["automated_processes"] == 8
        assert stats["alerts"] == 5


# ===========================================================================
# 2. SLA CRUD
# ===========================================================================


class TestSLACRUD:
    """Test SLA definition create, read, update, delete."""

    def test_create_sla(self, svc: OperationalDashboardService):
        req = SLACreateRequest(
            name="Test SLA",
            category=SLACategory.API_UPTIME,
            target_value=99.5,
            unit="%",
        )
        sla = svc.create_sla(req)
        assert sla.id is not None
        assert sla.name == "Test SLA"
        assert sla.status == SLAStatus.NOT_MEASURED

    def test_create_sla_with_penalty(self, svc: OperationalDashboardService):
        req = SLACreateRequest(
            name="Premium SLA",
            category=SLACategory.RESPONSE_TIME,
            target_value=200.0,
            unit="ms",
            penalty_amount=25000.0,
            client_id="CLIENT-123",
        )
        sla = svc.create_sla(req)
        assert sla.penalty_amount == 25000.0
        assert sla.client_id == "CLIENT-123"

    def test_get_sla_by_id(self, svc: OperationalDashboardService):
        sla = svc.get_sla("SLA-001")
        assert sla is not None
        assert sla.name == "API Uptime"

    def test_get_sla_not_found(self, svc: OperationalDashboardService):
        sla = svc.get_sla("SLA-NONEXISTENT")
        assert sla is None

    def test_update_sla_name(self, svc: OperationalDashboardService):
        req = SLAUpdateRequest(name="Updated API Uptime")
        sla = svc.update_sla("SLA-001", req)
        assert sla is not None
        assert sla.name == "Updated API Uptime"

    def test_update_sla_target(self, svc: OperationalDashboardService):
        req = SLAUpdateRequest(target_value=99.99)
        sla = svc.update_sla("SLA-001", req)
        assert sla is not None
        assert sla.target_value == 99.99

    def test_update_sla_not_found(self, svc: OperationalDashboardService):
        req = SLAUpdateRequest(name="nope")
        result = svc.update_sla("SLA-NONE", req)
        assert result is None

    def test_delete_sla(self, svc: OperationalDashboardService):
        assert svc.delete_sla("SLA-001") is True
        assert svc.get_sla("SLA-001") is None

    def test_delete_sla_removes_measurements(self, svc: OperationalDashboardService):
        svc.delete_sla("SLA-001")
        measurements = svc.get_measurements("SLA-001")
        assert len(measurements) == 0

    def test_delete_sla_not_found(self, svc: OperationalDashboardService):
        assert svc.delete_sla("SLA-NONEXISTENT") is False

    def test_list_slas_filter_by_category(self, svc: OperationalDashboardService):
        result = svc.list_slas(category=SLACategory.DATA_FRESHNESS)
        assert result.total >= 1
        for sla in result.items:
            assert sla.category == SLACategory.DATA_FRESHNESS

    def test_list_slas_no_filter(self, svc: OperationalDashboardService):
        result = svc.list_slas()
        assert result.total == 8

    def test_create_sla_increments_count(self, svc: OperationalDashboardService):
        initial = svc.list_slas().total
        svc.create_sla(SLACreateRequest(
            name="New", category=SLACategory.API_UPTIME, target_value=99.0, unit="%"
        ))
        assert svc.list_slas().total == initial + 1


# ===========================================================================
# 3. SLA Measurements & Breach Detection
# ===========================================================================


class TestSLAMeasurements:
    """Test recording measurements and breach detection logic."""

    def test_record_measurement_meeting(self, svc: OperationalDashboardService):
        req = SLAMeasurementCreateRequest(sla_id="SLA-001", value=99.95)
        m = svc.record_measurement(req)
        assert m is not None
        assert m.meets_target is True

    def test_record_measurement_breach_percentage(self, svc: OperationalDashboardService):
        req = SLAMeasurementCreateRequest(sla_id="SLA-001", value=98.0)
        m = svc.record_measurement(req)
        assert m is not None
        assert m.meets_target is False

    def test_record_measurement_breach_seconds(self, svc: OperationalDashboardService):
        # NLP turnaround: target 5.0s, lower is better
        req = SLAMeasurementCreateRequest(sla_id="SLA-002", value=6.0)
        m = svc.record_measurement(req)
        assert m is not None
        assert m.meets_target is False

    def test_record_measurement_meeting_seconds(self, svc: OperationalDashboardService):
        req = SLAMeasurementCreateRequest(sla_id="SLA-002", value=3.5)
        m = svc.record_measurement(req)
        assert m is not None
        assert m.meets_target is True

    def test_record_measurement_updates_current_value(self, svc: OperationalDashboardService):
        svc.record_measurement(SLAMeasurementCreateRequest(sla_id="SLA-001", value=99.88))
        sla = svc.get_sla("SLA-001")
        assert sla is not None
        assert sla.current_value == 99.88

    def test_record_measurement_updates_status_to_breached(self, svc: OperationalDashboardService):
        svc.record_measurement(SLAMeasurementCreateRequest(sla_id="SLA-001", value=95.0))
        sla = svc.get_sla("SLA-001")
        assert sla is not None
        assert sla.status == SLAStatus.BREACHED

    def test_record_measurement_updates_status_to_meeting(self, svc: OperationalDashboardService):
        # First breach it
        svc.record_measurement(SLAMeasurementCreateRequest(sla_id="SLA-001", value=95.0))
        # Then meet it
        svc.record_measurement(SLAMeasurementCreateRequest(sla_id="SLA-001", value=99.95))
        sla = svc.get_sla("SLA-001")
        assert sla is not None
        assert sla.status == SLAStatus.MEETING

    def test_record_measurement_increments_breach_count(self, svc: OperationalDashboardService):
        sla = svc.get_sla("SLA-001")
        initial_breaches = sla.breach_count_30d
        svc.record_measurement(SLAMeasurementCreateRequest(sla_id="SLA-001", value=90.0))
        sla = svc.get_sla("SLA-001")
        assert sla.breach_count_30d == initial_breaches + 1

    def test_record_measurement_invalid_sla(self, svc: OperationalDashboardService):
        req = SLAMeasurementCreateRequest(sla_id="SLA-NONEXISTENT", value=99.0)
        m = svc.record_measurement(req)
        assert m is None

    def test_get_measurements(self, svc: OperationalDashboardService):
        measurements = svc.get_measurements("SLA-001")
        assert len(measurements) >= 1

    def test_get_measurements_sorted_newest_first(self, svc: OperationalDashboardService):
        measurements = svc.get_measurements("SLA-001")
        if len(measurements) >= 2:
            assert measurements[0].measured_at >= measurements[1].measured_at

    def test_get_measurements_with_limit(self, svc: OperationalDashboardService):
        measurements = svc.get_measurements("SLA-001", limit=2)
        assert len(measurements) <= 2

    def test_detect_breaches(self, svc: OperationalDashboardService):
        breached = svc.detect_breaches()
        assert len(breached) >= 1
        for sla in breached:
            assert sla.status == SLAStatus.BREACHED

    def test_patients_per_day_meets_target(self, svc: OperationalDashboardService):
        # SLA-008 is patients/day with target 1000
        req = SLAMeasurementCreateRequest(sla_id="SLA-008", value=1200.0)
        m = svc.record_measurement(req)
        assert m is not None
        assert m.meets_target is True

    def test_patients_per_day_breaches(self, svc: OperationalDashboardService):
        req = SLAMeasurementCreateRequest(sla_id="SLA-008", value=800.0)
        m = svc.record_measurement(req)
        assert m is not None
        assert m.meets_target is False


# ===========================================================================
# 4. SLA Compliance Trending
# ===========================================================================


class TestSLAComplianceTrend:
    """Test historical compliance trend generation."""

    def test_compliance_trend_returns_list(self, svc: OperationalDashboardService):
        trend = svc.get_sla_compliance_trend("SLA-001")
        assert isinstance(trend, list)

    def test_compliance_trend_period_count(self, svc: OperationalDashboardService):
        trend = svc.get_sla_compliance_trend("SLA-001", periods=7)
        assert len(trend) == 7

    def test_compliance_trend_custom_periods(self, svc: OperationalDashboardService):
        trend = svc.get_sla_compliance_trend("SLA-001", periods=14)
        assert len(trend) == 14

    def test_compliance_trend_has_period_labels(self, svc: OperationalDashboardService):
        trend = svc.get_sla_compliance_trend("SLA-001", periods=3)
        for item in trend:
            assert item.period is not None
            assert len(item.period) == 10  # YYYY-MM-DD

    def test_compliance_trend_empty_sla(self, svc: OperationalDashboardService):
        # Create SLA with no measurements
        sla = svc.create_sla(SLACreateRequest(
            name="Empty", category=SLACategory.API_UPTIME, target_value=99.0, unit="%"
        ))
        trend = svc.get_sla_compliance_trend(sla.id)
        assert isinstance(trend, list)


# ===========================================================================
# 5. System Health
# ===========================================================================


class TestSystemHealth:
    """Test system health monitoring."""

    def test_get_all_system_health(self, svc: OperationalDashboardService):
        health = svc.get_system_health()
        assert len(health) == 6

    def test_get_service_health(self, svc: OperationalDashboardService):
        health = svc.get_service_health("API Gateway")
        assert health is not None
        assert health.service_name == "API Gateway"

    def test_get_service_health_not_found(self, svc: OperationalDashboardService):
        health = svc.get_service_health("Nonexistent Service")
        assert health is None

    def test_update_service_health(self, svc: OperationalDashboardService):
        result = svc.update_service_health("API Gateway", OperationalStatus.DEGRADED)
        assert result is not None
        assert result.status == OperationalStatus.DEGRADED

    def test_update_service_health_sets_incident_time(self, svc: OperationalDashboardService):
        result = svc.update_service_health("API Gateway", OperationalStatus.DOWN)
        assert result is not None
        assert result.last_incident is not None

    def test_update_service_health_not_found(self, svc: OperationalDashboardService):
        result = svc.update_service_health("Fake Service", OperationalStatus.DOWN)
        assert result is None

    def test_degraded_service_exists_in_seed(self, svc: OperationalDashboardService):
        health = svc.get_system_health()
        degraded = [h for h in health if h.status == OperationalStatus.DEGRADED]
        assert len(degraded) >= 1

    def test_system_health_has_metrics(self, svc: OperationalDashboardService):
        health = svc.get_service_health("API Gateway")
        assert health.uptime_percent_30d > 0
        assert health.response_time_p99_ms > 0


# ===========================================================================
# 6. Trial Operations Summaries
# ===========================================================================


class TestTrialOperations:
    """Test trial operations summary retrieval."""

    def test_get_all_trial_summaries(self, svc: OperationalDashboardService):
        summaries = svc.get_trial_summaries()
        assert len(summaries) == 3

    def test_get_trial_summary_by_id(self, svc: OperationalDashboardService):
        summary = svc.get_trial_summary("TRIAL-EYLEA-HD-001")
        assert summary is not None
        assert "EYLEA" in summary.trial_name

    def test_get_trial_summary_not_found(self, svc: OperationalDashboardService):
        summary = svc.get_trial_summary("TRIAL-NONEXISTENT")
        assert summary is None

    def test_trial_summary_has_enrollment_data(self, svc: OperationalDashboardService):
        summary = svc.get_trial_summary("TRIAL-EYLEA-HD-001")
        assert summary.patients_screened > 0
        assert summary.patients_enrolled > 0
        assert summary.enrollment_rate_per_week > 0

    def test_trial_summary_has_site_data(self, svc: OperationalDashboardService):
        summary = svc.get_trial_summary("TRIAL-EYLEA-HD-001")
        assert summary.site_count > 0
        assert summary.active_sites > 0

    def test_trial_screen_failure_rate(self, svc: OperationalDashboardService):
        summary = svc.get_trial_summary("TRIAL-EYLEA-HD-001")
        assert 0 <= summary.screen_failure_rate <= 1.0


# ===========================================================================
# 7. Automated Processes
# ===========================================================================


class TestAutomatedProcesses:
    """Test automated process management."""

    def test_list_all_processes(self, svc: OperationalDashboardService):
        result = svc.list_processes()
        assert result.total == 8

    def test_list_processes_filter_by_status(self, svc: OperationalDashboardService):
        result = svc.list_processes(status=ProcessStatus.COMPLETED)
        assert result.total >= 1
        for p in result.items:
            assert p.status == ProcessStatus.COMPLETED

    def test_get_process_by_id(self, svc: OperationalDashboardService):
        proc = svc.get_process("PROC-001")
        assert proc is not None
        assert proc.name == "Daily Patient Screening"

    def test_get_process_not_found(self, svc: OperationalDashboardService):
        proc = svc.get_process("PROC-NONEXISTENT")
        assert proc is None

    def test_create_process(self, svc: OperationalDashboardService):
        req = ProcessCreateRequest(
            name="New Batch Job",
            process_type="batch",
            schedule_cron="0 12 * * *",
        )
        proc = svc.create_process(req)
        assert proc.id is not None
        assert proc.name == "New Batch Job"
        assert proc.status == ProcessStatus.SCHEDULED

    def test_update_process_status(self, svc: OperationalDashboardService):
        req = ProcessUpdateRequest(status=ProcessStatus.PAUSED)
        proc = svc.update_process("PROC-001", req)
        assert proc is not None
        assert proc.status == ProcessStatus.PAUSED

    def test_update_process_name(self, svc: OperationalDashboardService):
        req = ProcessUpdateRequest(name="Renamed Process")
        proc = svc.update_process("PROC-001", req)
        assert proc is not None
        assert proc.name == "Renamed Process"

    def test_update_process_not_found(self, svc: OperationalDashboardService):
        req = ProcessUpdateRequest(name="nope")
        result = svc.update_process("PROC-NONE", req)
        assert result is None

    def test_trigger_process(self, svc: OperationalDashboardService):
        proc = svc.trigger_process("PROC-001")
        assert proc is not None
        assert proc.status == ProcessStatus.RUNNING
        assert proc.last_run is not None

    def test_trigger_clears_last_error(self, svc: OperationalDashboardService):
        # PROC-006 has a last_error set
        proc = svc.trigger_process("PROC-006")
        assert proc is not None
        assert proc.last_error is None

    def test_trigger_process_not_found(self, svc: OperationalDashboardService):
        result = svc.trigger_process("PROC-NONE")
        assert result is None

    def test_delete_process(self, svc: OperationalDashboardService):
        assert svc.delete_process("PROC-001") is True
        assert svc.get_process("PROC-001") is None

    def test_delete_process_not_found(self, svc: OperationalDashboardService):
        assert svc.delete_process("PROC-NONEXISTENT") is False

    def test_create_process_increments_count(self, svc: OperationalDashboardService):
        initial = svc.list_processes().total
        svc.create_process(ProcessCreateRequest(name="Temp", process_type="test"))
        assert svc.list_processes().total == initial + 1

    def test_failed_process_has_error(self, svc: OperationalDashboardService):
        proc = svc.get_process("PROC-006")
        assert proc is not None
        assert proc.status == ProcessStatus.FAILED
        assert proc.last_error is not None


# ===========================================================================
# 8. Alerts
# ===========================================================================


class TestAlerts:
    """Test alert management."""

    def test_list_all_alerts(self, svc: OperationalDashboardService):
        alerts = svc.list_alerts()
        assert len(alerts) == 5

    def test_list_alerts_by_severity(self, svc: OperationalDashboardService):
        critical = svc.list_alerts(severity=AlertSeverity.CRITICAL)
        assert len(critical) >= 1
        for a in critical:
            assert a.severity == AlertSeverity.CRITICAL

    def test_list_alerts_by_acknowledged(self, svc: OperationalDashboardService):
        acked = svc.list_alerts(acknowledged=True)
        for a in acked:
            assert a.acknowledged is True

    def test_list_alerts_unacknowledged(self, svc: OperationalDashboardService):
        unacked = svc.list_alerts(acknowledged=False)
        for a in unacked:
            assert a.acknowledged is False

    def test_list_alerts_with_limit(self, svc: OperationalDashboardService):
        alerts = svc.list_alerts(limit=2)
        assert len(alerts) <= 2

    def test_list_alerts_sorted_newest_first(self, svc: OperationalDashboardService):
        alerts = svc.list_alerts()
        if len(alerts) >= 2:
            assert alerts[0].created_at >= alerts[1].created_at

    def test_get_alert_by_id(self, svc: OperationalDashboardService):
        alert = svc.get_alert("ALERT-001")
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    def test_get_alert_not_found(self, svc: OperationalDashboardService):
        alert = svc.get_alert("ALERT-NONEXISTENT")
        assert alert is None

    def test_create_alert(self, svc: OperationalDashboardService):
        req = AlertCreateRequest(
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="This is a test alert.",
            source="test",
        )
        alert = svc.create_alert(req)
        assert alert.id is not None
        assert alert.title == "Test Alert"
        assert alert.acknowledged is False

    def test_acknowledge_alert(self, svc: OperationalDashboardService):
        alert = svc.acknowledge_alert("ALERT-001", acknowledged_by="admin")
        assert alert is not None
        assert alert.acknowledged is True
        assert alert.acknowledged_by == "admin"

    def test_acknowledge_alert_not_found(self, svc: OperationalDashboardService):
        result = svc.acknowledge_alert("ALERT-NONEXISTENT")
        assert result is None

    def test_delete_alert(self, svc: OperationalDashboardService):
        assert svc.delete_alert("ALERT-001") is True
        assert svc.get_alert("ALERT-001") is None

    def test_delete_alert_not_found(self, svc: OperationalDashboardService):
        assert svc.delete_alert("ALERT-NONEXISTENT") is False

    def test_create_alert_increments_count(self, svc: OperationalDashboardService):
        initial = len(svc.list_alerts())
        svc.create_alert(AlertCreateRequest(
            title="New", message="New alert", severity=AlertSeverity.INFO
        ))
        assert len(svc.list_alerts()) == initial + 1


# ===========================================================================
# 9. Full Dashboard
# ===========================================================================


class TestFullDashboard:
    """Test the unified dashboard snapshot."""

    def test_dashboard_returns_response(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        assert result.dashboard is not None

    def test_dashboard_has_timestamp(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        assert result.dashboard.timestamp is not None

    def test_dashboard_has_overall_status(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        assert result.dashboard.overall_status is not None

    def test_dashboard_active_trials(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        assert result.dashboard.active_trials == 3

    def test_dashboard_total_patients(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        assert result.dashboard.total_patients_pipeline > 0

    def test_dashboard_total_sites(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        assert result.dashboard.total_sites > 0

    def test_dashboard_has_system_health(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        assert len(result.dashboard.system_health) == 6

    def test_dashboard_has_trial_summaries(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        assert len(result.dashboard.trial_summaries) == 3

    def test_dashboard_has_sla_summary(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        assert result.dashboard.sla_summary.total_slas == 8

    def test_dashboard_sla_summary_counts(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        s = result.dashboard.sla_summary
        assert s.meeting + s.at_risk + s.breached + s.not_measured == s.total_slas

    def test_dashboard_has_processes(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        assert len(result.dashboard.automated_processes) == 8

    def test_dashboard_has_alerts(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        assert len(result.dashboard.alerts) == 5

    def test_dashboard_has_key_metrics(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        assert len(result.dashboard.key_metrics) >= 3

    def test_dashboard_overall_status_degraded(self, svc: OperationalDashboardService):
        # We have a breached SLA in seed data, so should be at least DEGRADED
        result = svc.get_full_dashboard()
        assert result.dashboard.overall_status in (
            OperationalStatus.DEGRADED,
            OperationalStatus.IMPAIRED,
        )

    def test_dashboard_overall_status_down_when_service_down(self, svc: OperationalDashboardService):
        svc.update_service_health("API Gateway", OperationalStatus.DOWN)
        result = svc.get_full_dashboard()
        assert result.dashboard.overall_status == OperationalStatus.DOWN

    def test_dashboard_compliance_rate(self, svc: OperationalDashboardService):
        result = svc.get_full_dashboard()
        rate = result.dashboard.sla_summary.overall_compliance_rate
        assert 0 <= rate <= 100


# ===========================================================================
# 10. Key Metrics
# ===========================================================================


class TestKeyMetrics:
    """Test key operational metrics calculation."""

    def test_key_metrics_returns_list(self, svc: OperationalDashboardService):
        metrics = svc.get_key_metrics()
        assert isinstance(metrics, list)
        assert len(metrics) >= 3

    def test_key_metrics_has_cost_per_patient(self, svc: OperationalDashboardService):
        metrics = svc.get_key_metrics()
        names = [m.name for m in metrics]
        assert "Cost per Patient Screened" in names

    def test_key_metrics_has_time_to_match(self, svc: OperationalDashboardService):
        metrics = svc.get_key_metrics()
        names = [m.name for m in metrics]
        assert "Average Time to Match" in names

    def test_key_metrics_has_enrollment_velocity(self, svc: OperationalDashboardService):
        metrics = svc.get_key_metrics()
        names = [m.name for m in metrics]
        assert "Enrollment Velocity" in names

    def test_key_metrics_have_units(self, svc: OperationalDashboardService):
        metrics = svc.get_key_metrics()
        for m in metrics:
            assert m.unit is not None
            assert len(m.unit) > 0

    def test_key_metrics_have_trends(self, svc: OperationalDashboardService):
        metrics = svc.get_key_metrics()
        for m in metrics:
            assert m.trend in ("up", "down", "stable")

    def test_key_metrics_have_change_percent(self, svc: OperationalDashboardService):
        metrics = svc.get_key_metrics()
        for m in metrics:
            assert m.change_percent is not None


# ===========================================================================
# 11. Capacity Assessment
# ===========================================================================


class TestCapacityAssessment:
    """Test operational capacity assessment."""

    def test_capacity_returns_assessment(self, svc: OperationalDashboardService):
        cap = svc.get_capacity_assessment()
        assert cap is not None

    def test_capacity_has_overall_percent(self, svc: OperationalDashboardService):
        cap = svc.get_capacity_assessment()
        assert 0 <= cap.overall_capacity_percent <= 100

    def test_capacity_has_utilization_metrics(self, svc: OperationalDashboardService):
        cap = svc.get_capacity_assessment()
        assert cap.cpu_utilization >= 0
        assert cap.memory_utilization >= 0
        assert cap.storage_utilization >= 0

    def test_capacity_has_connection_info(self, svc: OperationalDashboardService):
        cap = svc.get_capacity_assessment()
        assert cap.active_connections > 0
        assert cap.max_connections > 0

    def test_capacity_has_recommendation(self, svc: OperationalDashboardService):
        cap = svc.get_capacity_assessment()
        assert cap.recommendation in ("normal", "monitor", "scale_up")


# ===========================================================================
# 12. Stats
# ===========================================================================


class TestStats:
    """Test service statistics."""

    def test_stats_has_all_keys(self, svc: OperationalDashboardService):
        stats = svc.get_stats()
        assert "sla_definitions" in stats
        assert "sla_measurements" in stats
        assert "trial_summaries" in stats
        assert "system_health_entries" in stats
        assert "automated_processes" in stats
        assert "alerts" in stats
        assert "unacknowledged_alerts" in stats

    def test_stats_unacknowledged_count(self, svc: OperationalDashboardService):
        stats = svc.get_stats()
        all_alerts = svc.list_alerts()
        unacked = [a for a in all_alerts if not a.acknowledged]
        assert stats["unacknowledged_alerts"] == len(unacked)


# ===========================================================================
# 13. API Endpoint Integration
# ===========================================================================


@pytest.mark.anyio
class TestAPIEndpoints:
    """Integration tests for all API endpoints."""

    async def test_get_dashboard(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/")
        assert resp.status_code == 200
        data = resp.json()
        assert "dashboard" in data

    async def test_get_stats(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/stats")
        assert resp.status_code == 200

    # SLA endpoints

    async def test_list_slas(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/slas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    async def test_list_slas_with_filter(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/slas?category=api_uptime")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_create_sla(self, api_client: AsyncClient):
        resp = await api_client.post(f"{API_PREFIX}/slas", json={
            "name": "API Test SLA",
            "category": "api_uptime",
            "target_value": 99.5,
            "unit": "%",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API Test SLA"

    async def test_get_sla(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/slas/SLA-001")
        assert resp.status_code == 200
        assert resp.json()["name"] == "API Uptime"

    async def test_get_sla_not_found(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/slas/SLA-NONE")
        assert resp.status_code == 404

    async def test_update_sla(self, api_client: AsyncClient):
        resp = await api_client.put(f"{API_PREFIX}/slas/SLA-001", json={
            "name": "Updated API Uptime"
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated API Uptime"

    async def test_update_sla_not_found(self, api_client: AsyncClient):
        resp = await api_client.put(f"{API_PREFIX}/slas/SLA-NONE", json={"name": "x"})
        assert resp.status_code == 404

    async def test_delete_sla(self, api_client: AsyncClient):
        resp = await api_client.delete(f"{API_PREFIX}/slas/SLA-001")
        assert resp.status_code == 204

    async def test_delete_sla_not_found(self, api_client: AsyncClient):
        resp = await api_client.delete(f"{API_PREFIX}/slas/SLA-NONE")
        assert resp.status_code == 404

    async def test_get_breached_slas(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/slas/breaches")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_sla_measurements(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/slas/SLA-001/measurements")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_sla_measurements_not_found(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/slas/SLA-NONE/measurements")
        assert resp.status_code == 404

    async def test_record_measurement(self, api_client: AsyncClient):
        resp = await api_client.post(f"{API_PREFIX}/slas/SLA-001/measurements", json={
            "sla_id": "SLA-001",
            "value": 99.92,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["meets_target"] is True

    async def test_record_measurement_not_found(self, api_client: AsyncClient):
        resp = await api_client.post(f"{API_PREFIX}/slas/SLA-NONE/measurements", json={
            "sla_id": "SLA-NONE",
            "value": 99.0,
        })
        assert resp.status_code == 404

    async def test_get_sla_trend(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/slas/SLA-001/trend")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_sla_trend_not_found(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/slas/SLA-NONE/trend")
        assert resp.status_code == 404

    # System health endpoints

    async def test_get_system_health(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/health")
        assert resp.status_code == 200
        assert len(resp.json()) == 6

    async def test_get_service_health(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/health/API Gateway")
        assert resp.status_code == 200

    async def test_get_service_health_not_found(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/health/Nonexistent")
        assert resp.status_code == 404

    async def test_update_service_health(self, api_client: AsyncClient):
        resp = await api_client.put(f"{API_PREFIX}/health/API Gateway?status=degraded")
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"

    async def test_update_service_health_not_found(self, api_client: AsyncClient):
        resp = await api_client.put(f"{API_PREFIX}/health/Fake?status=down")
        assert resp.status_code == 404

    # Trial operations endpoints

    async def test_get_trial_summaries(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/trials")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    async def test_get_trial_summary(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/trials/TRIAL-EYLEA-HD-001")
        assert resp.status_code == 200

    async def test_get_trial_summary_not_found(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/trials/TRIAL-NONE")
        assert resp.status_code == 404

    # Automated process endpoints

    async def test_list_processes(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/processes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 8

    async def test_list_processes_filter(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/processes?status=completed")
        assert resp.status_code == 200

    async def test_create_process(self, api_client: AsyncClient):
        resp = await api_client.post(f"{API_PREFIX}/processes", json={
            "name": "Test Process",
            "process_type": "batch",
        })
        assert resp.status_code == 201

    async def test_get_process(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/processes/PROC-001")
        assert resp.status_code == 200

    async def test_get_process_not_found(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/processes/PROC-NONE")
        assert resp.status_code == 404

    async def test_update_process(self, api_client: AsyncClient):
        resp = await api_client.put(f"{API_PREFIX}/processes/PROC-001", json={
            "status": "paused",
        })
        assert resp.status_code == 200

    async def test_update_process_not_found(self, api_client: AsyncClient):
        resp = await api_client.put(f"{API_PREFIX}/processes/PROC-NONE", json={
            "name": "x",
        })
        assert resp.status_code == 404

    async def test_trigger_process(self, api_client: AsyncClient):
        resp = await api_client.post(f"{API_PREFIX}/processes/PROC-001/trigger")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    async def test_trigger_process_not_found(self, api_client: AsyncClient):
        resp = await api_client.post(f"{API_PREFIX}/processes/PROC-NONE/trigger")
        assert resp.status_code == 404

    async def test_delete_process(self, api_client: AsyncClient):
        resp = await api_client.delete(f"{API_PREFIX}/processes/PROC-001")
        assert resp.status_code == 204

    async def test_delete_process_not_found(self, api_client: AsyncClient):
        resp = await api_client.delete(f"{API_PREFIX}/processes/PROC-NONE")
        assert resp.status_code == 404

    # Alert endpoints

    async def test_list_alerts(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/alerts")
        assert resp.status_code == 200
        assert len(resp.json()) == 5

    async def test_list_alerts_by_severity(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/alerts?severity=critical")
        assert resp.status_code == 200

    async def test_list_alerts_by_acknowledged(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/alerts?acknowledged=false")
        assert resp.status_code == 200

    async def test_create_alert(self, api_client: AsyncClient):
        resp = await api_client.post(f"{API_PREFIX}/alerts", json={
            "severity": "warning",
            "title": "Test Alert",
            "message": "Test message",
        })
        assert resp.status_code == 201

    async def test_get_alert(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/alerts/ALERT-001")
        assert resp.status_code == 200

    async def test_get_alert_not_found(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/alerts/ALERT-NONE")
        assert resp.status_code == 404

    async def test_acknowledge_alert(self, api_client: AsyncClient):
        resp = await api_client.post(f"{API_PREFIX}/alerts/ALERT-001/acknowledge")
        assert resp.status_code == 200
        assert resp.json()["acknowledged"] is True

    async def test_acknowledge_alert_not_found(self, api_client: AsyncClient):
        resp = await api_client.post(f"{API_PREFIX}/alerts/ALERT-NONE/acknowledge")
        assert resp.status_code == 404

    async def test_delete_alert(self, api_client: AsyncClient):
        resp = await api_client.delete(f"{API_PREFIX}/alerts/ALERT-001")
        assert resp.status_code == 204

    async def test_delete_alert_not_found(self, api_client: AsyncClient):
        resp = await api_client.delete(f"{API_PREFIX}/alerts/ALERT-NONE")
        assert resp.status_code == 404

    # Analytics endpoints

    async def test_get_key_metrics(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_capacity(self, api_client: AsyncClient):
        resp = await api_client.get(f"{API_PREFIX}/capacity")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_capacity_percent" in data
        assert "recommendation" in data
