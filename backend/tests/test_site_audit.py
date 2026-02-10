"""Tests for Site Audit Management (QA-AUDIT).

Covers:
- Seed data verification (audits, findings, CAPAs, reports)
- Audit CRUD (create, read, update, delete, list, filter by trial/status/type)
- Finding CRUD (create, read, update, delete, list, filter by audit/classification/status)
- CAPA CRUD (create, read, update, delete, list, filter by audit/finding/status)
- Report CRUD (create, read, update, delete, list, filter by audit/status)
- Metrics computation
- Error handling (404s)
- Edge cases (empty filters, all enum values)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.site_audit import (
    AuditStatus,
    AuditType,
    CAPAStatus,
    FindingClassification,
    FindingStatus,
    ReportStatus,
)
from app.services.site_audit_service import (
    SiteAuditService,
    get_site_audit_service,
    reset_site_audit_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/site-audit"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_site_audit_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SiteAuditService:
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


def _make_audit_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-999",
        "site_name": "Test Clinical Site",
        "audit_type": "routine",
        "planned_date": (now + timedelta(days=30)).isoformat(),
        "lead_auditor": "Test Auditor",
        "audit_team": ["Test Auditor", "Assistant Auditor"],
        "scope": "Routine GCP compliance audit covering informed consent and source data verification",
    }
    defaults.update(overrides)
    return defaults


def _make_finding_create(**overrides) -> dict:
    defaults = {
        "audit_id": "AUD-001",
        "finding_number": "AUD-001-F99",
        "classification": "minor",
        "area": "Informed Consent",
        "description": "Test finding description for consent documentation gap",
        "evidence": "Source document review worksheet; Consent tracking log",
    }
    defaults.update(overrides)
    return defaults


def _make_capa_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "finding_id": "FND-001",
        "audit_id": "AUD-001",
        "corrective_action": "Implement corrective measures for the identified deficiency",
        "preventive_action": "Establish preventive controls to avoid recurrence",
        "responsible_party": "Dr. Test Investigator",
        "due_date": (now + timedelta(days=30)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_report_create(**overrides) -> dict:
    defaults = {
        "audit_id": "AUD-001",
        "report_number": "AUD-001-RPT-TEST",
        "title": "Test Audit Report",
        "executive_summary": "Test audit report executive summary with findings overview",
        "author": "Test Author",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_audits_count(self, svc: SiteAuditService):
        audits = svc.list_audits()
        assert len(audits) == 12

    def test_seed_audits_across_trials(self, svc: SiteAuditService):
        trials = {a.trial_id for a in svc.list_audits()}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_findings_count(self, svc: SiteAuditService):
        findings = svc.list_findings()
        assert len(findings) == 18

    def test_seed_capas_count(self, svc: SiteAuditService):
        capas = svc.list_capas()
        assert len(capas) == 10

    def test_seed_reports_count(self, svc: SiteAuditService):
        reports = svc.list_reports()
        assert len(reports) == 6

    def test_seed_audit_types_present(self, svc: SiteAuditService):
        audits = svc.list_audits()
        types = {a.audit_type for a in audits}
        assert AuditType.ROUTINE in types
        assert AuditType.FOR_CAUSE in types
        assert AuditType.REGULATORY_INSPECTION in types
        assert AuditType.CRO_OVERSIGHT in types

    def test_seed_audit_statuses_present(self, svc: SiteAuditService):
        audits = svc.list_audits()
        statuses = {a.status for a in audits}
        assert AuditStatus.PLANNED in statuses
        assert AuditStatus.SCHEDULED in statuses
        assert AuditStatus.IN_PROGRESS in statuses
        assert AuditStatus.FINALIZED in statuses
        assert AuditStatus.CLOSED in statuses

    def test_seed_finding_classifications_present(self, svc: SiteAuditService):
        findings = svc.list_findings()
        classifications = {f.classification for f in findings}
        assert FindingClassification.CRITICAL in classifications
        assert FindingClassification.MAJOR in classifications
        assert FindingClassification.MINOR in classifications
        assert FindingClassification.OBSERVATION in classifications

    def test_seed_capa_statuses_present(self, svc: SiteAuditService):
        capas = svc.list_capas()
        statuses = {c.status for c in capas}
        assert CAPAStatus.PLANNED in statuses
        assert CAPAStatus.IN_PROGRESS in statuses
        assert CAPAStatus.COMPLETED in statuses
        assert CAPAStatus.VERIFIED in statuses
        assert CAPAStatus.CLOSED in statuses

    def test_seed_report_statuses_present(self, svc: SiteAuditService):
        reports = svc.list_reports()
        statuses = {r.status for r in reports}
        assert ReportStatus.APPROVED in statuses
        assert ReportStatus.DISTRIBUTED in statuses


# =====================================================================
# AUDIT CRUD
# =====================================================================


class TestAuditCrud:
    """Test audit create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_audits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_audits_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audits", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_audits_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audits", params={"status": "finalized"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "finalized"

    @pytest.mark.anyio
    async def test_list_audits_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audits", params={"audit_type": "routine"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["audit_type"] == "routine"

    @pytest.mark.anyio
    async def test_get_audit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audits/AUD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AUD-001"
        assert data["site_name"] == "Bascom Palmer Eye Institute"

    @pytest.mark.anyio
    async def test_get_audit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audits/AUD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_audit(self, client: AsyncClient):
        payload = _make_audit_create()
        resp = await client.post(f"{API_PREFIX}/audits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_name"] == "Test Clinical Site"
        assert data["status"] == "planned"
        assert data["id"].startswith("AUD-")

    @pytest.mark.anyio
    async def test_update_audit(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/audits/AUD-004",
            json={"status": "report_drafting", "scope": "Updated scope"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "report_drafting"
        assert data["scope"] == "Updated scope"

    @pytest.mark.anyio
    async def test_update_audit_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/audits/AUD-NONEXISTENT",
            json={"status": "finalized"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_audit(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/audits/AUD-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/audits/AUD-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_audit_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/audits/AUD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# FINDING CRUD
# =====================================================================


class TestFindingCrud:
    """Test audit finding CRUD operations."""

    @pytest.mark.anyio
    async def test_list_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 18

    @pytest.mark.anyio
    async def test_list_findings_filter_audit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"audit_id": "AUD-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["audit_id"] == "AUD-001"

    @pytest.mark.anyio
    async def test_list_findings_filter_classification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"classification": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["classification"] == "critical"

    @pytest.mark.anyio
    async def test_list_findings_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"status": "open"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_get_finding(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/FND-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FND-001"
        assert data["audit_id"] == "AUD-001"

    @pytest.mark.anyio
    async def test_get_finding_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/FND-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_finding(self, client: AsyncClient):
        payload = _make_finding_create()
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["audit_id"] == "AUD-001"
        assert data["status"] == "open"
        assert data["id"].startswith("FND-")

    @pytest.mark.anyio
    async def test_update_finding(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/FND-010",
            json={"status": "capa_assigned", "site_response": "Issue acknowledged. CAPA being developed."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "capa_assigned"
        assert data["site_response"] is not None

    @pytest.mark.anyio
    async def test_update_finding_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/FND-NONEXISTENT",
            json={"status": "closed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_finding(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/FND-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/findings/FND-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_finding_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/FND-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CAPA CRUD
# =====================================================================


class TestCapaCrud:
    """Test CAPA CRUD operations."""

    @pytest.mark.anyio
    async def test_list_capas(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_capas_filter_audit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas", params={"audit_id": "AUD-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["audit_id"] == "AUD-001"

    @pytest.mark.anyio
    async def test_list_capas_filter_finding(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas", params={"finding_id": "FND-003"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["finding_id"] == "FND-003"

    @pytest.mark.anyio
    async def test_list_capas_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas", params={"status": "in_progress"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_get_capa(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas/CAPA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CAPA-001"
        assert data["finding_id"] == "FND-001"

    @pytest.mark.anyio
    async def test_get_capa_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas/CAPA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_capa(self, client: AsyncClient):
        payload = _make_capa_create()
        resp = await client.post(f"{API_PREFIX}/capas", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["finding_id"] == "FND-001"
        assert data["status"] == "planned"
        assert data["id"].startswith("CAPA-")

    @pytest.mark.anyio
    async def test_update_capa(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capas/CAPA-004",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_capa_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capas/CAPA-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_capa_auto_completion_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capas/CAPA-004",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completion_date"] is not None

    @pytest.mark.anyio
    async def test_delete_capa(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/capas/CAPA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/capas/CAPA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_capa_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/capas/CAPA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# REPORT CRUD
# =====================================================================


class TestReportCrud:
    """Test audit report CRUD operations."""

    @pytest.mark.anyio
    async def test_list_reports(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_reports_filter_audit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports", params={"audit_id": "AUD-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["audit_id"] == "AUD-001"

    @pytest.mark.anyio
    async def test_list_reports_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports", params={"status": "distributed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "distributed"

    @pytest.mark.anyio
    async def test_get_report(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/RPT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RPT-001"
        assert data["audit_id"] == "AUD-001"

    @pytest.mark.anyio
    async def test_get_report_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/RPT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_report(self, client: AsyncClient):
        payload = _make_report_create()
        resp = await client.post(f"{API_PREFIX}/reports", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["audit_id"] == "AUD-001"
        assert data["status"] == "draft"
        assert data["id"].startswith("RPT-")

    @pytest.mark.anyio
    async def test_update_report(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reports/RPT-002",
            json={"status": "distributed", "title": "Updated Report Title"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "distributed"
        assert data["title"] == "Updated Report Title"

    @pytest.mark.anyio
    async def test_update_report_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reports/RPT-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_report(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reports/RPT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/reports/RPT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_report_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reports/RPT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test site audit metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_audits"] == 12
        assert data["total_findings"] == 18
        assert data["total_capas"] == 10
        assert data["total_reports"] == 6
        assert data["open_findings"] > 0
        assert data["closed_findings"] > 0
        assert data["avg_findings_per_audit"] > 0

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_audits"] == 4

    def test_metrics_audits_by_type(self, svc: SiteAuditService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.audits_by_type.values())
        assert total_by_type == metrics.total_audits

    def test_metrics_audits_by_status(self, svc: SiteAuditService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.audits_by_status.values())
        assert total_by_status == metrics.total_audits

    def test_metrics_findings_by_classification(self, svc: SiteAuditService):
        metrics = svc.get_metrics()
        total_by_classification = sum(metrics.findings_by_classification.values())
        assert total_by_classification == metrics.total_findings

    def test_metrics_open_closed_findings_sum(self, svc: SiteAuditService):
        metrics = svc.get_metrics()
        assert metrics.open_findings + metrics.closed_findings == metrics.total_findings

    def test_metrics_approved_reports(self, svc: SiteAuditService):
        metrics = svc.get_metrics()
        assert metrics.approved_reports > 0
        assert metrics.approved_reports <= metrics.total_reports

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_audits"] == 0
        assert data["total_findings"] == 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_site_audit_service()
        svc2 = get_site_audit_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_site_audit_service()
        svc2 = reset_site_audit_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_site_audit_service()
        svc.delete_audit("AUD-001")
        assert svc.get_audit("AUD-001") is None
        svc2 = reset_site_audit_service()
        assert svc2.get_audit("AUD-001") is not None


# =====================================================================
# EDGE CASES AND DATA VALIDATION
# =====================================================================


class TestEdgeCases:
    """Test edge cases and data validation."""

    @pytest.mark.anyio
    async def test_list_audits_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audits")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_findings_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_capas_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_reports_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_audit_all_types(self, client: AsyncClient):
        for at in ["routine", "for_cause", "regulatory_inspection", "pre_approval", "systems_audit", "cro_oversight", "vendor_audit"]:
            payload = _make_audit_create(audit_type=at, site_id=f"SITE-{at}")
            resp = await client.post(f"{API_PREFIX}/audits", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["audit_type"] == at

    @pytest.mark.anyio
    async def test_create_finding_all_classifications(self, client: AsyncClient):
        for cls in ["critical", "major", "minor", "observation"]:
            payload = _make_finding_create(classification=cls, finding_number=f"TEST-{cls}")
            resp = await client.post(f"{API_PREFIX}/findings", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["classification"] == cls

    @pytest.mark.anyio
    async def test_audit_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audits/AUD-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "site_id" in data
        assert "site_name" in data
        assert "audit_type" in data
        assert "status" in data
        assert "planned_date" in data
        assert "lead_auditor" in data
        assert "audit_team" in data
        assert "scope" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_finding_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/FND-001")
        data = resp.json()
        assert "id" in data
        assert "audit_id" in data
        assert "finding_number" in data
        assert "classification" in data
        assert "area" in data
        assert "description" in data
        assert "evidence" in data
        assert "status" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_capa_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas/CAPA-001")
        data = resp.json()
        assert "id" in data
        assert "finding_id" in data
        assert "audit_id" in data
        assert "corrective_action" in data
        assert "preventive_action" in data
        assert "responsible_party" in data
        assert "due_date" in data
        assert "status" in data

    @pytest.mark.anyio
    async def test_report_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports/RPT-001")
        data = resp.json()
        assert "id" in data
        assert "audit_id" in data
        assert "report_number" in data
        assert "title" in data
        assert "executive_summary" in data
        assert "status" in data
        assert "author" in data
        assert "total_findings" in data
        assert "critical_findings" in data
        assert "major_findings" in data
        assert "minor_findings" in data
        assert "observations" in data
        assert "distribution_list" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_audits" in data
        assert "audits_by_type" in data
        assert "audits_by_status" in data
        assert "total_findings" in data
        assert "findings_by_classification" in data
        assert "open_findings" in data
        assert "closed_findings" in data
        assert "total_capas" in data
        assert "open_capas" in data
        assert "overdue_capas" in data
        assert "total_reports" in data
        assert "approved_reports" in data
        assert "avg_findings_per_audit" in data

    def test_finalized_audits_have_dates(self, svc: SiteAuditService):
        audits = svc.list_audits(status=AuditStatus.FINALIZED)
        for a in audits:
            assert a.actual_start_date is not None
            assert a.actual_end_date is not None

    def test_planned_audits_have_no_actual_dates(self, svc: SiteAuditService):
        audits = svc.list_audits(status=AuditStatus.PLANNED)
        for a in audits:
            assert a.actual_start_date is None
            assert a.actual_end_date is None

    def test_closed_capas_have_verification(self, svc: SiteAuditService):
        capas = svc.list_capas(status=CAPAStatus.CLOSED)
        for c in capas:
            assert c.verification_date is not None
            assert c.verified_by is not None

    def test_eylea_audits_count(self, svc: SiteAuditService):
        audits = svc.list_audits(trial_id=EYLEA_TRIAL)
        assert len(audits) == 4

    def test_dupixent_audits_count(self, svc: SiteAuditService):
        audits = svc.list_audits(trial_id=DUPIXENT_TRIAL)
        assert len(audits) == 4

    def test_libtayo_audits_count(self, svc: SiteAuditService):
        audits = svc.list_audits(trial_id=LIBTAYO_TRIAL)
        assert len(audits) == 4

    @pytest.mark.anyio
    async def test_create_audit_with_regulatory_authority(self, client: AsyncClient):
        payload = _make_audit_create(
            audit_type="regulatory_inspection",
            regulatory_authority="FDA",
        )
        resp = await client.post(f"{API_PREFIX}/audits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["regulatory_authority"] == "FDA"

    @pytest.mark.anyio
    async def test_create_finding_with_regulation_reference(self, client: AsyncClient):
        payload = _make_finding_create(regulation_reference="ICH E6(R2) 4.8.2")
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["regulation_reference"] == "ICH E6(R2) 4.8.2"

    @pytest.mark.anyio
    async def test_update_capa_verified_auto_date(self, client: AsyncClient):
        # First move to completed
        await client.put(
            f"{API_PREFIX}/capas/CAPA-004",
            json={"status": "completed"},
        )
        # Then verify
        resp = await client.put(
            f"{API_PREFIX}/capas/CAPA-004",
            json={"status": "verified", "verified_by": "Test Verifier", "effectiveness_evidence": "Evidence of effective resolution"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "verified"
        assert data["verification_date"] is not None
        assert data["verified_by"] == "Test Verifier"
