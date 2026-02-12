"""Tests for Product Complaint Management (PROD-COMPL).

Covers:
- Seed data verification (complaint intakes, investigations, root cause analyses, CAPA linkages, regulatory reports)
- Complaint intake CRUD (create, read, update, delete, list, filter by trial/category/severity/status)
- Investigation record CRUD (create, read, update, delete, list, filter by trial/complaint/outcome)
- Root cause analysis CRUD (create, read, update, delete, list, filter by trial/complaint/category)
- CAPA linkage CRUD (create, read, update, delete, list, filter by trial/complaint/status)
- Regulatory report CRUD (create, read, update, delete, list, filter by trial/complaint/type/authority)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.product_complaint import (
    ComplaintCategory,
    ComplaintSeverity,
    ComplaintStatus,
    InvestigationOutcome,
    RootCauseCategory,
)
from app.services.product_complaint_service import (
    ProductComplaintService,
    get_product_complaint_service,
    reset_product_complaint_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/product-complaint"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_product_complaint_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ProductComplaintService:
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


def _make_complaint_intake_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "complaint_number": "COMPL-TEST-001",
        "category": "product_quality",
        "product_name": "Test Product 100mg",
        "description": "Test complaint description for product quality issue",
        "reporter_name": "Dr. Test Reporter",
        "received_by": "QA Test Specialist",
        "severity": "moderate",
    }
    defaults.update(overrides)
    return defaults


def _make_investigation_record_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "complaint_id": "CI-001",
        "investigator": "QA Test Investigator",
        "testing_performed": ["visual_inspection", "chemical_analysis"],
    }
    defaults.update(overrides)
    return defaults


def _make_root_cause_analysis_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "complaint_id": "CI-005",
        "root_cause_category": "human_error",
        "root_cause_description": "Test root cause: operator error during manufacturing process",
        "identified_by": "QA Test Analyst",
        "analysis_method": "fishbone",
    }
    defaults.update(overrides)
    return defaults


def _make_capa_linkage_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "complaint_id": "CI-009",
        "capa_number": "CAPA-TEST-001",
        "description": "Test CAPA: implement corrective action for manufacturing deviation",
        "assigned_to": "Test QA Manager",
        "due_date": (now + timedelta(days=30)).isoformat(),
        "created_by": "Test QA Director",
    }
    defaults.update(overrides)
    return defaults


def _make_regulatory_report_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "complaint_id": "CI-004",
        "regulatory_authority": "FDA",
        "reporting_criteria_met": "Product quality defect meeting 21 CFR 314.81 criteria",
        "prepared_by": "Test Regulatory Specialist",
        "report_type": "field_alert",
        "submission_deadline": (now + timedelta(days=15)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_complaint_intakes_count(self, svc: ProductComplaintService):
        intakes = svc.list_complaint_intakes()
        assert len(intakes) == 12

    def test_seed_investigation_records_count(self, svc: ProductComplaintService):
        records = svc.list_investigation_records()
        assert len(records) == 10

    def test_seed_root_cause_analyses_count(self, svc: ProductComplaintService):
        analyses = svc.list_root_cause_analyses()
        assert len(analyses) == 10

    def test_seed_capa_linkages_count(self, svc: ProductComplaintService):
        capas = svc.list_capa_linkages()
        assert len(capas) == 10

    def test_seed_regulatory_reports_count(self, svc: ProductComplaintService):
        reports = svc.list_regulatory_reports()
        assert len(reports) == 10

    def test_seed_intakes_cover_all_trials(self, svc: ProductComplaintService):
        intakes = svc.list_complaint_intakes()
        trial_ids = {c.trial_id for c in intakes}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_intakes_have_multiple_categories(self, svc: ProductComplaintService):
        intakes = svc.list_complaint_intakes()
        categories = {c.category for c in intakes}
        assert len(categories) >= 4

    def test_seed_intakes_have_multiple_severities(self, svc: ProductComplaintService):
        intakes = svc.list_complaint_intakes()
        severities = {c.severity for c in intakes}
        assert ComplaintSeverity.MINOR in severities
        assert ComplaintSeverity.CRITICAL in severities

    def test_seed_intakes_have_multiple_statuses(self, svc: ProductComplaintService):
        intakes = svc.list_complaint_intakes()
        statuses = {c.status for c in intakes}
        assert ComplaintStatus.RESOLVED in statuses
        assert ComplaintStatus.UNDER_INVESTIGATION in statuses

    def test_seed_investigations_have_multiple_outcomes(self, svc: ProductComplaintService):
        records = svc.list_investigation_records()
        outcomes = {r.outcome for r in records if r.outcome is not None}
        assert InvestigationOutcome.CONFIRMED in outcomes
        assert InvestigationOutcome.NOT_CONFIRMED in outcomes

    def test_seed_rca_have_multiple_categories(self, svc: ProductComplaintService):
        analyses = svc.list_root_cause_analyses()
        categories = {a.root_cause_category for a in analyses}
        assert RootCauseCategory.MANUFACTURING in categories
        assert RootCauseCategory.HUMAN_ERROR in categories

    def test_seed_capas_have_multiple_statuses(self, svc: ProductComplaintService):
        capas = svc.list_capa_linkages()
        statuses = {c.status for c in capas}
        assert "open" in statuses
        assert "closed" in statuses
        assert "in_progress" in statuses

    def test_seed_reports_have_multiple_authorities(self, svc: ProductComplaintService):
        reports = svc.list_regulatory_reports()
        authorities = {r.regulatory_authority for r in reports}
        assert "FDA" in authorities
        assert "EMA" in authorities


# =====================================================================
# COMPLAINT INTAKE CRUD
# =====================================================================


class TestComplaintIntakeCrud:
    """Test complaint intake CRUD operations."""

    @pytest.mark.anyio
    async def test_list_complaint_intakes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/complaint-intakes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_complaint_intakes_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/complaint-intakes", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_complaint_intakes_filter_category(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/complaint-intakes", params={"category": "product_quality"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["category"] == "product_quality"

    @pytest.mark.anyio
    async def test_list_complaint_intakes_filter_severity(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/complaint-intakes", params={"severity": "critical"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["severity"] == "critical"

    @pytest.mark.anyio
    async def test_list_complaint_intakes_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/complaint-intakes", params={"status": "under_investigation"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "under_investigation"

    @pytest.mark.anyio
    async def test_get_complaint_intake(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/complaint-intakes/CI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CI-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["category"] == "product_quality"

    @pytest.mark.anyio
    async def test_get_complaint_intake_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/complaint-intakes/CI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_complaint_intake(self, client: AsyncClient):
        payload = _make_complaint_intake_create()
        resp = await client.post(f"{API_PREFIX}/complaint-intakes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["category"] == "product_quality"
        assert data["status"] == "received"
        assert data["id"].startswith("CI-")

    @pytest.mark.anyio
    async def test_update_complaint_intake(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/complaint-intakes/CI-010",
            json={"status": "acknowledged", "initial_assessment": "Under review", "notes": "Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "acknowledged"
        assert data["initial_assessment"] == "Under review"
        assert data["notes"] == "Updated"

    @pytest.mark.anyio
    async def test_update_complaint_intake_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/complaint-intakes/CI-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_complaint_intake(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/complaint-intakes/CI-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/complaint-intakes/CI-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_complaint_intake_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/complaint-intakes/CI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# INVESTIGATION RECORD CRUD
# =====================================================================


class TestInvestigationRecordCrud:
    """Test investigation record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_investigation_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/investigation-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_investigation_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/investigation-records", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_investigation_records_filter_complaint(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/investigation-records", params={"complaint_id": "CI-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["complaint_id"] == "CI-001"

    @pytest.mark.anyio
    async def test_list_investigation_records_filter_outcome(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/investigation-records", params={"outcome": "confirmed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["outcome"] == "confirmed"

    @pytest.mark.anyio
    async def test_get_investigation_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/investigation-records/INV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "INV-001"
        assert data["complaint_id"] == "CI-001"

    @pytest.mark.anyio
    async def test_get_investigation_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/investigation-records/INV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_investigation_record(self, client: AsyncClient):
        payload = _make_investigation_record_create()
        resp = await client.post(f"{API_PREFIX}/investigation-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["complaint_id"] == "CI-001"
        assert data["outcome"] is None
        assert data["id"].startswith("INV-")

    @pytest.mark.anyio
    async def test_update_investigation_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/investigation-records/INV-006",
            json={"outcome": "confirmed", "reviewed_by": "Dr. Reviewer", "notes": "Investigation complete"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "confirmed"
        assert data["reviewed_by"] == "Dr. Reviewer"
        assert data["notes"] == "Investigation complete"

    @pytest.mark.anyio
    async def test_update_investigation_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/investigation-records/INV-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_investigation_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/investigation-records/INV-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/investigation-records/INV-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_investigation_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/investigation-records/INV-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ROOT CAUSE ANALYSIS CRUD
# =====================================================================


class TestRootCauseAnalysisCrud:
    """Test root cause analysis CRUD operations."""

    @pytest.mark.anyio
    async def test_list_root_cause_analyses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/root-cause-analyses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_root_cause_analyses_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/root-cause-analyses", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_root_cause_analyses_filter_complaint(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/root-cause-analyses", params={"complaint_id": "CI-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["complaint_id"] == "CI-001"

    @pytest.mark.anyio
    async def test_list_root_cause_analyses_filter_category(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/root-cause-analyses", params={"root_cause_category": "manufacturing"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["root_cause_category"] == "manufacturing"

    @pytest.mark.anyio
    async def test_get_root_cause_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/root-cause-analyses/RCA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RCA-001"
        assert data["root_cause_category"] == "manufacturing"

    @pytest.mark.anyio
    async def test_get_root_cause_analysis_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/root-cause-analyses/RCA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_root_cause_analysis(self, client: AsyncClient):
        payload = _make_root_cause_analysis_create()
        resp = await client.post(f"{API_PREFIX}/root-cause-analyses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["root_cause_category"] == "human_error"
        assert data["verified"] is False
        assert data["id"].startswith("RCA-")

    @pytest.mark.anyio
    async def test_update_root_cause_analysis(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/root-cause-analyses/RCA-006",
            json={"verified": True, "verified_by": "VP Quality", "notes": "Verified after review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is True
        assert data["verified_by"] == "VP Quality"
        assert data["notes"] == "Verified after review"

    @pytest.mark.anyio
    async def test_update_root_cause_analysis_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/root-cause-analyses/RCA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_root_cause_analysis(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/root-cause-analyses/RCA-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/root-cause-analyses/RCA-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_root_cause_analysis_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/root-cause-analyses/RCA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CAPA LINKAGE CRUD
# =====================================================================


class TestCAPALinkageCrud:
    """Test CAPA linkage CRUD operations."""

    @pytest.mark.anyio
    async def test_list_capa_linkages(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capa-linkages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_capa_linkages_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/capa-linkages", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_capa_linkages_filter_complaint(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/capa-linkages", params={"complaint_id": "CI-004"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["complaint_id"] == "CI-004"

    @pytest.mark.anyio
    async def test_list_capa_linkages_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/capa-linkages", params={"status": "closed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "closed"

    @pytest.mark.anyio
    async def test_get_capa_linkage(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capa-linkages/CAPA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CAPA-001"
        assert data["capa_type"] == "corrective"

    @pytest.mark.anyio
    async def test_get_capa_linkage_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capa-linkages/CAPA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_capa_linkage(self, client: AsyncClient):
        payload = _make_capa_linkage_create()
        resp = await client.post(f"{API_PREFIX}/capa-linkages", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["status"] == "open"
        assert data["id"].startswith("CAPA-")

    @pytest.mark.anyio
    async def test_update_capa_linkage(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capa-linkages/CAPA-004",
            json={"status": "in_progress", "approved_by": "VP Quality", "notes": "Approved for implementation"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["approved_by"] == "VP Quality"
        assert data["notes"] == "Approved for implementation"

    @pytest.mark.anyio
    async def test_update_capa_linkage_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capa-linkages/CAPA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_capa_linkage(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/capa-linkages/CAPA-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/capa-linkages/CAPA-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_capa_linkage_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/capa-linkages/CAPA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# REGULATORY REPORT CRUD
# =====================================================================


class TestRegulatoryReportCrud:
    """Test regulatory report CRUD operations."""

    @pytest.mark.anyio
    async def test_list_regulatory_reports(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/regulatory-reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_regulatory_reports_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/regulatory-reports", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_regulatory_reports_filter_complaint(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/regulatory-reports", params={"complaint_id": "CI-008"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["complaint_id"] == "CI-008"

    @pytest.mark.anyio
    async def test_list_regulatory_reports_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/regulatory-reports", params={"report_type": "field_alert"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["report_type"] == "field_alert"

    @pytest.mark.anyio
    async def test_list_regulatory_reports_filter_authority(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/regulatory-reports", params={"regulatory_authority": "FDA"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["regulatory_authority"] == "FDA"

    @pytest.mark.anyio
    async def test_get_regulatory_report(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/regulatory-reports/RR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RR-001"
        assert data["report_type"] == "field_alert"

    @pytest.mark.anyio
    async def test_get_regulatory_report_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/regulatory-reports/RR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_regulatory_report(self, client: AsyncClient):
        payload = _make_regulatory_report_create()
        resp = await client.post(f"{API_PREFIX}/regulatory-reports", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["report_type"] == "field_alert"
        assert data["acknowledgment_received"] is False
        assert data["id"].startswith("RR-")

    @pytest.mark.anyio
    async def test_update_regulatory_report(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/regulatory-reports/RR-003",
            json={"report_number": "FA-2025-EYLEA-002", "reviewed_by": "VP Quality", "notes": "Ready for submission"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_number"] == "FA-2025-EYLEA-002"
        assert data["reviewed_by"] == "VP Quality"
        assert data["notes"] == "Ready for submission"

    @pytest.mark.anyio
    async def test_update_regulatory_report_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/regulatory-reports/RR-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_regulatory_report(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/regulatory-reports/RR-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/regulatory-reports/RR-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_regulatory_report_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/regulatory-reports/RR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestProductComplaintMetrics:
    """Test product complaint metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_complaints"] == 12
        assert data["total_investigations"] == 10
        assert data["total_root_causes"] == 10
        assert data["total_capas"] == 10
        assert data["total_regulatory_reports"] == 10

    @pytest.mark.anyio
    async def test_metrics_complaints_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_category = data["complaints_by_category"]
        total = sum(by_category.values())
        assert total == data["total_complaints"]

    @pytest.mark.anyio
    async def test_metrics_complaints_by_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_severity = data["complaints_by_severity"]
        total = sum(by_severity.values())
        assert total == data["total_complaints"]

    @pytest.mark.anyio
    async def test_metrics_complaints_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["complaints_by_status"]
        total = sum(by_status.values())
        assert total == data["total_complaints"]

    @pytest.mark.anyio
    async def test_metrics_avg_days_open(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_days_open"] > 0
        assert isinstance(data["avg_days_open"], float)

    @pytest.mark.anyio
    async def test_metrics_investigations_by_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_outcome = data["investigations_by_outcome"]
        total = sum(by_outcome.values())
        assert total == data["total_investigations"]

    @pytest.mark.anyio
    async def test_metrics_root_causes_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_category = data["root_causes_by_category"]
        total = sum(by_category.values())
        assert total == data["total_root_causes"]

    @pytest.mark.anyio
    async def test_metrics_open_capas(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["open_capas"] > 0
        assert data["open_capas"] <= data["total_capas"]

    @pytest.mark.anyio
    async def test_metrics_reports_pending_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["reports_pending_submission"] >= 1
        assert data["reports_pending_submission"] <= data["total_regulatory_reports"]


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_product_complaint_service()
        svc2 = get_product_complaint_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_product_complaint_service()
        svc2 = reset_product_complaint_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_product_complaint_service()
        # Delete a complaint
        svc.delete_complaint_intake("CI-001")
        assert svc.get_complaint_intake("CI-001") is None
        # Reset should bring it back
        svc2 = reset_product_complaint_service()
        assert svc2.get_complaint_intake("CI-001") is not None


# =====================================================================
# FILTERING AND EDGE CASES
# =====================================================================


class TestFilteringAndEdgeCases:
    """Test filtering combinations and edge cases."""

    @pytest.mark.anyio
    async def test_list_intakes_empty_filter(self, client: AsyncClient):
        """Filter by a trial that has no complaints."""
        resp = await client.get(
            f"{API_PREFIX}/complaint-intakes",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_intakes_combined_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/complaint-intakes",
            params={"category": "counterfeit", "trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        # EYLEA doesn't have counterfeit complaints
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_investigations_empty_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/investigation-records",
            params={"complaint_id": "CI-NONEXISTENT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_reports_combined_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/regulatory-reports",
            params={"regulatory_authority": "EMA", "trial_id": DUPIXENT_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["regulatory_authority"] == "EMA"
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_create_intake_then_retrieve(self, client: AsyncClient):
        """Create an intake and verify it shows in the list."""
        payload = _make_complaint_intake_create()
        resp = await client.post(f"{API_PREFIX}/complaint-intakes", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/complaint-intakes/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == created_id

    @pytest.mark.anyio
    async def test_create_intake_then_update_status(self, client: AsyncClient):
        """Create an intake, then update its status through lifecycle."""
        payload = _make_complaint_intake_create()
        resp = await client.post(f"{API_PREFIX}/complaint-intakes", json=payload)
        assert resp.status_code == 201
        intake_id = resp.json()["id"]
        assert resp.json()["status"] == "received"

        # Update to acknowledged
        resp2 = await client.put(
            f"{API_PREFIX}/complaint-intakes/{intake_id}",
            json={"status": "acknowledged"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "acknowledged"

        # Update to under_investigation
        resp3 = await client.put(
            f"{API_PREFIX}/complaint-intakes/{intake_id}",
            json={"status": "under_investigation", "initial_assessment": "Under review"},
        )
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "under_investigation"
        assert resp3.json()["initial_assessment"] == "Under review"

    @pytest.mark.anyio
    async def test_create_and_delete_investigation(self, client: AsyncClient):
        """Create an investigation and then delete it."""
        payload = _make_investigation_record_create()
        resp = await client.post(f"{API_PREFIX}/investigation-records", json=payload)
        assert resp.status_code == 201
        record_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/investigation-records/{record_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/investigation-records/{record_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_create_rca_with_investigation_id(self, client: AsyncClient):
        """Create a root cause analysis linked to an investigation."""
        payload = _make_root_cause_analysis_create(investigation_id="INV-005")
        resp = await client.post(f"{API_PREFIX}/root-cause-analyses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["investigation_id"] == "INV-005"

    @pytest.mark.anyio
    async def test_create_capa_with_root_cause_id(self, client: AsyncClient):
        """Create a CAPA linkage linked to a root cause."""
        payload = _make_capa_linkage_create(root_cause_id="RCA-005")
        resp = await client.post(f"{API_PREFIX}/capa-linkages", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["root_cause_id"] == "RCA-005"

    @pytest.mark.anyio
    async def test_intakes_sorted_by_complaint_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/complaint-intakes")
        data = resp.json()
        dates = [item["complaint_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_investigations_sorted_by_start_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/investigation-records")
        data = resp.json()
        dates = [item["investigation_start_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_metrics_after_create_and_delete(self, client: AsyncClient):
        """Metrics should reflect dynamic changes."""
        # Get baseline metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        baseline = resp1.json()

        # Create a new complaint
        payload = _make_complaint_intake_create()
        await client.post(f"{API_PREFIX}/complaint-intakes", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        after_create = resp2.json()
        assert after_create["total_complaints"] == baseline["total_complaints"] + 1

        # Delete a complaint
        await client.delete(f"{API_PREFIX}/complaint-intakes/CI-012")
        resp3 = await client.get(f"{API_PREFIX}/metrics")
        after_delete = resp3.json()
        assert after_delete["total_complaints"] == baseline["total_complaints"]


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Verify enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_complaint_categories_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/complaint-intakes")
        data = resp.json()
        categories = {item["category"] for item in data["items"]}
        assert "product_quality" in categories
        assert "packaging" in categories
        assert "labeling" in categories
        assert "adverse_event" in categories
        assert "device_malfunction" in categories
        assert "counterfeit" in categories

    @pytest.mark.anyio
    async def test_complaint_severities_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/complaint-intakes")
        data = resp.json()
        severities = {item["severity"] for item in data["items"]}
        assert "minor" in severities
        assert "moderate" in severities
        assert "major" in severities
        assert "critical" in severities
        assert "life_threatening" in severities

    @pytest.mark.anyio
    async def test_complaint_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/complaint-intakes")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "received" in statuses
        assert "acknowledged" in statuses
        assert "under_investigation" in statuses
        assert "root_cause_identified" in statuses
        assert "resolved" in statuses
        assert "closed" in statuses

    @pytest.mark.anyio
    async def test_investigation_outcomes_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/investigation-records")
        data = resp.json()
        outcomes = {item["outcome"] for item in data["items"] if item["outcome"] is not None}
        assert "confirmed" in outcomes
        assert "not_confirmed" in outcomes

    @pytest.mark.anyio
    async def test_root_cause_categories_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/root-cause-analyses")
        data = resp.json()
        categories = {item["root_cause_category"] for item in data["items"]}
        assert "manufacturing" in categories
        assert "raw_material" in categories
        assert "storage" in categories
        assert "transportation" in categories
        assert "design" in categories
        assert "human_error" in categories

    @pytest.mark.anyio
    async def test_capa_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capa-linkages")
        data = resp.json()
        types = {item["capa_type"] for item in data["items"]}
        assert "corrective" in types
        assert "preventive" in types

    @pytest.mark.anyio
    async def test_report_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/regulatory-reports")
        data = resp.json()
        types = {item["report_type"] for item in data["items"]}
        assert "field_alert" in types
        assert "mdr" in types
        assert "safety_report" in types
        assert "annual_report" in types

    @pytest.mark.anyio
    async def test_regulatory_authorities_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/regulatory-reports")
        data = resp.json()
        authorities = {item["regulatory_authority"] for item in data["items"]}
        assert "FDA" in authorities
        assert "EMA" in authorities
        assert "Health Canada" in authorities


# =====================================================================
# ADDITIONAL EDGE CASES
# =====================================================================


class TestAdditionalEdgeCases:
    """Additional edge case tests for completeness."""

    @pytest.mark.anyio
    async def test_create_intake_minimal_fields(self, client: AsyncClient):
        """Create with only required fields."""
        payload = {
            "trial_id": LIBTAYO_TRIAL,
            "complaint_number": "COMPL-MIN-001",
            "category": "packaging",
            "product_name": "Minimal Product",
            "description": "Minimal description",
            "reporter_name": "Minimal Reporter",
            "received_by": "Minimal Receiver",
        }
        resp = await client.post(f"{API_PREFIX}/complaint-intakes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "minor"  # default
        assert data["batch_number"] is None

    @pytest.mark.anyio
    async def test_create_rca_minimal_fields(self, client: AsyncClient):
        """Create root cause analysis with only required fields."""
        payload = {
            "trial_id": EYLEA_TRIAL,
            "complaint_id": "CI-003",
            "root_cause_category": "manufacturing",
            "root_cause_description": "Minimal root cause",
            "identified_by": "Minimal Analyst",
        }
        resp = await client.post(f"{API_PREFIX}/root-cause-analyses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["analysis_method"] == "fishbone"  # default
        assert data["investigation_id"] is None

    @pytest.mark.anyio
    async def test_update_intake_severity(self, client: AsyncClient):
        """Update severity of a complaint."""
        resp = await client.put(
            f"{API_PREFIX}/complaint-intakes/CI-010",
            json={"severity": "major"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "major"

    @pytest.mark.anyio
    async def test_update_investigation_recall_considered(self, client: AsyncClient):
        """Update investigation with recall consideration."""
        resp = await client.put(
            f"{API_PREFIX}/investigation-records/INV-003",
            json={"recall_considered": True, "trend_analysis_performed": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["recall_considered"] is True
        assert data["trend_analysis_performed"] is True

    @pytest.mark.anyio
    async def test_update_rca_probability(self, client: AsyncClient):
        """Update root cause analysis probability and impact."""
        resp = await client.put(
            f"{API_PREFIX}/root-cause-analyses/RCA-006",
            json={"probability_of_recurrence": "low", "impact_scope": "single_batch"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["probability_of_recurrence"] == "low"
        assert data["impact_scope"] == "single_batch"

    @pytest.mark.anyio
    async def test_update_capa_effectiveness(self, client: AsyncClient):
        """Update CAPA with effectiveness confirmation."""
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/capa-linkages/CAPA-003",
            json={
                "effectiveness_confirmed": True,
                "completed_date": now.isoformat(),
                "status": "closed",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["effectiveness_confirmed"] is True
        assert data["status"] == "closed"

    @pytest.mark.anyio
    async def test_update_report_acknowledgment(self, client: AsyncClient):
        """Update regulatory report acknowledgment status."""
        resp = await client.put(
            f"{API_PREFIX}/regulatory-reports/RR-006",
            json={"acknowledgment_received": True, "follow_up_required": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledgment_received"] is True
        assert data["follow_up_required"] is True

    @pytest.mark.anyio
    async def test_list_capas_open_status(self, client: AsyncClient):
        """Filter CAPAs by open status."""
        resp = await client.get(
            f"{API_PREFIX}/capa-linkages", params={"status": "open"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_list_capas_in_progress_status(self, client: AsyncClient):
        """Filter CAPAs by in_progress status."""
        resp = await client.get(
            f"{API_PREFIX}/capa-linkages", params={"status": "in_progress"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_patient_impact_complaints_exist(self, client: AsyncClient):
        """Verify some complaints have patient impact."""
        resp = await client.get(f"{API_PREFIX}/complaint-intakes")
        data = resp.json()
        patient_impact = [item for item in data["items"] if item["patient_impact"] is True]
        assert len(patient_impact) >= 1

    @pytest.mark.anyio
    async def test_sample_received_complaints_exist(self, client: AsyncClient):
        """Verify some complaints have samples received."""
        resp = await client.get(f"{API_PREFIX}/complaint-intakes")
        data = resp.json()
        sample_received = [item for item in data["items"] if item["sample_received"] is True]
        assert len(sample_received) >= 1

    @pytest.mark.anyio
    async def test_verified_root_causes_exist(self, client: AsyncClient):
        """Verify some root causes are verified."""
        resp = await client.get(f"{API_PREFIX}/root-cause-analyses")
        data = resp.json()
        verified = [item for item in data["items"] if item["verified"] is True]
        assert len(verified) >= 1

    @pytest.mark.anyio
    async def test_unverified_root_causes_exist(self, client: AsyncClient):
        """Verify some root causes are not yet verified."""
        resp = await client.get(f"{API_PREFIX}/root-cause-analyses")
        data = resp.json()
        unverified = [item for item in data["items"] if item["verified"] is False]
        assert len(unverified) >= 1

    @pytest.mark.anyio
    async def test_effectiveness_confirmed_capas_exist(self, client: AsyncClient):
        """Verify some CAPAs have effectiveness confirmed."""
        resp = await client.get(f"{API_PREFIX}/capa-linkages")
        data = resp.json()
        confirmed = [item for item in data["items"] if item["effectiveness_confirmed"] is True]
        assert len(confirmed) >= 1

    @pytest.mark.anyio
    async def test_reports_with_follow_up_exist(self, client: AsyncClient):
        """Verify some reports require follow-up."""
        resp = await client.get(f"{API_PREFIX}/regulatory-reports")
        data = resp.json()
        follow_up = [item for item in data["items"] if item["follow_up_required"] is True]
        assert len(follow_up) >= 1

    @pytest.mark.anyio
    async def test_create_and_delete_rca(self, client: AsyncClient):
        """Create a root cause analysis and then delete it."""
        payload = _make_root_cause_analysis_create()
        resp = await client.post(f"{API_PREFIX}/root-cause-analyses", json=payload)
        assert resp.status_code == 201
        rca_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/root-cause-analyses/{rca_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/root-cause-analyses/{rca_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_delete_regulatory_report(self, client: AsyncClient):
        """Create a regulatory report and then delete it."""
        payload = _make_regulatory_report_create()
        resp = await client.post(f"{API_PREFIX}/regulatory-reports", json=payload)
        assert resp.status_code == 201
        report_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/regulatory-reports/{report_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/regulatory-reports/{report_id}")
        assert resp3.status_code == 404

    def test_service_direct_get_nonexistent(self, svc: ProductComplaintService):
        """Service returns None for nonexistent IDs."""
        assert svc.get_complaint_intake("NONEXISTENT") is None
        assert svc.get_investigation_record("NONEXISTENT") is None
        assert svc.get_root_cause_analysis("NONEXISTENT") is None
        assert svc.get_capa_linkage("NONEXISTENT") is None
        assert svc.get_regulatory_report("NONEXISTENT") is None

    def test_service_direct_delete_nonexistent(self, svc: ProductComplaintService):
        """Service returns False for deleting nonexistent IDs."""
        assert svc.delete_complaint_intake("NONEXISTENT") is False
        assert svc.delete_investigation_record("NONEXISTENT") is False
        assert svc.delete_root_cause_analysis("NONEXISTENT") is False
        assert svc.delete_capa_linkage("NONEXISTENT") is False
        assert svc.delete_regulatory_report("NONEXISTENT") is False
