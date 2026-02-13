"""Tests for Treatment Compliance Monitoring (TCM-MON).

Covers:
- Seed data verification (dosing records, compliance assessments, accountability
  logs, treatment interruption events)
- CRUD for all 4 entities (create, read, update, delete, list, trial_id filter)
- Metrics computation (overall and per-trial)
- Not-found error handling (404s)
- Singleton reset behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.treatment_compliance_monitoring_service import (
    TreatmentComplianceMonitoringService,
    reset_treatment_compliance_monitoring_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/treatment-compliance-monitoring"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_treatment_compliance_monitoring_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> TreatmentComplianceMonitoringService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dosing_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-101",
        "study_drug_name": "Test Drug 100mg",
        "dose_amount": 100.0,
        "dose_unit": "mg",
        "route_of_administration": "Oral",
        "scheduled_date": now.isoformat(),
        "dosing_status": "administered",
    }
    defaults.update(overrides)
    return defaults


def _make_compliance_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-101",
        "assessment_date": now.isoformat(),
        "assessment_period_start": (now - timedelta(days=30)).isoformat(),
        "assessment_period_end": now.isoformat(),
        "assessment_method": "Pill count",
        "assessed_by": "CRA Test User",
        "compliance_level": "fully_compliant",
    }
    defaults.update(overrides)
    return defaults


def _make_accountability_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-101",
        "study_drug_name": "Test Drug 100mg",
        "lot_number": "LOT-TEST-001",
        "action_date": now.isoformat(),
        "performed_by": "Pharmacist Test",
        "accountability_action": "dispensed",
        "quantity_units": 10,
    }
    defaults.update(overrides)
    return defaults


def _make_interruption_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-101",
        "interruption_reason": "adverse_event",
        "study_drug_name": "Test Drug 100mg",
        "interruption_date": now.isoformat(),
        "reported_by": "Dr. Test",
        "interruption_status": "active",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_dosing_records_count(self, svc: TreatmentComplianceMonitoringService):
        records = svc.list_dosing_records()
        assert len(records) == 12

    def test_seed_compliance_assessments_count(self, svc: TreatmentComplianceMonitoringService):
        assessments = svc.list_compliance_assessments()
        assert len(assessments) == 12

    def test_seed_accountability_logs_count(self, svc: TreatmentComplianceMonitoringService):
        logs = svc.list_medication_accountability_logs()
        assert len(logs) == 12

    def test_seed_interruption_events_count(self, svc: TreatmentComplianceMonitoringService):
        events = svc.list_treatment_interruption_events()
        assert len(events) == 12

    def test_seed_dosing_records_per_trial(self, svc: TreatmentComplianceMonitoringService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            records = svc.list_dosing_records(trial_id=trial_id)
            assert len(records) == 4

    def test_seed_compliance_assessments_per_trial(self, svc: TreatmentComplianceMonitoringService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            assessments = svc.list_compliance_assessments(trial_id=trial_id)
            assert len(assessments) == 4

    def test_seed_accountability_logs_per_trial(self, svc: TreatmentComplianceMonitoringService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            logs = svc.list_medication_accountability_logs(trial_id=trial_id)
            assert len(logs) == 4

    def test_seed_interruption_events_per_trial(self, svc: TreatmentComplianceMonitoringService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            events = svc.list_treatment_interruption_events(trial_id=trial_id)
            assert len(events) == 4


# =====================================================================
# DOSING RECORDS CRUD
# =====================================================================


class TestDosingRecordsCrud:
    """Test dosing record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_dosing_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dosing-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_dosing_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dosing-records", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_dosing_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dosing-records/DOS-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DOS-00000001"
        assert data["study_drug_name"] == "Aflibercept 2mg"

    @pytest.mark.anyio
    async def test_get_dosing_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dosing-records/DOS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_dosing_record(self, client: AsyncClient):
        payload = _make_dosing_create()
        resp = await client.post(f"{API_PREFIX}/dosing-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DOS-")
        assert data["study_drug_name"] == "Test Drug 100mg"
        assert data["dosing_status"] == "administered"

    @pytest.mark.anyio
    async def test_update_dosing_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dosing-records/DOS-00000003",
            json={"dosing_status": "administered", "notes": "Rescheduled and administered"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dosing_status"] == "administered"
        assert data["notes"] == "Rescheduled and administered"

    @pytest.mark.anyio
    async def test_update_dosing_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dosing-records/DOS-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dosing_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dosing-records/DOS-00000001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/dosing-records/DOS-00000001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dosing_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dosing-records/DOS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COMPLIANCE ASSESSMENTS CRUD
# =====================================================================


class TestComplianceAssessmentsCrud:
    """Test compliance assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_compliance_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_compliance_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-assessments", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_compliance_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-assessments/CAS-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CAS-00000001"
        assert data["compliance_level"] == "fully_compliant"

    @pytest.mark.anyio
    async def test_get_compliance_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-assessments/CAS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_compliance_assessment(self, client: AsyncClient):
        payload = _make_compliance_create()
        resp = await client.post(f"{API_PREFIX}/compliance-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("CAS-")
        assert data["compliance_level"] == "fully_compliant"

    @pytest.mark.anyio
    async def test_update_compliance_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-assessments/CAS-00000002",
            json={"compliance_level": "non_compliant", "intervention_recommended": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["compliance_level"] == "non_compliant"
        assert data["intervention_recommended"] is True

    @pytest.mark.anyio
    async def test_update_compliance_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-assessments/CAS-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance-assessments/CAS-00000001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/compliance-assessments/CAS-00000001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance-assessments/CAS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# MEDICATION ACCOUNTABILITY LOGS CRUD
# =====================================================================


class TestMedicationAccountabilityLogsCrud:
    """Test medication accountability log CRUD operations."""

    @pytest.mark.anyio
    async def test_list_accountability_logs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accountability-logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_accountability_logs_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accountability-logs", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_accountability_log(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accountability-logs/MAL-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MAL-00000001"
        assert data["accountability_action"] == "dispensed"

    @pytest.mark.anyio
    async def test_get_accountability_log_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accountability-logs/MAL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_accountability_log(self, client: AsyncClient):
        payload = _make_accountability_create()
        resp = await client.post(f"{API_PREFIX}/accountability-logs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("MAL-")
        assert data["accountability_action"] == "dispensed"

    @pytest.mark.anyio
    async def test_update_accountability_log(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/accountability-logs/MAL-00000004",
            json={"temperature_excursion": False, "verified_by": "QA Manager", "notes": "Cleared after review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["temperature_excursion"] is False
        assert data["verified_by"] == "QA Manager"

    @pytest.mark.anyio
    async def test_update_accountability_log_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/accountability-logs/MAL-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_accountability_log(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/accountability-logs/MAL-00000001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/accountability-logs/MAL-00000001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_accountability_log_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/accountability-logs/MAL-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# TREATMENT INTERRUPTION EVENTS CRUD
# =====================================================================


class TestTreatmentInterruptionEventsCrud:
    """Test treatment interruption event CRUD operations."""

    @pytest.mark.anyio
    async def test_list_interruption_events(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interruption-events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_interruption_events_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interruption-events", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_interruption_event(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interruption-events/TIE-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TIE-00000001"
        assert data["interruption_reason"] == "patient_request"
        assert data["interruption_status"] == "resolved"

    @pytest.mark.anyio
    async def test_get_interruption_event_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interruption-events/TIE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_interruption_event(self, client: AsyncClient):
        payload = _make_interruption_create()
        resp = await client.post(f"{API_PREFIX}/interruption-events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("TIE-")
        assert data["interruption_reason"] == "adverse_event"
        assert data["interruption_status"] == "active"

    @pytest.mark.anyio
    async def test_update_interruption_event(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/interruption-events/TIE-00000002",
            json={
                "interruption_status": "resolved",
                "resumption_date": now.isoformat(),
                "resumed_at_same_dose": True,
                "notes": "Resolved after monitoring period",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["interruption_status"] == "resolved"
        assert data["resumed_at_same_dose"] is True

    @pytest.mark.anyio
    async def test_update_interruption_event_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/interruption-events/TIE-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_interruption_event(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/interruption-events/TIE-00000001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/interruption-events/TIE-00000001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_interruption_event_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/interruption-events/TIE-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test treatment compliance metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_dosing_records"] == 12
        assert data["total_compliance_assessments"] == 12
        assert data["total_accountability_logs"] == 12
        assert data["total_interruptions"] == 12
        assert data["avg_compliance_percentage"] > 0
        assert data["avg_interruption_duration_days"] > 0

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_dosing_records"] == 4
        assert data["total_compliance_assessments"] == 4
        assert data["total_accountability_logs"] == 4
        assert data["total_interruptions"] == 4

    def test_metrics_records_by_status(self, svc: TreatmentComplianceMonitoringService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.records_by_status.values())
        assert total_by_status == metrics.total_dosing_records

    def test_metrics_assessments_by_level(self, svc: TreatmentComplianceMonitoringService):
        metrics = svc.get_metrics()
        total_by_level = sum(metrics.assessments_by_level.values())
        assert total_by_level == metrics.total_compliance_assessments

    def test_metrics_logs_by_action(self, svc: TreatmentComplianceMonitoringService):
        metrics = svc.get_metrics()
        total_by_action = sum(metrics.logs_by_action.values())
        assert total_by_action == metrics.total_accountability_logs

    def test_metrics_interruptions_by_reason(self, svc: TreatmentComplianceMonitoringService):
        metrics = svc.get_metrics()
        total_by_reason = sum(metrics.interruptions_by_reason.values())
        assert total_by_reason == metrics.total_interruptions

    def test_metrics_interruptions_by_status(self, svc: TreatmentComplianceMonitoringService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.interruptions_by_status.values())
        assert total_by_status == metrics.total_interruptions

    def test_metrics_avg_compliance_range(self, svc: TreatmentComplianceMonitoringService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.avg_compliance_percentage <= 100

    def test_metrics_avg_interruption_duration_positive(self, svc: TreatmentComplianceMonitoringService):
        metrics = svc.get_metrics()
        assert metrics.avg_interruption_duration_days >= 0


# =====================================================================
# ENUM VALUES IN SEED DATA
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly represented in seed data."""

    @pytest.mark.anyio
    async def test_dosing_statuses_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dosing-records")
        data = resp.json()
        statuses = {item["dosing_status"] for item in data["items"]}
        assert "administered" in statuses
        assert "missed" in statuses
        assert "delayed" in statuses

    @pytest.mark.anyio
    async def test_compliance_levels_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-assessments")
        data = resp.json()
        levels = {item["compliance_level"] for item in data["items"]}
        assert "fully_compliant" in levels
        assert "partially_compliant" in levels
        assert "non_compliant" in levels

    @pytest.mark.anyio
    async def test_accountability_actions_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/accountability-logs")
        data = resp.json()
        actions = {item["accountability_action"] for item in data["items"]}
        assert "dispensed" in actions
        assert "returned" in actions
        assert "destroyed" in actions

    @pytest.mark.anyio
    async def test_interruption_reasons_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interruption-events")
        data = resp.json()
        reasons = {item["interruption_reason"] for item in data["items"]}
        assert "adverse_event" in reasons
        assert "patient_request" in reasons
        assert "supply_issue" in reasons

    @pytest.mark.anyio
    async def test_interruption_statuses_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/interruption-events")
        data = resp.json()
        statuses = {item["interruption_status"] for item in data["items"]}
        assert "active" in statuses
        assert "resolved" in statuses
        assert "permanent" in statuses


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_reset_creates_fresh_instance(self):
        from app.services.treatment_compliance_monitoring_service import (
            get_treatment_compliance_monitoring_service,
        )
        svc1 = get_treatment_compliance_monitoring_service()
        svc2 = reset_treatment_compliance_monitoring_service()
        assert svc1 is not svc2

    def test_get_service_returns_same_instance(self):
        from app.services.treatment_compliance_monitoring_service import (
            get_treatment_compliance_monitoring_service,
        )
        svc1 = get_treatment_compliance_monitoring_service()
        svc2 = get_treatment_compliance_monitoring_service()
        assert svc1 is svc2

    def test_reset_reseeds_data(self):
        from app.services.treatment_compliance_monitoring_service import (
            get_treatment_compliance_monitoring_service,
        )
        svc = get_treatment_compliance_monitoring_service()
        svc.delete_dosing_record("DOS-00000001")
        assert svc.get_dosing_record("DOS-00000001") is None
        svc2 = reset_treatment_compliance_monitoring_service()
        assert svc2.get_dosing_record("DOS-00000001") is not None
