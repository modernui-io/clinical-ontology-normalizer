"""Tests for Safety Database & CIOMS Reporting (CLINICAL-23).

Covers:
- Seed data verification (cases, submissions, aggregate reports)
- Safety case CRUD (create, read, update, delete, list, filter)
- Case filtering by trial, site, type, status, seriousness, expectedness, relatedness, outcome
- Regulatory submission management (list, create, update, overdue detection)
- CIOMS form generation (CIOMS I, CIOMS II, MedWatch, E2B)
- Expedited reporting timeline calculation (7-day, 15-day)
- SUSAR identification (serious + unexpected + related)
- Aggregate report CRUD (DSUR, PSUR, PBRER, ASR)
- Safety database metrics computation
- Seriousness, expectedness, relatedness classification
- MedDRA coding (PT, SOC)
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.safety_database import (
    AggregateReportCreate,
    AggregateReportStatus,
    AggregateReportType,
    AggregateReportUpdate,
    CaseType,
    CIOMSFormType,
    EventOutcome,
    Expectedness,
    Relatedness,
    RegulatoryAuthority,
    RegulatorySubmissionCreate,
    RegulatorySubmissionUpdate,
    ReporterType,
    ReportingStatus,
    SafetyCaseCreate,
    SafetyCaseUpdate,
    Seriousness,
    SubmissionStatus,
)
from app.services.safety_database_service import (
    EXPEDITED_FATAL_DAYS,
    EXPEDITED_SERIOUS_DAYS,
    SafetyDatabaseService,
    get_safety_db_service,
    reset_safety_db_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/safety-database"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_safety_db_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SafetyDatabaseService:
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


def _make_case_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "patient_id": "PAT-TEST-001",
        "site_id": "SITE-101",
        "case_type": "initial",
        "seriousness_criteria": ["hospitalization"],
        "expectedness": "expected",
        "relatedness": "related",
        "reporter_type": "physician",
        "narrative": "Test case for unit testing purposes.",
        "meddra_pt": "Test reaction",
        "meddra_soc": "Test SOC",
        "onset_date": (now - timedelta(days=3)).isoformat(),
        "outcome": "recovered",
    }
    defaults.update(overrides)
    return defaults


def _make_submission_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "authority": "FDA",
        "form_type": "medwatch_3500a",
        "due_date": (now + timedelta(days=15)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_aggregate_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "report_type": "DSUR",
        "period_start": (now - timedelta(days=365)).isoformat(),
        "period_end": now.isoformat(),
        "due_date": (now + timedelta(days=90)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_cases_count(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        assert len(cases) == 25

    def test_seed_cases_have_all_trials(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        trials = {c.trial_id for c in cases}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_cases_have_case_numbers(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        for case in cases:
            assert case.case_number.startswith("CASE-")

    def test_seed_submissions_count(self, svc: SafetyDatabaseService):
        submissions = svc.list_submissions()
        assert len(submissions) == 40

    def test_seed_aggregate_reports_count(self, svc: SafetyDatabaseService):
        reports = svc.list_aggregate_reports()
        assert len(reports) == 3

    def test_seed_aggregate_reports_one_per_trial(self, svc: SafetyDatabaseService):
        reports = svc.list_aggregate_reports()
        trials = {r.trial_id for r in reports}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_cases_have_seriousness(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        serious = [c for c in cases if c.seriousness_criteria]
        assert len(serious) > 0

    def test_seed_cases_have_fatal_outcomes(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        fatal = [c for c in cases if c.outcome == EventOutcome.FATAL]
        assert len(fatal) >= 2

    def test_seed_cases_have_unexpected(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        unexpected = [c for c in cases if c.expectedness == Expectedness.UNEXPECTED]
        assert len(unexpected) > 0

    def test_seed_cases_have_multiple_case_types(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        types = {c.case_type for c in cases}
        assert CaseType.INITIAL in types
        assert CaseType.FOLLOW_UP in types
        assert CaseType.AMENDMENT in types

    def test_seed_submissions_have_multiple_authorities(self, svc: SafetyDatabaseService):
        submissions = svc.list_submissions()
        authorities = {s.authority for s in submissions}
        assert RegulatoryAuthority.FDA in authorities
        assert RegulatoryAuthority.EMA in authorities

    def test_seed_cases_linked_to_submissions(self, svc: SafetyDatabaseService):
        case = svc.get_case("SC-002")
        assert case is not None
        assert len(case.regulatory_submissions) > 0


# =====================================================================
# SAFETY CASE CRUD
# =====================================================================


class TestSafetyCaseCrud:
    """Test safety case create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_cases(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25
        assert len(data["items"]) == 25

    @pytest.mark.anyio
    async def test_list_cases_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_cases_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_cases_filter_case_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"case_type": "initial"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["case_type"] == "initial"

    @pytest.mark.anyio
    async def test_list_cases_filter_reporting_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"reporting_status": "closed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["reporting_status"] == "closed"

    @pytest.mark.anyio
    async def test_list_cases_filter_seriousness(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"seriousness": "death"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert "death" in item["seriousness_criteria"]

    @pytest.mark.anyio
    async def test_list_cases_filter_expectedness(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"expectedness": "unexpected"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["expectedness"] == "unexpected"

    @pytest.mark.anyio
    async def test_list_cases_filter_relatedness(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"relatedness": "related"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["relatedness"] == "related"

    @pytest.mark.anyio
    async def test_list_cases_filter_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"outcome": "fatal"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["outcome"] == "fatal"

    @pytest.mark.anyio
    async def test_get_case(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SC-001"
        assert data["case_number"] == "CASE-2025-0001"

    @pytest.mark.anyio
    async def test_get_case_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_case(self, client: AsyncClient):
        payload = _make_case_create()
        resp = await client.post(f"{API_PREFIX}/cases", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["case_number"].startswith("CASE-")
        assert data["reporting_status"] == "draft"

    @pytest.mark.anyio
    async def test_create_case_with_all_seriousness(self, client: AsyncClient):
        payload = _make_case_create(
            seriousness_criteria=["death", "life_threatening", "hospitalization"],
            expectedness="unexpected",
            relatedness="related",
            outcome="fatal",
        )
        resp = await client.post(f"{API_PREFIX}/cases", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["seriousness_criteria"]) == 3

    @pytest.mark.anyio
    async def test_update_case(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cases/SC-001",
            json={"narrative": "Updated narrative for case.", "reporting_status": "submitted_to_authority"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["narrative"] == "Updated narrative for case."
        assert data["reporting_status"] == "submitted_to_authority"

    @pytest.mark.anyio
    async def test_update_case_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cases/SC-NONEXISTENT",
            json={"narrative": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_case_most_recent_date_updates(self, client: AsyncClient):
        before = await client.get(f"{API_PREFIX}/cases/SC-001")
        old_date = before.json()["most_recent_date"]
        resp = await client.put(
            f"{API_PREFIX}/cases/SC-001",
            json={"narrative": "Updated again."},
        )
        assert resp.status_code == 200
        new_date = resp.json()["most_recent_date"]
        assert new_date >= old_date

    @pytest.mark.anyio
    async def test_delete_case(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/cases/SC-020")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/cases/SC-020")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_case_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/cases/SC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_case_removes_submissions(self, svc: SafetyDatabaseService, client: AsyncClient):
        # SC-001 has submissions
        case = svc.get_case("SC-001")
        assert case is not None
        assert len(case.regulatory_submissions) > 0
        resp = await client.delete(f"{API_PREFIX}/cases/SC-001")
        assert resp.status_code == 204
        # Submissions should be gone
        subs = svc.list_submissions(case_id="SC-001")
        assert len(subs) == 0

    @pytest.mark.anyio
    async def test_cases_sorted_by_receipt_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases")
        data = resp.json()
        dates = [item["initial_receipt_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# REGULATORY SUBMISSIONS
# =====================================================================


class TestRegulatorySubmissions:
    """Test regulatory submission operations."""

    @pytest.mark.anyio
    async def test_list_all_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 40

    @pytest.mark.anyio
    async def test_list_submissions_filter_case(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"case_id": "SC-002"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["case_id"] == "SC-002"

    @pytest.mark.anyio
    async def test_list_submissions_filter_authority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"authority": "FDA"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["authority"] == "FDA"

    @pytest.mark.anyio
    async def test_list_submissions_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"status": "pending"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "pending"

    @pytest.mark.anyio
    async def test_list_case_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-008/submissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_list_case_submissions_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-NONEXISTENT/submissions")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_submission(self, client: AsyncClient):
        payload = _make_submission_create()
        resp = await client.post(f"{API_PREFIX}/cases/SC-015/submissions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["case_id"] == "SC-015"
        assert data["authority"] == "FDA"
        assert data["status"] == "pending"

    @pytest.mark.anyio
    async def test_create_submission_case_not_found(self, client: AsyncClient):
        payload = _make_submission_create()
        resp = await client.post(f"{API_PREFIX}/cases/SC-NONEXISTENT/submissions", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions/SUB-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SUB-001"

    @pytest.mark.anyio
    async def test_get_submission_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions/SUB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_submission(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/submissions/SUB-026",
            json={"submission_date": now.isoformat(), "status": "submitted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"
        assert data["submission_date"] is not None

    @pytest.mark.anyio
    async def test_update_submission_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/submissions/SUB-NONEXISTENT",
            json={"status": "submitted"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_overdue_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions/overdue")
        assert resp.status_code == 200
        data = resp.json()
        # Should have some overdue (SUB-026, SUB-027, SUB-030 are pending and past due)
        assert data["total"] > 0
        now = datetime.now(timezone.utc)
        for item in data["items"]:
            due = datetime.fromisoformat(item["due_date"])
            assert due < now
            assert item["status"] == "pending"

    @pytest.mark.anyio
    async def test_create_submission_ema(self, client: AsyncClient):
        payload = _make_submission_create(authority="EMA", form_type="cioms_i")
        resp = await client.post(f"{API_PREFIX}/cases/SC-024/submissions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["authority"] == "EMA"
        assert data["form_type"] == "cioms_i"


# =====================================================================
# CIOMS FORM GENERATION
# =====================================================================


class TestCIOMSFormGeneration:
    """Test CIOMS form generation from case data."""

    @pytest.mark.anyio
    async def test_generate_cioms_form(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-001/cioms-form")
        assert resp.status_code == 200
        data = resp.json()
        assert data["case_id"] == "SC-001"
        assert data["form_type"] == "cioms_i"
        assert "reaction_terms" in data
        assert len(data["reaction_terms"]) > 0

    @pytest.mark.anyio
    async def test_generate_cioms_form_medwatch(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/cases/SC-001/cioms-form",
            params={"form_type": "medwatch_3500a"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["form_type"] == "medwatch_3500a"

    @pytest.mark.anyio
    async def test_generate_cioms_form_e2b(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/cases/SC-001/cioms-form",
            params={"form_type": "e2b_r3"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["form_type"] == "e2b_r3"

    @pytest.mark.anyio
    async def test_generate_cioms_form_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-NONEXISTENT/cioms-form")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_cioms_form_has_suspect_drug(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-007/cioms-form")
        data = resp.json()
        assert "Cemiplimab" in data["suspect_drug"] or "LIBTAYO" in data["suspect_drug"]

    @pytest.mark.anyio
    async def test_cioms_form_has_dose_info(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-004/cioms-form")
        data = resp.json()
        assert len(data["dose"]) > 0
        assert len(data["route"]) > 0

    @pytest.mark.anyio
    async def test_cioms_form_has_indication(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-001/cioms-form")
        data = resp.json()
        assert len(data["indication"]) > 0

    @pytest.mark.anyio
    async def test_list_cioms_forms(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cioms-forms")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_list_cioms_forms_filter_case(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cioms-forms", params={"case_id": "SC-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["case_id"] == "SC-001"

    @pytest.mark.anyio
    async def test_cioms_form_has_reporter_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-002/cioms-form")
        data = resp.json()
        assert data["reporter_assessment"] is not None
        assert data["company_assessment"] is not None


# =====================================================================
# EXPEDITED REPORTING TIMELINES
# =====================================================================


class TestExpeditedReporting:
    """Test expedited reporting timeline calculation."""

    @pytest.mark.anyio
    async def test_reporting_deadline_fatal_unexpected(self, client: AsyncClient):
        """Fatal + unexpected -> 7 days."""
        resp = await client.get(f"{API_PREFIX}/cases/SC-008/reporting-deadline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["expedited_days"] == EXPEDITED_FATAL_DAYS
        assert data["is_susar"] is True
        assert data["deadline"] is not None

    @pytest.mark.anyio
    async def test_reporting_deadline_life_threatening_unexpected(self, client: AsyncClient):
        """Life-threatening + unexpected -> 7 days."""
        resp = await client.get(f"{API_PREFIX}/cases/SC-002/reporting-deadline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["expedited_days"] == EXPEDITED_FATAL_DAYS
        assert data["is_susar"] is True

    @pytest.mark.anyio
    async def test_reporting_deadline_serious_expected(self, client: AsyncClient):
        """Serious + expected -> 15 days."""
        resp = await client.get(f"{API_PREFIX}/cases/SC-001/reporting-deadline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["expedited_days"] == EXPEDITED_SERIOUS_DAYS
        assert data["is_susar"] is False

    @pytest.mark.anyio
    async def test_reporting_deadline_non_serious(self, client: AsyncClient):
        """Non-serious -> 0 (periodic only)."""
        resp = await client.get(f"{API_PREFIX}/cases/SC-015/reporting-deadline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["expedited_days"] == 0
        assert data["deadline"] is None

    @pytest.mark.anyio
    async def test_reporting_deadline_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-NONEXISTENT/reporting-deadline")
        assert resp.status_code == 404

    def test_calculate_deadline_service_fatal(self, svc: SafetyDatabaseService):
        case = svc.get_case("SC-008")
        assert case is not None
        days = svc.calculate_reporting_deadline(case)
        assert days == EXPEDITED_FATAL_DAYS

    def test_calculate_deadline_service_serious(self, svc: SafetyDatabaseService):
        case = svc.get_case("SC-001")
        assert case is not None
        days = svc.calculate_reporting_deadline(case)
        assert days == EXPEDITED_SERIOUS_DAYS

    def test_calculate_deadline_service_non_serious(self, svc: SafetyDatabaseService):
        case = svc.get_case("SC-015")
        assert case is not None
        days = svc.calculate_reporting_deadline(case)
        assert days == 0


# =====================================================================
# SUSARs
# =====================================================================


class TestSUSARs:
    """Test SUSAR identification (serious + unexpected + at least possibly related)."""

    @pytest.mark.anyio
    async def test_list_susars(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/susars")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            # Verify SUSAR criteria
            assert len(item["seriousness_criteria"]) > 0
            assert item["expectedness"] == "unexpected"
            assert item["relatedness"] in ("related", "possibly_related")

    @pytest.mark.anyio
    async def test_susar_includes_known_cases(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/susars")
        data = resp.json()
        susar_ids = {item["id"] for item in data["items"]}
        # SC-002: life-threatening, unexpected, related
        assert "SC-002" in susar_ids
        # SC-008: death, unexpected, possibly_related
        assert "SC-008" in susar_ids
        # SC-025: life-threatening, unexpected, related
        assert "SC-025" in susar_ids

    @pytest.mark.anyio
    async def test_susar_excludes_expected_cases(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/susars")
        data = resp.json()
        susar_ids = {item["id"] for item in data["items"]}
        # SC-001: expected -> not SUSAR
        assert "SC-001" not in susar_ids

    @pytest.mark.anyio
    async def test_susar_excludes_unrelated_cases(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/susars")
        data = resp.json()
        susar_ids = {item["id"] for item in data["items"]}
        # SC-013: death, expected, unrelated -> not SUSAR
        assert "SC-013" not in susar_ids

    def test_susar_service_method(self, svc: SafetyDatabaseService):
        susars = svc.get_susars()
        for s in susars:
            assert s.seriousness_criteria
            assert s.expectedness == Expectedness.UNEXPECTED
            assert s.relatedness in (Relatedness.RELATED, Relatedness.POSSIBLY_RELATED)


# =====================================================================
# AGGREGATE REPORTS
# =====================================================================


class TestAggregateReports:
    """Test aggregate safety report operations."""

    @pytest.mark.anyio
    async def test_list_aggregate_reports(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aggregate-reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_aggregate_reports_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/aggregate-reports", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_aggregate_reports_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/aggregate-reports", params={"report_type": "DSUR"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["report_type"] == "DSUR"

    @pytest.mark.anyio
    async def test_list_aggregate_reports_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/aggregate-reports", params={"status": "in_review"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "in_review"

    @pytest.mark.anyio
    async def test_get_aggregate_report(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aggregate-reports/AGG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AGG-001"
        assert data["report_type"] == "DSUR"

    @pytest.mark.anyio
    async def test_get_aggregate_report_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aggregate-reports/AGG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_aggregate_report(self, client: AsyncClient):
        payload = _make_aggregate_create(report_type="PSUR")
        resp = await client.post(f"{API_PREFIX}/aggregate-reports", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["report_type"] == "PSUR"
        assert data["status"] == "drafting"
        assert data["id"].startswith("AGG-")

    @pytest.mark.anyio
    async def test_update_aggregate_report(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/aggregate-reports/AGG-001",
            json={
                "status": "approved",
                "total_cases": 10,
                "serious_cases": 7,
                "fatal_cases": 1,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["total_cases"] == 10
        assert data["serious_cases"] == 7
        assert data["fatal_cases"] == 1

    @pytest.mark.anyio
    async def test_update_aggregate_report_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/aggregate-reports/AGG-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_aggregate_report(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/aggregate-reports/AGG-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/aggregate-reports/AGG-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_aggregate_report_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/aggregate-reports/AGG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_aggregate_report_has_case_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aggregate-reports/AGG-003")
        data = resp.json()
        assert data["total_cases"] > 0
        assert data["serious_cases"] > 0
        assert data["fatal_cases"] >= 0


# =====================================================================
# METRICS
# =====================================================================


class TestSafetyDatabaseMetrics:
    """Test safety database metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cases"] == 25
        assert data["total_submissions"] == 40
        assert data["fatal_cases"] >= 2

    @pytest.mark.anyio
    async def test_metrics_cases_by_seriousness(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        seriousness = data["cases_by_seriousness"]
        assert isinstance(seriousness, dict)
        assert len(seriousness) > 0
        # Should have at least hospitalization and death
        assert "hospitalization" in seriousness
        assert "death" in seriousness

    @pytest.mark.anyio
    async def test_metrics_cases_by_relatedness(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        relatedness = data["cases_by_relatedness"]
        assert isinstance(relatedness, dict)
        assert len(relatedness) > 0
        assert "related" in relatedness

    @pytest.mark.anyio
    async def test_metrics_cases_by_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        outcome = data["cases_by_outcome"]
        assert isinstance(outcome, dict)
        assert "recovered" in outcome
        assert "fatal" in outcome

    @pytest.mark.anyio
    async def test_metrics_overdue_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["overdue_submissions"] >= 0

    @pytest.mark.anyio
    async def test_metrics_avg_submission_time(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_submission_time_days"] >= 0

    @pytest.mark.anyio
    async def test_metrics_aggregate_reports_due(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["aggregate_reports_due"] >= 0

    @pytest.mark.anyio
    async def test_metrics_unexpected_serious(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["unexpected_serious_cases"] > 0

    def test_metrics_service_overdue_matches(self, svc: SafetyDatabaseService):
        metrics = svc.get_metrics()
        overdue = svc.get_overdue_submissions()
        assert metrics.overdue_submissions == len(overdue)

    def test_metrics_service_fatal_count(self, svc: SafetyDatabaseService):
        metrics = svc.get_metrics()
        fatal = [c for c in svc.list_cases() if c.outcome == EventOutcome.FATAL]
        assert metrics.fatal_cases == len(fatal)

    def test_metrics_service_susar_count(self, svc: SafetyDatabaseService):
        metrics = svc.get_metrics()
        susars = svc.get_susars()
        assert metrics.unexpected_serious_cases == len(susars)

    def test_metrics_pending_submissions(self, svc: SafetyDatabaseService):
        metrics = svc.get_metrics()
        pending = svc.list_submissions(status=SubmissionStatus.PENDING)
        assert metrics.pending_submissions == len(pending)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_safety_db_service()
        svc2 = get_safety_db_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_safety_db_service()
        svc2 = reset_safety_db_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_safety_db_service()
        svc.delete_case("SC-001")
        assert svc.get_case("SC-001") is None
        svc2 = reset_safety_db_service()
        assert svc2.get_case("SC-001") is not None


# =====================================================================
# MEDDRA CODING
# =====================================================================


class TestMedDRACoding:
    """Test MedDRA coding in cases."""

    @pytest.mark.anyio
    async def test_case_has_meddra_pt(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-001")
        data = resp.json()
        assert len(data["meddra_pt"]) > 0

    @pytest.mark.anyio
    async def test_case_has_meddra_soc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-001")
        data = resp.json()
        assert len(data["meddra_soc"]) > 0

    @pytest.mark.anyio
    async def test_cioms_form_reaction_terms_match_case(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-007/cioms-form")
        data = resp.json()
        # Should contain the MedDRA PT from the case
        assert "Pneumonitis" in data["reaction_terms"]

    def test_all_cases_have_meddra(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        for case in cases:
            assert len(case.meddra_pt) > 0
            assert len(case.meddra_soc) > 0


# =====================================================================
# SERIOUSNESS CLASSIFICATION
# =====================================================================


class TestSeriousnessClassification:
    """Test seriousness criteria usage."""

    @pytest.mark.anyio
    async def test_death_seriousness(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"seriousness": "death"})
        data = resp.json()
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_hospitalization_seriousness(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"seriousness": "hospitalization"})
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_life_threatening_seriousness(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"seriousness": "life_threatening"})
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_disability_seriousness(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"seriousness": "disability"})
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_congenital_anomaly_seriousness(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases", params={"seriousness": "congenital_anomaly"})
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_multiple_seriousness_criteria(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-006")
        data = resp.json()
        assert len(data["seriousness_criteria"]) > 1

    def test_non_serious_cases_exist(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        non_serious = [c for c in cases if not c.seriousness_criteria]
        assert len(non_serious) > 0


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_cases_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_submissions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_aggregate_reports_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aggregate-reports")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_case_non_serious(self, client: AsyncClient):
        payload = _make_case_create(seriousness_criteria=[], outcome="recovered")
        resp = await client.post(f"{API_PREFIX}/cases", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["seriousness_criteria"] == []

    @pytest.mark.anyio
    async def test_create_case_follow_up(self, client: AsyncClient):
        payload = _make_case_create(case_type="follow_up")
        resp = await client.post(f"{API_PREFIX}/cases", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["case_type"] == "follow_up"

    @pytest.mark.anyio
    async def test_create_case_amendment(self, client: AsyncClient):
        payload = _make_case_create(case_type="amendment")
        resp = await client.post(f"{API_PREFIX}/cases", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["case_type"] == "amendment"

    @pytest.mark.anyio
    async def test_create_submission_pmda(self, client: AsyncClient):
        payload = _make_submission_create(authority="PMDA", form_type="cioms_i")
        resp = await client.post(f"{API_PREFIX}/cases/SC-015/submissions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["authority"] == "PMDA"

    @pytest.mark.anyio
    async def test_create_aggregate_report_pbrer(self, client: AsyncClient):
        payload = _make_aggregate_create(report_type="PBRER")
        resp = await client.post(f"{API_PREFIX}/aggregate-reports", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["report_type"] == "PBRER"

    @pytest.mark.anyio
    async def test_create_aggregate_report_asr(self, client: AsyncClient):
        payload = _make_aggregate_create(report_type="ASR")
        resp = await client.post(f"{API_PREFIX}/aggregate-reports", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["report_type"] == "ASR"

    @pytest.mark.anyio
    async def test_update_case_outcome(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cases/SC-009",
            json={"outcome": "recovered", "resolution_date": datetime.now(timezone.utc).isoformat()},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "recovered"
        assert data["resolution_date"] is not None

    @pytest.mark.anyio
    async def test_update_case_expectedness(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cases/SC-001",
            json={"expectedness": "unexpected"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["expectedness"] == "unexpected"

    @pytest.mark.anyio
    async def test_update_submission_acknowledgment(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/submissions/SUB-024",
            json={"acknowledgment_date": now.isoformat(), "status": "acknowledged"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "acknowledged"

    @pytest.mark.anyio
    async def test_cioms_form_for_dupixent_case(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-004/cioms-form")
        data = resp.json()
        assert "Dupilumab" in data["suspect_drug"] or "DUPIXENT" in data["suspect_drug"]

    @pytest.mark.anyio
    async def test_cioms_form_for_eylea_case(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cases/SC-001/cioms-form")
        data = resp.json()
        assert "Aflibercept" in data["suspect_drug"] or "EYLEA" in data["suspect_drug"]


# =====================================================================
# REPORTER TYPE COVERAGE
# =====================================================================


class TestReporterTypes:
    """Test reporter type coverage in seed data."""

    def test_physician_reporter(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        physicians = [c for c in cases if c.reporter_type == ReporterType.PHYSICIAN]
        assert len(physicians) > 0

    def test_nurse_reporter(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        nurses = [c for c in cases if c.reporter_type == ReporterType.NURSE]
        assert len(nurses) > 0

    def test_patient_reporter(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        patients = [c for c in cases if c.reporter_type == ReporterType.PATIENT]
        assert len(patients) > 0

    def test_pharmacist_reporter(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        pharmacists = [c for c in cases if c.reporter_type == ReporterType.PHARMACIST]
        assert len(pharmacists) > 0

    def test_other_hcp_reporter(self, svc: SafetyDatabaseService):
        cases = svc.list_cases()
        others = [c for c in cases if c.reporter_type == ReporterType.OTHER_HCP]
        assert len(others) > 0


# =====================================================================
# OUTCOME COVERAGE
# =====================================================================


class TestOutcomeCoverage:
    """Test event outcome coverage."""

    def test_recovered_outcome(self, svc: SafetyDatabaseService):
        cases = svc.list_cases(outcome=EventOutcome.RECOVERED)
        assert len(cases) > 0

    def test_recovering_outcome(self, svc: SafetyDatabaseService):
        cases = svc.list_cases(outcome=EventOutcome.RECOVERING)
        assert len(cases) > 0

    def test_not_recovered_outcome(self, svc: SafetyDatabaseService):
        cases = svc.list_cases(outcome=EventOutcome.NOT_RECOVERED)
        assert len(cases) > 0

    def test_fatal_outcome(self, svc: SafetyDatabaseService):
        cases = svc.list_cases(outcome=EventOutcome.FATAL)
        assert len(cases) > 0

    def test_unknown_outcome(self, svc: SafetyDatabaseService):
        cases = svc.list_cases(outcome=EventOutcome.UNKNOWN)
        assert len(cases) > 0


# =====================================================================
# SUBMISSION AUTHORITY COVERAGE
# =====================================================================


class TestAuthoritySubmissions:
    """Test regulatory authority coverage."""

    @pytest.mark.anyio
    async def test_fda_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"authority": "FDA"})
        assert resp.status_code == 200
        assert resp.json()["total"] > 0

    @pytest.mark.anyio
    async def test_ema_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"authority": "EMA"})
        assert resp.status_code == 200
        assert resp.json()["total"] > 0

    @pytest.mark.anyio
    async def test_pmda_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"authority": "PMDA"})
        assert resp.status_code == 200
        assert resp.json()["total"] > 0

    @pytest.mark.anyio
    async def test_mhra_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"authority": "MHRA"})
        assert resp.status_code == 200
        assert resp.json()["total"] > 0

    @pytest.mark.anyio
    async def test_hc_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"authority": "HC"})
        assert resp.status_code == 200
        assert resp.json()["total"] > 0

    @pytest.mark.anyio
    async def test_tga_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"authority": "TGA"})
        assert resp.status_code == 200
        assert resp.json()["total"] > 0


# =====================================================================
# SUBMISSION STATUS COVERAGE
# =====================================================================


class TestSubmissionStatuses:
    """Test submission status coverage."""

    @pytest.mark.anyio
    async def test_pending_submissions_exist(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"status": "pending"})
        assert resp.status_code == 200
        assert resp.json()["total"] > 0

    @pytest.mark.anyio
    async def test_submitted_submissions_exist(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"status": "submitted"})
        assert resp.status_code == 200
        assert resp.json()["total"] > 0

    @pytest.mark.anyio
    async def test_acknowledged_submissions_exist(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"status": "acknowledged"})
        assert resp.status_code == 200
        assert resp.json()["total"] > 0
