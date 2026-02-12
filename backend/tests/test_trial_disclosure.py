"""Tests for Trial Disclosure Management (TRIAL-DISC).

Covers:
- Seed data verification (results disclosures, registry submissions, mandates, summaries, timelines)
- Results disclosure CRUD (create, read, update, delete, list, filter by trial/type/status)
- Registry submission CRUD (create, read, update, delete, list, filter by trial/registry)
- Publication mandate CRUD (create, read, update, delete, list, filter by trial/type)
- Lay summary CRUD (create, read, update, delete, list, filter by trial/audience/status)
- Compliance timeline CRUD (create, read, update, delete, list, filter by trial/status)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.trial_disclosure import (
    DisclosureStatus,
    DisclosureType,
    MandateType,
    RegistryName,
    SummaryAudience,
)
from app.services.trial_disclosure_service import (
    TrialDisclosureService,
    get_trial_disclosure_service,
    reset_trial_disclosure_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/trial-disclosure"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_trial_disclosure_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> TrialDisclosureService:
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


def _make_disclosure_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "disclosure_type": "results_posting",
        "prepared_by": "Dr. Test Preparer",
        "registry_name": "clinicaltrials_gov",
        "registry_id": "NCT99999999",
    }
    defaults.update(overrides)
    return defaults


def _make_submission_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "registry_name": "clinicaltrials_gov",
        "registry_id": "NCT04056789",
        "submitted_by": "Dr. Test Submitter",
        "submission_type": "amendment",
    }
    defaults.update(overrides)
    return defaults


def _make_mandate_create(**overrides) -> dict:
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "mandate_type": "fdaaa_801",
        "regulation_reference": "42 USC 282(j)(3)(C)",
        "responsible_party": "Dr. Test Responsible",
        "deadline_months_from_completion": 12,
    }
    defaults.update(overrides)
    return defaults


def _make_summary_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "target_audience": "general_public",
        "authored_by": "Dr. Test Author",
        "language": "en",
        "word_count": 500,
    }
    defaults.update(overrides)
    return defaults


def _make_timeline_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "milestone_name": "Test milestone",
        "target_date": (now + timedelta(days=90)).isoformat(),
        "responsible_party": "Dr. Test Responsible",
        "managed_by": "Test Manager",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_results_disclosures_count(self, svc: TrialDisclosureService):
        items = svc.list_results_disclosures()
        assert len(items) == 12

    def test_seed_registry_submissions_count(self, svc: TrialDisclosureService):
        items = svc.list_registry_submissions()
        assert len(items) == 12

    def test_seed_publication_mandates_count(self, svc: TrialDisclosureService):
        items = svc.list_publication_mandates()
        assert len(items) == 12

    def test_seed_lay_summaries_count(self, svc: TrialDisclosureService):
        items = svc.list_lay_summaries()
        assert len(items) == 12

    def test_seed_compliance_timelines_count(self, svc: TrialDisclosureService):
        items = svc.list_compliance_timelines()
        assert len(items) == 12

    def test_seed_disclosures_cover_all_trials(self, svc: TrialDisclosureService):
        items = svc.list_results_disclosures()
        trial_ids = {d.trial_id for d in items}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_disclosures_have_multiple_types(self, svc: TrialDisclosureService):
        items = svc.list_results_disclosures()
        types = {d.disclosure_type for d in items}
        assert len(types) >= 4

    def test_seed_disclosures_have_overdue(self, svc: TrialDisclosureService):
        items = svc.list_results_disclosures()
        statuses = {d.status for d in items}
        assert DisclosureStatus.OVERDUE in statuses
        assert DisclosureStatus.POSTED in statuses

    def test_seed_submissions_have_multiple_registries(self, svc: TrialDisclosureService):
        items = svc.list_registry_submissions()
        registries = {s.registry_name for s in items}
        assert len(registries) >= 4

    def test_seed_mandates_have_multiple_types(self, svc: TrialDisclosureService):
        items = svc.list_publication_mandates()
        types = {m.mandate_type for m in items}
        assert len(types) >= 4

    def test_seed_summaries_have_multiple_audiences(self, svc: TrialDisclosureService):
        items = svc.list_lay_summaries()
        audiences = {ls.target_audience for ls in items}
        assert len(audiences) >= 4

    def test_seed_timelines_have_overdue(self, svc: TrialDisclosureService):
        items = svc.list_compliance_timelines()
        statuses = {t.status for t in items}
        assert "overdue" in statuses
        assert "completed" in statuses


# =====================================================================
# RESULTS DISCLOSURE CRUD
# =====================================================================


class TestResultsDisclosureCrud:
    """Test results disclosure CRUD operations."""

    @pytest.mark.anyio
    async def test_list_results_disclosures(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results-disclosures")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_disclosures_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/results-disclosures", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_disclosures_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/results-disclosures", params={"disclosure_type": "results_posting"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["disclosure_type"] == "results_posting"

    @pytest.mark.anyio
    async def test_list_disclosures_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/results-disclosures", params={"status": "overdue"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "overdue"

    @pytest.mark.anyio
    async def test_get_results_disclosure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results-disclosures/RD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RD-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["disclosure_type"] == "results_posting"

    @pytest.mark.anyio
    async def test_get_results_disclosure_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results-disclosures/RD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_results_disclosure(self, client: AsyncClient):
        payload = _make_disclosure_create()
        resp = await client.post(f"{API_PREFIX}/results-disclosures", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["disclosure_type"] == "results_posting"
        assert data["status"] == "not_due"
        assert data["id"].startswith("RD-")

    @pytest.mark.anyio
    async def test_update_results_disclosure(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/results-disclosures/RD-004",
            json={"status": "in_preparation", "notes": "Work started"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_preparation"
        assert data["notes"] == "Work started"

    @pytest.mark.anyio
    async def test_update_results_disclosure_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/results-disclosures/RD-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_results_disclosure(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/results-disclosures/RD-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/results-disclosures/RD-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_results_disclosure_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/results-disclosures/RD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# REGISTRY SUBMISSION CRUD
# =====================================================================


class TestRegistrySubmissionCrud:
    """Test registry submission CRUD operations."""

    @pytest.mark.anyio
    async def test_list_registry_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/registry-submissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_submissions_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/registry-submissions", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_submissions_filter_registry(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/registry-submissions",
            params={"registry_name": "clinicaltrials_gov"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["registry_name"] == "clinicaltrials_gov"

    @pytest.mark.anyio
    async def test_get_registry_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/registry-submissions/RS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RS-001"
        assert data["registry_name"] == "clinicaltrials_gov"

    @pytest.mark.anyio
    async def test_get_registry_submission_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/registry-submissions/RS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_registry_submission(self, client: AsyncClient):
        payload = _make_submission_create()
        resp = await client.post(f"{API_PREFIX}/registry-submissions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["registry_name"] == "clinicaltrials_gov"
        assert data["submission_type"] == "amendment"
        assert data["id"].startswith("RS-")

    @pytest.mark.anyio
    async def test_update_registry_submission(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/registry-submissions/RS-006",
            json={"qc_passed": True, "prs_review_status": "accepted", "reviewer": "PRS Lead"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["qc_passed"] is True
        assert data["prs_review_status"] == "accepted"
        assert data["reviewer"] == "PRS Lead"

    @pytest.mark.anyio
    async def test_update_registry_submission_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/registry-submissions/RS-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_registry_submission(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/registry-submissions/RS-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/registry-submissions/RS-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_registry_submission_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/registry-submissions/RS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PUBLICATION MANDATE CRUD
# =====================================================================


class TestPublicationMandateCrud:
    """Test publication mandate CRUD operations."""

    @pytest.mark.anyio
    async def test_list_publication_mandates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publication-mandates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_mandates_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/publication-mandates", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_mandates_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/publication-mandates", params={"mandate_type": "fdaaa_801"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["mandate_type"] == "fdaaa_801"

    @pytest.mark.anyio
    async def test_get_publication_mandate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publication-mandates/PM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PM-001"
        assert data["mandate_type"] == "fdaaa_801"

    @pytest.mark.anyio
    async def test_get_publication_mandate_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publication-mandates/PM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_publication_mandate(self, client: AsyncClient):
        payload = _make_mandate_create()
        resp = await client.post(f"{API_PREFIX}/publication-mandates", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["mandate_type"] == "fdaaa_801"
        assert data["compliance_status"] == "on_track"
        assert data["id"].startswith("PM-")

    @pytest.mark.anyio
    async def test_update_publication_mandate(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/publication-mandates/PM-005",
            json={"compliance_status": "at_risk", "legal_reviewed": True, "notes": "Urgent"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["compliance_status"] == "at_risk"
        assert data["legal_reviewed"] is True
        assert data["notes"] == "Urgent"

    @pytest.mark.anyio
    async def test_update_publication_mandate_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/publication-mandates/PM-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_publication_mandate(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/publication-mandates/PM-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/publication-mandates/PM-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_publication_mandate_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/publication-mandates/PM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# LAY SUMMARY CRUD
# =====================================================================


class TestLaySummaryCrud:
    """Test lay summary CRUD operations."""

    @pytest.mark.anyio
    async def test_list_lay_summaries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lay-summaries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_summaries_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lay-summaries", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_summaries_filter_audience(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lay-summaries", params={"target_audience": "general_public"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["target_audience"] == "general_public"

    @pytest.mark.anyio
    async def test_list_summaries_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lay-summaries", params={"status": "posted"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "posted"

    @pytest.mark.anyio
    async def test_get_lay_summary(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lay-summaries/LS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LS-001"
        assert data["target_audience"] == "general_public"

    @pytest.mark.anyio
    async def test_get_lay_summary_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lay-summaries/LS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_lay_summary(self, client: AsyncClient):
        payload = _make_summary_create()
        resp = await client.post(f"{API_PREFIX}/lay-summaries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["target_audience"] == "general_public"
        assert data["status"] == "pending"
        assert data["id"].startswith("LS-")

    @pytest.mark.anyio
    async def test_update_lay_summary(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/lay-summaries/LS-004",
            json={"status": "under_review", "patient_reviewed": True, "reviewed_by": "PAB"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "under_review"
        assert data["patient_reviewed"] is True
        assert data["reviewed_by"] == "PAB"

    @pytest.mark.anyio
    async def test_update_lay_summary_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/lay-summaries/LS-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_lay_summary(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/lay-summaries/LS-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/lay-summaries/LS-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_lay_summary_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/lay-summaries/LS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COMPLIANCE TIMELINE CRUD
# =====================================================================


class TestComplianceTimelineCrud:
    """Test compliance timeline CRUD operations."""

    @pytest.mark.anyio
    async def test_list_compliance_timelines(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-timelines")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_timelines_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-timelines", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_timelines_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-timelines", params={"status": "overdue"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "overdue"

    @pytest.mark.anyio
    async def test_get_compliance_timeline(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-timelines/CT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CT-001"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_compliance_timeline_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-timelines/CT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_compliance_timeline(self, client: AsyncClient):
        payload = _make_timeline_create()
        resp = await client.post(f"{API_PREFIX}/compliance-timelines", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["milestone_name"] == "Test milestone"
        assert data["status"] == "upcoming"
        assert data["id"].startswith("CT-")

    @pytest.mark.anyio
    async def test_update_compliance_timeline(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-timelines/CT-007",
            json={"status": "in_progress", "escalation_required": True, "escalated_to": "VP Reg"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["escalation_required"] is True
        assert data["escalated_to"] == "VP Reg"

    @pytest.mark.anyio
    async def test_update_compliance_timeline_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-timelines/CT-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance_timeline(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance-timelines/CT-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/compliance-timelines/CT-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance_timeline_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance-timelines/CT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestTrialDisclosureMetrics:
    """Test trial disclosure metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_disclosures"] == 12
        assert data["total_registry_submissions"] == 12
        assert data["total_mandates"] == 12
        assert data["total_lay_summaries"] == 12
        assert data["total_milestones"] == 12

    @pytest.mark.anyio
    async def test_metrics_disclosures_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["disclosures_by_type"]
        total = sum(by_type.values())
        assert total == data["total_disclosures"]

    @pytest.mark.anyio
    async def test_metrics_disclosures_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["disclosures_by_status"]
        total = sum(by_status.values())
        assert total == data["total_disclosures"]

    @pytest.mark.anyio
    async def test_metrics_overdue_disclosures(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["overdue_disclosures"] >= 2
        assert data["overdue_disclosures"] <= data["total_disclosures"]

    @pytest.mark.anyio
    async def test_metrics_submissions_by_registry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_registry = data["submissions_by_registry"]
        total = sum(by_registry.values())
        assert total == data["total_registry_submissions"]

    @pytest.mark.anyio
    async def test_metrics_mandates_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["mandates_by_type"]
        total = sum(by_type.values())
        assert total == data["total_mandates"]

    @pytest.mark.anyio
    async def test_metrics_mandates_at_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["mandates_at_risk"] >= 1
        assert data["mandates_at_risk"] <= data["total_mandates"]

    @pytest.mark.anyio
    async def test_metrics_summaries_by_audience(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_audience = data["summaries_by_audience"]
        total = sum(by_audience.values())
        assert total == data["total_lay_summaries"]

    @pytest.mark.anyio
    async def test_metrics_milestones_overdue(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["milestones_overdue"] >= 1
        assert data["milestones_overdue"] <= data["total_milestones"]

    @pytest.mark.anyio
    async def test_metrics_milestones_escalated(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["milestones_escalated"] >= 1
        assert data["milestones_escalated"] <= data["total_milestones"]

    def test_metrics_via_service(self, svc: TrialDisclosureService):
        metrics = svc.get_metrics()
        assert metrics.total_disclosures == 12
        assert metrics.overdue_disclosures >= 2
        assert metrics.mandates_at_risk >= 1


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_trial_disclosure_service()
        svc2 = get_trial_disclosure_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_trial_disclosure_service()
        svc2 = reset_trial_disclosure_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_trial_disclosure_service()
        # Delete a disclosure
        svc.delete_results_disclosure("RD-001")
        assert svc.get_results_disclosure("RD-001") is None
        # Reset should bring it back
        svc2 = reset_trial_disclosure_service()
        assert svc2.get_results_disclosure("RD-001") is not None


# =====================================================================
# FILTERING AND EDGE CASES
# =====================================================================


class TestFilteringAndEdgeCases:
    """Test filtering combinations and edge cases."""

    @pytest.mark.anyio
    async def test_list_disclosures_empty_filter(self, client: AsyncClient):
        """Filter by a trial that has no disclosures."""
        resp = await client.get(
            f"{API_PREFIX}/results-disclosures",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_submissions_empty_filter(self, client: AsyncClient):
        """Filter by a registry not present for a specific trial."""
        resp = await client.get(
            f"{API_PREFIX}/registry-submissions",
            params={"registry_name": "japic", "trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_summaries_combined_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/lay-summaries",
            params={"target_audience": "general_public", "status": "posted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["target_audience"] == "general_public"
            assert item["status"] == "posted"

    @pytest.mark.anyio
    async def test_create_disclosure_then_retrieve(self, client: AsyncClient):
        """Create a disclosure and verify it shows in the list."""
        payload = _make_disclosure_create()
        resp = await client.post(f"{API_PREFIX}/results-disclosures", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/results-disclosures/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == created_id

    @pytest.mark.anyio
    async def test_create_submission_then_update(self, client: AsyncClient):
        """Create a submission, then update its review status."""
        payload = _make_submission_create()
        resp = await client.post(f"{API_PREFIX}/registry-submissions", json=payload)
        assert resp.status_code == 201
        submission_id = resp.json()["id"]
        assert resp.json()["qc_passed"] is False

        # Update QC status
        resp2 = await client.put(
            f"{API_PREFIX}/registry-submissions/{submission_id}",
            json={"qc_passed": True, "prs_review_status": "accepted"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["qc_passed"] is True
        assert resp2.json()["prs_review_status"] == "accepted"

    @pytest.mark.anyio
    async def test_create_and_delete_mandate(self, client: AsyncClient):
        """Create a mandate and then delete it."""
        payload = _make_mandate_create()
        resp = await client.post(f"{API_PREFIX}/publication-mandates", json=payload)
        assert resp.status_code == 201
        mandate_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/publication-mandates/{mandate_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/publication-mandates/{mandate_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_create_summary_with_language(self, client: AsyncClient):
        """Create a lay summary with a specific language."""
        payload = _make_summary_create(language="fr", word_count=800)
        resp = await client.post(f"{API_PREFIX}/lay-summaries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["language"] == "fr"
        assert data["word_count"] == 800

    @pytest.mark.anyio
    async def test_create_timeline_with_mandate_id(self, client: AsyncClient):
        """Create a compliance timeline linked to a mandate."""
        payload = _make_timeline_create(mandate_id="PM-004")
        resp = await client.post(f"{API_PREFIX}/compliance-timelines", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["mandate_id"] == "PM-004"

    @pytest.mark.anyio
    async def test_metrics_after_create_and_delete(self, client: AsyncClient):
        """Metrics should reflect dynamic changes."""
        # Get baseline metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        baseline = resp1.json()

        # Create a new disclosure
        payload = _make_disclosure_create()
        await client.post(f"{API_PREFIX}/results-disclosures", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        after_create = resp2.json()
        assert after_create["total_disclosures"] == baseline["total_disclosures"] + 1

        # Delete a disclosure
        await client.delete(f"{API_PREFIX}/results-disclosures/RD-012")
        resp3 = await client.get(f"{API_PREFIX}/metrics")
        after_delete = resp3.json()
        assert after_delete["total_disclosures"] == baseline["total_disclosures"]

    @pytest.mark.anyio
    async def test_update_disclosure_lifecycle(self, client: AsyncClient):
        """Update disclosure through status lifecycle."""
        payload = _make_disclosure_create()
        resp = await client.post(f"{API_PREFIX}/results-disclosures", json=payload)
        assert resp.status_code == 201
        disclosure_id = resp.json()["id"]
        assert resp.json()["status"] == "not_due"

        # Progress through statuses
        for status in ["pending", "in_preparation", "under_review", "submitted", "posted"]:
            resp2 = await client.put(
                f"{API_PREFIX}/results-disclosures/{disclosure_id}",
                json={"status": status},
            )
            assert resp2.status_code == 200
            assert resp2.json()["status"] == status


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Verify enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_disclosure_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results-disclosures")
        data = resp.json()
        types = {item["disclosure_type"] for item in data["items"]}
        assert "results_posting" in types
        assert "summary_report" in types
        assert "lay_summary" in types
        assert "csr_synopsis" in types
        assert "registry_update" in types
        assert "publication" in types

    @pytest.mark.anyio
    async def test_disclosure_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results-disclosures")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "posted" in statuses
        assert "submitted" in statuses
        assert "in_preparation" in statuses
        assert "overdue" in statuses
        assert "pending" in statuses
        assert "not_due" in statuses
        assert "under_review" in statuses

    @pytest.mark.anyio
    async def test_registry_names_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/registry-submissions")
        data = resp.json()
        registries = {item["registry_name"] for item in data["items"]}
        assert "clinicaltrials_gov" in registries
        assert "eudract" in registries
        assert "ctis" in registries
        assert "japic" in registries
        assert "anzctr" in registries
        assert "isrctn" in registries

    @pytest.mark.anyio
    async def test_mandate_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/publication-mandates")
        data = resp.json()
        types = {item["mandate_type"] for item in data["items"]}
        assert "fdaaa_801" in types
        assert "eu_ctr" in types
        assert "health_canada" in types
        assert "icmje" in types
        assert "who_ictrp" in types
        assert "company_policy" in types

    @pytest.mark.anyio
    async def test_summary_audiences_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/lay-summaries")
        data = resp.json()
        audiences = {item["target_audience"] for item in data["items"]}
        assert "general_public" in audiences
        assert "patients" in audiences
        assert "healthcare_providers" in audiences
        assert "regulators" in audiences
        assert "investigators" in audiences
