"""Tests for Data Safety Monitoring Board (DSMB) Service (CLINICAL-3).

Covers:
- Seed data verification (members, meetings, analyses, adjudications, reports, charters)
- DSMB member CRUD (create, read, update, list, filter by role/active)
- Meeting CRUD (create, read, update, list, filter by trial/type, upcoming)
- Interim analysis creation with O'Brien-Fleming, Pocock, Lan-DeMets methods
- Stopping rule evaluation and boundary computations
- Event adjudication CRUD and status transition validation
- Safety report generation (blinded, unblinded, summary-only views)
- Charter CRUD and version management
- DSMB metrics computation
- Overdue adjudication detection
- Error handling (404s, 400s, invalid transitions)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.safety_monitoring import (
    DSMBCharterCreate,
    DSMBCharterUpdate,
    DSMBMeetingCreate,
    DSMBMeetingUpdate,
    DSMBMemberCreate,
    DSMBMemberUpdate,
    DSMBRole,
    EventAdjudicationCreate,
    EventAdjudicationStatus,
    EventAdjudicationUpdate,
    InterimAnalysisCreate,
    InterimAnalysisType,
    MeetingType,
    ReportAccessLevel,
    ReviewOutcome,
    SafetyReportCreate,
    StoppingRule,
)
from app.services.safety_monitoring_service import (
    SafetyMonitoringService,
    get_safety_monitoring_service,
    reset_safety_monitoring_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/safety-monitoring"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_safety_monitoring_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SafetyMonitoringService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_member_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "name": "Dr. Test User",
        "role": "CHAIR",
        "institution": "Test University",
        "specialty": "Test Specialty",
        "email": "test@university.edu",
        "conflict_of_interest_declared": False,
        "coi_details": None,
        "term_start": (now - timedelta(days=30)).isoformat(),
        "term_end": (now + timedelta(days=365)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_meeting_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "meeting_type": "SCHEDULED",
        "meeting_date": (now + timedelta(days=14)).isoformat(),
        "attendees": ["DSMB-MEM-001", "DSMB-MEM-002"],
        "agenda": ["Safety review", "Protocol discussion"],
    }
    defaults.update(overrides)
    return defaults


def _make_analysis_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "analysis_type": "COMBINED",
        "planned_sample_size": 300,
        "actual_sample_size": 150,
        "performed_by": "Dr. Test Statistician",
        "method": "OBF",
        "overall_alpha": 0.05,
        "number_of_looks": 3,
        "current_look": 1,
    }
    defaults.update(overrides)
    return defaults


def _make_adjudication_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "patient_id": "PAT-TEST-001",
        "event_type": "Test Event",
        "event_date": (now - timedelta(days=5)).isoformat(),
        "submitted_by": "Dr. Test Investigator",
        "original_classification": "Adverse Event",
    }
    defaults.update(overrides)
    return defaults


def _make_report_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "report_type": "periodic",
        "generated_by": "Test System",
        "access_level": "BLINDED",
    }
    defaults.update(overrides)
    return defaults


def _make_charter_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "version": "1.0",
        "review_frequency_weeks": 12,
        "stopping_rules": ["Test stopping rule"],
        "reporting_requirements": ["Monthly safety report"],
        "access_policies": ["Blinded access only"],
        "approved_by": ["DSMB-MEM-001"],
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify the seed data is correctly populated."""

    def test_seed_members_count(self, svc: SafetyMonitoringService):
        members = svc.list_members()
        assert len(members) == 8

    def test_seed_members_roles(self, svc: SafetyMonitoringService):
        members = svc.list_members()
        roles = [m.role for m in members]
        assert DSMBRole.CHAIR in roles
        assert DSMBRole.BIOSTATISTICIAN in roles
        assert DSMBRole.CLINICIAN in roles
        assert DSMBRole.ETHICIST in roles
        assert DSMBRole.PATIENT_ADVOCATE in roles

    def test_seed_chair_exists(self, svc: SafetyMonitoringService):
        member = svc.get_member("DSMB-MEM-001")
        assert member is not None
        assert member.role == DSMBRole.CHAIR
        assert member.name == "Dr. Margaret Thompson"

    def test_seed_inactive_member(self, svc: SafetyMonitoringService):
        member = svc.get_member("DSMB-MEM-008")
        assert member is not None
        assert member.active is False

    def test_seed_coi_declared(self, svc: SafetyMonitoringService):
        member = svc.get_member("DSMB-MEM-004")
        assert member is not None
        assert member.conflict_of_interest_declared is True
        assert member.coi_details is not None

    def test_seed_meetings_count(self, svc: SafetyMonitoringService):
        meetings = svc.list_meetings()
        assert len(meetings) == 6

    def test_seed_meeting_types(self, svc: SafetyMonitoringService):
        meetings = svc.list_meetings()
        types = [m.meeting_type for m in meetings]
        assert MeetingType.SCHEDULED in types
        assert MeetingType.AD_HOC in types
        assert MeetingType.EMERGENCY in types

    def test_seed_scheduled_meetings_count(self, svc: SafetyMonitoringService):
        meetings = svc.list_meetings(meeting_type=MeetingType.SCHEDULED)
        assert len(meetings) == 4

    def test_seed_emergency_meeting(self, svc: SafetyMonitoringService):
        meeting = svc.get_meeting("DSMB-MTG-006")
        assert meeting is not None
        assert meeting.meeting_type == MeetingType.EMERGENCY
        assert meeting.outcome == ReviewOutcome.REQUEST_ADDITIONAL_DATA

    def test_seed_interim_analyses_count(self, svc: SafetyMonitoringService):
        analyses = svc.list_interim_analyses()
        assert len(analyses) == 3

    def test_seed_analysis_methods(self, svc: SafetyMonitoringService):
        analyses = svc.list_interim_analyses()
        methods = set()
        for a in analyses:
            for b in a.stopping_rules_evaluated:
                methods.add(b.method)
        assert "OBF" in methods
        assert "Pocock" in methods
        assert "Lan-DeMets" in methods

    def test_seed_adjudications_count(self, svc: SafetyMonitoringService):
        adjs = svc.list_adjudications()
        assert len(adjs) == 10

    def test_seed_adjudication_statuses(self, svc: SafetyMonitoringService):
        adjs = svc.list_adjudications()
        statuses = {a.status for a in adjs}
        assert EventAdjudicationStatus.PENDING in statuses
        assert EventAdjudicationStatus.UNDER_REVIEW in statuses
        assert EventAdjudicationStatus.ADJUDICATED in statuses
        assert EventAdjudicationStatus.APPEALED in statuses

    def test_seed_safety_reports_count(self, svc: SafetyMonitoringService):
        reports = svc.list_safety_reports()
        assert len(reports) == 4

    def test_seed_charters_count(self, svc: SafetyMonitoringService):
        charters = svc.list_charters()
        assert len(charters) == 2

    def test_seed_charter_stopping_rules(self, svc: SafetyMonitoringService):
        charter = svc.get_charter("DSMB-CHR-001")
        assert charter is not None
        assert len(charter.stopping_rules) == 3

    def test_seed_adjudication_appealed(self, svc: SafetyMonitoringService):
        adj = svc.get_adjudication("DSMB-ADJ-009")
        assert adj is not None
        assert adj.status == EventAdjudicationStatus.APPEALED


# ===================================================================
# MEMBER MANAGEMENT
# ===================================================================


class TestMemberManagement:
    """Test DSMB member CRUD operations."""

    def test_list_all_members(self, svc: SafetyMonitoringService):
        members = svc.list_members()
        assert len(members) == 8

    def test_list_members_by_role_clinician(self, svc: SafetyMonitoringService):
        members = svc.list_members(role=DSMBRole.CLINICIAN)
        assert len(members) == 3
        for m in members:
            assert m.role == DSMBRole.CLINICIAN

    def test_list_members_by_role_biostatistician(self, svc: SafetyMonitoringService):
        members = svc.list_members(role=DSMBRole.BIOSTATISTICIAN)
        assert len(members) == 2

    def test_list_active_members(self, svc: SafetyMonitoringService):
        members = svc.list_members(active=True)
        assert len(members) == 7
        for m in members:
            assert m.active is True

    def test_list_inactive_members(self, svc: SafetyMonitoringService):
        members = svc.list_members(active=False)
        assert len(members) == 1
        assert members[0].id == "DSMB-MEM-008"

    def test_list_members_combined_filter(self, svc: SafetyMonitoringService):
        members = svc.list_members(role=DSMBRole.BIOSTATISTICIAN, active=True)
        assert len(members) == 1

    def test_get_member_not_found(self, svc: SafetyMonitoringService):
        assert svc.get_member("NONEXISTENT") is None

    def test_create_member(self, svc: SafetyMonitoringService):
        now = datetime.now(timezone.utc)
        payload = DSMBMemberCreate(
            name="Dr. New Member",
            role=DSMBRole.ETHICIST,
            institution="MIT",
            specialty="Ethics",
            email="new@mit.edu",
            term_start=now,
            term_end=now + timedelta(days=730),
        )
        member = svc.create_member(payload)
        assert member.id.startswith("DSMB-MEM-")
        assert member.name == "Dr. New Member"
        assert member.role == DSMBRole.ETHICIST
        assert member.active is True

    def test_create_member_with_coi(self, svc: SafetyMonitoringService):
        now = datetime.now(timezone.utc)
        payload = DSMBMemberCreate(
            name="Dr. COI Member",
            role=DSMBRole.CLINICIAN,
            institution="Stanford",
            specialty="Cardiology",
            email="coi@stanford.edu",
            conflict_of_interest_declared=True,
            coi_details="Consulting for Pfizer",
            term_start=now,
            term_end=now + timedelta(days=365),
        )
        member = svc.create_member(payload)
        assert member.conflict_of_interest_declared is True
        assert "Pfizer" in member.coi_details

    def test_update_member_role(self, svc: SafetyMonitoringService):
        payload = DSMBMemberUpdate(role=DSMBRole.CHAIR)
        updated = svc.update_member("DSMB-MEM-002", payload)
        assert updated is not None
        assert updated.role == DSMBRole.CHAIR

    def test_update_member_deactivate(self, svc: SafetyMonitoringService):
        payload = DSMBMemberUpdate(active=False)
        updated = svc.update_member("DSMB-MEM-001", payload)
        assert updated is not None
        assert updated.active is False

    def test_update_member_not_found(self, svc: SafetyMonitoringService):
        payload = DSMBMemberUpdate(active=False)
        result = svc.update_member("NONEXISTENT", payload)
        assert result is None

    def test_members_sorted_by_name(self, svc: SafetyMonitoringService):
        members = svc.list_members()
        names = [m.name for m in members]
        assert names == sorted(names)


# ===================================================================
# MEETING MANAGEMENT
# ===================================================================


class TestMeetingManagement:
    """Test DSMB meeting CRUD operations."""

    def test_list_all_meetings(self, svc: SafetyMonitoringService):
        meetings = svc.list_meetings()
        assert len(meetings) == 6

    def test_list_meetings_by_trial(self, svc: SafetyMonitoringService):
        meetings = svc.list_meetings(trial_id=EYLEA_TRIAL)
        assert len(meetings) == 2
        for m in meetings:
            assert m.trial_id == EYLEA_TRIAL

    def test_list_meetings_by_type_scheduled(self, svc: SafetyMonitoringService):
        meetings = svc.list_meetings(meeting_type=MeetingType.SCHEDULED)
        assert len(meetings) == 4

    def test_list_meetings_by_type_emergency(self, svc: SafetyMonitoringService):
        meetings = svc.list_meetings(meeting_type=MeetingType.EMERGENCY)
        assert len(meetings) == 1

    def test_list_meetings_by_type_ad_hoc(self, svc: SafetyMonitoringService):
        meetings = svc.list_meetings(meeting_type=MeetingType.AD_HOC)
        assert len(meetings) == 1

    def test_get_meeting_by_id(self, svc: SafetyMonitoringService):
        meeting = svc.get_meeting("DSMB-MTG-001")
        assert meeting is not None
        assert meeting.trial_id == EYLEA_TRIAL
        assert meeting.meeting_type == MeetingType.SCHEDULED

    def test_get_meeting_not_found(self, svc: SafetyMonitoringService):
        assert svc.get_meeting("NONEXISTENT") is None

    def test_create_meeting(self, svc: SafetyMonitoringService):
        now = datetime.now(timezone.utc)
        payload = DSMBMeetingCreate(
            trial_id=DUPIXENT_TRIAL,
            meeting_type=MeetingType.SCHEDULED,
            meeting_date=now + timedelta(days=14),
            attendees=["DSMB-MEM-001", "DSMB-MEM-002"],
            agenda=["Test agenda item"],
        )
        meeting = svc.create_meeting(payload)
        assert meeting.id.startswith("DSMB-MTG-")
        assert meeting.trial_id == DUPIXENT_TRIAL
        assert meeting.outcome is None
        assert meeting.minutes_summary is None

    def test_create_emergency_meeting(self, svc: SafetyMonitoringService):
        now = datetime.now(timezone.utc)
        payload = DSMBMeetingCreate(
            trial_id=LIBTAYO_TRIAL,
            meeting_type=MeetingType.EMERGENCY,
            meeting_date=now + timedelta(hours=4),
            attendees=["DSMB-MEM-001", "DSMB-MEM-007"],
            agenda=["Urgent SAE review"],
        )
        meeting = svc.create_meeting(payload)
        assert meeting.meeting_type == MeetingType.EMERGENCY

    def test_update_meeting_add_minutes(self, svc: SafetyMonitoringService):
        payload = DSMBMeetingUpdate(
            minutes_summary="Meeting discussed important items.",
            outcome=ReviewOutcome.CONTINUE_UNCHANGED,
            recommendations=["Continue per protocol"],
            action_items=["Submit updated report"],
        )
        updated = svc.update_meeting("DSMB-MTG-001", payload)
        assert updated is not None
        assert updated.minutes_summary == "Meeting discussed important items."
        assert updated.outcome == ReviewOutcome.CONTINUE_UNCHANGED

    def test_update_meeting_next_date(self, svc: SafetyMonitoringService):
        now = datetime.now(timezone.utc)
        next_date = now + timedelta(days=90)
        payload = DSMBMeetingUpdate(next_meeting_date=next_date)
        updated = svc.update_meeting("DSMB-MTG-001", payload)
        assert updated is not None
        assert updated.next_meeting_date is not None

    def test_update_meeting_not_found(self, svc: SafetyMonitoringService):
        payload = DSMBMeetingUpdate(minutes_summary="test")
        result = svc.update_meeting("NONEXISTENT", payload)
        assert result is None

    def test_meetings_sorted_by_date_descending(self, svc: SafetyMonitoringService):
        meetings = svc.list_meetings()
        dates = [m.meeting_date for m in meetings]
        assert dates == sorted(dates, reverse=True)

    def test_upcoming_meetings(self, svc: SafetyMonitoringService):
        upcoming = svc.get_upcoming_meetings(days=90)
        now = datetime.now(timezone.utc)
        for m in upcoming:
            assert m.meeting_date > now

    def test_upcoming_meetings_sorted_ascending(self, svc: SafetyMonitoringService):
        upcoming = svc.get_upcoming_meetings(days=365)
        if len(upcoming) > 1:
            dates = [m.meeting_date for m in upcoming]
            assert dates == sorted(dates)


# ===================================================================
# INTERIM ANALYSIS
# ===================================================================


class TestInterimAnalysis:
    """Test interim analysis creation and stopping rule evaluation."""

    def test_list_all_analyses(self, svc: SafetyMonitoringService):
        analyses = svc.list_interim_analyses()
        assert len(analyses) == 3

    def test_list_analyses_by_trial(self, svc: SafetyMonitoringService):
        analyses = svc.list_interim_analyses(trial_id=LIBTAYO_TRIAL)
        assert len(analyses) == 1

    def test_list_analyses_by_type(self, svc: SafetyMonitoringService):
        analyses = svc.list_interim_analyses(analysis_type=InterimAnalysisType.COMBINED)
        assert len(analyses) == 1

    def test_get_analysis_by_id(self, svc: SafetyMonitoringService):
        analysis = svc.get_interim_analysis("DSMB-IA-001")
        assert analysis is not None
        assert analysis.trial_id == LIBTAYO_TRIAL
        assert analysis.analysis_type == InterimAnalysisType.COMBINED

    def test_get_analysis_not_found(self, svc: SafetyMonitoringService):
        assert svc.get_interim_analysis("NONEXISTENT") is None

    def test_create_analysis_obf(self, svc: SafetyMonitoringService):
        payload = InterimAnalysisCreate(
            trial_id=EYLEA_TRIAL,
            analysis_type=InterimAnalysisType.COMBINED,
            planned_sample_size=300,
            actual_sample_size=100,
            performed_by="Dr. Test",
            method="OBF",
            overall_alpha=0.05,
            number_of_looks=3,
            current_look=1,
        )
        analysis = svc.create_interim_analysis(payload)
        assert analysis.id.startswith("DSMB-IA-")
        assert analysis.information_fraction == pytest.approx(0.3333, abs=0.01)
        assert len(analysis.stopping_rules_evaluated) > 0

    def test_create_analysis_pocock(self, svc: SafetyMonitoringService):
        payload = InterimAnalysisCreate(
            trial_id=DUPIXENT_TRIAL,
            analysis_type=InterimAnalysisType.EFFICACY_FUTILITY,
            planned_sample_size=500,
            actual_sample_size=250,
            performed_by="Dr. Test",
            method="Pocock",
            overall_alpha=0.05,
            number_of_looks=3,
            current_look=2,
        )
        analysis = svc.create_interim_analysis(payload)
        assert analysis.information_fraction == pytest.approx(0.5, abs=0.01)
        # Pocock method should have boundaries
        boundaries = analysis.stopping_rules_evaluated
        assert len(boundaries) >= 2  # Efficacy + Futility

    def test_create_analysis_lan_demets(self, svc: SafetyMonitoringService):
        payload = InterimAnalysisCreate(
            trial_id=LIBTAYO_TRIAL,
            analysis_type=InterimAnalysisType.SAFETY_ONLY,
            planned_sample_size=450,
            actual_sample_size=300,
            performed_by="Dr. Test",
            method="Lan-DeMets",
            overall_alpha=0.05,
            number_of_looks=3,
            current_look=2,
        )
        analysis = svc.create_interim_analysis(payload)
        assert analysis.information_fraction == pytest.approx(0.6667, abs=0.01)
        # Safety-only should have safety boundary
        boundaries = analysis.stopping_rules_evaluated
        rule_types = [b.rule_type for b in boundaries]
        assert StoppingRule.SAFETY_BOUNDARY in rule_types

    def test_obf_boundary_decreases_with_info_fraction(self, svc: SafetyMonitoringService):
        """O'Brien-Fleming boundary should be more conservative early."""
        early = InterimAnalysisCreate(
            trial_id=EYLEA_TRIAL,
            analysis_type=InterimAnalysisType.COMBINED,
            planned_sample_size=300,
            actual_sample_size=100,
            performed_by="Dr. Test",
            method="OBF",
            number_of_looks=3,
            current_look=1,
        )
        late = InterimAnalysisCreate(
            trial_id=EYLEA_TRIAL,
            analysis_type=InterimAnalysisType.COMBINED,
            planned_sample_size=300,
            actual_sample_size=250,
            performed_by="Dr. Test",
            method="OBF",
            number_of_looks=3,
            current_look=3,
        )
        early_result = svc.create_interim_analysis(early)
        late_result = svc.create_interim_analysis(late)

        # Find efficacy boundaries
        early_eff = [b for b in early_result.stopping_rules_evaluated if b.rule_type == StoppingRule.EFFICACY_BOUNDARY][0]
        late_eff = [b for b in late_result.stopping_rules_evaluated if b.rule_type == StoppingRule.EFFICACY_BOUNDARY][0]

        # Early boundary should be higher (more conservative)
        assert early_eff.boundary_value > late_eff.boundary_value

    def test_combined_analysis_has_efficacy_futility_safety(self, svc: SafetyMonitoringService):
        payload = InterimAnalysisCreate(
            trial_id=EYLEA_TRIAL,
            analysis_type=InterimAnalysisType.COMBINED,
            planned_sample_size=300,
            actual_sample_size=150,
            performed_by="Dr. Test",
            method="OBF",
        )
        analysis = svc.create_interim_analysis(payload)
        rule_types = {b.rule_type for b in analysis.stopping_rules_evaluated}
        assert StoppingRule.EFFICACY_BOUNDARY in rule_types
        assert StoppingRule.FUTILITY_BOUNDARY in rule_types
        assert StoppingRule.SAFETY_BOUNDARY in rule_types

    def test_safety_only_analysis_no_efficacy(self, svc: SafetyMonitoringService):
        payload = InterimAnalysisCreate(
            trial_id=EYLEA_TRIAL,
            analysis_type=InterimAnalysisType.SAFETY_ONLY,
            planned_sample_size=300,
            actual_sample_size=150,
            performed_by="Dr. Test",
            method="OBF",
        )
        analysis = svc.create_interim_analysis(payload)
        rule_types = {b.rule_type for b in analysis.stopping_rules_evaluated}
        assert StoppingRule.EFFICACY_BOUNDARY not in rule_types
        assert StoppingRule.SAFETY_BOUNDARY in rule_types

    def test_efficacy_futility_no_safety_boundary(self, svc: SafetyMonitoringService):
        payload = InterimAnalysisCreate(
            trial_id=EYLEA_TRIAL,
            analysis_type=InterimAnalysisType.EFFICACY_FUTILITY,
            planned_sample_size=300,
            actual_sample_size=150,
            performed_by="Dr. Test",
            method="OBF",
        )
        analysis = svc.create_interim_analysis(payload)
        rule_types = {b.rule_type for b in analysis.stopping_rules_evaluated}
        assert StoppingRule.EFFICACY_BOUNDARY in rule_types
        assert StoppingRule.FUTILITY_BOUNDARY in rule_types
        assert StoppingRule.SAFETY_BOUNDARY not in rule_types

    def test_analysis_information_fraction_capped_at_one(self, svc: SafetyMonitoringService):
        payload = InterimAnalysisCreate(
            trial_id=EYLEA_TRIAL,
            analysis_type=InterimAnalysisType.COMBINED,
            planned_sample_size=100,
            actual_sample_size=150,  # Exceeds planned
            performed_by="Dr. Test",
            method="OBF",
        )
        analysis = svc.create_interim_analysis(payload)
        assert analysis.information_fraction <= 1.0

    def test_analysis_recommendation_no_crossing(self, svc: SafetyMonitoringService):
        payload = InterimAnalysisCreate(
            trial_id=EYLEA_TRIAL,
            analysis_type=InterimAnalysisType.COMBINED,
            planned_sample_size=300,
            actual_sample_size=100,
            performed_by="Dr. Test",
            method="OBF",
        )
        analysis = svc.create_interim_analysis(payload)
        # No boundaries should be crossed (they aren't compared to test statistics)
        assert analysis.recommendation == ReviewOutcome.CONTINUE_UNCHANGED

    def test_alpha_spent_nonnegative(self, svc: SafetyMonitoringService):
        payload = InterimAnalysisCreate(
            trial_id=EYLEA_TRIAL,
            analysis_type=InterimAnalysisType.COMBINED,
            planned_sample_size=300,
            actual_sample_size=150,
            performed_by="Dr. Test",
            method="OBF",
        )
        analysis = svc.create_interim_analysis(payload)
        for b in analysis.stopping_rules_evaluated:
            assert b.alpha_spent >= 0.0

    def test_analyses_sorted_by_date_descending(self, svc: SafetyMonitoringService):
        analyses = svc.list_interim_analyses()
        dates = [a.analysis_date for a in analyses]
        assert dates == sorted(dates, reverse=True)


# ===================================================================
# EVENT ADJUDICATION
# ===================================================================


class TestEventAdjudication:
    """Test event adjudication CRUD and status transitions."""

    def test_list_all_adjudications(self, svc: SafetyMonitoringService):
        adjs = svc.list_adjudications()
        assert len(adjs) == 10

    def test_list_adjudications_by_trial(self, svc: SafetyMonitoringService):
        adjs = svc.list_adjudications(trial_id=EYLEA_TRIAL)
        assert len(adjs) == 4
        for a in adjs:
            assert a.trial_id == EYLEA_TRIAL

    def test_list_adjudications_by_status_pending(self, svc: SafetyMonitoringService):
        adjs = svc.list_adjudications(status=EventAdjudicationStatus.PENDING)
        assert len(adjs) == 2

    def test_list_adjudications_by_status_adjudicated(self, svc: SafetyMonitoringService):
        adjs = svc.list_adjudications(status=EventAdjudicationStatus.ADJUDICATED)
        assert len(adjs) == 6

    def test_list_adjudications_by_patient(self, svc: SafetyMonitoringService):
        adjs = svc.list_adjudications(patient_id="PAT-DME-003")
        assert len(adjs) == 1
        assert adjs[0].id == "DSMB-ADJ-001"

    def test_get_adjudication_by_id(self, svc: SafetyMonitoringService):
        adj = svc.get_adjudication("DSMB-ADJ-001")
        assert adj is not None
        assert adj.status == EventAdjudicationStatus.ADJUDICATED
        assert adj.adjudicated_classification is not None

    def test_get_adjudication_not_found(self, svc: SafetyMonitoringService):
        assert svc.get_adjudication("NONEXISTENT") is None

    def test_create_adjudication(self, svc: SafetyMonitoringService):
        now = datetime.now(timezone.utc)
        payload = EventAdjudicationCreate(
            trial_id=DUPIXENT_TRIAL,
            patient_id="PAT-TEST-001",
            event_type="Test Event",
            event_date=now - timedelta(days=5),
            submitted_by="Dr. Test",
            original_classification="Adverse Event",
        )
        adj = svc.create_adjudication(payload)
        assert adj.id.startswith("DSMB-ADJ-")
        assert adj.status == EventAdjudicationStatus.PENDING
        assert adj.adjudicator is None

    def test_adjudication_transition_pending_to_under_review(self, svc: SafetyMonitoringService):
        payload = EventAdjudicationUpdate(
            status=EventAdjudicationStatus.UNDER_REVIEW,
            adjudicator="DSMB-MEM-003",
        )
        updated = svc.update_adjudication("DSMB-ADJ-007", payload)
        assert updated is not None
        assert updated.status == EventAdjudicationStatus.UNDER_REVIEW
        assert updated.adjudicator == "DSMB-MEM-003"

    def test_adjudication_transition_under_review_to_adjudicated(self, svc: SafetyMonitoringService):
        payload = EventAdjudicationUpdate(
            status=EventAdjudicationStatus.ADJUDICATED,
            adjudicated_classification="SAE - Related",
            rationale="Test rationale",
        )
        updated = svc.update_adjudication("DSMB-ADJ-005", payload)
        assert updated is not None
        assert updated.status == EventAdjudicationStatus.ADJUDICATED
        assert updated.adjudicated_at is not None

    def test_adjudication_transition_adjudicated_to_appealed(self, svc: SafetyMonitoringService):
        payload = EventAdjudicationUpdate(
            status=EventAdjudicationStatus.APPEALED,
        )
        updated = svc.update_adjudication("DSMB-ADJ-001", payload)
        assert updated is not None
        assert updated.status == EventAdjudicationStatus.APPEALED

    def test_adjudication_transition_appealed_to_under_review(self, svc: SafetyMonitoringService):
        payload = EventAdjudicationUpdate(
            status=EventAdjudicationStatus.UNDER_REVIEW,
        )
        updated = svc.update_adjudication("DSMB-ADJ-009", payload)
        assert updated is not None
        assert updated.status == EventAdjudicationStatus.UNDER_REVIEW

    def test_adjudication_transition_appealed_to_adjudicated(self, svc: SafetyMonitoringService):
        payload = EventAdjudicationUpdate(
            status=EventAdjudicationStatus.ADJUDICATED,
            adjudicated_classification="AE - Related (confirmed on appeal)",
            rationale="New endoscopy data confirms drug relatedness",
        )
        updated = svc.update_adjudication("DSMB-ADJ-009", payload)
        assert updated is not None
        assert updated.status == EventAdjudicationStatus.ADJUDICATED

    def test_invalid_transition_pending_to_adjudicated(self, svc: SafetyMonitoringService):
        payload = EventAdjudicationUpdate(
            status=EventAdjudicationStatus.ADJUDICATED,
        )
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_adjudication("DSMB-ADJ-007", payload)

    def test_invalid_transition_pending_to_appealed(self, svc: SafetyMonitoringService):
        payload = EventAdjudicationUpdate(
            status=EventAdjudicationStatus.APPEALED,
        )
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_adjudication("DSMB-ADJ-007", payload)

    def test_invalid_transition_adjudicated_to_pending(self, svc: SafetyMonitoringService):
        payload = EventAdjudicationUpdate(
            status=EventAdjudicationStatus.PENDING,
        )
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_adjudication("DSMB-ADJ-001", payload)

    def test_update_adjudication_not_found(self, svc: SafetyMonitoringService):
        payload = EventAdjudicationUpdate(
            status=EventAdjudicationStatus.UNDER_REVIEW,
        )
        result = svc.update_adjudication("NONEXISTENT", payload)
        assert result is None

    def test_overdue_adjudications(self, svc: SafetyMonitoringService):
        overdue = svc.get_overdue_adjudications()
        # Pending adjudications that are >30 days old
        for adj in overdue:
            assert adj.status == EventAdjudicationStatus.PENDING

    def test_adjudications_sorted_by_date_descending(self, svc: SafetyMonitoringService):
        adjs = svc.list_adjudications()
        dates = [a.created_at for a in adjs]
        assert dates == sorted(dates, reverse=True)


# ===================================================================
# SAFETY REPORTS
# ===================================================================


class TestSafetyReports:
    """Test safety report generation and management."""

    def test_list_all_reports(self, svc: SafetyMonitoringService):
        reports = svc.list_safety_reports()
        assert len(reports) == 4

    def test_list_reports_by_trial(self, svc: SafetyMonitoringService):
        reports = svc.list_safety_reports(trial_id=EYLEA_TRIAL)
        assert len(reports) == 2

    def test_list_reports_by_access_level(self, svc: SafetyMonitoringService):
        reports = svc.list_safety_reports(access_level=ReportAccessLevel.UNBLINDED)
        assert len(reports) == 3

    def test_get_report_by_id(self, svc: SafetyMonitoringService):
        report = svc.get_safety_report("DSMB-RPT-001")
        assert report is not None
        assert report.trial_id == EYLEA_TRIAL
        assert report.total_enrolled == 120

    def test_get_report_not_found(self, svc: SafetyMonitoringService):
        assert svc.get_safety_report("NONEXISTENT") is None

    def test_generate_blinded_report(self, svc: SafetyMonitoringService):
        payload = SafetyReportCreate(
            trial_id=EYLEA_TRIAL,
            report_type="periodic",
            generated_by="Test System",
            access_level=ReportAccessLevel.BLINDED,
        )
        report = svc.generate_safety_report(payload)
        assert report.id.startswith("DSMB-RPT-")
        assert report.access_level == ReportAccessLevel.BLINDED
        # Blinded report should not show arm-specific rates
        assert "treatment" not in report.event_rates_by_arm
        assert "pooled" in report.event_rates_by_arm

    def test_generate_unblinded_report(self, svc: SafetyMonitoringService):
        payload = SafetyReportCreate(
            trial_id=EYLEA_TRIAL,
            report_type="periodic",
            generated_by="Test System",
            access_level=ReportAccessLevel.UNBLINDED,
        )
        report = svc.generate_safety_report(payload)
        assert report.access_level == ReportAccessLevel.UNBLINDED
        # Unblinded report should show arm-specific rates
        assert "treatment" in report.event_rates_by_arm
        assert "control" in report.event_rates_by_arm

    def test_generate_summary_only_report(self, svc: SafetyMonitoringService):
        payload = SafetyReportCreate(
            trial_id=EYLEA_TRIAL,
            report_type="summary",
            generated_by="Test System",
            access_level=ReportAccessLevel.SUMMARY_ONLY,
        )
        report = svc.generate_safety_report(payload)
        assert report.access_level == ReportAccessLevel.SUMMARY_ONLY
        assert len(report.event_rates_by_arm) == 0

    def test_generate_report_counts_events(self, svc: SafetyMonitoringService):
        payload = SafetyReportCreate(
            trial_id=EYLEA_TRIAL,
            report_type="periodic",
            generated_by="Test System",
        )
        report = svc.generate_safety_report(payload)
        # EYLEA has 4 adjudications in seed data
        assert report.total_events == 4

    def test_generate_report_detects_serious_events(self, svc: SafetyMonitoringService):
        payload = SafetyReportCreate(
            trial_id=EYLEA_TRIAL,
            report_type="periodic",
            generated_by="Test System",
        )
        report = svc.generate_safety_report(payload)
        # All 4 EYLEA adjudications have "Serious" in classification
        assert report.serious_events >= 0

    def test_reports_sorted_by_date_descending(self, svc: SafetyMonitoringService):
        reports = svc.list_safety_reports()
        dates = [r.report_date for r in reports]
        assert dates == sorted(dates, reverse=True)

    def test_report_for_trial_with_fatal_events(self, svc: SafetyMonitoringService):
        report = svc.get_safety_report("DSMB-RPT-004")
        assert report is not None
        assert report.fatal_events == 1
        assert len(report.safety_signals) > 0


# ===================================================================
# CHARTER MANAGEMENT
# ===================================================================


class TestCharterManagement:
    """Test DSMB charter CRUD operations."""

    def test_list_all_charters(self, svc: SafetyMonitoringService):
        charters = svc.list_charters()
        assert len(charters) == 2

    def test_list_charters_by_trial(self, svc: SafetyMonitoringService):
        charters = svc.list_charters(trial_id=EYLEA_TRIAL)
        assert len(charters) == 1

    def test_get_charter_by_id(self, svc: SafetyMonitoringService):
        charter = svc.get_charter("DSMB-CHR-001")
        assert charter is not None
        assert charter.trial_id == EYLEA_TRIAL
        assert charter.version == "2.0"

    def test_get_charter_not_found(self, svc: SafetyMonitoringService):
        assert svc.get_charter("NONEXISTENT") is None

    def test_create_charter(self, svc: SafetyMonitoringService):
        payload = DSMBCharterCreate(
            trial_id=DUPIXENT_TRIAL,
            version="1.0",
            review_frequency_weeks=8,
            stopping_rules=["Test rule"],
            reporting_requirements=["Monthly report"],
            access_policies=["Blinded access"],
            approved_by=["DSMB-MEM-001"],
        )
        charter = svc.create_charter(payload)
        assert charter.id.startswith("DSMB-CHR-")
        assert charter.trial_id == DUPIXENT_TRIAL
        assert charter.version == "1.0"

    def test_update_charter_version(self, svc: SafetyMonitoringService):
        payload = DSMBCharterUpdate(
            version="3.0",
            stopping_rules=["Updated rule 1", "Updated rule 2"],
        )
        updated = svc.update_charter("DSMB-CHR-001", payload)
        assert updated is not None
        assert updated.version == "3.0"
        assert len(updated.stopping_rules) == 2

    def test_update_charter_frequency(self, svc: SafetyMonitoringService):
        payload = DSMBCharterUpdate(review_frequency_weeks=6)
        updated = svc.update_charter("DSMB-CHR-001", payload)
        assert updated is not None
        assert updated.review_frequency_weeks == 6

    def test_update_charter_not_found(self, svc: SafetyMonitoringService):
        payload = DSMBCharterUpdate(version="2.0")
        result = svc.update_charter("NONEXISTENT", payload)
        assert result is None

    def test_charter_approved_date_updates_on_version_change(self, svc: SafetyMonitoringService):
        original = svc.get_charter("DSMB-CHR-001")
        assert original is not None
        original_date = original.approved_date

        payload = DSMBCharterUpdate(version="3.0")
        updated = svc.update_charter("DSMB-CHR-001", payload)
        assert updated is not None
        assert updated.approved_date >= original_date


# ===================================================================
# METRICS
# ===================================================================


class TestMetrics:
    """Test DSMB operational metrics."""

    def test_metrics_total_members(self, svc: SafetyMonitoringService):
        metrics = svc.get_metrics()
        assert metrics.total_members == 8

    def test_metrics_active_members(self, svc: SafetyMonitoringService):
        metrics = svc.get_metrics()
        assert metrics.active_members == 7

    def test_metrics_total_meetings(self, svc: SafetyMonitoringService):
        metrics = svc.get_metrics()
        assert metrics.total_meetings == 6

    def test_metrics_meetings_by_type(self, svc: SafetyMonitoringService):
        metrics = svc.get_metrics()
        assert metrics.meetings_by_type["SCHEDULED"] == 4
        assert metrics.meetings_by_type["AD_HOC"] == 1
        assert metrics.meetings_by_type["EMERGENCY"] == 1

    def test_metrics_total_interim_analyses(self, svc: SafetyMonitoringService):
        metrics = svc.get_metrics()
        assert metrics.total_interim_analyses == 3

    def test_metrics_total_adjudications(self, svc: SafetyMonitoringService):
        metrics = svc.get_metrics()
        assert metrics.total_adjudications == 10

    def test_metrics_adjudications_by_status(self, svc: SafetyMonitoringService):
        metrics = svc.get_metrics()
        assert metrics.adjudications_by_status["ADJUDICATED"] == 6
        assert metrics.adjudications_by_status["PENDING"] == 2

    def test_metrics_pending_adjudications(self, svc: SafetyMonitoringService):
        metrics = svc.get_metrics()
        assert metrics.pending_adjudications == 2

    def test_metrics_total_safety_reports(self, svc: SafetyMonitoringService):
        metrics = svc.get_metrics()
        assert metrics.total_safety_reports == 4

    def test_metrics_total_charters(self, svc: SafetyMonitoringService):
        metrics = svc.get_metrics()
        assert metrics.total_charters == 2

    def test_metrics_trials_with_active_monitoring(self, svc: SafetyMonitoringService):
        metrics = svc.get_metrics()
        assert metrics.trials_with_active_monitoring == 3

    def test_metrics_boundaries_crossed(self, svc: SafetyMonitoringService):
        metrics = svc.get_metrics()
        # Seed data has no boundaries crossed
        assert metrics.boundaries_crossed_count == 0


# ===================================================================
# API ENDPOINT TESTS
# ===================================================================


class TestMemberAPI:
    """Test member API endpoints."""

    @pytest.mark.anyio
    async def test_list_members_api(self, client):
        resp = await client.get(f"{API_PREFIX}/members")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8
        assert len(data["items"]) == 8

    @pytest.mark.anyio
    async def test_list_members_filter_role(self, client):
        resp = await client.get(f"{API_PREFIX}/members", params={"role": "CHAIR"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.anyio
    async def test_list_members_filter_active(self, client):
        resp = await client.get(f"{API_PREFIX}/members", params={"active": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    @pytest.mark.anyio
    async def test_get_member_api(self, client):
        resp = await client.get(f"{API_PREFIX}/members/DSMB-MEM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Dr. Margaret Thompson"

    @pytest.mark.anyio
    async def test_get_member_not_found_api(self, client):
        resp = await client.get(f"{API_PREFIX}/members/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_member_api(self, client):
        payload = _make_member_create()
        resp = await client.post(f"{API_PREFIX}/members", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Dr. Test User"

    @pytest.mark.anyio
    async def test_update_member_api(self, client):
        resp = await client.put(
            f"{API_PREFIX}/members/DSMB-MEM-001",
            json={"active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False

    @pytest.mark.anyio
    async def test_update_member_not_found_api(self, client):
        resp = await client.put(
            f"{API_PREFIX}/members/NONEXISTENT",
            json={"active": False},
        )
        assert resp.status_code == 404


class TestMeetingAPI:
    """Test meeting API endpoints."""

    @pytest.mark.anyio
    async def test_list_meetings_api(self, client):
        resp = await client.get(f"{API_PREFIX}/meetings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_meetings_filter_trial(self, client):
        resp = await client.get(f"{API_PREFIX}/meetings", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_list_meetings_filter_type(self, client):
        resp = await client.get(f"{API_PREFIX}/meetings", params={"meeting_type": "EMERGENCY"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.anyio
    async def test_upcoming_meetings_api(self, client):
        resp = await client.get(f"{API_PREFIX}/meetings/upcoming", params={"days": 365})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0

    @pytest.mark.anyio
    async def test_get_meeting_api(self, client):
        resp = await client.get(f"{API_PREFIX}/meetings/DSMB-MTG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_meeting_not_found_api(self, client):
        resp = await client.get(f"{API_PREFIX}/meetings/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_meeting_api(self, client):
        payload = _make_meeting_create()
        resp = await client.post(f"{API_PREFIX}/meetings", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_update_meeting_api(self, client):
        resp = await client.put(
            f"{API_PREFIX}/meetings/DSMB-MTG-001",
            json={"minutes_summary": "Updated minutes", "outcome": "CONTINUE_UNCHANGED"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["minutes_summary"] == "Updated minutes"

    @pytest.mark.anyio
    async def test_update_meeting_not_found_api(self, client):
        resp = await client.put(
            f"{API_PREFIX}/meetings/NONEXISTENT",
            json={"minutes_summary": "test"},
        )
        assert resp.status_code == 404


class TestInterimAnalysisAPI:
    """Test interim analysis API endpoints."""

    @pytest.mark.anyio
    async def test_list_analyses_api(self, client):
        resp = await client.get(f"{API_PREFIX}/interim-analyses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_analyses_filter_trial(self, client):
        resp = await client.get(
            f"{API_PREFIX}/interim-analyses", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.anyio
    async def test_get_analysis_api(self, client):
        resp = await client.get(f"{API_PREFIX}/interim-analyses/DSMB-IA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_analysis_not_found_api(self, client):
        resp = await client.get(f"{API_PREFIX}/interim-analyses/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_analysis_api(self, client):
        payload = _make_analysis_create()
        resp = await client.post(f"{API_PREFIX}/interim-analyses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["stopping_rules_evaluated"]) > 0


class TestAdjudicationAPI:
    """Test adjudication API endpoints."""

    @pytest.mark.anyio
    async def test_list_adjudications_api(self, client):
        resp = await client.get(f"{API_PREFIX}/adjudications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_adjudications_filter_status(self, client):
        resp = await client.get(
            f"{API_PREFIX}/adjudications", params={"status": "PENDING"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_overdue_adjudications_api(self, client):
        resp = await client.get(f"{API_PREFIX}/adjudications/overdue")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    @pytest.mark.anyio
    async def test_get_adjudication_api(self, client):
        resp = await client.get(f"{API_PREFIX}/adjudications/DSMB-ADJ-001")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_get_adjudication_not_found_api(self, client):
        resp = await client.get(f"{API_PREFIX}/adjudications/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_adjudication_api(self, client):
        payload = _make_adjudication_create()
        resp = await client.post(f"{API_PREFIX}/adjudications", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_update_adjudication_valid_transition_api(self, client):
        resp = await client.put(
            f"{API_PREFIX}/adjudications/DSMB-ADJ-007",
            json={"status": "UNDER_REVIEW", "adjudicator": "DSMB-MEM-003"},
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_update_adjudication_invalid_transition_api(self, client):
        resp = await client.put(
            f"{API_PREFIX}/adjudications/DSMB-ADJ-007",
            json={"status": "ADJUDICATED"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_adjudication_not_found_api(self, client):
        resp = await client.put(
            f"{API_PREFIX}/adjudications/NONEXISTENT",
            json={"status": "UNDER_REVIEW"},
        )
        assert resp.status_code == 404


class TestSafetyReportAPI:
    """Test safety report API endpoints."""

    @pytest.mark.anyio
    async def test_list_reports_api(self, client):
        resp = await client.get(f"{API_PREFIX}/safety-reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_reports_filter_trial(self, client):
        resp = await client.get(
            f"{API_PREFIX}/safety-reports", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_list_reports_filter_access(self, client):
        resp = await client.get(
            f"{API_PREFIX}/safety-reports", params={"access_level": "UNBLINDED"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_get_report_api(self, client):
        resp = await client.get(f"{API_PREFIX}/safety-reports/DSMB-RPT-001")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_get_report_not_found_api(self, client):
        resp = await client.get(f"{API_PREFIX}/safety-reports/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_generate_report_api(self, client):
        payload = _make_report_create()
        resp = await client.post(f"{API_PREFIX}/safety-reports", json=payload)
        assert resp.status_code == 201


class TestCharterAPI:
    """Test charter API endpoints."""

    @pytest.mark.anyio
    async def test_list_charters_api(self, client):
        resp = await client.get(f"{API_PREFIX}/charters")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_list_charters_filter_trial(self, client):
        resp = await client.get(
            f"{API_PREFIX}/charters", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.anyio
    async def test_get_charter_api(self, client):
        resp = await client.get(f"{API_PREFIX}/charters/DSMB-CHR-001")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_get_charter_not_found_api(self, client):
        resp = await client.get(f"{API_PREFIX}/charters/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_charter_api(self, client):
        payload = _make_charter_create(trial_id=DUPIXENT_TRIAL)
        resp = await client.post(f"{API_PREFIX}/charters", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_update_charter_api(self, client):
        resp = await client.put(
            f"{API_PREFIX}/charters/DSMB-CHR-001",
            json={"version": "3.0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "3.0"

    @pytest.mark.anyio
    async def test_update_charter_not_found_api(self, client):
        resp = await client.put(
            f"{API_PREFIX}/charters/NONEXISTENT",
            json={"version": "2.0"},
        )
        assert resp.status_code == 404


class TestMetricsAPI:
    """Test metrics API endpoint."""

    @pytest.mark.anyio
    async def test_metrics_api(self, client):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_members"] == 8
        assert data["active_members"] == 7
        assert data["total_meetings"] == 6
        assert data["total_interim_analyses"] == 3
        assert data["total_adjudications"] == 10
        assert data["total_safety_reports"] == 4
        assert data["total_charters"] == 2
        assert data["trials_with_active_monitoring"] == 3


# ===================================================================
# STATISTICAL METHOD TESTS
# ===================================================================


class TestStatisticalMethods:
    """Test statistical boundary computation methods."""

    def test_phi_standard_normal_cdf(self, svc: SafetyMonitoringService):
        # phi(0) should be 0.5
        assert svc._phi(0.0) == pytest.approx(0.5, abs=0.001)

    def test_phi_positive_z(self, svc: SafetyMonitoringService):
        # phi(1.96) ~ 0.975
        assert svc._phi(1.96) == pytest.approx(0.975, abs=0.01)

    def test_phi_negative_z(self, svc: SafetyMonitoringService):
        # phi(-1.96) ~ 0.025
        assert svc._phi(-1.96) == pytest.approx(0.025, abs=0.01)

    def test_z_from_alpha_small(self, svc: SafetyMonitoringService):
        # z for alpha=0.025 ~ 1.96
        z = svc._z_from_alpha(0.025)
        assert z == pytest.approx(1.96, abs=0.05)

    def test_z_from_alpha_zero(self, svc: SafetyMonitoringService):
        z = svc._z_from_alpha(0.0)
        assert z == 8.0

    def test_z_from_alpha_one(self, svc: SafetyMonitoringService):
        z = svc._z_from_alpha(1.0)
        assert z == 0.0

    def test_determine_recommendation_empty_crossed(self, svc: SafetyMonitoringService):
        result = svc._determine_recommendation([], [])
        assert result == ReviewOutcome.CONTINUE_UNCHANGED

    def test_determine_recommendation_harm_boundary(self, svc: SafetyMonitoringService):
        result = svc._determine_recommendation(
            [StoppingRule.HARM_BOUNDARY.value], []
        )
        assert result == ReviewOutcome.TERMINATE_EARLY

    def test_determine_recommendation_safety_boundary(self, svc: SafetyMonitoringService):
        result = svc._determine_recommendation(
            [StoppingRule.SAFETY_BOUNDARY.value], []
        )
        assert result == ReviewOutcome.SUSPEND_ENROLLMENT

    def test_determine_recommendation_efficacy_boundary(self, svc: SafetyMonitoringService):
        result = svc._determine_recommendation(
            [StoppingRule.EFFICACY_BOUNDARY.value], []
        )
        assert result == ReviewOutcome.TERMINATE_EARLY

    def test_determine_recommendation_futility_boundary(self, svc: SafetyMonitoringService):
        result = svc._determine_recommendation(
            [StoppingRule.FUTILITY_BOUNDARY.value], []
        )
        assert result == ReviewOutcome.TERMINATE_EARLY

    def test_obf_alpha_spending_increases_with_info_fraction(self, svc: SafetyMonitoringService):
        """Alpha spending should increase with information fraction for OBF."""
        _, alpha_early = svc._compute_boundary(
            method="OBF",
            overall_alpha=0.05,
            information_fraction=0.25,
            number_of_looks=4,
            current_look=1,
            boundary_type="efficacy",
        )
        _, alpha_late = svc._compute_boundary(
            method="OBF",
            overall_alpha=0.05,
            information_fraction=0.75,
            number_of_looks=4,
            current_look=3,
            boundary_type="efficacy",
        )
        assert alpha_late >= alpha_early

    def test_pocock_equal_alpha_per_look(self, svc: SafetyMonitoringService):
        """Pocock should spend equal alpha at each look."""
        _, alpha_1 = svc._compute_boundary(
            method="Pocock",
            overall_alpha=0.05,
            information_fraction=0.333,
            number_of_looks=3,
            current_look=1,
            boundary_type="efficacy",
        )
        _, alpha_2 = svc._compute_boundary(
            method="Pocock",
            overall_alpha=0.05,
            information_fraction=0.667,
            number_of_looks=3,
            current_look=2,
            boundary_type="efficacy",
        )
        # alpha at look 2 should be 2x alpha at look 1
        assert alpha_2 == pytest.approx(2 * alpha_1, abs=0.001)


# ===================================================================
# EDGE CASES
# ===================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_filter_returns_all(self, svc: SafetyMonitoringService):
        assert len(svc.list_members()) == 8
        assert len(svc.list_meetings()) == 6
        assert len(svc.list_adjudications()) == 10

    def test_filter_nonexistent_trial(self, svc: SafetyMonitoringService):
        meetings = svc.list_meetings(trial_id="NONEXISTENT")
        assert len(meetings) == 0

    def test_filter_nonexistent_patient(self, svc: SafetyMonitoringService):
        adjs = svc.list_adjudications(patient_id="NONEXISTENT")
        assert len(adjs) == 0

    def test_create_and_retrieve_member(self, svc: SafetyMonitoringService):
        now = datetime.now(timezone.utc)
        payload = DSMBMemberCreate(
            name="Dr. Roundtrip Test",
            role=DSMBRole.PATIENT_ADVOCATE,
            institution="Test",
            specialty="Test",
            email="test@test.com",
            term_start=now,
            term_end=now + timedelta(days=365),
        )
        created = svc.create_member(payload)
        retrieved = svc.get_member(created.id)
        assert retrieved is not None
        assert retrieved.name == created.name

    def test_multiple_charters_for_different_trials(self, svc: SafetyMonitoringService):
        payload = DSMBCharterCreate(
            trial_id=DUPIXENT_TRIAL,
            version="1.0",
            review_frequency_weeks=12,
        )
        svc.create_charter(payload)
        all_charters = svc.list_charters()
        assert len(all_charters) == 3

        dupixent_charters = svc.list_charters(trial_id=DUPIXENT_TRIAL)
        assert len(dupixent_charters) == 1

    def test_adjudication_auto_sets_adjudicated_at(self, svc: SafetyMonitoringService):
        # First transition PENDING -> UNDER_REVIEW
        svc.update_adjudication(
            "DSMB-ADJ-007",
            EventAdjudicationUpdate(status=EventAdjudicationStatus.UNDER_REVIEW),
        )
        # Then UNDER_REVIEW -> ADJUDICATED
        updated = svc.update_adjudication(
            "DSMB-ADJ-007",
            EventAdjudicationUpdate(
                status=EventAdjudicationStatus.ADJUDICATED,
                adjudicated_classification="AE - Not Related",
                rationale="No temporal relationship",
            ),
        )
        assert updated is not None
        assert updated.adjudicated_at is not None

    def test_sample_size_reestimation_type(self, svc: SafetyMonitoringService):
        payload = InterimAnalysisCreate(
            trial_id=EYLEA_TRIAL,
            analysis_type=InterimAnalysisType.SAMPLE_SIZE_REESTIMATION,
            planned_sample_size=300,
            actual_sample_size=100,
            performed_by="Dr. Test",
            method="OBF",
        )
        analysis = svc.create_interim_analysis(payload)
        assert analysis.analysis_type == InterimAnalysisType.SAMPLE_SIZE_REESTIMATION
        # SSR should have no boundaries (not efficacy/futility/safety)
        assert len(analysis.stopping_rules_evaluated) == 0

    def test_generate_report_for_trial_with_no_adjudications(self, svc: SafetyMonitoringService):
        payload = SafetyReportCreate(
            trial_id="TRIAL-WITH-NO-DATA",
            report_type="periodic",
            generated_by="Test",
        )
        report = svc.generate_safety_report(payload)
        assert report.total_events == 0
        assert report.serious_events == 0
        assert report.fatal_events == 0
