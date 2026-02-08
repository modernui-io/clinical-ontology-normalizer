"""Tests for Protocol Deviation Tracking (CMO-7).

Covers:
- Deviation CRUD (create, read, update, list with all filter combinations)
- Auto notification requirements by severity
- Status transition validation
- CAPA linkage
- IRB and sponsor notification recording
- Overdue notification detection
- Metrics calculation (MTR, compliance rates, per-trial breakdown)
- Trend data generation
- Impact assessment recording
- API endpoint integration tests
- Edge cases (non-existent deviation, duplicate notification, invalid transitions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.protocol_deviation import (
    DeviationCreate,
    DeviationSeverity,
    DeviationStatus,
    DeviationType,
    DeviationUpdate,
)
from app.services.protocol_deviation_service import (
    ProtocolDeviationService,
    get_protocol_deviation_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/protocol-deviations"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_service():
    """Ensure a fresh service for every test."""
    svc = get_protocol_deviation_service()
    svc.clear()
    yield svc
    svc.clear()


@pytest.fixture
def svc(clean_service) -> ProtocolDeviationService:
    """Shorthand for the clean service."""
    return clean_service


def _make_create(
    trial_id: str = EYLEA_TRIAL,
    severity: DeviationSeverity = DeviationSeverity.MINOR,
    deviation_type: DeviationType = DeviationType.VISIT_WINDOW,
    **kwargs,
) -> DeviationCreate:
    """Helper to build a DeviationCreate with defaults."""
    now = datetime.now(timezone.utc)
    defaults = dict(
        trial_id=trial_id,
        site_id="SITE-100",
        deviation_type=deviation_type,
        severity=severity,
        title="Test deviation",
        description="Test deviation description",
        date_occurred=now - timedelta(days=1),
        reported_by="Test Reporter",
    )
    defaults.update(kwargs)
    return DeviationCreate(**defaults)


def _seed_mixed(svc: ProtocolDeviationService) -> list[str]:
    """Seed a variety of deviations and return their IDs."""
    ids = []
    configs = [
        (EYLEA_TRIAL, DeviationSeverity.MINOR, DeviationType.VISIT_WINDOW),
        (EYLEA_TRIAL, DeviationSeverity.MODERATE, DeviationType.INCLUSION_CRITERIA),
        (EYLEA_TRIAL, DeviationSeverity.MAJOR, DeviationType.INFORMED_CONSENT),
        (DUPIXENT_TRIAL, DeviationSeverity.MINOR, DeviationType.DATA_COLLECTION),
        (DUPIXENT_TRIAL, DeviationSeverity.MODERATE, DeviationType.PROHIBITED_MEDICATION),
        (DUPIXENT_TRIAL, DeviationSeverity.CRITICAL, DeviationType.RANDOMIZATION_ERROR),
        (LIBTAYO_TRIAL, DeviationSeverity.MAJOR, DeviationType.SAFETY_REPORTING),
        (LIBTAYO_TRIAL, DeviationSeverity.MODERATE, DeviationType.DOSING_ERROR),
    ]
    for trial_id, severity, dtype in configs:
        rec = svc.create_deviation(_make_create(
            trial_id=trial_id,
            severity=severity,
            deviation_type=dtype,
            title=f"{dtype.value} - {severity.value}",
        ))
        ids.append(rec.id)
    return ids


# ===========================================================================
# 1. Deviation CRUD - Create
# ===========================================================================


class TestDeviationCreate:
    """Tests for create_deviation."""

    def test_create_basic(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        assert rec.id.startswith("DEV-")
        assert rec.trial_id == EYLEA_TRIAL
        assert rec.status == DeviationStatus.REPORTED
        assert rec.severity == DeviationSeverity.MINOR
        assert rec.deviation_type == DeviationType.VISIT_WINDOW
        assert rec.created_at is not None
        assert rec.updated_at is not None

    def test_create_sets_date_reported_automatically(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        assert rec.date_reported is not None
        # date_reported should be close to now
        delta = (datetime.now(timezone.utc) - rec.date_reported).total_seconds()
        assert delta < 5

    def test_create_minor_no_notifications(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.MINOR))
        assert rec.irb_notification_required is False
        assert rec.sponsor_notification_required is False

    def test_create_moderate_no_notifications(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.MODERATE))
        assert rec.irb_notification_required is False
        assert rec.sponsor_notification_required is False

    def test_create_major_irb_required(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.MAJOR))
        assert rec.irb_notification_required is True
        assert rec.sponsor_notification_required is False

    def test_create_critical_both_required(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.CRITICAL))
        assert rec.irb_notification_required is True
        assert rec.sponsor_notification_required is True

    def test_create_with_patient_id(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create(patient_id="PAT-001"))
        assert rec.patient_id == "PAT-001"

    def test_create_without_patient_id(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        assert rec.patient_id is None

    def test_create_initial_fields_are_none(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        assert rec.reviewer is None
        assert rec.root_cause is None
        assert rec.impact_assessment is None
        assert rec.capa_id is None
        assert rec.irb_notified_date is None
        assert rec.sponsor_notified_date is None
        assert rec.resolution_notes is None
        assert rec.closed_at is None


# ===========================================================================
# 2. Deviation CRUD - Read
# ===========================================================================


class TestDeviationRead:
    """Tests for get_deviation."""

    def test_get_existing(self, svc: ProtocolDeviationService):
        created = svc.create_deviation(_make_create())
        fetched = svc.get_deviation(created.id)
        assert fetched.id == created.id
        assert fetched.title == created.title

    def test_get_nonexistent(self, svc: ProtocolDeviationService):
        with pytest.raises(KeyError, match="not found"):
            svc.get_deviation("DEV-DOES-NOT-EXIST")


# ===========================================================================
# 3. Deviation CRUD - Update
# ===========================================================================


class TestDeviationUpdate:
    """Tests for update_deviation."""

    def test_update_status(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(status=DeviationStatus.UNDER_REVIEW)
        )
        assert updated.status == DeviationStatus.UNDER_REVIEW

    def test_update_reviewer(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(reviewer="Dr. Smith")
        )
        assert updated.reviewer == "Dr. Smith"

    def test_update_root_cause(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(root_cause="Training gap")
        )
        assert updated.root_cause == "Training gap"

    def test_update_resolution_notes(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.UNDER_REVIEW))
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.CONFIRMED))
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(
                status=DeviationStatus.RESOLVED,
                resolution_notes="Issue addressed",
            )
        )
        assert updated.resolution_notes == "Issue addressed"
        assert updated.status == DeviationStatus.RESOLVED

    def test_update_severity_recalculates_notifications(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.MINOR))
        assert rec.irb_notification_required is False
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(severity=DeviationSeverity.CRITICAL)
        )
        assert updated.irb_notification_required is True
        assert updated.sponsor_notification_required is True

    def test_update_nonexistent(self, svc: ProtocolDeviationService):
        with pytest.raises(KeyError, match="not found"):
            svc.update_deviation("DEV-NOPE", DeviationUpdate(reviewer="Dr. X"))

    def test_update_sets_updated_at(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        old_updated = rec.updated_at
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(reviewer="Dr. Y")
        )
        assert updated.updated_at >= old_updated

    def test_closing_sets_closed_at(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        assert rec.closed_at is None
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(status=DeviationStatus.CLOSED)
        )
        assert updated.closed_at is not None


# ===========================================================================
# 4. Status Transition Validation
# ===========================================================================


class TestStatusTransitions:
    """Tests for valid and invalid status transitions."""

    def test_reported_to_under_review(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(status=DeviationStatus.UNDER_REVIEW)
        )
        assert updated.status == DeviationStatus.UNDER_REVIEW

    def test_reported_to_closed(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(status=DeviationStatus.CLOSED)
        )
        assert updated.status == DeviationStatus.CLOSED

    def test_reported_to_confirmed_invalid(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_deviation(
                rec.id, DeviationUpdate(status=DeviationStatus.CONFIRMED)
            )

    def test_under_review_to_confirmed(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.UNDER_REVIEW))
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(status=DeviationStatus.CONFIRMED)
        )
        assert updated.status == DeviationStatus.CONFIRMED

    def test_confirmed_to_capa_required(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.UNDER_REVIEW))
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.CONFIRMED))
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(status=DeviationStatus.CAPA_REQUIRED)
        )
        assert updated.status == DeviationStatus.CAPA_REQUIRED

    def test_capa_required_to_capa_in_progress(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.UNDER_REVIEW))
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.CONFIRMED))
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.CAPA_REQUIRED))
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(status=DeviationStatus.CAPA_IN_PROGRESS)
        )
        assert updated.status == DeviationStatus.CAPA_IN_PROGRESS

    def test_capa_in_progress_to_resolved(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.UNDER_REVIEW))
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.CONFIRMED))
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.CAPA_REQUIRED))
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.CAPA_IN_PROGRESS))
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(status=DeviationStatus.RESOLVED)
        )
        assert updated.status == DeviationStatus.RESOLVED

    def test_resolved_to_closed(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.UNDER_REVIEW))
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.CONFIRMED))
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.RESOLVED))
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(status=DeviationStatus.CLOSED)
        )
        assert updated.status == DeviationStatus.CLOSED
        assert updated.closed_at is not None

    def test_closed_is_terminal(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.CLOSED))
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_deviation(
                rec.id, DeviationUpdate(status=DeviationStatus.REPORTED)
            )

    def test_reported_to_resolved_invalid(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_deviation(
                rec.id, DeviationUpdate(status=DeviationStatus.RESOLVED)
            )

    def test_same_status_is_noop(self, svc: ProtocolDeviationService):
        """Setting same status should not raise."""
        rec = svc.create_deviation(_make_create())
        updated = svc.update_deviation(
            rec.id, DeviationUpdate(status=DeviationStatus.REPORTED)
        )
        assert updated.status == DeviationStatus.REPORTED


# ===========================================================================
# 5. List / Filter
# ===========================================================================


class TestDeviationList:
    """Tests for list_deviations with filter combinations."""

    def test_list_all(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        items, total = svc.list_deviations()
        assert total == 8
        assert len(items) == 8

    def test_list_by_trial(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        items, total = svc.list_deviations(trial_id=EYLEA_TRIAL)
        assert total == 3
        assert all(r.trial_id == EYLEA_TRIAL for r in items)

    def test_list_by_severity(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        items, total = svc.list_deviations(severity=DeviationSeverity.MINOR)
        assert total == 2
        assert all(r.severity == DeviationSeverity.MINOR for r in items)

    def test_list_by_status(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        items, total = svc.list_deviations(status=DeviationStatus.REPORTED)
        assert total == 8  # all newly created are REPORTED

    def test_list_by_type(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        items, total = svc.list_deviations(deviation_type=DeviationType.VISIT_WINDOW)
        assert total == 1

    def test_list_combined_filters(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        items, total = svc.list_deviations(
            trial_id=DUPIXENT_TRIAL,
            severity=DeviationSeverity.CRITICAL,
        )
        assert total == 1
        assert items[0].deviation_type == DeviationType.RANDOMIZATION_ERROR

    def test_list_pagination(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        items_p1, total = svc.list_deviations(limit=3, offset=0)
        items_p2, _ = svc.list_deviations(limit=3, offset=3)
        assert len(items_p1) == 3
        assert len(items_p2) == 3
        assert total == 8
        # Pages should be distinct
        ids_p1 = {r.id for r in items_p1}
        ids_p2 = {r.id for r in items_p2}
        assert ids_p1.isdisjoint(ids_p2)

    def test_list_empty_result(self, svc: ProtocolDeviationService):
        items, total = svc.list_deviations(trial_id="nonexistent-trial")
        assert total == 0
        assert items == []

    def test_list_sorted_by_date_reported_desc(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        items, _ = svc.list_deviations()
        dates = [r.date_reported for r in items]
        assert dates == sorted(dates, reverse=True)


# ===========================================================================
# 6. CAPA Linkage
# ===========================================================================


class TestCAPALinkage:
    """Tests for link_capa."""

    def test_link_capa(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        updated = svc.link_capa(rec.id, "CAPA-2024-001")
        assert updated.capa_id == "CAPA-2024-001"

    def test_link_capa_nonexistent_deviation(self, svc: ProtocolDeviationService):
        with pytest.raises(KeyError, match="not found"):
            svc.link_capa("DEV-NOPE", "CAPA-001")

    def test_link_capa_overwrites_previous(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        svc.link_capa(rec.id, "CAPA-001")
        updated = svc.link_capa(rec.id, "CAPA-002")
        assert updated.capa_id == "CAPA-002"

    def test_link_capa_updates_timestamp(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        old_ts = rec.updated_at
        updated = svc.link_capa(rec.id, "CAPA-001")
        assert updated.updated_at >= old_ts


# ===========================================================================
# 7. IRB Notification
# ===========================================================================


class TestIRBNotification:
    """Tests for record_irb_notification."""

    def test_record_irb_notification(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.MAJOR))
        notified_date = datetime.now(timezone.utc)
        updated = svc.record_irb_notification(rec.id, notified_date)
        assert updated.irb_notified_date == notified_date

    def test_record_irb_nonexistent(self, svc: ProtocolDeviationService):
        with pytest.raises(KeyError, match="not found"):
            svc.record_irb_notification("DEV-NOPE", datetime.now(timezone.utc))

    def test_record_irb_overwrites(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.MAJOR))
        d1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        d2 = datetime(2025, 6, 1, tzinfo=timezone.utc)
        svc.record_irb_notification(rec.id, d1)
        updated = svc.record_irb_notification(rec.id, d2)
        assert updated.irb_notified_date == d2


# ===========================================================================
# 8. Sponsor Notification
# ===========================================================================


class TestSponsorNotification:
    """Tests for record_sponsor_notification."""

    def test_record_sponsor_notification(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.CRITICAL))
        notified_date = datetime.now(timezone.utc)
        updated = svc.record_sponsor_notification(rec.id, notified_date)
        assert updated.sponsor_notified_date == notified_date

    def test_record_sponsor_nonexistent(self, svc: ProtocolDeviationService):
        with pytest.raises(KeyError, match="not found"):
            svc.record_sponsor_notification("DEV-NOPE", datetime.now(timezone.utc))


# ===========================================================================
# 9. Impact Assessment
# ===========================================================================


class TestImpactAssessment:
    """Tests for assess_impact."""

    def test_assess_impact(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        updated = svc.assess_impact(rec.id, "No impact on patient safety")
        assert updated.impact_assessment == "No impact on patient safety"

    def test_assess_impact_nonexistent(self, svc: ProtocolDeviationService):
        with pytest.raises(KeyError, match="not found"):
            svc.assess_impact("DEV-NOPE", "text")

    def test_assess_impact_overwrites(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        svc.assess_impact(rec.id, "First assessment")
        updated = svc.assess_impact(rec.id, "Revised assessment")
        assert updated.impact_assessment == "Revised assessment"

    def test_assess_impact_updates_timestamp(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        old_ts = rec.updated_at
        updated = svc.assess_impact(rec.id, "Some impact")
        assert updated.updated_at >= old_ts


# ===========================================================================
# 10. Overdue Notifications
# ===========================================================================


class TestOverdueNotifications:
    """Tests for get_overdue_notifications."""

    def test_no_overdue_on_empty(self, svc: ProtocolDeviationService):
        overdue = svc.get_overdue_notifications()
        assert overdue == []

    def test_major_irb_overdue(self, svc: ProtocolDeviationService):
        """MAJOR deviation reported 10 days ago with no IRB notification → overdue."""
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.MAJOR))
        # Backdate the report
        with svc._lock:
            old = svc._deviations[rec.id]
            svc._deviations[rec.id] = old.model_copy(
                update={"date_reported": datetime.now(timezone.utc) - timedelta(days=10)}
            )
        overdue = svc.get_overdue_notifications()
        assert len(overdue) == 1
        assert overdue[0].id == rec.id

    def test_critical_sponsor_overdue(self, svc: ProtocolDeviationService):
        """CRITICAL deviation reported 2 days ago with no sponsor notification → overdue."""
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.CRITICAL))
        with svc._lock:
            old = svc._deviations[rec.id]
            svc._deviations[rec.id] = old.model_copy(
                update={"date_reported": datetime.now(timezone.utc) - timedelta(days=2)}
            )
        overdue = svc.get_overdue_notifications()
        assert any(d.id == rec.id for d in overdue)

    def test_notified_not_overdue(self, svc: ProtocolDeviationService):
        """Deviation with IRB notification recorded should NOT be overdue."""
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.MAJOR))
        with svc._lock:
            old = svc._deviations[rec.id]
            svc._deviations[rec.id] = old.model_copy(
                update={"date_reported": datetime.now(timezone.utc) - timedelta(days=10)}
            )
        svc.record_irb_notification(rec.id, datetime.now(timezone.utc))
        overdue = svc.get_overdue_notifications()
        assert not any(d.id == rec.id for d in overdue)

    def test_closed_not_overdue(self, svc: ProtocolDeviationService):
        """Closed deviations should NOT appear in overdue list."""
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.MAJOR))
        with svc._lock:
            old = svc._deviations[rec.id]
            svc._deviations[rec.id] = old.model_copy(
                update={
                    "date_reported": datetime.now(timezone.utc) - timedelta(days=10),
                    "status": DeviationStatus.CLOSED,
                }
            )
        overdue = svc.get_overdue_notifications()
        assert not any(d.id == rec.id for d in overdue)

    def test_minor_not_overdue(self, svc: ProtocolDeviationService):
        """MINOR severity should never trigger overdue (no notification required)."""
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.MINOR))
        with svc._lock:
            old = svc._deviations[rec.id]
            svc._deviations[rec.id] = old.model_copy(
                update={"date_reported": datetime.now(timezone.utc) - timedelta(days=30)}
            )
        overdue = svc.get_overdue_notifications()
        assert not any(d.id == rec.id for d in overdue)


# ===========================================================================
# 11. Metrics
# ===========================================================================


class TestMetrics:
    """Tests for get_metrics."""

    def test_empty_metrics(self, svc: ProtocolDeviationService):
        metrics = svc.get_metrics()
        assert metrics.total_deviations == 0
        assert metrics.by_type == {}
        assert metrics.by_severity == {}
        assert metrics.mean_time_to_resolution_days is None

    def test_metrics_totals(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        metrics = svc.get_metrics()
        assert metrics.total_deviations == 8

    def test_metrics_by_type(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        metrics = svc.get_metrics()
        assert DeviationType.VISIT_WINDOW.value in metrics.by_type
        assert metrics.by_type[DeviationType.VISIT_WINDOW.value] == 1

    def test_metrics_by_severity(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        metrics = svc.get_metrics()
        assert metrics.by_severity[DeviationSeverity.MINOR.value] == 2
        assert metrics.by_severity[DeviationSeverity.MODERATE.value] == 3
        assert metrics.by_severity[DeviationSeverity.MAJOR.value] == 2
        assert metrics.by_severity[DeviationSeverity.CRITICAL.value] == 1

    def test_metrics_by_trial(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        metrics = svc.get_metrics()
        assert metrics.by_trial[EYLEA_TRIAL] == 3
        assert metrics.by_trial[DUPIXENT_TRIAL] == 3
        assert metrics.by_trial[LIBTAYO_TRIAL] == 2

    def test_metrics_filtered_by_trial(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        metrics = svc.get_metrics(trial_id=EYLEA_TRIAL)
        assert metrics.total_deviations == 3
        assert EYLEA_TRIAL in metrics.by_trial

    def test_metrics_capa_linkage_rate(self, svc: ProtocolDeviationService):
        ids = _seed_mixed(svc)
        # Link 2 out of 8
        svc.link_capa(ids[0], "CAPA-001")
        svc.link_capa(ids[1], "CAPA-002")
        metrics = svc.get_metrics()
        assert metrics.capa_linkage_rate == pytest.approx(2 / 8, abs=0.01)

    def test_metrics_irb_compliance_rate(self, svc: ProtocolDeviationService):
        # 2 MAJOR deviations → IRB required
        # Notify only 1
        r1 = svc.create_deviation(_make_create(severity=DeviationSeverity.MAJOR))
        r2 = svc.create_deviation(_make_create(severity=DeviationSeverity.MAJOR))
        svc.record_irb_notification(r1.id, datetime.now(timezone.utc))
        metrics = svc.get_metrics()
        assert metrics.irb_notification_compliance_rate == pytest.approx(0.5, abs=0.01)

    def test_metrics_sponsor_compliance_rate(self, svc: ProtocolDeviationService):
        r1 = svc.create_deviation(_make_create(severity=DeviationSeverity.CRITICAL))
        svc.record_sponsor_notification(r1.id, datetime.now(timezone.utc))
        metrics = svc.get_metrics()
        assert metrics.sponsor_notification_compliance_rate == pytest.approx(1.0, abs=0.01)

    def test_metrics_mtr(self, svc: ProtocolDeviationService):
        """Mean time to resolution for resolved deviations."""
        rec = svc.create_deviation(_make_create())
        # Close it immediately → very small MTR
        svc.update_deviation(rec.id, DeviationUpdate(status=DeviationStatus.CLOSED))
        metrics = svc.get_metrics()
        assert metrics.mean_time_to_resolution_days is not None
        assert metrics.mean_time_to_resolution_days >= 0

    def test_metrics_no_irb_required_defaults_to_full_compliance(self, svc: ProtocolDeviationService):
        """If no deviations require IRB, compliance rate should be 1.0."""
        svc.create_deviation(_make_create(severity=DeviationSeverity.MINOR))
        metrics = svc.get_metrics()
        assert metrics.irb_notification_compliance_rate == 1.0

    def test_metrics_trends_populated(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        metrics = svc.get_metrics()
        assert len(metrics.trends) > 0


# ===========================================================================
# 12. Trends
# ===========================================================================


class TestTrends:
    """Tests for get_trends."""

    def test_trends_empty(self, svc: ProtocolDeviationService):
        trends = svc.get_trends(months=6)
        assert isinstance(trends, list)
        # Should still have month entries even if empty
        assert len(trends) > 0

    def test_trends_contains_current_month(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        trends = svc.get_trends(months=3)
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        month_keys = [t.month for t in trends]
        assert current_month in month_keys

    def test_trends_current_month_has_data(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        trends = svc.get_trends(months=1)
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        for t in trends:
            if t.month == current_month:
                assert t.count == 8

    def test_trends_by_severity(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        trends = svc.get_trends(months=1)
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        for t in trends:
            if t.month == current_month:
                assert t.by_severity.get("MINOR", 0) == 2


# ===========================================================================
# 13. Seed Demo Data
# ===========================================================================


class TestSeedDemoData:
    """Verify demo data seeding produces expected records."""

    def test_seed_populates_service(self):
        """A fresh service should have seed data."""
        svc = ProtocolDeviationService()
        items, total = svc.list_deviations()
        assert total == 8

    def test_seed_covers_all_three_trials(self):
        svc = ProtocolDeviationService()
        items, _ = svc.list_deviations()
        trial_ids = {r.trial_id for r in items}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_has_critical(self):
        svc = ProtocolDeviationService()
        items, _ = svc.list_deviations(severity=DeviationSeverity.CRITICAL)
        assert len(items) >= 1


# ===========================================================================
# 14. API Integration Tests
# ===========================================================================


@pytest.mark.anyio
class TestAPIEndpoints:
    """Integration tests for the protocol deviations API."""

    async def test_list_deviations(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/deviations")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 8
            assert len(data["items"]) == 8

    async def test_list_deviations_filter_trial(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/deviations",
                params={"trial_id": EYLEA_TRIAL},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 3

    async def test_list_deviations_filter_severity(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/deviations",
                params={"severity": "MINOR"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2

    async def test_list_deviations_filter_status(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/deviations",
                params={"status": "REPORTED"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 8

    async def test_list_deviations_filter_type(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/deviations",
                params={"deviation_type": "VISIT_WINDOW"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1

    async def test_list_deviations_pagination(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/deviations",
                params={"limit": 3, "offset": 0},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["items"]) == 3
            assert data["total"] == 8

    async def test_get_deviation_detail(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/deviations/{rec.id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == rec.id

    async def test_get_deviation_not_found(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/deviations/DEV-NOPE")
            assert resp.status_code == 404

    async def test_create_deviation_api(self):
        now = datetime.now(timezone.utc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/deviations",
                json={
                    "trial_id": EYLEA_TRIAL,
                    "site_id": "SITE-100",
                    "deviation_type": "VISIT_WINDOW",
                    "severity": "MINOR",
                    "title": "API created",
                    "description": "Created via API test",
                    "date_occurred": now.isoformat(),
                    "reported_by": "API Tester",
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["id"].startswith("DEV-")
            assert data["status"] == "REPORTED"

    async def test_update_deviation_api(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/deviations/{rec.id}",
                json={"status": "UNDER_REVIEW", "reviewer": "Dr. API"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "UNDER_REVIEW"
            assert data["reviewer"] == "Dr. API"

    async def test_update_deviation_invalid_transition(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/deviations/{rec.id}",
                json={"status": "RESOLVED"},
            )
            assert resp.status_code == 422

    async def test_update_deviation_not_found(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/deviations/DEV-NOPE",
                json={"reviewer": "Dr. X"},
            )
            assert resp.status_code == 404

    async def test_link_capa_api(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/deviations/{rec.id}/link-capa",
                json={"capa_id": "CAPA-API-001"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["capa_id"] == "CAPA-API-001"

    async def test_link_capa_not_found(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/deviations/DEV-NOPE/link-capa",
                json={"capa_id": "CAPA-001"},
            )
            assert resp.status_code == 404

    async def test_irb_notification_api(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.MAJOR))
        now = datetime.now(timezone.utc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/deviations/{rec.id}/irb-notification",
                json={"notified_date": now.isoformat()},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["irb_notified_date"] is not None

    async def test_irb_notification_not_found(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/deviations/DEV-NOPE/irb-notification",
                json={"notified_date": datetime.now(timezone.utc).isoformat()},
            )
            assert resp.status_code == 404

    async def test_sponsor_notification_api(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.CRITICAL))
        now = datetime.now(timezone.utc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/deviations/{rec.id}/sponsor-notification",
                json={"notified_date": now.isoformat()},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["sponsor_notified_date"] is not None

    async def test_sponsor_notification_not_found(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/deviations/DEV-NOPE/sponsor-notification",
                json={"notified_date": datetime.now(timezone.utc).isoformat()},
            )
            assert resp.status_code == 404

    async def test_impact_assessment_api(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/deviations/{rec.id}/impact-assessment",
                json={"impact_text": "No safety impact"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["impact_assessment"] == "No safety impact"

    async def test_impact_assessment_not_found(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/deviations/DEV-NOPE/impact-assessment",
                json={"impact_text": "text"},
            )
            assert resp.status_code == 404

    async def test_metrics_api(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/deviations/metrics")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_deviations"] == 8

    async def test_metrics_api_with_trial_filter(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/deviations/metrics",
                params={"trial_id": EYLEA_TRIAL},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_deviations"] == 3

    async def test_trends_api(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/deviations/trends",
                params={"months": 3},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) > 0

    async def test_overdue_notifications_api(self, svc: ProtocolDeviationService):
        # Create an overdue deviation
        rec = svc.create_deviation(_make_create(severity=DeviationSeverity.MAJOR))
        with svc._lock:
            old = svc._deviations[rec.id]
            svc._deviations[rec.id] = old.model_copy(
                update={"date_reported": datetime.now(timezone.utc) - timedelta(days=10)}
            )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/deviations/overdue-notifications")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) >= 1


# ===========================================================================
# 15. Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Edge case and boundary tests."""

    def test_clear_empties_all(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        svc.clear()
        items, total = svc.list_deviations()
        assert total == 0

    def test_get_stats(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        stats = svc.get_stats()
        assert stats["total_deviations"] == 8
        assert stats["service"] == "protocol_deviation"

    def test_multiple_creates_unique_ids(self, svc: ProtocolDeviationService):
        ids = set()
        for _ in range(20):
            rec = svc.create_deviation(_make_create())
            ids.add(rec.id)
        assert len(ids) == 20

    def test_update_with_no_changes(self, svc: ProtocolDeviationService):
        rec = svc.create_deviation(_make_create())
        # Empty update should succeed
        updated = svc.update_deviation(rec.id, DeviationUpdate())
        assert updated.id == rec.id

    def test_list_offset_beyond_total(self, svc: ProtocolDeviationService):
        _seed_mixed(svc)
        items, total = svc.list_deviations(offset=100)
        assert total == 8
        assert items == []

    def test_create_all_deviation_types(self, svc: ProtocolDeviationService):
        """Ensure every deviation type can be created."""
        for dtype in DeviationType:
            rec = svc.create_deviation(_make_create(deviation_type=dtype))
            assert rec.deviation_type == dtype

    def test_create_all_severities(self, svc: ProtocolDeviationService):
        """Ensure every severity can be created."""
        for sev in DeviationSeverity:
            rec = svc.create_deviation(_make_create(severity=sev))
            assert rec.severity == sev
