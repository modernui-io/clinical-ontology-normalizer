"""Tests for SAE Regulatory Reporting (CLINICAL-SAE).

Covers:
- Seed data verification (SAE reports, causality records, regulatory submissions, narratives)
- SAE report CRUD (create, read, update, delete, list, filter by trial/status/seriousness/drug)
- SAE report lifecycle (draft -> medical_review -> submitted -> acknowledged -> closed)
- Causality assessment CRUD and validation
- Regulatory submission workflow (submit to authority, record acknowledgment)
- Reporting deadline enforcement (overdue reports, approaching deadlines)
- Form generation (MedWatch 3500A, CIOMS I)
- Narrative management (initial, follow-up, medical review notes)
- Follow-up and final report creation
- SAE metrics and trial safety summary
- Error handling (404s, 400s, invalid lifecycle transitions)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.sae_reporting import (
    CausalityAssessment,
    CausalityRecordCreate,
    RegulatoryAuthority,
    RegulatorySubmissionCreate,
    ReportingTimeline,
    ReportType,
    SAEOutcome,
    SAEReportCreate,
    SAEReportUpdate,
    SAESeriousness,
    SAEStatus,
)
from app.services.sae_reporting_service import (
    SAEReportingService,
    get_sae_reporting_service,
    reset_sae_reporting_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/sae-reporting"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_sae_reporting_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SAEReportingService:
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


def _make_sae_report_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "subject_id": "SUBJ-9999",
        "seriousness": "hospitalization",
        "outcome": "recovering",
        "event_description": "Test adverse event requiring hospitalization",
        "event_term": "Test event",
        "study_drug": "aflibercept",
        "onset_date": (now - timedelta(days=2)).isoformat(),
        "awareness_date": (now - timedelta(days=1)).isoformat(),
        "initial_narrative": "Test patient developed test event requiring hospitalization.",
    }
    defaults.update(overrides)
    return defaults


def _make_causality_create(**overrides) -> dict:
    defaults = {
        "assessor": "Test Investigator",
        "assessment": "possibly_related",
        "rationale": "Temporal relationship exists between drug administration and event onset.",
    }
    defaults.update(overrides)
    return defaults


def _make_regulatory_submission_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "authority": "fda",
        "submission_type": "initial",
        "submitted_date": now.isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_reports_count(self, svc: SAEReportingService):
        reports = svc.list_sae_reports()
        assert len(reports) == 10

    def test_seed_reports_across_trials(self, svc: SAEReportingService):
        eylea = svc.list_sae_reports(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_sae_reports(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_sae_reports(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 3  # SAE-001, SAE-002, SAE-008
        assert len(dupixent) == 3  # SAE-003, SAE-004, SAE-009
        assert len(libtayo) == 4  # SAE-005, SAE-006, SAE-007, SAE-010

    def test_seed_report_statuses(self, svc: SAEReportingService):
        reports = svc.list_sae_reports()
        statuses = {r.status for r in reports}
        assert SAEStatus.DRAFT in statuses
        assert SAEStatus.SUBMITTED in statuses
        assert SAEStatus.ACKNOWLEDGED in statuses
        assert SAEStatus.CLOSED in statuses
        assert SAEStatus.MEDICAL_REVIEW in statuses

    def test_seed_seriousness_levels(self, svc: SAEReportingService):
        reports = svc.list_sae_reports()
        levels = {r.seriousness for r in reports}
        assert SAESeriousness.DEATH in levels
        assert SAESeriousness.LIFE_THREATENING in levels
        assert SAESeriousness.HOSPITALIZATION in levels
        assert SAESeriousness.DISABILITY in levels
        assert SAESeriousness.CONGENITAL_ANOMALY in levels
        assert SAESeriousness.IMPORTANT_MEDICAL_EVENT in levels

    def test_seed_outcomes(self, svc: SAEReportingService):
        reports = svc.list_sae_reports()
        outcomes = {r.outcome for r in reports}
        assert SAEOutcome.RECOVERED in outcomes
        assert SAEOutcome.RECOVERING in outcomes
        assert SAEOutcome.FATAL in outcomes
        assert SAEOutcome.NOT_RECOVERED in outcomes
        assert SAEOutcome.UNKNOWN in outcomes

    def test_seed_study_drugs(self, svc: SAEReportingService):
        reports = svc.list_sae_reports()
        drugs = {r.study_drug for r in reports}
        assert "aflibercept" in drugs
        assert "dupilumab" in drugs
        assert "cemiplimab" in drugs

    def test_seed_causality_records_count(self, svc: SAEReportingService):
        records = svc.list_causality_records()
        assert len(records) == 10

    def test_seed_causality_assessments(self, svc: SAEReportingService):
        records = svc.list_causality_records()
        assessments = {c.assessment for c in records}
        assert CausalityAssessment.RELATED in assessments
        assert CausalityAssessment.POSSIBLY_RELATED in assessments
        assert CausalityAssessment.UNLIKELY_RELATED in assessments
        assert CausalityAssessment.NOT_RELATED in assessments

    def test_seed_regulatory_submissions_count(self, svc: SAEReportingService):
        submissions = svc.list_regulatory_submissions()
        assert len(submissions) == 12

    def test_seed_regulatory_authorities(self, svc: SAEReportingService):
        submissions = svc.list_regulatory_submissions()
        authorities = {s.authority for s in submissions}
        assert RegulatoryAuthority.FDA in authorities
        assert RegulatoryAuthority.EMA in authorities
        assert RegulatoryAuthority.MHRA in authorities
        assert RegulatoryAuthority.HEALTH_CANADA in authorities
        assert RegulatoryAuthority.PMDA in authorities

    def test_seed_causality_embedded_in_report(self, svc: SAEReportingService):
        report = svc.get_sae_report("SAE-001")
        assert report is not None
        assert len(report.causality_records) >= 2

    def test_seed_submissions_embedded_in_report(self, svc: SAEReportingService):
        report = svc.get_sae_report("SAE-001")
        assert report is not None
        assert len(report.regulatory_submissions) >= 2

    def test_seed_narratives(self, svc: SAEReportingService):
        narrative = svc.get_narrative("SAE-001")
        assert narrative is not None
        assert len(narrative.initial_narrative) > 50
        assert len(narrative.follow_up_narratives) >= 1
        assert len(narrative.medical_review_notes) >= 1

    def test_seed_narrative_embedded_in_report(self, svc: SAEReportingService):
        report = svc.get_sae_report("SAE-003")
        assert report is not None
        assert report.narrative is not None
        assert len(report.narrative.initial_narrative) > 50

    def test_seed_reporting_timelines(self, svc: SAEReportingService):
        reports = svc.list_sae_reports()
        timelines = {r.reporting_timeline for r in reports}
        assert ReportingTimeline.SEVEN_DAY in timelines
        assert ReportingTimeline.FIFTEEN_DAY in timelines

    def test_seed_seven_day_for_death(self, svc: SAEReportingService):
        report = svc.get_sae_report("SAE-006")  # Fatal pneumonitis
        assert report is not None
        assert report.seriousness == SAESeriousness.DEATH
        assert report.reporting_timeline == ReportingTimeline.SEVEN_DAY

    def test_seed_seven_day_for_life_threatening(self, svc: SAEReportingService):
        report = svc.get_sae_report("SAE-003")  # Anaphylaxis
        assert report is not None
        assert report.seriousness == SAESeriousness.LIFE_THREATENING
        assert report.reporting_timeline == ReportingTimeline.SEVEN_DAY


# =====================================================================
# SAE REPORT CRUD
# =====================================================================


class TestSAEReportCrud:
    """Test SAE report create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_reports(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_reports_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_reports_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"status": "submitted"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "submitted"

    @pytest.mark.anyio
    async def test_list_reports_filter_seriousness(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"seriousness": "death"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["seriousness"] == "death"

    @pytest.mark.anyio
    async def test_list_reports_filter_study_drug(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"study_drug": "cemiplimab"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["study_drug"] == "cemiplimab"

    @pytest.mark.anyio
    async def test_get_report(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SAE-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["study_drug"] == "aflibercept"
        assert data["event_term"] == "Retinal detachment"

    @pytest.mark.anyio
    async def test_get_report_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_report(self, client: AsyncClient):
        payload = _make_sae_report_create()
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SAE-")
        assert data["status"] == "draft"
        assert data["report_type"] == "initial"
        assert data["study_drug"] == "aflibercept"
        assert data["reporting_timeline"] == "fifteen_day"

    @pytest.mark.anyio
    async def test_create_report_death_gets_seven_day(self, client: AsyncClient):
        payload = _make_sae_report_create(seriousness="death", outcome="fatal")
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reporting_timeline"] == "seven_day"

    @pytest.mark.anyio
    async def test_create_report_life_threatening_gets_seven_day(self, client: AsyncClient):
        payload = _make_sae_report_create(seriousness="life_threatening")
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reporting_timeline"] == "seven_day"

    @pytest.mark.anyio
    async def test_create_report_has_narrative(self, client: AsyncClient):
        payload = _make_sae_report_create()
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["narrative"] is not None
        assert data["narrative"]["initial_narrative"] == payload["initial_narrative"]

    @pytest.mark.anyio
    async def test_create_report_has_deadline(self, client: AsyncClient):
        payload = _make_sae_report_create()
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reporting_deadline"] is not None

    @pytest.mark.anyio
    async def test_update_report(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/SAE-007",
            json={"outcome": "recovering", "event_description": "Updated description"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "recovering"
        assert data["event_description"] == "Updated description"

    @pytest.mark.anyio
    async def test_update_report_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/SAE-NONEXISTENT",
            json={"outcome": "recovered"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_report(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/SAE-009")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/SAE-009")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_report_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/SAE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_report_cleans_up_related_data(self, svc: SAEReportingService, client: AsyncClient):
        # Verify related data exists before deletion
        crs = svc.list_causality_records(sae_report_id="SAE-001")
        assert len(crs) >= 2
        subs = svc.list_regulatory_submissions(sae_report_id="SAE-001")
        assert len(subs) >= 2
        assert svc.get_narrative("SAE-001") is not None

        resp = await client.delete(f"{API_PREFIX}/SAE-001")
        assert resp.status_code == 204

        # Verify cleanup
        assert len(svc.list_causality_records(sae_report_id="SAE-001")) == 0
        assert len(svc.list_regulatory_submissions(sae_report_id="SAE-001")) == 0
        assert svc.get_narrative("SAE-001") is None


# =====================================================================
# SAE REPORT LIFECYCLE
# =====================================================================


class TestSAELifecycle:
    """Test SAE report lifecycle transitions."""

    @pytest.mark.anyio
    async def test_submit_for_medical_review(self, client: AsyncClient):
        # SAE-007 is draft
        resp = await client.post(f"{API_PREFIX}/SAE-007/submit-for-review")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "medical_review"

    @pytest.mark.anyio
    async def test_submit_for_review_non_draft_fails(self, client: AsyncClient):
        # SAE-001 is acknowledged
        resp = await client.post(f"{API_PREFIX}/SAE-001/submit-for-review")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_submit_for_review_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/SAE-NONEXISTENT/submit-for-review")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_approve_medical_review(self, client: AsyncClient):
        # SAE-004 is in medical_review
        resp = await client.post(f"{API_PREFIX}/SAE-004/approve-review")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"

    @pytest.mark.anyio
    async def test_approve_review_non_medical_review_fails(self, client: AsyncClient):
        # SAE-007 is draft
        resp = await client.post(f"{API_PREFIX}/SAE-007/approve-review")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_approve_review_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/SAE-NONEXISTENT/approve-review")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_close_acknowledged_report(self, client: AsyncClient):
        # SAE-001 is acknowledged
        resp = await client.post(f"{API_PREFIX}/SAE-001/close")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"

    @pytest.mark.anyio
    async def test_close_submitted_report(self, client: AsyncClient):
        # SAE-002 is submitted
        resp = await client.post(f"{API_PREFIX}/SAE-002/close")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"

    @pytest.mark.anyio
    async def test_close_draft_fails(self, client: AsyncClient):
        # SAE-007 is draft
        resp = await client.post(f"{API_PREFIX}/SAE-007/close")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_close_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/SAE-NONEXISTENT/close")
        assert resp.status_code == 404

    def test_full_lifecycle_via_service(self, svc: SAEReportingService):
        """Test complete lifecycle: draft -> medical_review -> submitted -> acknowledged -> closed."""
        now = datetime.now(timezone.utc)

        # Create report
        report = svc.create_sae_report(SAEReportCreate(
            trial_id=EYLEA_TRIAL,
            site_id="SITE-101",
            subject_id="SUBJ-LC01",
            seriousness=SAESeriousness.HOSPITALIZATION,
            outcome=SAEOutcome.RECOVERING,
            event_description="Lifecycle test event",
            event_term="Test event",
            study_drug="aflibercept",
            onset_date=now - timedelta(days=2),
            awareness_date=now - timedelta(days=1),
            initial_narrative="Patient developed test event.",
        ))
        assert report.status == SAEStatus.DRAFT

        # Submit for medical review
        report = svc.submit_for_medical_review(report.id)
        assert report is not None
        assert report.status == SAEStatus.MEDICAL_REVIEW

        # Approve medical review -> submitted
        report = svc.approve_medical_review(report.id)
        assert report is not None
        assert report.status == SAEStatus.SUBMITTED

        # Submit to authority
        sub = svc.submit_to_authority(report.id, RegulatorySubmissionCreate(
            authority=RegulatoryAuthority.FDA,
            submission_type=ReportType.INITIAL,
            submitted_date=now,
        ))
        assert sub is not None

        # Record acknowledgment -> acknowledged
        updated_sub = svc.record_acknowledgment(sub.id, "FDA-TEST-001", now)
        assert updated_sub is not None
        assert updated_sub.acknowledgment_number == "FDA-TEST-001"

        # Verify report moved to acknowledged
        report = svc.get_sae_report(report.id)
        assert report is not None
        assert report.status == SAEStatus.ACKNOWLEDGED

        # Close
        report = svc.close_report(report.id)
        assert report is not None
        assert report.status == SAEStatus.CLOSED

    def test_close_already_closed_fails(self, svc: SAEReportingService):
        # SAE-005 is closed
        with pytest.raises(ValueError):
            svc.close_report("SAE-005")


# =====================================================================
# CAUSALITY ASSESSMENT
# =====================================================================


class TestCausalityAssessment:
    """Test causality assessment operations."""

    @pytest.mark.anyio
    async def test_list_causality_records_for_report(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-001/causality-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["sae_report_id"] == "SAE-001"

    @pytest.mark.anyio
    async def test_get_causality_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/causality-records/CR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CR-001"
        assert data["assessment"] == "unlikely_related"

    @pytest.mark.anyio
    async def test_get_causality_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/causality-records/CR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_causality_record(self, client: AsyncClient):
        payload = _make_causality_create()
        resp = await client.post(f"{API_PREFIX}/SAE-007/causality-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["sae_report_id"] == "SAE-007"
        assert data["assessment"] == "possibly_related"
        assert data["id"].startswith("CR-")

    @pytest.mark.anyio
    async def test_create_causality_invalid_report(self, client: AsyncClient):
        payload = _make_causality_create()
        resp = await client.post(f"{API_PREFIX}/SAE-NONEXISTENT/causality-records", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_causality_related(self, client: AsyncClient):
        payload = _make_causality_create(
            assessor="Sponsor Medical Monitor",
            assessment="related",
            rationale="Clear causal relationship established",
        )
        resp = await client.post(f"{API_PREFIX}/SAE-007/causality-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["assessment"] == "related"

    @pytest.mark.anyio
    async def test_create_causality_not_assessable(self, client: AsyncClient):
        payload = _make_causality_create(
            assessment="not_assessable",
            rationale="Insufficient information available",
        )
        resp = await client.post(f"{API_PREFIX}/SAE-009/causality-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["assessment"] == "not_assessable"

    def test_causality_embedded_in_report_after_create(self, svc: SAEReportingService):
        initial_count = len(svc.get_sae_report("SAE-007").causality_records) if svc.get_sae_report("SAE-007") else 0
        svc.create_causality_record("SAE-007", CausalityRecordCreate(
            assessor="Test Assessor",
            assessment=CausalityAssessment.POSSIBLY_RELATED,
            rationale="Test rationale",
        ))
        report = svc.get_sae_report("SAE-007")
        assert report is not None
        assert len(report.causality_records) == initial_count + 1

    def test_multiple_causality_assessments(self, svc: SAEReportingService):
        # SAE-006 has 2 assessments (both related)
        records = svc.list_causality_records(sae_report_id="SAE-006")
        assert len(records) == 2
        for r in records:
            assert r.assessment == CausalityAssessment.RELATED

    def test_all_causality_assessments_represented(self, svc: SAEReportingService):
        records = svc.list_causality_records()
        assessments = {c.assessment for c in records}
        assert CausalityAssessment.RELATED in assessments
        assert CausalityAssessment.POSSIBLY_RELATED in assessments
        assert CausalityAssessment.UNLIKELY_RELATED in assessments
        assert CausalityAssessment.NOT_RELATED in assessments


# =====================================================================
# REGULATORY SUBMISSION
# =====================================================================


class TestRegulatorySubmission:
    """Test regulatory submission operations."""

    @pytest.mark.anyio
    async def test_list_regulatory_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-001/regulatory-submissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["sae_report_id"] == "SAE-001"

    @pytest.mark.anyio
    async def test_list_submissions_filter_authority(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/SAE-006/regulatory-submissions",
            params={"authority": "fda"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["authority"] == "fda"

    @pytest.mark.anyio
    async def test_get_regulatory_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/regulatory-submissions/RS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RS-001"
        assert data["authority"] == "fda"
        assert data["acknowledgment_number"] is not None

    @pytest.mark.anyio
    async def test_get_submission_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/regulatory-submissions/RS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_submit_to_authority(self, client: AsyncClient):
        # SAE-002 is submitted
        payload = _make_regulatory_submission_create()
        resp = await client.post(f"{API_PREFIX}/SAE-002/regulatory-submissions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["authority"] == "fda"
        assert data["sae_report_id"] == "SAE-002"
        assert data["id"].startswith("RS-")

    @pytest.mark.anyio
    async def test_submit_to_authority_draft_fails(self, client: AsyncClient):
        # SAE-007 is draft, cannot submit to authority
        payload = _make_regulatory_submission_create()
        resp = await client.post(f"{API_PREFIX}/SAE-007/regulatory-submissions", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_submit_to_authority_not_found(self, client: AsyncClient):
        payload = _make_regulatory_submission_create()
        resp = await client.post(f"{API_PREFIX}/SAE-NONEXISTENT/regulatory-submissions", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_record_acknowledgment(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/regulatory-submissions/RS-003/acknowledge",
            json={
                "acknowledgment_number": "FDA-TEST-ACK-001",
                "acknowledgment_date": now.isoformat(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledgment_number"] == "FDA-TEST-ACK-001"
        assert data["acknowledgment_date"] is not None

    @pytest.mark.anyio
    async def test_record_acknowledgment_not_found(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/regulatory-submissions/RS-NONEXISTENT/acknowledge",
            json={
                "acknowledgment_number": "TEST",
                "acknowledgment_date": now.isoformat(),
            },
        )
        assert resp.status_code == 404

    def test_acknowledged_submissions_have_numbers(self, svc: SAEReportingService):
        sub = svc.get_regulatory_submission("RS-001")
        assert sub is not None
        assert sub.acknowledgment_number is not None
        assert sub.acknowledgment_date is not None

    def test_pending_submission_no_acknowledgment(self, svc: SAEReportingService):
        sub = svc.get_regulatory_submission("RS-003")
        assert sub is not None
        assert sub.acknowledgment_number is None
        assert sub.acknowledgment_date is None

    def test_submission_across_multiple_authorities(self, svc: SAEReportingService):
        # SAE-006 submitted to FDA, EMA, MHRA
        subs = svc.list_regulatory_submissions(sae_report_id="SAE-006")
        authorities = {s.authority for s in subs}
        assert len(authorities) >= 3


# =====================================================================
# REPORTING DEADLINES
# =====================================================================


class TestReportingDeadlines:
    """Test reporting deadline enforcement."""

    @pytest.mark.anyio
    async def test_get_overdue_reports(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/overdue")
        assert resp.status_code == 200
        data = resp.json()
        # SAE-007 is draft and past deadline (awareness was 20 days ago, 15-day timeline)
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_check_deadlines(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deadlines")
        assert resp.status_code == 200
        data = resp.json()
        # Should include reports approaching deadline (within 48h) or past deadline
        assert data["total"] >= 1

    def test_overdue_report_is_sae007(self, svc: SAEReportingService):
        overdue = svc.get_overdue_reports()
        overdue_ids = {r.id for r in overdue}
        assert "SAE-007" in overdue_ids

    def test_overdue_reports_are_draft_or_medical_review(self, svc: SAEReportingService):
        overdue = svc.get_overdue_reports()
        for report in overdue:
            assert report.status in (SAEStatus.DRAFT, SAEStatus.MEDICAL_REVIEW)

    def test_submitted_report_not_overdue(self, svc: SAEReportingService):
        overdue = svc.get_overdue_reports()
        overdue_ids = {r.id for r in overdue}
        # SAE-002 is submitted, should not be overdue
        assert "SAE-002" not in overdue_ids

    def test_deadline_sorting(self, svc: SAEReportingService):
        approaching = svc.check_reporting_deadlines()
        if len(approaching) > 1:
            dates = [r.reporting_deadline for r in approaching]
            assert dates == sorted(dates)

    def test_seven_day_deadline_calculation(self, svc: SAEReportingService):
        report = svc.get_sae_report("SAE-003")  # 7-day
        assert report is not None
        expected_deadline = report.awareness_date + timedelta(days=7)
        assert abs((report.reporting_deadline - expected_deadline).total_seconds()) < 1

    def test_fifteen_day_deadline_calculation(self, svc: SAEReportingService):
        report = svc.get_sae_report("SAE-001")  # 15-day
        assert report is not None
        expected_deadline = report.awareness_date + timedelta(days=15)
        assert abs((report.reporting_deadline - expected_deadline).total_seconds()) < 1


# =====================================================================
# FORM GENERATION
# =====================================================================


class TestFormGeneration:
    """Test MedWatch and CIOMS form generation."""

    @pytest.mark.anyio
    async def test_generate_medwatch_form(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-001/medwatch")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sae_report_id"] == "SAE-001"
        assert data["form_version"] == "3500A"
        assert data["suspect_product"] == "aflibercept"
        assert data["event_term"] == "Retinal detachment"
        assert data["patient_identifier"] == "SUBJ-1001"
        assert len(data["seriousness_criteria"]) >= 1
        assert data["narrative_summary"] is not None
        assert len(data["narrative_summary"]) > 50

    @pytest.mark.anyio
    async def test_generate_medwatch_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-NONEXISTENT/medwatch")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_generate_cioms_form(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-003/cioms")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sae_report_id"] == "SAE-003"
        assert data["form_version"] == "CIOMS-I"
        assert data["suspect_drug"] == "dupilumab"
        assert data["reaction_description"] is not None
        assert data["reaction_outcome"] == "recovered"
        assert data["study_number"] == DUPIXENT_TRIAL
        assert data["sender_organization"] == "Regeneron Pharmaceuticals"
        assert len(data["narrative_summary"]) > 50

    @pytest.mark.anyio
    async def test_generate_cioms_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-NONEXISTENT/cioms")
        assert resp.status_code == 404

    def test_medwatch_form_fields(self, svc: SAEReportingService):
        form = svc.generate_medwatch_form("SAE-006")
        assert form is not None
        assert form.event_outcome == "fatal"
        assert form.suspect_product == "cemiplimab"
        assert "death" in form.seriousness_criteria
        assert form.generated_at is not None

    def test_cioms_form_fields(self, svc: SAEReportingService):
        form = svc.generate_cioms_form("SAE-005")
        assert form is not None
        assert form.suspect_drug == "cemiplimab"
        assert form.reaction_outcome == "recovered"
        assert form.reporter_country == "US"
        assert form.generated_at is not None

    def test_medwatch_without_narrative(self, svc: SAEReportingService):
        # SAE-007 has no seeded narrative
        form = svc.generate_medwatch_form("SAE-007")
        assert form is not None
        assert form.narrative_summary == ""

    def test_cioms_without_narrative(self, svc: SAEReportingService):
        form = svc.generate_cioms_form("SAE-007")
        assert form is not None
        assert form.narrative_summary == ""


# =====================================================================
# NARRATIVE MANAGEMENT
# =====================================================================


class TestNarrativeManagement:
    """Test narrative management operations."""

    @pytest.mark.anyio
    async def test_get_narrative(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-001/narrative")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sae_report_id"] == "SAE-001"
        assert len(data["initial_narrative"]) > 50
        assert len(data["follow_up_narratives"]) >= 1

    @pytest.mark.anyio
    async def test_get_narrative_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-NONEXISTENT/narrative")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_add_follow_up_narrative(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/SAE-001/narrative/follow-up",
            json={"text": "Patient continues to improve. Visual acuity 20/25."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["follow_up_narratives"]) >= 2
        assert "continues to improve" in data["follow_up_narratives"][-1]

    @pytest.mark.anyio
    async def test_add_follow_up_narrative_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/SAE-NONEXISTENT/narrative/follow-up",
            json={"text": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_add_medical_review_note(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/SAE-003/narrative/medical-review",
            json={"text": "Reviewed by safety committee. No protocol changes required."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["medical_review_notes"]) >= 3
        assert "safety committee" in data["medical_review_notes"][-1]

    @pytest.mark.anyio
    async def test_add_medical_review_note_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/SAE-NONEXISTENT/narrative/medical-review",
            json={"text": "Test"},
        )
        assert resp.status_code == 404

    def test_narrative_follow_up_updates_report(self, svc: SAEReportingService):
        svc.add_follow_up_narrative("SAE-005", "Final follow-up note.")
        report = svc.get_sae_report("SAE-005")
        assert report is not None
        assert report.narrative is not None
        assert "Final follow-up note." in report.narrative.follow_up_narratives

    def test_narrative_medical_review_updates_report(self, svc: SAEReportingService):
        svc.add_medical_review_note("SAE-001", "Additional review note.")
        report = svc.get_sae_report("SAE-001")
        assert report is not None
        assert report.narrative is not None
        assert "Additional review note." in report.narrative.medical_review_notes

    def test_narrative_has_detailed_content(self, svc: SAEReportingService):
        narrative = svc.get_narrative("SAE-006")
        assert narrative is not None
        # Fatal pneumonitis narrative should be detailed
        assert len(narrative.initial_narrative) > 100
        assert len(narrative.follow_up_narratives) >= 1
        assert len(narrative.medical_review_notes) >= 2


# =====================================================================
# FOLLOW-UP AND FINAL REPORTS
# =====================================================================


class TestFollowUpAndFinalReports:
    """Test follow-up and final report creation."""

    @pytest.mark.anyio
    async def test_create_follow_up_report(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = _make_sae_report_create(
            event_description="Follow-up: Patient condition improving",
            initial_narrative="Follow-up narrative for ongoing event.",
        )
        resp = await client.post(f"{API_PREFIX}/SAE-001/follow-up", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["report_type"] == "follow_up"
        assert data["parent_report_id"] == "SAE-001"
        assert data["status"] == "draft"

    @pytest.mark.anyio
    async def test_create_follow_up_invalid_parent(self, client: AsyncClient):
        payload = _make_sae_report_create()
        resp = await client.post(f"{API_PREFIX}/SAE-NONEXISTENT/follow-up", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_final_report(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = _make_sae_report_create(
            outcome="recovered",
            event_description="Final: Patient fully recovered",
            initial_narrative="Final narrative. Event has resolved completely.",
        )
        resp = await client.post(f"{API_PREFIX}/SAE-001/final", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["report_type"] == "final"
        assert data["parent_report_id"] == "SAE-001"

    @pytest.mark.anyio
    async def test_create_final_invalid_parent(self, client: AsyncClient):
        payload = _make_sae_report_create()
        resp = await client.post(f"{API_PREFIX}/SAE-NONEXISTENT/final", json=payload)
        assert resp.status_code == 400

    def test_follow_up_inherits_parent_timeline(self, svc: SAEReportingService):
        now = datetime.now(timezone.utc)
        parent = svc.get_sae_report("SAE-003")  # 7-day timeline
        assert parent is not None
        assert parent.reporting_timeline == ReportingTimeline.SEVEN_DAY

        follow_up = svc.create_follow_up_report("SAE-003", SAEReportCreate(
            trial_id=DUPIXENT_TRIAL,
            site_id="SITE-103",
            subject_id="SUBJ-2015",
            seriousness=SAESeriousness.LIFE_THREATENING,
            outcome=SAEOutcome.RECOVERED,
            event_description="Follow-up for anaphylaxis",
            event_term="Anaphylactic reaction",
            study_drug="dupilumab",
            onset_date=now - timedelta(days=2),
            awareness_date=now,
            initial_narrative="Follow-up narrative.",
        ))
        assert follow_up.reporting_timeline == ReportingTimeline.SEVEN_DAY
        assert follow_up.report_type == ReportType.FOLLOW_UP
        assert follow_up.parent_report_id == "SAE-003"

    def test_final_report_type(self, svc: SAEReportingService):
        now = datetime.now(timezone.utc)
        final = svc.create_final_report("SAE-001", SAEReportCreate(
            trial_id=EYLEA_TRIAL,
            site_id="SITE-101",
            subject_id="SUBJ-1001",
            seriousness=SAESeriousness.HOSPITALIZATION,
            outcome=SAEOutcome.RECOVERED,
            event_description="Final report",
            event_term="Retinal detachment",
            study_drug="aflibercept",
            onset_date=now - timedelta(days=60),
            awareness_date=now,
            initial_narrative="Final report narrative.",
        ))
        assert final.report_type == ReportType.FINAL
        assert final.parent_report_id == "SAE-001"


# =====================================================================
# SAE METRICS
# =====================================================================


class TestSAEMetrics:
    """Test SAE metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_saes"] == 10
        assert data["total_submissions"] == 12
        assert data["avg_reporting_time_hours"] > 0
        assert data["overdue_reports"] >= 1

    def test_metrics_by_seriousness(self, svc: SAEReportingService):
        metrics = svc.get_sae_metrics()
        total_by_seriousness = sum(metrics.by_seriousness.values())
        assert total_by_seriousness == metrics.total_saes

    def test_metrics_by_status(self, svc: SAEReportingService):
        metrics = svc.get_sae_metrics()
        total_by_status = sum(metrics.by_status.values())
        assert total_by_status == metrics.total_saes

    def test_metrics_by_causality(self, svc: SAEReportingService):
        metrics = svc.get_sae_metrics()
        # Should have multiple causality categories
        assert len(metrics.by_causality) >= 3

    def test_metrics_submissions_by_authority(self, svc: SAEReportingService):
        metrics = svc.get_sae_metrics()
        total_by_authority = sum(metrics.submissions_by_authority.values())
        assert total_by_authority == metrics.total_submissions
        assert "fda" in metrics.submissions_by_authority

    def test_metrics_overdue_count(self, svc: SAEReportingService):
        metrics = svc.get_sae_metrics()
        overdue_list = svc.get_overdue_reports()
        assert metrics.overdue_reports == len(overdue_list)


# =====================================================================
# TRIAL SAFETY SUMMARY
# =====================================================================


class TestTrialSafetySummary:
    """Test trial safety summary."""

    @pytest.mark.anyio
    async def test_get_trial_safety_summary_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trial/{EYLEA_TRIAL}/safety-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["total_saes"] == 3

    @pytest.mark.anyio
    async def test_get_trial_safety_summary_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trial/{LIBTAYO_TRIAL}/safety-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_saes"] == 4

    @pytest.mark.anyio
    async def test_get_trial_safety_summary_empty(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trial/nonexistent-trial/safety-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_saes"] == 0
        assert data["overdue_reports"] == 0

    def test_trial_summary_by_seriousness(self, svc: SAEReportingService):
        summary = svc.get_trial_safety_summary(LIBTAYO_TRIAL)
        total = sum(summary.by_seriousness.values())
        assert total == summary.total_saes

    def test_trial_summary_by_outcome(self, svc: SAEReportingService):
        summary = svc.get_trial_safety_summary(LIBTAYO_TRIAL)
        total = sum(summary.by_outcome.values())
        assert total == summary.total_saes

    def test_trial_summary_by_status(self, svc: SAEReportingService):
        summary = svc.get_trial_safety_summary(DUPIXENT_TRIAL)
        total = sum(summary.by_status.values())
        assert total == summary.total_saes

    def test_trial_summary_recent_saes(self, svc: SAEReportingService):
        summary = svc.get_trial_safety_summary(LIBTAYO_TRIAL)
        assert len(summary.recent_saes) <= 5
        assert len(summary.recent_saes) > 0

    def test_trial_summary_overdue_count(self, svc: SAEReportingService):
        summary = svc.get_trial_safety_summary(LIBTAYO_TRIAL)
        # SAE-007 is overdue in LIBTAYO trial
        assert summary.overdue_reports >= 1


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_sae_reporting_service()
        svc2 = get_sae_reporting_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_sae_reporting_service()
        svc2 = reset_sae_reporting_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_sae_reporting_service()
        svc.delete_sae_report("SAE-001")
        assert svc.get_sae_report("SAE-001") is None
        svc2 = reset_sae_reporting_service()
        assert svc2.get_sae_report("SAE-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_reports_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_reports_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_reports_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/",
            params={"trial_id": LIBTAYO_TRIAL, "status": "closed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL
            assert item["status"] == "closed"

    @pytest.mark.anyio
    async def test_reports_sorted_by_created_at(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        data = resp.json()
        dates = [item["created_at"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_create_report_minimal(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "trial_id": EYLEA_TRIAL,
            "site_id": "SITE-101",
            "subject_id": "SUBJ-MIN",
            "seriousness": "hospitalization",
            "outcome": "unknown",
            "event_description": "Minimal event",
            "event_term": "Minimal",
            "study_drug": "aflibercept",
            "onset_date": now.isoformat(),
            "awareness_date": now.isoformat(),
            "initial_narrative": "Minimal narrative.",
        }
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_update_seriousness(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/SAE-007",
            json={"seriousness": "life_threatening"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["seriousness"] == "life_threatening"

    @pytest.mark.anyio
    async def test_update_event_term(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/SAE-004",
            json={"event_term": "Eczema herpeticum disseminated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_term"] == "Eczema herpeticum disseminated"

    def test_empty_causality_list_for_report(self, svc: SAEReportingService):
        # SAE-009 has no causality records
        records = svc.list_causality_records(sae_report_id="SAE-009")
        assert len(records) == 0

    def test_empty_submission_list_for_report(self, svc: SAEReportingService):
        # SAE-007 has no submissions (draft)
        subs = svc.list_regulatory_submissions(sae_report_id="SAE-007")
        assert len(subs) == 0

    def test_get_narrative_for_no_narrative_report(self, svc: SAEReportingService):
        # SAE-007 has no seeded narrative
        narrative = svc.get_narrative("SAE-007")
        assert narrative is None


# =====================================================================
# REPORT DETAILS AND CONTENT VALIDATION
# =====================================================================


class TestReportDetails:
    """Test report content and field validation."""

    @pytest.mark.anyio
    async def test_fatal_report_has_death_seriousness(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-006")
        data = resp.json()
        assert data["seriousness"] == "death"
        assert data["outcome"] == "fatal"

    @pytest.mark.anyio
    async def test_report_has_event_term(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-003")
        data = resp.json()
        assert data["event_term"] == "Anaphylactic reaction"

    @pytest.mark.anyio
    async def test_report_has_study_drug(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-003")
        data = resp.json()
        assert data["study_drug"] == "dupilumab"

    @pytest.mark.anyio
    async def test_report_has_dates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-001")
        data = resp.json()
        assert data["onset_date"] is not None
        assert data["awareness_date"] is not None
        assert data["reporting_deadline"] is not None

    @pytest.mark.anyio
    async def test_report_has_site_and_subject(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-001")
        data = resp.json()
        assert data["site_id"] == "SITE-101"
        assert data["subject_id"] == "SUBJ-1001"

    @pytest.mark.anyio
    async def test_closed_report_is_final(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-005")
        data = resp.json()
        assert data["status"] == "closed"
        assert data["report_type"] == "final"

    @pytest.mark.anyio
    async def test_report_description_is_detailed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-006")
        data = resp.json()
        assert len(data["event_description"]) > 100

    def test_report_types_in_seed_data(self, svc: SAEReportingService):
        reports = svc.list_sae_reports()
        types = {r.report_type for r in reports}
        assert ReportType.INITIAL in types
        assert ReportType.FINAL in types


# =====================================================================
# ENUMERATION VALUES
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout."""

    @pytest.mark.anyio
    async def test_seriousness_values_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        data = resp.json()
        valid_values = {"death", "life_threatening", "hospitalization", "disability", "congenital_anomaly", "important_medical_event"}
        for item in data["items"]:
            assert item["seriousness"] in valid_values

    @pytest.mark.anyio
    async def test_outcome_values_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        data = resp.json()
        valid_values = {"recovered", "recovering", "not_recovered", "fatal", "unknown"}
        for item in data["items"]:
            assert item["outcome"] in valid_values

    @pytest.mark.anyio
    async def test_status_values_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        data = resp.json()
        valid_values = {"draft", "medical_review", "submitted", "acknowledged", "closed"}
        for item in data["items"]:
            assert item["status"] in valid_values

    @pytest.mark.anyio
    async def test_report_type_values(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        data = resp.json()
        valid_values = {"initial", "follow_up", "final"}
        for item in data["items"]:
            assert item["report_type"] in valid_values

    @pytest.mark.anyio
    async def test_timeline_values(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        data = resp.json()
        valid_values = {"seven_day", "fifteen_day", "thirty_day"}
        for item in data["items"]:
            assert item["reporting_timeline"] in valid_values

    @pytest.mark.anyio
    async def test_authority_values_in_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-006/regulatory-submissions")
        data = resp.json()
        valid_values = {"fda", "ema", "mhra", "pmda", "health_canada"}
        for item in data["items"]:
            assert item["authority"] in valid_values

    @pytest.mark.anyio
    async def test_causality_values_in_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/SAE-001/causality-records")
        data = resp.json()
        valid_values = {"related", "possibly_related", "unlikely_related", "not_related", "not_assessable"}
        for item in data["items"]:
            assert item["assessment"] in valid_values


# =====================================================================
# CROSS-REPORT ANALYSIS
# =====================================================================


class TestCrossReportAnalysis:
    """Test cross-report and cross-trial analysis."""

    def test_reports_across_multiple_trials(self, svc: SAEReportingService):
        reports = svc.list_sae_reports()
        trial_ids = {r.trial_id for r in reports}
        assert len(trial_ids) >= 3

    def test_multiple_drugs_represented(self, svc: SAEReportingService):
        reports = svc.list_sae_reports()
        drugs = {r.study_drug for r in reports}
        assert len(drugs) >= 3

    def test_submissions_across_reports(self, svc: SAEReportingService):
        submissions = svc.list_regulatory_submissions()
        report_ids = {s.sae_report_id for s in submissions}
        assert len(report_ids) >= 5

    def test_causality_across_reports(self, svc: SAEReportingService):
        records = svc.list_causality_records()
        report_ids = {c.sae_report_id for c in records}
        assert len(report_ids) >= 5

    def test_related_causality_count(self, svc: SAEReportingService):
        records = svc.list_causality_records()
        related_count = sum(1 for c in records if c.assessment == CausalityAssessment.RELATED)
        assert related_count >= 4

    def test_total_authorities_submitted_to(self, svc: SAEReportingService):
        submissions = svc.list_regulatory_submissions()
        authorities = {s.authority for s in submissions}
        assert len(authorities) >= 5  # FDA, EMA, MHRA, PMDA, Health Canada

    def test_acknowledged_submissions_count(self, svc: SAEReportingService):
        submissions = svc.list_regulatory_submissions()
        acknowledged = [s for s in submissions if s.acknowledgment_number is not None]
        assert len(acknowledged) >= 8

    def test_pending_submissions_count(self, svc: SAEReportingService):
        submissions = svc.list_regulatory_submissions()
        pending = [s for s in submissions if s.acknowledgment_number is None]
        assert len(pending) >= 2
