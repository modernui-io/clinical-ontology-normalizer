"""Tests for Clinical Monitoring (CLINICAL-18).

Covers:
- Seed data verification (visits, findings, SDV records, reports, CAPAs)
- Visit CRUD (create, read, update, delete, list, filter by trial/site/type/status/CRA)
- Visit lifecycle (schedule, confirm, start, complete, cancel)
- Finding CRUD (create, read, update, list, filter by severity/category/status)
- Finding lifecycle (resolve, escalate)
- SDV record creation and tracking (record, list, filter, rate by site, summary)
- Monitoring report CRUD (create, read, update, list, filter, submit, approve)
- CAPA workflow (create, update, close with effectiveness check)
- Monitoring metrics computation
- Site monitoring summary
- Error handling (404s, 400s, invalid state transitions)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.clinical_monitoring import (
    CAPAItemCreate,
    CAPAItemUpdate,
    CAPAStatus,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    MonitoringFindingCreate,
    MonitoringFindingUpdate,
    MonitoringReportCreate,
    MonitoringReportUpdate,
    MonitoringVisitCreate,
    MonitoringVisitUpdate,
    ReportStatus,
    ReportSubmitPayload,
    SDVRecordCreate,
    SDVStatus,
    VisitCompletePayload,
    VisitStartPayload,
    VisitStatus,
    VisitType,
)
from app.services.clinical_monitoring_service import (
    ClinicalMonitoringService,
    get_clinical_monitoring_service,
    reset_clinical_monitoring_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-monitoring"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_monitoring_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalMonitoringService:
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

NOW = datetime.now(timezone.utc)


def _make_visit_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "visit_type": "routine",
        "cra_name": "Test CRA",
        "cra_id": "CRA-TEST",
        "scheduled_date": (NOW + timedelta(days=7)).isoformat(),
        "objectives": ["Routine monitoring"],
    }
    defaults.update(overrides)
    return defaults


def _make_finding_create(**overrides) -> dict:
    defaults = {
        "visit_id": "MV-001",
        "severity": "minor",
        "category": "data_entry",
        "description": "Test finding description",
    }
    defaults.update(overrides)
    return defaults


def _make_sdv_create(**overrides) -> dict:
    defaults = {
        "visit_id": "MV-001",
        "subject_id": "S-TEST",
        "form": "Demographics",
        "field": "Weight",
        "source_verified": True,
        "discrepancy_noted": False,
    }
    defaults.update(overrides)
    return defaults


def _make_report_create(**overrides) -> dict:
    defaults = {
        "visit_id": "MV-001",
        "summary": "Test monitoring report summary.",
        "follow_up_items": ["Item 1"],
    }
    defaults.update(overrides)
    return defaults


def _make_capa_create(**overrides) -> dict:
    defaults = {
        "finding_id": "MF-002",
        "root_cause": "Test root cause",
        "corrective_action": "Test corrective action",
        "preventive_action": "Test preventive action",
        "responsible_party": "Test Person",
        "due_date": (NOW + timedelta(days=30)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# SEED DATA VERIFICATION
# ===========================================================================


class TestSeedData:
    """Verify pre-populated demo data."""

    def test_seed_visits_count(self, svc: ClinicalMonitoringService):
        visits = svc.list_visits()
        assert len(visits) == 12

    def test_seed_visits_across_trials(self, svc: ClinicalMonitoringService):
        eylea = svc.list_visits(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_visits(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_visits(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) >= 3
        assert len(dupixent) >= 2
        assert len(libtayo) >= 2
        assert len(eylea) + len(dupixent) + len(libtayo) == 12

    def test_seed_visit_types_variety(self, svc: ClinicalMonitoringService):
        visits = svc.list_visits()
        types = {v.visit_type for v in visits}
        assert VisitType.ROUTINE in types
        assert VisitType.FOR_CAUSE in types
        assert VisitType.REMOTE in types
        assert VisitType.TRIGGERED in types
        assert VisitType.CLOSEOUT in types

    def test_seed_visit_statuses_variety(self, svc: ClinicalMonitoringService):
        visits = svc.list_visits()
        statuses = {v.status for v in visits}
        assert VisitStatus.COMPLETED in statuses
        assert VisitStatus.SCHEDULED in statuses
        assert VisitStatus.IN_PROGRESS in statuses
        assert VisitStatus.CONFIRMED in statuses
        assert VisitStatus.CANCELLED in statuses

    def test_seed_findings_count(self, svc: ClinicalMonitoringService):
        findings = svc.list_findings()
        assert len(findings) == 8

    def test_seed_findings_severity_variety(self, svc: ClinicalMonitoringService):
        findings = svc.list_findings()
        severities = {f.severity for f in findings}
        assert FindingSeverity.CRITICAL in severities
        assert FindingSeverity.MAJOR in severities
        assert FindingSeverity.MINOR in severities
        assert FindingSeverity.OBSERVATION in severities

    def test_seed_findings_category_variety(self, svc: ClinicalMonitoringService):
        findings = svc.list_findings()
        categories = {f.category for f in findings}
        assert len(categories) >= 5

    def test_seed_sdv_records_count(self, svc: ClinicalMonitoringService):
        records = svc.list_sdv_records()
        assert len(records) == 15

    def test_seed_sdv_has_discrepancies(self, svc: ClinicalMonitoringService):
        discrepancies = svc.list_sdv_records(status=SDVStatus.DISCREPANCY)
        assert len(discrepancies) >= 2

    def test_seed_reports_count(self, svc: ClinicalMonitoringService):
        reports = svc.list_reports()
        assert len(reports) == 5

    def test_seed_reports_status_variety(self, svc: ClinicalMonitoringService):
        reports = svc.list_reports()
        statuses = {r.status for r in reports}
        assert ReportStatus.APPROVED in statuses
        assert ReportStatus.SUBMITTED in statuses

    def test_seed_capas_count(self, svc: ClinicalMonitoringService):
        capas = svc.list_capas()
        assert len(capas) == 4

    def test_seed_capas_status_variety(self, svc: ClinicalMonitoringService):
        capas = svc.list_capas()
        statuses = {c.status for c in capas}
        assert CAPAStatus.OPEN in statuses
        assert CAPAStatus.IN_PROGRESS in statuses
        assert CAPAStatus.CLOSED in statuses

    def test_seed_specific_visit_mv001(self, svc: ClinicalMonitoringService):
        v = svc.get_visit("MV-001")
        assert v is not None
        assert v.trial_id == EYLEA_TRIAL
        assert v.site_id == "SITE-101"
        assert v.visit_type == VisitType.ROUTINE
        assert v.status == VisitStatus.COMPLETED
        assert v.cra_name == "Sarah Chen"
        assert len(v.objectives) == 4

    def test_seed_specific_finding_mf002(self, svc: ClinicalMonitoringService):
        f = svc.get_finding("MF-002")
        assert f is not None
        assert f.severity == FindingSeverity.CRITICAL
        assert f.category == FindingCategory.DATA_ENTRY
        assert f.status == FindingStatus.RESPONSE_REQUIRED
        assert f.capa_id == "CAPA-001"

    def test_seed_specific_capa_001(self, svc: ClinicalMonitoringService):
        c = svc.get_capa("CAPA-001")
        assert c is not None
        assert c.finding_id == "MF-002"
        assert c.status == CAPAStatus.IN_PROGRESS
        assert c.trial_id == EYLEA_TRIAL
        assert c.site_id == "SITE-102"

    def test_seed_closed_capa(self, svc: ClinicalMonitoringService):
        c = svc.get_capa("CAPA-004")
        assert c is not None
        assert c.status == CAPAStatus.CLOSED
        assert c.completion_date is not None
        assert c.verification_date is not None
        assert c.effectiveness_check is not None


# ===========================================================================
# VISIT CRUD
# ===========================================================================


class TestVisitCRUD:
    """Test visit create, read, update, delete, list, filter."""

    def test_create_visit(self, svc: ClinicalMonitoringService):
        payload = MonitoringVisitCreate(
            trial_id=EYLEA_TRIAL,
            site_id="SITE-NEW",
            visit_type=VisitType.ROUTINE,
            cra_name="New CRA",
            cra_id="CRA-NEW",
            scheduled_date=NOW + timedelta(days=14),
            objectives=["Test objective"],
        )
        visit = svc.create_visit(payload)
        assert visit.id.startswith("MV-")
        assert visit.status == VisitStatus.SCHEDULED
        assert visit.trial_id == EYLEA_TRIAL
        assert visit.site_id == "SITE-NEW"
        assert visit.cra_name == "New CRA"

    def test_get_visit(self, svc: ClinicalMonitoringService):
        v = svc.get_visit("MV-001")
        assert v is not None
        assert v.id == "MV-001"

    def test_get_visit_not_found(self, svc: ClinicalMonitoringService):
        assert svc.get_visit("MV-NONEXISTENT") is None

    def test_update_visit(self, svc: ClinicalMonitoringService):
        payload = MonitoringVisitUpdate(notes="Updated notes")
        updated = svc.update_visit("MV-004", payload)
        assert updated is not None
        assert updated.notes == "Updated notes"

    def test_update_visit_not_found(self, svc: ClinicalMonitoringService):
        payload = MonitoringVisitUpdate(notes="Test")
        assert svc.update_visit("MV-NONEXISTENT", payload) is None

    def test_delete_visit(self, svc: ClinicalMonitoringService):
        assert svc.delete_visit("MV-011") is True
        assert svc.get_visit("MV-011") is None

    def test_delete_visit_not_found(self, svc: ClinicalMonitoringService):
        assert svc.delete_visit("MV-NONEXISTENT") is False

    def test_list_visits_all(self, svc: ClinicalMonitoringService):
        visits = svc.list_visits()
        assert len(visits) == 12

    def test_list_visits_by_trial(self, svc: ClinicalMonitoringService):
        visits = svc.list_visits(trial_id=EYLEA_TRIAL)
        assert all(v.trial_id == EYLEA_TRIAL for v in visits)
        assert len(visits) >= 3

    def test_list_visits_by_site(self, svc: ClinicalMonitoringService):
        visits = svc.list_visits(site_id="SITE-101")
        assert all(v.site_id == "SITE-101" for v in visits)
        assert len(visits) >= 2

    def test_list_visits_by_type(self, svc: ClinicalMonitoringService):
        visits = svc.list_visits(visit_type=VisitType.FOR_CAUSE)
        assert all(v.visit_type == VisitType.FOR_CAUSE for v in visits)
        assert len(visits) >= 1

    def test_list_visits_by_status(self, svc: ClinicalMonitoringService):
        visits = svc.list_visits(status=VisitStatus.COMPLETED)
        assert all(v.status == VisitStatus.COMPLETED for v in visits)
        assert len(visits) >= 4

    def test_list_visits_by_cra(self, svc: ClinicalMonitoringService):
        visits = svc.list_visits(cra_id="CRA-001")
        assert all(v.cra_id == "CRA-001" for v in visits)
        assert len(visits) >= 2

    def test_list_visits_combined_filters(self, svc: ClinicalMonitoringService):
        visits = svc.list_visits(
            trial_id=EYLEA_TRIAL, status=VisitStatus.COMPLETED,
        )
        assert all(v.trial_id == EYLEA_TRIAL for v in visits)
        assert all(v.status == VisitStatus.COMPLETED for v in visits)

    def test_list_visits_empty_filter(self, svc: ClinicalMonitoringService):
        visits = svc.list_visits(trial_id="NONEXISTENT")
        assert len(visits) == 0

    def test_list_visits_sorted_by_date(self, svc: ClinicalMonitoringService):
        visits = svc.list_visits()
        dates = [v.scheduled_date for v in visits]
        assert dates == sorted(dates, reverse=True)


# ===========================================================================
# VISIT LIFECYCLE
# ===========================================================================


class TestVisitLifecycle:
    """Test visit state transitions."""

    def test_confirm_scheduled_visit(self, svc: ClinicalMonitoringService):
        visit = svc.confirm_visit("MV-004")
        assert visit is not None
        assert visit.status == VisitStatus.CONFIRMED

    def test_confirm_non_scheduled_fails(self, svc: ClinicalMonitoringService):
        with pytest.raises(ValueError, match="cannot be confirmed"):
            svc.confirm_visit("MV-001")  # already completed

    def test_confirm_not_found(self, svc: ClinicalMonitoringService):
        result = svc.confirm_visit("MV-NONEXISTENT")
        assert result is None

    def test_start_scheduled_visit(self, svc: ClinicalMonitoringService):
        payload = VisitStartPayload(actual_start_date=NOW)
        visit = svc.start_visit("MV-004", payload)
        assert visit is not None
        assert visit.status == VisitStatus.IN_PROGRESS
        assert visit.actual_start_date == NOW

    def test_start_confirmed_visit(self, svc: ClinicalMonitoringService):
        payload = VisitStartPayload(actual_start_date=NOW)
        visit = svc.start_visit("MV-008", payload)  # confirmed
        assert visit is not None
        assert visit.status == VisitStatus.IN_PROGRESS

    def test_start_completed_visit_fails(self, svc: ClinicalMonitoringService):
        payload = VisitStartPayload(actual_start_date=NOW)
        with pytest.raises(ValueError, match="cannot be started"):
            svc.start_visit("MV-001", payload)  # completed

    def test_start_not_found(self, svc: ClinicalMonitoringService):
        payload = VisitStartPayload(actual_start_date=NOW)
        assert svc.start_visit("MV-NONEXISTENT", payload) is None

    def test_complete_in_progress_visit(self, svc: ClinicalMonitoringService):
        payload = VisitCompletePayload(actual_end_date=NOW)
        visit = svc.complete_visit("MV-003", payload)  # in_progress
        assert visit is not None
        assert visit.status == VisitStatus.COMPLETED
        assert visit.actual_end_date == NOW

    def test_complete_scheduled_fails(self, svc: ClinicalMonitoringService):
        payload = VisitCompletePayload(actual_end_date=NOW)
        with pytest.raises(ValueError, match="cannot be completed"):
            svc.complete_visit("MV-004", payload)  # scheduled

    def test_complete_not_found(self, svc: ClinicalMonitoringService):
        payload = VisitCompletePayload(actual_end_date=NOW)
        assert svc.complete_visit("MV-NONEXISTENT", payload) is None

    def test_cancel_scheduled_visit(self, svc: ClinicalMonitoringService):
        visit = svc.cancel_visit("MV-004")
        assert visit is not None
        assert visit.status == VisitStatus.CANCELLED

    def test_cancel_confirmed_visit(self, svc: ClinicalMonitoringService):
        visit = svc.cancel_visit("MV-008")
        assert visit is not None
        assert visit.status == VisitStatus.CANCELLED

    def test_cancel_in_progress_visit(self, svc: ClinicalMonitoringService):
        visit = svc.cancel_visit("MV-003")
        assert visit is not None
        assert visit.status == VisitStatus.CANCELLED

    def test_cancel_completed_fails(self, svc: ClinicalMonitoringService):
        with pytest.raises(ValueError, match="cannot be cancelled"):
            svc.cancel_visit("MV-001")

    def test_cancel_already_cancelled_fails(self, svc: ClinicalMonitoringService):
        with pytest.raises(ValueError, match="cannot be cancelled"):
            svc.cancel_visit("MV-011")

    def test_cancel_not_found(self, svc: ClinicalMonitoringService):
        assert svc.cancel_visit("MV-NONEXISTENT") is None

    def test_full_lifecycle_flow(self, svc: ClinicalMonitoringService):
        # Create -> confirm -> start -> complete
        payload = MonitoringVisitCreate(
            trial_id=EYLEA_TRIAL,
            site_id="SITE-101",
            visit_type=VisitType.ROUTINE,
            cra_name="Lifecycle CRA",
            cra_id="CRA-LC",
            scheduled_date=NOW + timedelta(days=7),
        )
        visit = svc.create_visit(payload)
        assert visit.status == VisitStatus.SCHEDULED

        confirmed = svc.confirm_visit(visit.id)
        assert confirmed.status == VisitStatus.CONFIRMED

        started = svc.start_visit(visit.id, VisitStartPayload(actual_start_date=NOW))
        assert started.status == VisitStatus.IN_PROGRESS

        completed = svc.complete_visit(visit.id, VisitCompletePayload(actual_end_date=NOW))
        assert completed.status == VisitStatus.COMPLETED


# ===========================================================================
# FINDINGS CRUD
# ===========================================================================


class TestFindingsCRUD:
    """Test finding create, read, update, list, filter."""

    def test_create_finding(self, svc: ClinicalMonitoringService):
        payload = MonitoringFindingCreate(
            visit_id="MV-001",
            severity=FindingSeverity.MINOR,
            category=FindingCategory.DATA_ENTRY,
            description="Test finding",
        )
        finding = svc.create_finding(payload)
        assert finding.id.startswith("MF-")
        assert finding.status == FindingStatus.OPEN
        assert finding.trial_id == EYLEA_TRIAL
        assert finding.site_id == "SITE-101"

    def test_create_finding_with_details(self, svc: ClinicalMonitoringService):
        payload = MonitoringFindingCreate(
            visit_id="MV-002",
            severity=FindingSeverity.MAJOR,
            category=FindingCategory.PROTOCOL_DEVIATION,
            description="Major protocol deviation found",
            corrective_action="Retrain staff",
            response_due_date=NOW + timedelta(days=14),
        )
        finding = svc.create_finding(payload)
        assert finding.corrective_action == "Retrain staff"
        assert finding.response_due_date is not None

    def test_create_finding_invalid_visit(self, svc: ClinicalMonitoringService):
        payload = MonitoringFindingCreate(
            visit_id="MV-NONEXISTENT",
            severity=FindingSeverity.MINOR,
            category=FindingCategory.DATA_ENTRY,
            description="Test",
        )
        with pytest.raises(ValueError, match="not found"):
            svc.create_finding(payload)

    def test_get_finding(self, svc: ClinicalMonitoringService):
        f = svc.get_finding("MF-001")
        assert f is not None
        assert f.id == "MF-001"

    def test_get_finding_not_found(self, svc: ClinicalMonitoringService):
        assert svc.get_finding("MF-NONEXISTENT") is None

    def test_update_finding(self, svc: ClinicalMonitoringService):
        payload = MonitoringFindingUpdate(
            response="Site has addressed the finding",
            status=FindingStatus.RESPONSE_RECEIVED,
        )
        updated = svc.update_finding("MF-004", payload)
        assert updated is not None
        assert updated.response == "Site has addressed the finding"
        assert updated.status == FindingStatus.RESPONSE_RECEIVED

    def test_update_finding_not_found(self, svc: ClinicalMonitoringService):
        payload = MonitoringFindingUpdate(description="Test")
        assert svc.update_finding("MF-NONEXISTENT", payload) is None

    def test_list_findings_all(self, svc: ClinicalMonitoringService):
        findings = svc.list_findings()
        assert len(findings) == 8

    def test_list_findings_by_visit(self, svc: ClinicalMonitoringService):
        findings = svc.list_findings(visit_id="MV-002")
        assert all(f.visit_id == "MV-002" for f in findings)
        assert len(findings) == 3

    def test_list_findings_by_trial(self, svc: ClinicalMonitoringService):
        findings = svc.list_findings(trial_id=EYLEA_TRIAL)
        assert all(f.trial_id == EYLEA_TRIAL for f in findings)

    def test_list_findings_by_site(self, svc: ClinicalMonitoringService):
        findings = svc.list_findings(site_id="SITE-102")
        assert all(f.site_id == "SITE-102" for f in findings)
        assert len(findings) == 3

    def test_list_findings_by_severity(self, svc: ClinicalMonitoringService):
        findings = svc.list_findings(severity=FindingSeverity.CRITICAL)
        assert all(f.severity == FindingSeverity.CRITICAL for f in findings)
        assert len(findings) >= 1

    def test_list_findings_by_category(self, svc: ClinicalMonitoringService):
        findings = svc.list_findings(category=FindingCategory.INFORMED_CONSENT)
        assert all(f.category == FindingCategory.INFORMED_CONSENT for f in findings)

    def test_list_findings_by_status(self, svc: ClinicalMonitoringService):
        resolved = svc.list_findings(status=FindingStatus.RESOLVED)
        assert all(f.status == FindingStatus.RESOLVED for f in resolved)
        assert len(resolved) >= 3

    def test_list_findings_empty_filter(self, svc: ClinicalMonitoringService):
        findings = svc.list_findings(trial_id="NONEXISTENT")
        assert len(findings) == 0


# ===========================================================================
# FINDINGS LIFECYCLE
# ===========================================================================


class TestFindingsLifecycle:
    """Test finding resolve and escalate operations."""

    def test_resolve_finding(self, svc: ClinicalMonitoringService):
        result = svc.resolve_finding("MF-004")  # open finding
        assert result is not None
        assert result.status == FindingStatus.RESOLVED
        assert result.resolved_date is not None

    def test_resolve_already_resolved(self, svc: ClinicalMonitoringService):
        with pytest.raises(ValueError, match="already resolved"):
            svc.resolve_finding("MF-001")  # already resolved

    def test_resolve_not_found(self, svc: ClinicalMonitoringService):
        assert svc.resolve_finding("MF-NONEXISTENT") is None

    def test_escalate_finding(self, svc: ClinicalMonitoringService):
        result = svc.escalate_finding("MF-004")  # open finding
        assert result is not None
        assert result.status == FindingStatus.ESCALATED

    def test_escalate_resolved_fails(self, svc: ClinicalMonitoringService):
        with pytest.raises(ValueError, match="cannot be escalated"):
            svc.escalate_finding("MF-001")  # resolved

    def test_escalate_already_escalated_fails(self, svc: ClinicalMonitoringService):
        with pytest.raises(ValueError, match="cannot be escalated"):
            svc.escalate_finding("MF-005")  # already escalated

    def test_escalate_not_found(self, svc: ClinicalMonitoringService):
        assert svc.escalate_finding("MF-NONEXISTENT") is None


# ===========================================================================
# SDV RECORDS
# ===========================================================================


class TestSDVRecords:
    """Test SDV record operations."""

    def test_record_sdv_verified(self, svc: ClinicalMonitoringService):
        payload = SDVRecordCreate(
            visit_id="MV-003",
            subject_id="S-NEW",
            form="Vital Signs",
            field="Temperature",
            source_verified=True,
            discrepancy_noted=False,
        )
        rec = svc.record_sdv(payload)
        assert rec.id.startswith("SDV-")
        assert rec.status == SDVStatus.VERIFIED
        assert rec.source_verified is True
        assert rec.discrepancy_noted is False
        assert rec.verified_by == "Sarah Chen"  # CRA from MV-003
        assert rec.trial_id == EYLEA_TRIAL
        assert rec.site_id == "SITE-103"

    def test_record_sdv_discrepancy(self, svc: ClinicalMonitoringService):
        payload = SDVRecordCreate(
            visit_id="MV-003",
            subject_id="S-NEW",
            form="Lab Results",
            field="Creatinine",
            source_verified=False,
            discrepancy_noted=True,
            discrepancy_description="Value mismatch between source and CRF",
        )
        rec = svc.record_sdv(payload)
        assert rec.status == SDVStatus.DISCREPANCY
        assert rec.discrepancy_noted is True
        assert rec.discrepancy_description is not None

    def test_record_sdv_pending(self, svc: ClinicalMonitoringService):
        payload = SDVRecordCreate(
            visit_id="MV-003",
            subject_id="S-NEW",
            form="Demographics",
            field="Race",
            source_verified=False,
            discrepancy_noted=False,
        )
        rec = svc.record_sdv(payload)
        assert rec.status == SDVStatus.PENDING
        assert rec.verified_date is None

    def test_record_sdv_invalid_visit(self, svc: ClinicalMonitoringService):
        payload = SDVRecordCreate(
            visit_id="MV-NONEXISTENT",
            subject_id="S-NEW",
            form="Test",
            field="Test",
        )
        with pytest.raises(ValueError, match="not found"):
            svc.record_sdv(payload)

    def test_get_sdv_record(self, svc: ClinicalMonitoringService):
        rec = svc.get_sdv_record("SDV-001")
        assert rec is not None
        assert rec.subject_id == "S-1040"

    def test_get_sdv_record_not_found(self, svc: ClinicalMonitoringService):
        assert svc.get_sdv_record("SDV-NONEXISTENT") is None

    def test_list_sdv_records_all(self, svc: ClinicalMonitoringService):
        records = svc.list_sdv_records()
        assert len(records) == 15

    def test_list_sdv_by_visit(self, svc: ClinicalMonitoringService):
        records = svc.list_sdv_records(visit_id="MV-001")
        assert all(r.visit_id == "MV-001" for r in records)
        assert len(records) == 5

    def test_list_sdv_by_site(self, svc: ClinicalMonitoringService):
        records = svc.list_sdv_records(site_id="SITE-101")
        assert all(r.site_id == "SITE-101" for r in records)
        assert len(records) == 5

    def test_list_sdv_by_subject(self, svc: ClinicalMonitoringService):
        records = svc.list_sdv_records(subject_id="S-1040")
        assert all(r.subject_id == "S-1040" for r in records)
        assert len(records) == 2

    def test_list_sdv_by_status(self, svc: ClinicalMonitoringService):
        records = svc.list_sdv_records(status=SDVStatus.DISCREPANCY)
        assert all(r.status == SDVStatus.DISCREPANCY for r in records)
        assert len(records) >= 2

    def test_list_sdv_by_trial(self, svc: ClinicalMonitoringService):
        records = svc.list_sdv_records(trial_id=DUPIXENT_TRIAL)
        assert all(r.trial_id == DUPIXENT_TRIAL for r in records)

    def test_sdv_rate_by_site(self, svc: ClinicalMonitoringService):
        rate = svc.get_sdv_rate_by_site("SITE-101")
        # 4 verified, 1 discrepancy out of 5 = 80%
        assert rate == 80.0

    def test_sdv_rate_by_site_no_data(self, svc: ClinicalMonitoringService):
        rate = svc.get_sdv_rate_by_site("SITE-NONEXISTENT")
        assert rate == 0.0

    def test_sdv_summary(self, svc: ClinicalMonitoringService):
        summary = svc.get_sdv_summary()
        assert len(summary) >= 4  # At least 4 sites with SDV data
        site_ids = {s.site_id for s in summary}
        assert "SITE-101" in site_ids
        assert "SITE-102" in site_ids
        assert "SITE-106" in site_ids
        assert "SITE-108" in site_ids

        # Check SITE-101 details
        s101 = next(s for s in summary if s.site_id == "SITE-101")
        assert s101.total_records == 5
        assert s101.verified_count == 4
        assert s101.discrepancy_count == 1
        assert s101.sdv_rate == 80.0


# ===========================================================================
# MONITORING REPORTS
# ===========================================================================


class TestMonitoringReports:
    """Test monitoring report operations."""

    def test_create_report(self, svc: ClinicalMonitoringService):
        payload = MonitoringReportCreate(
            visit_id="MV-003",
            summary="Test report for in-progress visit",
            follow_up_items=["Follow up item 1", "Follow up item 2"],
        )
        report = svc.create_report(payload)
        assert report.id.startswith("MR-")
        assert report.status == ReportStatus.DRAFT
        assert report.trial_id == EYLEA_TRIAL
        assert report.site_id == "SITE-103"
        assert len(report.follow_up_items) == 2

    def test_create_report_invalid_visit(self, svc: ClinicalMonitoringService):
        payload = MonitoringReportCreate(
            visit_id="MV-NONEXISTENT",
            summary="Test",
        )
        with pytest.raises(ValueError, match="not found"):
            svc.create_report(payload)

    def test_create_report_computes_findings(self, svc: ClinicalMonitoringService):
        # MV-002 has 3 findings (1 critical, 1 major, 1 minor)
        payload = MonitoringReportCreate(
            visit_id="MV-002",
            summary="Report with auto-computed findings",
        )
        report = svc.create_report(payload)
        assert report.findings_count == 3
        assert report.critical_findings == 1
        assert report.major_findings == 1

    def test_create_report_computes_sdv(self, svc: ClinicalMonitoringService):
        # MV-001 has 5 SDV records (4 verified, 1 discrepancy)
        payload = MonitoringReportCreate(
            visit_id="MV-001",
            summary="Report with auto-computed SDV rate",
        )
        report = svc.create_report(payload)
        assert report.sdv_rate == 80.0
        assert report.subjects_reviewed >= 4

    def test_get_report(self, svc: ClinicalMonitoringService):
        r = svc.get_report("MR-001")
        assert r is not None
        assert r.visit_id == "MV-001"

    def test_get_report_not_found(self, svc: ClinicalMonitoringService):
        assert svc.get_report("MR-NONEXISTENT") is None

    def test_update_report(self, svc: ClinicalMonitoringService):
        payload = MonitoringReportUpdate(summary="Updated summary")
        updated = svc.update_report("MR-001", payload)
        assert updated is not None
        assert updated.summary == "Updated summary"

    def test_update_report_not_found(self, svc: ClinicalMonitoringService):
        payload = MonitoringReportUpdate(summary="Test")
        assert svc.update_report("MR-NONEXISTENT", payload) is None

    def test_list_reports_all(self, svc: ClinicalMonitoringService):
        reports = svc.list_reports()
        assert len(reports) == 5

    def test_list_reports_by_trial(self, svc: ClinicalMonitoringService):
        reports = svc.list_reports(trial_id=EYLEA_TRIAL)
        assert all(r.trial_id == EYLEA_TRIAL for r in reports)
        assert len(reports) == 2

    def test_list_reports_by_site(self, svc: ClinicalMonitoringService):
        reports = svc.list_reports(site_id="SITE-101")
        assert all(r.site_id == "SITE-101" for r in reports)

    def test_list_reports_by_status(self, svc: ClinicalMonitoringService):
        approved = svc.list_reports(status=ReportStatus.APPROVED)
        assert all(r.status == ReportStatus.APPROVED for r in approved)
        assert len(approved) >= 2

    def test_list_reports_by_visit(self, svc: ClinicalMonitoringService):
        reports = svc.list_reports(visit_id="MV-001")
        assert len(reports) == 1
        assert reports[0].visit_id == "MV-001"

    def test_submit_report(self, svc: ClinicalMonitoringService):
        # Create a draft report first
        payload = MonitoringReportCreate(
            visit_id="MV-003",
            summary="Draft report to submit",
        )
        report = svc.create_report(payload)
        assert report.status == ReportStatus.DRAFT

        submitted = svc.submit_report(report.id, NOW)
        assert submitted is not None
        assert submitted.status == ReportStatus.SUBMITTED
        assert submitted.submitted_date == NOW

    def test_submit_non_draft_fails(self, svc: ClinicalMonitoringService):
        with pytest.raises(ValueError, match="cannot be submitted"):
            svc.submit_report("MR-002", NOW)  # already submitted

    def test_submit_not_found(self, svc: ClinicalMonitoringService):
        assert svc.submit_report("MR-NONEXISTENT", NOW) is None

    def test_approve_submitted_report(self, svc: ClinicalMonitoringService):
        approved = svc.approve_report("MR-002")  # submitted
        assert approved is not None
        assert approved.status == ReportStatus.APPROVED
        assert approved.approved_date is not None

    def test_approve_reviewed_report(self, svc: ClinicalMonitoringService):
        approved = svc.approve_report("MR-003")  # reviewed
        assert approved is not None
        assert approved.status == ReportStatus.APPROVED

    def test_approve_draft_fails(self, svc: ClinicalMonitoringService):
        # Create draft
        payload = MonitoringReportCreate(visit_id="MV-003", summary="Draft")
        report = svc.create_report(payload)
        with pytest.raises(ValueError, match="cannot be approved"):
            svc.approve_report(report.id)

    def test_approve_not_found(self, svc: ClinicalMonitoringService):
        assert svc.approve_report("MR-NONEXISTENT") is None

    def test_full_report_lifecycle(self, svc: ClinicalMonitoringService):
        # Create -> submit -> approve
        payload = MonitoringReportCreate(
            visit_id="MV-003",
            summary="Full lifecycle report",
            follow_up_items=["Check items"],
        )
        report = svc.create_report(payload)
        assert report.status == ReportStatus.DRAFT

        submitted = svc.submit_report(report.id, NOW)
        assert submitted.status == ReportStatus.SUBMITTED

        approved = svc.approve_report(report.id)
        assert approved.status == ReportStatus.APPROVED
        assert approved.approved_date is not None


# ===========================================================================
# CAPA WORKFLOW
# ===========================================================================


class TestCAPAWorkflow:
    """Test CAPA create, update, close operations."""

    def test_create_capa(self, svc: ClinicalMonitoringService):
        payload = CAPAItemCreate(
            finding_id="MF-004",  # open finding without CAPA
            root_cause="Inadequate training",
            corrective_action="Retrain staff",
            preventive_action="Update training schedule",
            responsible_party="Test Person",
            due_date=NOW + timedelta(days=30),
        )
        capa = svc.create_capa(payload)
        assert capa.id.startswith("CAPA-")
        assert capa.status == CAPAStatus.OPEN
        assert capa.trial_id == EYLEA_TRIAL
        assert capa.site_id == "SITE-102"
        assert capa.finding_id == "MF-004"

        # Verify finding was linked to CAPA
        finding = svc.get_finding("MF-004")
        assert finding.capa_id == capa.id

    def test_create_capa_invalid_finding(self, svc: ClinicalMonitoringService):
        payload = CAPAItemCreate(
            finding_id="MF-NONEXISTENT",
            root_cause="Test",
            corrective_action="Test",
            preventive_action="Test",
            responsible_party="Test",
            due_date=NOW + timedelta(days=30),
        )
        with pytest.raises(ValueError, match="not found"):
            svc.create_capa(payload)

    def test_get_capa(self, svc: ClinicalMonitoringService):
        c = svc.get_capa("CAPA-001")
        assert c is not None
        assert c.id == "CAPA-001"

    def test_get_capa_not_found(self, svc: ClinicalMonitoringService):
        assert svc.get_capa("CAPA-NONEXISTENT") is None

    def test_update_capa(self, svc: ClinicalMonitoringService):
        payload = CAPAItemUpdate(status=CAPAStatus.IN_PROGRESS)
        updated = svc.update_capa("CAPA-002", payload)
        assert updated is not None
        assert updated.status == CAPAStatus.IN_PROGRESS

    def test_update_capa_not_found(self, svc: ClinicalMonitoringService):
        payload = CAPAItemUpdate(status=CAPAStatus.IN_PROGRESS)
        assert svc.update_capa("CAPA-NONEXISTENT", payload) is None

    def test_close_capa(self, svc: ClinicalMonitoringService):
        result = svc.close_capa("CAPA-001", "Verified all corrective actions implemented")
        assert result is not None
        assert result.status == CAPAStatus.CLOSED
        assert result.completion_date is not None
        assert result.verification_date is not None
        assert result.effectiveness_check == "Verified all corrective actions implemented"

    def test_close_already_closed_capa_fails(self, svc: ClinicalMonitoringService):
        with pytest.raises(ValueError, match="already closed"):
            svc.close_capa("CAPA-004", "Test")

    def test_close_capa_not_found(self, svc: ClinicalMonitoringService):
        assert svc.close_capa("CAPA-NONEXISTENT", "Test") is None

    def test_list_capas_all(self, svc: ClinicalMonitoringService):
        capas = svc.list_capas()
        assert len(capas) == 4

    def test_list_capas_by_trial(self, svc: ClinicalMonitoringService):
        capas = svc.list_capas(trial_id=EYLEA_TRIAL)
        assert all(c.trial_id == EYLEA_TRIAL for c in capas)
        assert len(capas) == 2

    def test_list_capas_by_site(self, svc: ClinicalMonitoringService):
        capas = svc.list_capas(site_id="SITE-102")
        assert all(c.site_id == "SITE-102" for c in capas)
        assert len(capas) == 2

    def test_list_capas_by_status(self, svc: ClinicalMonitoringService):
        open_capas = svc.list_capas(status=CAPAStatus.OPEN)
        assert all(c.status == CAPAStatus.OPEN for c in open_capas)

    def test_list_capas_by_finding(self, svc: ClinicalMonitoringService):
        capas = svc.list_capas(finding_id="MF-002")
        assert len(capas) == 1
        assert capas[0].finding_id == "MF-002"

    def test_full_capa_lifecycle(self, svc: ClinicalMonitoringService):
        # Create CAPA -> update to in_progress -> close
        payload = CAPAItemCreate(
            finding_id="MF-004",
            root_cause="Root cause",
            corrective_action="Corrective",
            preventive_action="Preventive",
            responsible_party="Person",
            due_date=NOW + timedelta(days=30),
        )
        capa = svc.create_capa(payload)
        assert capa.status == CAPAStatus.OPEN

        updated = svc.update_capa(capa.id, CAPAItemUpdate(status=CAPAStatus.IN_PROGRESS))
        assert updated.status == CAPAStatus.IN_PROGRESS

        closed = svc.close_capa(capa.id, "Effectiveness verified")
        assert closed.status == CAPAStatus.CLOSED
        assert closed.effectiveness_check == "Effectiveness verified"


# ===========================================================================
# MONITORING METRICS
# ===========================================================================


class TestMonitoringMetrics:
    """Test aggregated monitoring metrics."""

    def test_metrics_total_visits(self, svc: ClinicalMonitoringService):
        metrics = svc.get_monitoring_metrics()
        assert metrics.total_visits == 12

    def test_metrics_completed_visits(self, svc: ClinicalMonitoringService):
        metrics = svc.get_monitoring_metrics()
        assert metrics.visits_completed >= 4

    def test_metrics_visits_by_type(self, svc: ClinicalMonitoringService):
        metrics = svc.get_monitoring_metrics()
        assert "routine" in metrics.visits_by_type
        assert "for_cause" in metrics.visits_by_type
        assert sum(metrics.visits_by_type.values()) == 12

    def test_metrics_visits_by_status(self, svc: ClinicalMonitoringService):
        metrics = svc.get_monitoring_metrics()
        assert "completed" in metrics.visits_by_status
        assert "scheduled" in metrics.visits_by_status
        assert sum(metrics.visits_by_status.values()) == 12

    def test_metrics_total_findings(self, svc: ClinicalMonitoringService):
        metrics = svc.get_monitoring_metrics()
        assert metrics.total_findings == 8

    def test_metrics_open_findings(self, svc: ClinicalMonitoringService):
        metrics = svc.get_monitoring_metrics()
        assert metrics.open_findings >= 3

    def test_metrics_findings_by_severity(self, svc: ClinicalMonitoringService):
        metrics = svc.get_monitoring_metrics()
        assert "critical" in metrics.findings_by_severity
        assert "major" in metrics.findings_by_severity
        assert "minor" in metrics.findings_by_severity
        assert "observation" in metrics.findings_by_severity
        assert sum(metrics.findings_by_severity.values()) == 8

    def test_metrics_findings_by_category(self, svc: ClinicalMonitoringService):
        metrics = svc.get_monitoring_metrics()
        assert len(metrics.findings_by_category) >= 5
        assert sum(metrics.findings_by_category.values()) == 8

    def test_metrics_sdv(self, svc: ClinicalMonitoringService):
        metrics = svc.get_monitoring_metrics()
        assert metrics.total_sdv_records == 15
        assert metrics.overall_sdv_rate > 0.0

    def test_metrics_capas(self, svc: ClinicalMonitoringService):
        metrics = svc.get_monitoring_metrics()
        assert metrics.total_capas == 4
        assert metrics.open_capas >= 2
        assert metrics.capa_closure_rate > 0.0

    def test_metrics_reports(self, svc: ClinicalMonitoringService):
        metrics = svc.get_monitoring_metrics()
        assert metrics.total_reports == 5
        assert metrics.reports_pending_review >= 1


# ===========================================================================
# SITE MONITORING SUMMARY
# ===========================================================================


class TestSiteMonitoringSummary:
    """Test site-level monitoring summary."""

    def test_site_summary_101(self, svc: ClinicalMonitoringService):
        summary = svc.get_site_monitoring_summary("SITE-101")
        assert summary is not None
        assert summary.site_id == "SITE-101"
        assert summary.total_visits >= 2
        assert summary.completed_visits >= 1
        assert summary.sdv_rate == 80.0
        assert summary.last_visit_date is not None

    def test_site_summary_102(self, svc: ClinicalMonitoringService):
        summary = svc.get_site_monitoring_summary("SITE-102")
        assert summary is not None
        assert summary.critical_findings >= 1  # MF-002 is critical
        assert summary.open_findings >= 2

    def test_site_summary_with_trial_filter(self, svc: ClinicalMonitoringService):
        summary = svc.get_site_monitoring_summary("SITE-103", trial_id=EYLEA_TRIAL)
        assert summary is not None
        assert summary.trial_id == EYLEA_TRIAL

    def test_site_summary_nonexistent(self, svc: ClinicalMonitoringService):
        summary = svc.get_site_monitoring_summary("SITE-NONEXISTENT")
        assert summary is None

    def test_site_summary_has_capa_count(self, svc: ClinicalMonitoringService):
        summary = svc.get_site_monitoring_summary("SITE-102")
        assert summary.open_capas >= 1  # CAPA-001 and CAPA-002

    def test_site_summary_106(self, svc: ClinicalMonitoringService):
        summary = svc.get_site_monitoring_summary("SITE-106")
        assert summary is not None
        assert summary.total_visits >= 2
        assert summary.open_capas >= 1  # CAPA-003


# ===========================================================================
# API ENDPOINT TESTS
# ===========================================================================


class TestVisitAPIEndpoints:
    """Test visit API endpoints via HTTP."""

    @pytest.mark.anyio
    async def test_list_visits_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_visits_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert all(v["trial_id"] == EYLEA_TRIAL for v in data["items"])

    @pytest.mark.anyio
    async def test_list_visits_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits", params={"visit_type": "for_cause"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(v["visit_type"] == "for_cause" for v in data["items"])

    @pytest.mark.anyio
    async def test_list_visits_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(v["status"] == "completed" for v in data["items"])

    @pytest.mark.anyio
    async def test_get_visit_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/MV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MV-001"
        assert data["cra_name"] == "Sarah Chen"

    @pytest.mark.anyio
    async def test_get_visit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/MV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_visit_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/visits", json=_make_visit_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "scheduled"
        assert data["id"].startswith("MV-")

    @pytest.mark.anyio
    async def test_update_visit_api(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/visits/MV-004",
            json={"notes": "Updated via API"},
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Updated via API"

    @pytest.mark.anyio
    async def test_update_visit_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/visits/MV-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_visit_api(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/visits/MV-011")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_visit_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/visits/MV-NONEXISTENT")
        assert resp.status_code == 404


class TestVisitLifecycleAPI:
    """Test visit lifecycle API endpoints."""

    @pytest.mark.anyio
    async def test_confirm_visit_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/visits/MV-004/confirm")
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

    @pytest.mark.anyio
    async def test_confirm_invalid_status(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/visits/MV-001/confirm")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_confirm_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/visits/MV-NONEXISTENT/confirm")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_start_visit_api(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/visits/MV-004/start",
            json={"actual_start_date": NOW.isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_start_invalid_status(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/visits/MV-001/start",
            json={"actual_start_date": NOW.isoformat()},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_start_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/visits/MV-NONEXISTENT/start",
            json={"actual_start_date": NOW.isoformat()},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_complete_visit_api(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/visits/MV-003/complete",
            json={"actual_end_date": NOW.isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    @pytest.mark.anyio
    async def test_complete_invalid_status(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/visits/MV-004/complete",
            json={"actual_end_date": NOW.isoformat()},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_cancel_visit_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/visits/MV-004/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    @pytest.mark.anyio
    async def test_cancel_completed_fails(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/visits/MV-001/cancel")
        assert resp.status_code == 400


class TestFindingsAPI:
    """Test finding API endpoints."""

    @pytest.mark.anyio
    async def test_list_findings_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_findings_filter_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"severity": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(f["severity"] == "critical" for f in data["items"])

    @pytest.mark.anyio
    async def test_list_findings_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"site_id": "SITE-102"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_get_finding_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/MF-002")
        assert resp.status_code == 200
        assert resp.json()["severity"] == "critical"

    @pytest.mark.anyio
    async def test_get_finding_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/MF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_finding_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/findings", json=_make_finding_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "open"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_finding_invalid_visit(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/findings",
            json=_make_finding_create(visit_id="MV-NONEXISTENT"),
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_finding_api(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/MF-004",
            json={"response": "Addressed", "status": "response_received"},
        )
        assert resp.status_code == 200
        assert resp.json()["response"] == "Addressed"

    @pytest.mark.anyio
    async def test_resolve_finding_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/findings/MF-004/resolve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    @pytest.mark.anyio
    async def test_resolve_already_resolved(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/findings/MF-001/resolve")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_resolve_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/findings/MF-NONEXISTENT/resolve")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_escalate_finding_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/findings/MF-004/escalate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "escalated"

    @pytest.mark.anyio
    async def test_escalate_resolved_fails(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/findings/MF-001/escalate")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_escalate_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/findings/MF-NONEXISTENT/escalate")
        assert resp.status_code == 404


class TestSDVAPI:
    """Test SDV API endpoints."""

    @pytest.mark.anyio
    async def test_list_sdv_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_sdv_filter_visit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv", params={"visit_id": "MV-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_sdv_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv", params={"status": "discrepancy"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["status"] == "discrepancy" for r in data["items"])

    @pytest.mark.anyio
    async def test_get_sdv_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv/SDV-001")
        assert resp.status_code == 200
        assert resp.json()["subject_id"] == "S-1040"

    @pytest.mark.anyio
    async def test_get_sdv_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv/SDV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_record_sdv_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/sdv", json=_make_sdv_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "verified"
        assert data["source_verified"] is True

    @pytest.mark.anyio
    async def test_record_sdv_invalid_visit(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/sdv",
            json=_make_sdv_create(visit_id="MV-NONEXISTENT"),
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_sdv_rate_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv/rate/SITE-101")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "SITE-101"
        assert data["sdv_rate"] == 80.0

    @pytest.mark.anyio
    async def test_sdv_rate_no_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv/rate/SITE-NONEXISTENT")
        assert resp.status_code == 200
        assert resp.json()["sdv_rate"] == 0.0

    @pytest.mark.anyio
    async def test_sdv_summary_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 4
        site_ids = {s["site_id"] for s in data}
        assert "SITE-101" in site_ids


class TestReportAPI:
    """Test monitoring report API endpoints."""

    @pytest.mark.anyio
    async def test_list_reports_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_reports_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports", params={"status": "approved"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["status"] == "approved" for r in data["items"])

    @pytest.mark.anyio
    async def test_get_report_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/MR-001")
        assert resp.status_code == 200
        assert resp.json()["visit_id"] == "MV-001"

    @pytest.mark.anyio
    async def test_get_report_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/MR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_report_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/reports", json=_make_report_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"

    @pytest.mark.anyio
    async def test_create_report_invalid_visit(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/reports",
            json=_make_report_create(visit_id="MV-NONEXISTENT"),
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_report_api(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reports/MR-001",
            json={"summary": "Updated via API"},
        )
        assert resp.status_code == 200
        assert resp.json()["summary"] == "Updated via API"

    @pytest.mark.anyio
    async def test_submit_report_api(self, client: AsyncClient):
        # Create draft first
        create_resp = await client.post(f"{API_PREFIX}/reports", json=_make_report_create())
        report_id = create_resp.json()["id"]

        resp = await client.post(
            f"{API_PREFIX}/reports/{report_id}/submit",
            json={"submitted_date": NOW.isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "submitted"

    @pytest.mark.anyio
    async def test_submit_non_draft_fails(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/reports/MR-002/submit",
            json={"submitted_date": NOW.isoformat()},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_approve_report_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/reports/MR-002/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    @pytest.mark.anyio
    async def test_approve_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/reports/MR-NONEXISTENT/approve")
        assert resp.status_code == 404


class TestCAPAAPI:
    """Test CAPA API endpoints."""

    @pytest.mark.anyio
    async def test_list_capas_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_capas_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas", params={"status": "in_progress"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(c["status"] == "in_progress" for c in data["items"])

    @pytest.mark.anyio
    async def test_list_capas_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert all(c["trial_id"] == EYLEA_TRIAL for c in data["items"])

    @pytest.mark.anyio
    async def test_get_capa_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas/CAPA-001")
        assert resp.status_code == 200
        assert resp.json()["finding_id"] == "MF-002"

    @pytest.mark.anyio
    async def test_get_capa_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas/CAPA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_capa_api(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/capas", json=_make_capa_create(finding_id="MF-004"))
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "open"
        assert data["finding_id"] == "MF-004"

    @pytest.mark.anyio
    async def test_create_capa_invalid_finding(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/capas",
            json=_make_capa_create(finding_id="MF-NONEXISTENT"),
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_capa_api(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capas/CAPA-002",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_capa_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capas/CAPA-NONEXISTENT",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_close_capa_api(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/capas/CAPA-001/close",
            params={"effectiveness_check": "Verified corrective actions"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["effectiveness_check"] == "Verified corrective actions"

    @pytest.mark.anyio
    async def test_close_already_closed_fails(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/capas/CAPA-004/close",
            params={"effectiveness_check": "Test"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_close_capa_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/capas/CAPA-NONEXISTENT/close",
            params={"effectiveness_check": "Test"},
        )
        assert resp.status_code == 404


class TestMetricsAPI:
    """Test metrics and summary API endpoints."""

    @pytest.mark.anyio
    async def test_metrics_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_visits"] == 12
        assert data["total_findings"] == 8
        assert data["total_sdv_records"] == 15
        assert data["total_capas"] == 4
        assert data["total_reports"] == 5
        assert data["overall_sdv_rate"] > 0.0
        assert data["capa_closure_rate"] > 0.0

    @pytest.mark.anyio
    async def test_site_summary_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-summary/SITE-101")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "SITE-101"
        assert data["total_visits"] >= 2
        assert data["sdv_rate"] == 80.0

    @pytest.mark.anyio
    async def test_site_summary_with_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-summary/SITE-103",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_site_summary_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-summary/SITE-NONEXISTENT")
        assert resp.status_code == 404


# ===========================================================================
# EDGE CASES & INTEGRATION
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and integration scenarios."""

    def test_create_visit_preserves_count(self, svc: ClinicalMonitoringService):
        initial = len(svc.list_visits())
        svc.create_visit(MonitoringVisitCreate(
            trial_id=EYLEA_TRIAL, site_id="SITE-NEW",
            visit_type=VisitType.ROUTINE, cra_name="CRA",
            cra_id="CRA-X", scheduled_date=NOW + timedelta(days=7),
        ))
        assert len(svc.list_visits()) == initial + 1

    def test_delete_visit_preserves_count(self, svc: ClinicalMonitoringService):
        initial = len(svc.list_visits())
        svc.delete_visit("MV-011")
        assert len(svc.list_visits()) == initial - 1

    def test_capa_links_to_finding(self, svc: ClinicalMonitoringService):
        capa = svc.create_capa(CAPAItemCreate(
            finding_id="MF-004",
            root_cause="Root",
            corrective_action="Correct",
            preventive_action="Prevent",
            responsible_party="Person",
            due_date=NOW + timedelta(days=30),
        ))
        finding = svc.get_finding("MF-004")
        assert finding.capa_id == capa.id

    def test_report_auto_computes_from_visit_data(self, svc: ClinicalMonitoringService):
        # Add SDV and finding to MV-003, then create report
        svc.record_sdv(SDVRecordCreate(
            visit_id="MV-003", subject_id="S-TEST1",
            form="Test", field="Test", source_verified=True,
        ))
        svc.record_sdv(SDVRecordCreate(
            visit_id="MV-003", subject_id="S-TEST2",
            form="Test", field="Test", source_verified=False, discrepancy_noted=True,
        ))
        svc.create_finding(MonitoringFindingCreate(
            visit_id="MV-003", severity=FindingSeverity.MINOR,
            category=FindingCategory.DATA_ENTRY, description="Test finding",
        ))

        report = svc.create_report(MonitoringReportCreate(
            visit_id="MV-003", summary="Test",
        ))
        assert report.findings_count == 1
        assert report.sdv_rate == 50.0
        assert report.subjects_reviewed == 2

    def test_singleton_pattern(self):
        svc1 = get_clinical_monitoring_service()
        svc2 = get_clinical_monitoring_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_clinical_monitoring_service()
        svc2 = reset_clinical_monitoring_service()
        assert svc1 is not svc2
        # Fresh data
        assert len(svc2.list_visits()) == 12

    def test_concurrent_operations_safe(self, svc: ClinicalMonitoringService):
        """Verify thread safety by rapid sequential operations."""
        import concurrent.futures

        def create_visit(i: int) -> str:
            v = svc.create_visit(MonitoringVisitCreate(
                trial_id=EYLEA_TRIAL, site_id=f"SITE-T{i}",
                visit_type=VisitType.ROUTINE, cra_name=f"CRA-{i}",
                cra_id=f"CRA-T{i}", scheduled_date=NOW + timedelta(days=i),
            ))
            return v.id

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(create_visit, i) for i in range(8)]
            ids = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(set(ids)) == 8
        assert len(svc.list_visits()) == 20  # 12 seed + 8 new

    @pytest.mark.anyio
    async def test_full_workflow_integration(self, client: AsyncClient):
        """End-to-end: create visit -> start -> create findings -> record SDV -> complete -> report -> CAPA."""
        # 1. Create visit
        resp = await client.post(f"{API_PREFIX}/visits", json=_make_visit_create(
            site_id="SITE-INT",
        ))
        assert resp.status_code == 201
        visit_id = resp.json()["id"]

        # 2. Start visit
        resp = await client.post(
            f"{API_PREFIX}/visits/{visit_id}/start",
            json={"actual_start_date": NOW.isoformat()},
        )
        assert resp.status_code == 200

        # 3. Create finding
        resp = await client.post(f"{API_PREFIX}/findings", json={
            "visit_id": visit_id,
            "severity": "major",
            "category": "protocol_deviation",
            "description": "Integration test finding",
            "corrective_action": "Fix the issue",
        })
        assert resp.status_code == 201
        finding_id = resp.json()["id"]

        # 4. Record SDV
        resp = await client.post(f"{API_PREFIX}/sdv", json={
            "visit_id": visit_id,
            "subject_id": "S-INT-1",
            "form": "Demographics",
            "field": "DOB",
            "source_verified": True,
        })
        assert resp.status_code == 201

        # 5. Complete visit
        resp = await client.post(
            f"{API_PREFIX}/visits/{visit_id}/complete",
            json={"actual_end_date": NOW.isoformat()},
        )
        assert resp.status_code == 200

        # 6. Create report
        resp = await client.post(f"{API_PREFIX}/reports", json={
            "visit_id": visit_id,
            "summary": "Integration test report",
            "follow_up_items": ["Follow up on finding"],
        })
        assert resp.status_code == 201
        report_id = resp.json()["id"]
        assert resp.json()["findings_count"] == 1

        # 7. Submit report
        resp = await client.post(
            f"{API_PREFIX}/reports/{report_id}/submit",
            json={"submitted_date": NOW.isoformat()},
        )
        assert resp.status_code == 200

        # 8. Create CAPA for finding
        resp = await client.post(f"{API_PREFIX}/capas", json={
            "finding_id": finding_id,
            "root_cause": "Integration test root cause",
            "corrective_action": "Fix it",
            "preventive_action": "Prevent it",
            "responsible_party": "Integration Tester",
            "due_date": (NOW + timedelta(days=30)).isoformat(),
        })
        assert resp.status_code == 201
        capa_id = resp.json()["id"]

        # 9. Close CAPA
        resp = await client.post(
            f"{API_PREFIX}/capas/{capa_id}/close",
            params={"effectiveness_check": "All good"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

        # 10. Verify metrics updated
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_visits"] == 13  # 12 seed + 1 new
        assert data["total_findings"] == 9  # 8 seed + 1 new
