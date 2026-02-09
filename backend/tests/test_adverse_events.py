"""Tests for Adverse Event Monitoring & Safety Reporting (CMO-9).

Covers:
- Seed data verification (events, signals, expedited reports)
- Adverse event CRUD (create, read, update, list with all filter combinations)
- Auto expedited-reporting detection (serious + unexpected)
- Status transition validation
- FDA 15-day and 7-day expedited reporting rules
- Safety signal detection via statistical analysis
- Safety signal CRUD and status updates
- Causality assessment (Naranjo algorithm)
- Narrative generation (MedWatch-style)
- Reporting metrics computation
- Category-based event queries
- Error handling (404s, 400s, invalid transitions)
- Pagination and edge cases
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.adverse_events import (
    AEActionTaken,
    AECategory,
    AECreate,
    AEOutcome,
    AERelatedness,
    AESeverity,
    AEStatus,
    AEUpdate,
    ExpeditedReportStatus,
    ExpeditedReportType,
    SafetySignalStatus,
)
from app.services.adverse_event_service import (
    AdverseEventService,
    get_adverse_event_service,
    reset_adverse_event_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/adverse-events"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_adverse_event_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> AdverseEventService:
    """Shorthand for the fresh service."""
    return fresh_service


def _make_create(
    trial_id: str = EYLEA_TRIAL,
    severity: AESeverity = AESeverity.MILD,
    category: AECategory = AECategory.GENERAL,
    serious: bool = False,
    expected: bool = True,
    **kwargs,
) -> AECreate:
    """Helper to build an AECreate with defaults."""
    now = datetime.now(timezone.utc)
    defaults = dict(
        trial_id=trial_id,
        patient_id="PAT-TEST-001",
        site_id="SITE-TEST",
        event_term="Test event",
        preferred_term="Test event",
        category=category,
        severity=severity,
        relatedness=AERelatedness.POSSIBLE,
        serious=serious,
        expected=expected,
        onset_date=now - timedelta(days=2),
        reporter="Test Reporter",
        description="Test description for adverse event",
        action_taken=AEActionTaken.NONE,
        outcome=AEOutcome.UNKNOWN,
    )
    defaults.update(kwargs)
    return AECreate(**defaults)


# ===========================================================================
# Section 1: Seed data verification
# ===========================================================================


class TestSeedData:
    """Verify the seed data is loaded correctly on service init."""

    def test_seed_events_count(self, svc: AdverseEventService):
        """Seed should contain 14 adverse events."""
        items, total = svc.list_events(limit=100)
        assert total == 14

    def test_seed_signals_count(self, svc: AdverseEventService):
        """Seed should contain 3 safety signals."""
        signals = svc.list_signals()
        assert len(signals) == 3

    def test_seed_expedited_reports_count(self, svc: AdverseEventService):
        """Seed should contain 3 expedited reports."""
        reports = svc.get_expedited_reports()
        assert len(reports) == 3

    def test_seed_event_ids_sequential(self, svc: AdverseEventService):
        """Seed event IDs should be AE-0001 through AE-0014."""
        for i in range(1, 15):
            ae = svc.get_event(f"AE-{i:04d}")
            assert ae.id == f"AE-{i:04d}"

    def test_seed_signal_ids(self, svc: AdverseEventService):
        """Seed signals should have IDs SIG-0001 through SIG-0003."""
        for i in range(1, 4):
            sig = svc.get_signal(f"SIG-{i:04d}")
            assert sig.id == f"SIG-{i:04d}"

    def test_seed_expedited_report_ids(self, svc: AdverseEventService):
        """Seed expedited reports should have IDs EXP-0001 through EXP-0003."""
        reports = svc.get_expedited_reports()
        ids = {r.id for r in reports}
        assert "EXP-0001" in ids
        assert "EXP-0002" in ids
        assert "EXP-0003" in ids

    def test_seed_eylea_events(self, svc: AdverseEventService):
        """EYLEA trial should have 4 seed events."""
        items, total = svc.list_events(trial_id=EYLEA_TRIAL, limit=100)
        assert total == 4

    def test_seed_dupixent_events(self, svc: AdverseEventService):
        """DUPIXENT trial should have 5 seed events."""
        items, total = svc.list_events(trial_id=DUPIXENT_TRIAL, limit=100)
        assert total == 5

    def test_seed_libtayo_events(self, svc: AdverseEventService):
        """LIBTAYO trial should have 5 seed events."""
        items, total = svc.list_events(trial_id=LIBTAYO_TRIAL, limit=100)
        assert total == 5

    def test_seed_serious_events(self, svc: AdverseEventService):
        """Should have correct number of serious events."""
        items, total = svc.list_events(serious=True, limit=100)
        # Endophthalmitis, Anaphylaxis, Pneumonitis, Neutropenia
        assert total == 4

    def test_seed_anaphylaxis_is_serious_unexpected(self, svc: AdverseEventService):
        """Anaphylaxis (AE-0007) should require expedited reporting."""
        ae = svc.get_event("AE-0007")
        assert ae.serious is True
        assert ae.expected is False
        assert ae.requires_expedited_reporting is True


# ===========================================================================
# Section 2: Adverse event CRUD (service level)
# ===========================================================================


class TestAECRUD:
    """Test adverse event create, read, update, list operations."""

    def test_report_event_basic(self, svc: AdverseEventService):
        """Report a basic non-serious AE."""
        data = _make_create()
        ae = svc.report_event(data)
        assert ae.id.startswith("AE-")
        assert ae.trial_id == EYLEA_TRIAL
        assert ae.status == AEStatus.REPORTED
        assert ae.requires_expedited_reporting is False

    def test_report_event_serious_expected(self, svc: AdverseEventService):
        """Serious + expected should NOT require expedited reporting."""
        data = _make_create(serious=True, expected=True)
        ae = svc.report_event(data)
        assert ae.serious is True
        assert ae.expected is True
        assert ae.requires_expedited_reporting is False

    def test_report_event_serious_unexpected(self, svc: AdverseEventService):
        """Serious + unexpected SHOULD require expedited reporting."""
        data = _make_create(serious=True, expected=False)
        ae = svc.report_event(data)
        assert ae.requires_expedited_reporting is True

    def test_report_event_creates_expedited_report(self, svc: AdverseEventService):
        """Serious + unexpected AE should auto-create an expedited report."""
        before_count = len(svc.get_expedited_reports())
        data = _make_create(serious=True, expected=False)
        ae = svc.report_event(data)
        after_count = len(svc.get_expedited_reports())
        assert after_count == before_count + 1

    def test_report_event_fatal_7day_deadline(self, svc: AdverseEventService):
        """Fatal + unexpected should create expedited report with 7-day deadline."""
        data = _make_create(
            serious=True,
            expected=False,
            severity=AESeverity.FATAL,
        )
        ae = svc.report_event(data)
        reports = svc.get_expedited_reports()
        matching = [r for r in reports if r.ae_id == ae.id]
        assert len(matching) == 1
        # 7-day deadline
        diff = (matching[0].due_date - ae.reported_date).days
        assert diff == 7

    def test_report_event_life_threatening_7day(self, svc: AdverseEventService):
        """Life-threatening + unexpected should have 7-day deadline."""
        data = _make_create(
            serious=True,
            expected=False,
            severity=AESeverity.LIFE_THREATENING,
        )
        ae = svc.report_event(data)
        reports = svc.get_expedited_reports()
        matching = [r for r in reports if r.ae_id == ae.id]
        assert len(matching) == 1
        diff = (matching[0].due_date - ae.reported_date).days
        assert diff == 7

    def test_report_event_severe_unexpected_15day(self, svc: AdverseEventService):
        """Severe + unexpected should have 15-day deadline."""
        data = _make_create(
            serious=True,
            expected=False,
            severity=AESeverity.SEVERE,
        )
        ae = svc.report_event(data)
        reports = svc.get_expedited_reports()
        matching = [r for r in reports if r.ae_id == ae.id]
        assert len(matching) == 1
        diff = (matching[0].due_date - ae.reported_date).days
        assert diff == 15

    def test_get_event_found(self, svc: AdverseEventService):
        """Getting an existing event should succeed."""
        ae = svc.get_event("AE-0001")
        assert ae.id == "AE-0001"

    def test_get_event_not_found(self, svc: AdverseEventService):
        """Getting a non-existent event should raise KeyError."""
        with pytest.raises(KeyError, match="not found"):
            svc.get_event("AE-NONEXISTENT")

    def test_update_event_status(self, svc: AdverseEventService):
        """Update event status with valid transition."""
        # AE-0009 is REPORTED (Fatigue)
        ae = svc.update_event("AE-0009", AEUpdate(status=AEStatus.UNDER_INVESTIGATION))
        assert ae.status == AEStatus.UNDER_INVESTIGATION

    def test_update_event_invalid_transition(self, svc: AdverseEventService):
        """Invalid status transition should raise ValueError."""
        # AE-0004 is RESOLVED, cannot go back to REPORTED
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_event("AE-0004", AEUpdate(status=AEStatus.REPORTED))

    def test_update_event_closed_is_terminal(self, svc: AdverseEventService):
        """CLOSED is terminal - no transitions allowed."""
        # First close an event
        ae = svc.update_event("AE-0009", AEUpdate(status=AEStatus.CONFIRMED))
        ae = svc.update_event("AE-0009", AEUpdate(status=AEStatus.CLOSED))
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_event("AE-0009", AEUpdate(status=AEStatus.RESOLVED))

    def test_update_event_severity(self, svc: AdverseEventService):
        """Should be able to update severity."""
        ae = svc.update_event("AE-0001", AEUpdate(severity=AESeverity.MODERATE))
        assert ae.severity == AESeverity.MODERATE

    def test_update_event_relatedness(self, svc: AdverseEventService):
        """Should be able to update relatedness."""
        ae = svc.update_event("AE-0001", AEUpdate(relatedness=AERelatedness.DEFINITE))
        assert ae.relatedness == AERelatedness.DEFINITE

    def test_update_event_description(self, svc: AdverseEventService):
        """Should be able to update description."""
        ae = svc.update_event("AE-0001", AEUpdate(description="Updated description"))
        assert ae.description == "Updated description"

    def test_update_event_not_found(self, svc: AdverseEventService):
        """Updating non-existent event should raise KeyError."""
        with pytest.raises(KeyError, match="not found"):
            svc.update_event("AE-NONE", AEUpdate(severity=AESeverity.MILD))

    def test_update_serious_recalculates_expedited(self, svc: AdverseEventService):
        """Changing serious flag should recalculate expedited requirement."""
        # AE-0001 is not serious, not requiring expedited
        ae = svc.update_event("AE-0001", AEUpdate(serious=True, expected=False))
        assert ae.requires_expedited_reporting is True

    def test_update_expected_recalculates_expedited(self, svc: AdverseEventService):
        """Changing expected flag should recalculate expedited requirement."""
        # AE-0011 is serious + expected (Pneumonitis)
        ae = svc.get_event("AE-0011")
        assert ae.serious is True
        assert ae.expected is True
        ae = svc.update_event("AE-0011", AEUpdate(expected=False))
        assert ae.requires_expedited_reporting is True

    def test_update_resolution_date(self, svc: AdverseEventService):
        """Should be able to set resolution date."""
        now = datetime.now(timezone.utc)
        ae = svc.update_event("AE-0009", AEUpdate(resolution_date=now))
        assert ae.resolution_date is not None

    def test_update_action_taken(self, svc: AdverseEventService):
        """Should be able to update action taken."""
        ae = svc.update_event("AE-0001", AEUpdate(action_taken=AEActionTaken.DOSE_REDUCED))
        assert ae.action_taken == AEActionTaken.DOSE_REDUCED

    def test_update_outcome(self, svc: AdverseEventService):
        """Should be able to update outcome."""
        ae = svc.update_event("AE-0009", AEUpdate(outcome=AEOutcome.RECOVERED))
        assert ae.outcome == AEOutcome.RECOVERED


# ===========================================================================
# Section 3: List / filter operations
# ===========================================================================


class TestListAndFilter:
    """Test list and filter operations."""

    def test_list_all_events(self, svc: AdverseEventService):
        """List all events without filters."""
        items, total = svc.list_events(limit=100)
        assert total == 14
        assert len(items) == 14

    def test_list_filter_by_trial(self, svc: AdverseEventService):
        """Filter by trial_id."""
        items, total = svc.list_events(trial_id=EYLEA_TRIAL, limit=100)
        assert total == 4
        assert all(ae.trial_id == EYLEA_TRIAL for ae in items)

    def test_list_filter_by_severity(self, svc: AdverseEventService):
        """Filter by severity."""
        items, total = svc.list_events(severity=AESeverity.SEVERE, limit=100)
        assert total > 0
        assert all(ae.severity == AESeverity.SEVERE for ae in items)

    def test_list_filter_by_status(self, svc: AdverseEventService):
        """Filter by status."""
        items, total = svc.list_events(status=AEStatus.RESOLVED, limit=100)
        assert total > 0
        assert all(ae.status == AEStatus.RESOLVED for ae in items)

    def test_list_filter_by_category(self, svc: AdverseEventService):
        """Filter by category."""
        items, total = svc.list_events(category=AECategory.OPHTHALMIC, limit=100)
        assert total > 0
        assert all(ae.category == AECategory.OPHTHALMIC for ae in items)

    def test_list_filter_by_serious(self, svc: AdverseEventService):
        """Filter by seriousness."""
        items, total = svc.list_events(serious=True, limit=100)
        assert total == 4
        assert all(ae.serious is True for ae in items)

    def test_list_filter_not_serious(self, svc: AdverseEventService):
        """Filter for non-serious events."""
        items, total = svc.list_events(serious=False, limit=100)
        assert total == 10
        assert all(ae.serious is False for ae in items)

    def test_list_pagination_limit(self, svc: AdverseEventService):
        """Pagination limit should work."""
        items, total = svc.list_events(limit=3)
        assert len(items) == 3
        assert total == 14

    def test_list_pagination_offset(self, svc: AdverseEventService):
        """Pagination offset should work."""
        items1, _ = svc.list_events(limit=5, offset=0)
        items2, _ = svc.list_events(limit=5, offset=5)
        ids1 = {ae.id for ae in items1}
        ids2 = {ae.id for ae in items2}
        assert len(ids1 & ids2) == 0  # no overlap

    def test_list_sorted_by_reported_date(self, svc: AdverseEventService):
        """Events should be sorted by reported_date descending."""
        items, _ = svc.list_events(limit=100)
        for i in range(len(items) - 1):
            assert items[i].reported_date >= items[i + 1].reported_date

    def test_list_combined_filters(self, svc: AdverseEventService):
        """Multiple filters should combine."""
        items, total = svc.list_events(
            trial_id=LIBTAYO_TRIAL,
            severity=AESeverity.SEVERE,
            limit=100,
        )
        assert total > 0
        assert all(
            ae.trial_id == LIBTAYO_TRIAL and ae.severity == AESeverity.SEVERE
            for ae in items
        )


# ===========================================================================
# Section 4: Safety signal operations
# ===========================================================================


class TestSafetySignals:
    """Test safety signal detection and management."""

    def test_list_signals_all(self, svc: AdverseEventService):
        """List all seed signals."""
        signals = svc.list_signals()
        assert len(signals) == 3

    def test_list_signals_filter_by_status(self, svc: AdverseEventService):
        """Filter signals by status."""
        signals = svc.list_signals(status=SafetySignalStatus.INVESTIGATING)
        assert len(signals) == 1
        assert signals[0].signal_term == "Anaphylaxis"

    def test_list_signals_new_status(self, svc: AdverseEventService):
        """Filter for NEW signals."""
        signals = svc.list_signals(status=SafetySignalStatus.NEW)
        assert len(signals) == 1
        assert signals[0].signal_term == "Pneumonitis"

    def test_list_signals_confirmed(self, svc: AdverseEventService):
        """Filter for CONFIRMED signals."""
        signals = svc.list_signals(status=SafetySignalStatus.CONFIRMED)
        assert len(signals) == 1
        assert signals[0].signal_term == "Conjunctivitis"

    def test_get_signal_found(self, svc: AdverseEventService):
        """Get a specific signal."""
        sig = svc.get_signal("SIG-0001")
        assert sig.signal_term == "Anaphylaxis"

    def test_get_signal_not_found(self, svc: AdverseEventService):
        """Get non-existent signal should raise KeyError."""
        with pytest.raises(KeyError, match="not found"):
            svc.get_signal("SIG-NONE")

    def test_update_signal_status(self, svc: AdverseEventService):
        """Update signal status."""
        sig = svc.update_signal_status("SIG-0002", SafetySignalStatus.INVESTIGATING, "Dr. Test")
        assert sig.status == SafetySignalStatus.INVESTIGATING
        assert sig.assessed_by == "Dr. Test"

    def test_update_signal_dismiss(self, svc: AdverseEventService):
        """Dismiss a signal."""
        sig = svc.update_signal_status("SIG-0001", SafetySignalStatus.DISMISSED, "Dr. Reviewer")
        assert sig.status == SafetySignalStatus.DISMISSED
        assert sig.assessed_by == "Dr. Reviewer"

    def test_update_signal_not_found(self, svc: AdverseEventService):
        """Updating non-existent signal should raise KeyError."""
        with pytest.raises(KeyError, match="not found"):
            svc.update_signal_status("SIG-NONE", SafetySignalStatus.DISMISSED)

    def test_detect_signals_returns_results(self, svc: AdverseEventService):
        """Signal detection should find signals when RR > 2.0."""
        detected = svc.detect_safety_signals()
        assert len(detected) > 0

    def test_detect_signals_by_trial(self, svc: AdverseEventService):
        """Signal detection scoped to a trial."""
        detected = svc.detect_safety_signals(trial_id=EYLEA_TRIAL)
        # May or may not find signals depending on population size
        assert isinstance(detected, list)

    def test_detect_signals_empty_trial(self, svc: AdverseEventService):
        """Signal detection with no events returns empty."""
        detected = svc.detect_safety_signals(trial_id="NONEXISTENT")
        assert detected == []

    def test_detect_signals_updates_existing(self, svc: AdverseEventService):
        """Repeated detection should update existing signal counts."""
        detected1 = svc.detect_safety_signals()
        detected2 = svc.detect_safety_signals()
        # Both runs should return results (updates existing signals)
        assert len(detected2) > 0


# ===========================================================================
# Section 5: Expedited reporting
# ===========================================================================


class TestExpeditedReporting:
    """Test expedited regulatory reporting."""

    def test_list_expedited_reports_all(self, svc: AdverseEventService):
        """List all expedited reports."""
        reports = svc.get_expedited_reports()
        assert len(reports) == 3

    def test_list_expedited_reports_filter_pending(self, svc: AdverseEventService):
        """Filter for pending reports."""
        reports = svc.get_expedited_reports(status=ExpeditedReportStatus.PENDING)
        assert len(reports) == 2

    def test_list_expedited_reports_filter_submitted(self, svc: AdverseEventService):
        """Filter for submitted reports."""
        reports = svc.get_expedited_reports(status=ExpeditedReportStatus.SUBMITTED)
        assert len(reports) == 1

    def test_submit_existing_pending_report(self, svc: AdverseEventService):
        """Submitting a matching pending report should mark it as submitted."""
        report = svc.submit_expedited_report(
            "AE-0007",
            ExpeditedReportType.SUSAR,
            "FDA",
        )
        assert report.status == ExpeditedReportStatus.SUBMITTED
        assert report.submitted_date is not None

    def test_submit_new_report(self, svc: AdverseEventService):
        """Submitting for an AE without matching pending creates a new report."""
        report = svc.submit_expedited_report(
            "AE-0003",
            ExpeditedReportType.CIOMS,
            "EMA",
        )
        assert report.status == ExpeditedReportStatus.SUBMITTED
        assert report.ae_id == "AE-0003"

    def test_submit_report_updates_ae(self, svc: AdverseEventService):
        """Submitting should update the AE's expedited_report_date."""
        svc.submit_expedited_report("AE-0007", ExpeditedReportType.SUSAR, "FDA")
        ae = svc.get_event("AE-0007")
        assert ae.expedited_report_date is not None

    def test_submit_report_nonexistent_ae(self, svc: AdverseEventService):
        """Submitting for non-existent AE should raise KeyError."""
        with pytest.raises(KeyError, match="not found"):
            svc.submit_expedited_report(
                "AE-NONE",
                ExpeditedReportType.IND_SAFETY,
                "FDA",
            )


# ===========================================================================
# Section 6: Causality assessment
# ===========================================================================


class TestCausalityAssessment:
    """Test the Naranjo causality assessment."""

    def test_causality_assessment_returns_result(self, svc: AdverseEventService):
        """Causality assessment should return a valid result."""
        result = svc.assess_causality("AE-0001")
        assert result.ae_id == "AE-0001"
        assert isinstance(result.total_score, int)
        assert result.classification is not None

    def test_causality_has_factors(self, svc: AdverseEventService):
        """Assessment should contain multiple factors."""
        result = svc.assess_causality("AE-0001")
        assert len(result.factors) == 9  # 9 Naranjo questions

    def test_causality_discontinued_recovered(self, svc: AdverseEventService):
        """Discontinued + recovered should score higher."""
        # AE-0007: Anaphylaxis - DISCONTINUED + RECOVERED
        result = svc.assess_causality("AE-0007")
        assert result.total_score > 0

    def test_causality_classification_mapping(self, svc: AdverseEventService):
        """Check that classification maps correctly from score."""
        result = svc.assess_causality("AE-0007")
        # Score determines classification
        if result.total_score >= 9:
            assert result.classification == AERelatedness.DEFINITE
        elif result.total_score >= 5:
            assert result.classification == AERelatedness.PROBABLE
        elif result.total_score >= 1:
            assert result.classification == AERelatedness.POSSIBLE
        else:
            assert result.classification == AERelatedness.UNLIKELY

    def test_causality_not_found(self, svc: AdverseEventService):
        """Causality for non-existent AE should raise KeyError."""
        with pytest.raises(KeyError, match="not found"):
            svc.assess_causality("AE-NONE")

    def test_causality_mild_non_serious(self, svc: AdverseEventService):
        """Mild non-serious event should have lower score."""
        # AE-0004: Headache - MILD, not serious
        result = svc.assess_causality("AE-0004")
        assert result.total_score >= 0

    def test_causality_severe_serious(self, svc: AdverseEventService):
        """Severe serious event should generally score higher."""
        # AE-0003: Endophthalmitis - SEVERE, serious
        result_severe = svc.assess_causality("AE-0003")
        # AE-0004: Headache - MILD, not serious
        result_mild = svc.assess_causality("AE-0004")
        # Severe + serious generally yields higher score
        assert result_severe.total_score >= result_mild.total_score


# ===========================================================================
# Section 7: Narrative generation
# ===========================================================================


class TestNarrativeGeneration:
    """Test MedWatch-style narrative generation."""

    def test_narrative_returns_result(self, svc: AdverseEventService):
        """Narrative generation should return a valid result."""
        result = svc.generate_narrative("AE-0001")
        assert result.ae_id == "AE-0001"
        assert len(result.narrative) > 0
        assert result.generated_at is not None

    def test_narrative_contains_patient_info(self, svc: AdverseEventService):
        """Narrative should contain patient and trial info."""
        result = svc.generate_narrative("AE-0001")
        ae = svc.get_event("AE-0001")
        assert ae.patient_id in result.narrative
        assert ae.trial_id in result.narrative

    def test_narrative_contains_event_details(self, svc: AdverseEventService):
        """Narrative should contain event term and severity."""
        result = svc.generate_narrative("AE-0001")
        ae = svc.get_event("AE-0001")
        assert ae.event_term in result.narrative
        assert ae.severity.value.lower() in result.narrative.lower()

    def test_narrative_resolved_event(self, svc: AdverseEventService):
        """Resolved event narrative should mention resolution."""
        result = svc.generate_narrative("AE-0001")
        ae = svc.get_event("AE-0001")
        if ae.resolution_date:
            assert "resolved" in result.narrative.lower()

    def test_narrative_unresolved_event(self, svc: AdverseEventService):
        """Unresolved event should state it hasn't resolved."""
        result = svc.generate_narrative("AE-0009")
        assert "not yet resolved" in result.narrative.lower()

    def test_narrative_action_taken(self, svc: AdverseEventService):
        """Narrative should mention action taken if applicable."""
        result = svc.generate_narrative("AE-0003")
        assert "interrupted" in result.narrative.lower()

    def test_narrative_serious_marker(self, svc: AdverseEventService):
        """Serious events should be labeled as such."""
        result = svc.generate_narrative("AE-0003")
        assert "serious" in result.narrative.lower()

    def test_narrative_not_found(self, svc: AdverseEventService):
        """Narrative for non-existent AE should raise KeyError."""
        with pytest.raises(KeyError, match="not found"):
            svc.generate_narrative("AE-NONE")


# ===========================================================================
# Section 8: Metrics
# ===========================================================================


class TestMetrics:
    """Test aggregated metrics computation."""

    def test_metrics_total_events(self, svc: AdverseEventService):
        """Metrics should report correct total events."""
        metrics = svc.get_metrics()
        assert metrics.total_events == 14

    def test_metrics_serious_count(self, svc: AdverseEventService):
        """Metrics should report correct serious count."""
        metrics = svc.get_metrics()
        assert metrics.serious_count == 4

    def test_metrics_by_severity(self, svc: AdverseEventService):
        """Metrics should break down by severity."""
        metrics = svc.get_metrics()
        assert len(metrics.by_severity) > 0
        assert sum(metrics.by_severity.values()) == 14

    def test_metrics_by_category(self, svc: AdverseEventService):
        """Metrics should break down by category."""
        metrics = svc.get_metrics()
        assert len(metrics.by_category) > 0
        assert sum(metrics.by_category.values()) == 14

    def test_metrics_by_trial(self, svc: AdverseEventService):
        """Metrics should break down by trial."""
        metrics = svc.get_metrics()
        assert EYLEA_TRIAL in metrics.by_trial
        assert DUPIXENT_TRIAL in metrics.by_trial
        assert LIBTAYO_TRIAL in metrics.by_trial

    def test_metrics_filtered_by_trial(self, svc: AdverseEventService):
        """Metrics filtered by trial should only count that trial."""
        metrics = svc.get_metrics(trial_id=EYLEA_TRIAL)
        assert metrics.total_events == 4
        assert len(metrics.by_trial) == 1

    def test_metrics_mean_time_to_resolution(self, svc: AdverseEventService):
        """Metrics should compute mean time to resolution."""
        metrics = svc.get_metrics()
        assert metrics.mean_time_to_resolution_days is not None
        assert metrics.mean_time_to_resolution_days > 0

    def test_metrics_empty_trial(self, svc: AdverseEventService):
        """Metrics for empty trial should return zeros."""
        metrics = svc.get_metrics(trial_id="NONEXISTENT")
        assert metrics.total_events == 0
        assert metrics.serious_count == 0
        assert metrics.mean_time_to_resolution_days is None

    def test_metrics_most_common_events(self, svc: AdverseEventService):
        """Metrics should report most common events."""
        metrics = svc.get_metrics()
        assert len(metrics.most_common_events) > 0

    def test_metrics_active_signals(self, svc: AdverseEventService):
        """Metrics should report active safety signals."""
        metrics = svc.get_metrics()
        assert metrics.active_safety_signals == 3  # All 3 seed signals are non-dismissed


# ===========================================================================
# Section 9: Category analysis
# ===========================================================================


class TestCategoryAnalysis:
    """Test category-based event queries."""

    def test_events_by_ophthalmic_category(self, svc: AdverseEventService):
        """Should return ophthalmic events."""
        events = svc.get_events_by_category(AECategory.OPHTHALMIC)
        assert len(events) > 0
        assert all(ae.category == AECategory.OPHTHALMIC for ae in events)

    def test_events_by_dermatological_category(self, svc: AdverseEventService):
        """Should return dermatological events."""
        events = svc.get_events_by_category(AECategory.DERMATOLOGICAL)
        assert len(events) > 0

    def test_events_by_empty_category(self, svc: AdverseEventService):
        """Category with no events should return empty list."""
        events = svc.get_events_by_category(AECategory.CARDIOVASCULAR)
        assert events == []

    def test_events_by_respiratory_category(self, svc: AdverseEventService):
        """Should return respiratory events."""
        events = svc.get_events_by_category(AECategory.RESPIRATORY)
        assert len(events) > 0


# ===========================================================================
# Section 10: API endpoint integration tests
# ===========================================================================


@pytest.mark.anyio
class TestAPIEndpoints:
    """Integration tests for all HTTP endpoints."""

    async def test_list_events_endpoint(self):
        """GET /events should return paginated list."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/events")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] == 14

    async def test_list_events_with_filters(self):
        """GET /events with query params should filter."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/events",
                params={"trial_id": EYLEA_TRIAL, "serious": "false"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] > 0

    async def test_list_events_pagination(self):
        """GET /events with limit and offset."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/events",
                params={"limit": 3, "offset": 0},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 3
        assert body["limit"] == 3
        assert body["offset"] == 0

    async def test_get_event_endpoint(self):
        """GET /events/{ae_id} should return single event."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/events/AE-0001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "AE-0001"

    async def test_get_event_not_found(self):
        """GET /events/{ae_id} with invalid ID should 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/events/AE-NONEXISTENT")
        assert resp.status_code == 404

    async def test_report_event_endpoint(self):
        """POST /events should create a new AE."""
        data = _make_create()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/events",
                json=data.model_dump(mode="json"),
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"].startswith("AE-")

    async def test_update_event_endpoint(self):
        """PUT /events/{ae_id} should update the AE."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/events/AE-0009",
                json={"status": "UNDER_INVESTIGATION"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "UNDER_INVESTIGATION"

    async def test_update_event_invalid_transition(self):
        """PUT /events/{ae_id} with invalid transition should 400."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/events/AE-0004",
                json={"status": "REPORTED"},
            )
        assert resp.status_code == 400

    async def test_update_event_not_found_endpoint(self):
        """PUT /events/{ae_id} with non-existent ID should 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/events/AE-NONE",
                json={"severity": "MILD"},
            )
        assert resp.status_code == 404

    async def test_causality_endpoint(self):
        """GET /events/{ae_id}/causality should return assessment."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/events/AE-0001/causality")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ae_id"] == "AE-0001"
        assert "total_score" in body
        assert "classification" in body
        assert len(body["factors"]) == 9

    async def test_causality_not_found_endpoint(self):
        """GET /events/{ae_id}/causality with invalid ID should 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/events/AE-NONE/causality")
        assert resp.status_code == 404

    async def test_narrative_endpoint(self):
        """GET /events/{ae_id}/narrative should return narrative."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/events/AE-0001/narrative")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ae_id"] == "AE-0001"
        assert len(body["narrative"]) > 0

    async def test_narrative_not_found_endpoint(self):
        """GET /events/{ae_id}/narrative with invalid ID should 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/events/AE-NONE/narrative")
        assert resp.status_code == 404

    async def test_metrics_endpoint(self):
        """GET /events/metrics should return metrics."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/events/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_events"] == 14

    async def test_metrics_with_trial_filter(self):
        """GET /events/metrics with trial_id filter."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/events/metrics",
                params={"trial_id": LIBTAYO_TRIAL},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_events"] == 5

    async def test_events_by_category_endpoint(self):
        """GET /events/by-category/{category} should return events."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/events/by-category/OPHTHALMIC")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) > 0
        assert all(e["category"] == "OPHTHALMIC" for e in body)

    async def test_list_signals_endpoint(self):
        """GET /signals should return signals."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/signals")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3

    async def test_list_signals_with_filter(self):
        """GET /signals with status filter."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/signals",
                params={"status": "NEW"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1

    async def test_get_signal_endpoint(self):
        """GET /signals/{signal_id} should return single signal."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/signals/SIG-0001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "SIG-0001"

    async def test_get_signal_not_found(self):
        """GET /signals/{signal_id} with invalid ID should 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/signals/SIG-NONE")
        assert resp.status_code == 404

    async def test_update_signal_endpoint(self):
        """PUT /signals/{signal_id} should update status."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/signals/SIG-0002",
                json={"status": "INVESTIGATING", "assessed_by": "Dr. Test"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "INVESTIGATING"
        assert body["assessed_by"] == "Dr. Test"

    async def test_update_signal_not_found_endpoint(self):
        """PUT /signals/{signal_id} with invalid ID should 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/signals/SIG-NONE",
                json={"status": "DISMISSED"},
            )
        assert resp.status_code == 404

    async def test_detect_signals_endpoint(self):
        """POST /signals/detect should run detection."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(f"{API_PREFIX}/signals/detect")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    async def test_detect_signals_with_trial_filter(self):
        """POST /signals/detect with trial_id filter."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/signals/detect",
                params={"trial_id": DUPIXENT_TRIAL},
            )
        assert resp.status_code == 200

    async def test_list_expedited_reports_endpoint(self):
        """GET /expedited-reports should return reports."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/expedited-reports")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3

    async def test_list_expedited_reports_with_filter(self):
        """GET /expedited-reports with status filter."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/expedited-reports",
                params={"status": "PENDING"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2

    async def test_submit_expedited_report_endpoint(self):
        """POST /expedited-reports/{ae_id}/submit should submit."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/expedited-reports/AE-0007/submit",
                json={
                    "report_type": "SUSAR",
                    "regulatory_body": "FDA",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "SUBMITTED"

    async def test_submit_expedited_report_not_found(self):
        """POST /expedited-reports/{ae_id}/submit with invalid AE should 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/expedited-reports/AE-NONE/submit",
                json={
                    "report_type": "IND_SAFETY",
                    "regulatory_body": "FDA",
                },
            )
        assert resp.status_code == 404


# ===========================================================================
# Section 11: Edge cases and additional coverage
# ===========================================================================


class TestEdgeCases:
    """Test edge cases for complete coverage."""

    def test_clear_and_reseed(self, svc: AdverseEventService):
        """Clear should empty all data."""
        svc.clear()
        items, total = svc.list_events(limit=100)
        assert total == 0
        signals = svc.list_signals()
        assert len(signals) == 0
        reports = svc.get_expedited_reports()
        assert len(reports) == 0

    def test_get_stats(self, svc: AdverseEventService):
        """Stats should return correct counts."""
        stats = svc.get_stats()
        assert stats["total_events"] == 14
        assert stats["total_signals"] == 3
        assert stats["total_expedited_reports"] == 3
        assert stats["service"] == "adverse_event"

    def test_report_multiple_events(self, svc: AdverseEventService):
        """Should be able to report multiple events."""
        for i in range(5):
            data = _make_create(patient_id=f"PAT-MULTI-{i}")
            ae = svc.report_event(data)
            assert ae.id.startswith("AE-")
        items, total = svc.list_events(limit=100)
        assert total == 19  # 14 seed + 5 new

    def test_status_transition_reported_to_confirmed(self, svc: AdverseEventService):
        """REPORTED -> CONFIRMED is valid."""
        ae = svc.update_event("AE-0009", AEUpdate(status=AEStatus.CONFIRMED))
        assert ae.status == AEStatus.CONFIRMED

    def test_status_transition_reported_to_closed(self, svc: AdverseEventService):
        """REPORTED -> CLOSED is valid."""
        ae = svc.update_event("AE-0009", AEUpdate(status=AEStatus.CLOSED))
        assert ae.status == AEStatus.CLOSED

    def test_status_transition_under_investigation_to_resolved(self, svc: AdverseEventService):
        """UNDER_INVESTIGATION -> RESOLVED is valid."""
        # AE-0006 is UNDER_INVESTIGATION
        ae = svc.update_event("AE-0006", AEUpdate(status=AEStatus.RESOLVED))
        assert ae.status == AEStatus.RESOLVED

    def test_status_transition_confirmed_to_closed(self, svc: AdverseEventService):
        """CONFIRMED -> CLOSED is valid."""
        # AE-0003 is CONFIRMED
        ae = svc.update_event("AE-0003", AEUpdate(status=AEStatus.CLOSED))
        assert ae.status == AEStatus.CLOSED

    def test_status_transition_resolved_to_closed(self, svc: AdverseEventService):
        """RESOLVED -> CLOSED is valid."""
        # AE-0001 is RESOLVED
        ae = svc.update_event("AE-0001", AEUpdate(status=AEStatus.CLOSED))
        assert ae.status == AEStatus.CLOSED

    def test_same_status_update_noop(self, svc: AdverseEventService):
        """Updating to the same status should succeed (no transition needed)."""
        ae = svc.update_event("AE-0009", AEUpdate(status=AEStatus.REPORTED))
        assert ae.status == AEStatus.REPORTED

    def test_multiple_expedited_submissions(self, svc: AdverseEventService):
        """Multiple submissions for same AE with different types should work."""
        svc.submit_expedited_report("AE-0003", ExpeditedReportType.IND_SAFETY, "FDA")
        svc.submit_expedited_report("AE-0003", ExpeditedReportType.CIOMS, "EMA")
        reports = svc.get_expedited_reports()
        ae_reports = [r for r in reports if r.ae_id == "AE-0003"]
        assert len(ae_reports) >= 2

    def test_expedited_compliance_rate_full(self, svc: AdverseEventService):
        """When all expedited reports are submitted, compliance should be high."""
        # Submit all pending reports
        svc.submit_expedited_report("AE-0007", ExpeditedReportType.SUSAR, "FDA")
        svc.submit_expedited_report("AE-0007", ExpeditedReportType.CIOMS, "EMA")
        metrics = svc.get_metrics()
        # Endophthalmitis (AE-0003) already submitted, Anaphylaxis (AE-0007) now submitted
        assert metrics.expedited_reporting_compliance_rate > 0

    def test_narrative_with_expedited_reporting(self, svc: AdverseEventService):
        """Narrative for event requiring expedited reporting should mention it."""
        result = svc.generate_narrative("AE-0007")
        assert "expedited" in result.narrative.lower()

    def test_narrative_discontinued_action(self, svc: AdverseEventService):
        """Narrative should mention discontinuation."""
        result = svc.generate_narrative("AE-0007")
        assert "discontinued" in result.narrative.lower()

    def test_report_event_all_categories(self, svc: AdverseEventService):
        """Should be able to create events in all categories."""
        for cat in AECategory:
            data = _make_create(category=cat, patient_id=f"PAT-CAT-{cat.value}")
            ae = svc.report_event(data)
            assert ae.category == cat

    def test_report_event_all_severities(self, svc: AdverseEventService):
        """Should be able to create events of all severities."""
        for sev in AESeverity:
            data = _make_create(severity=sev, patient_id=f"PAT-SEV-{sev.value}")
            ae = svc.report_event(data)
            assert ae.severity == sev

    def test_list_filter_severity_mild(self, svc: AdverseEventService):
        """Filter for MILD events."""
        items, total = svc.list_events(severity=AESeverity.MILD, limit=100)
        assert total > 0
        assert all(ae.severity == AESeverity.MILD for ae in items)

    def test_list_filter_severity_moderate(self, svc: AdverseEventService):
        """Filter for MODERATE events."""
        items, total = svc.list_events(severity=AESeverity.MODERATE, limit=100)
        assert total > 0
        assert all(ae.severity == AESeverity.MODERATE for ae in items)

    def test_signal_sorted_by_detected_at(self, svc: AdverseEventService):
        """Signals should be sorted by detected_at descending."""
        signals = svc.list_signals()
        for i in range(len(signals) - 1):
            assert signals[i].detected_at >= signals[i + 1].detected_at

    def test_expedited_reports_sorted_by_due_date(self, svc: AdverseEventService):
        """Expedited reports should be sorted by due_date ascending."""
        reports = svc.get_expedited_reports()
        for i in range(len(reports) - 1):
            assert reports[i].due_date <= reports[i + 1].due_date
