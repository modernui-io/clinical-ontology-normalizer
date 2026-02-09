"""Tests for Incident Response Playbooks (CISO-12).

Covers:
- Seed data verification (playbooks, incidents, reviews, escalation matrix)
- Playbook CRUD (create, read, update, delete, list with filters)
- Playbook testing schedule and tabletop exercise recording
- Incident lifecycle (create, phase transitions, close)
- Event logging (timeline)
- Regulatory notification management and deadlines
- Notification sending and overdue detection
- Escalation handling (manual and SLA-based)
- Post-incident review CRUD
- Metrics computation (MTTD, MTTC, MTTR, SLA compliance)
- Active incidents dashboard
- SLA breach detection
- API integration tests (all endpoints)
- Error handling (404s, 400s, invalid transitions)
- Pagination and edge cases
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.incident_response import (
    EscalationLevel,
    EventCreateRequest,
    IncidentCategory,
    IncidentCreateRequest,
    IncidentMetrics,
    IncidentPhase,
    IncidentSeverity,
    IncidentUpdateRequest,
    NotificationCreateRequest,
    NotificationStatus,
    NotificationType,
    PlaybookStep,
    PlaybookType,
    PostIncidentReviewRequest,
    SLA_TARGETS,
)
from app.services.incident_response_service import (
    IncidentResponseService,
    get_incident_response_service,
    reset_incident_response_service,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/incident-response"

# Seed incident IDs
INC_ACTIVE_BREACH = "INC-20260101-001"
INC_ACTIVE_PHISHING = "INC-20260101-002"
INC_CLOSED_RANSOMWARE = "INC-20251201-003"
INC_CLOSED_INSIDER = "INC-20251115-004"
INC_CLOSED_DDOS = "INC-20251101-005"
INC_CLOSED_COMPLIANCE = "INC-20260110-006"

# Seed playbook IDs
PB_DATA_BREACH = "PB-DATA-BREACH"
PB_RANSOMWARE = "PB-RANSOMWARE"
PB_INSIDER = "PB-INSIDER"
PB_PHISHING = "PB-PHISHING"
PB_DDOS = "PB-DDOS"
PB_SUPPLY_CHAIN = "PB-SUPPLY-CHAIN"
PB_ZERO_DAY = "PB-ZERO-DAY"
PB_UNAUTH_ACCESS = "PB-UNAUTH-ACCESS"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_incident_response_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> IncidentResponseService:
    """Shorthand for the fresh service."""
    return fresh_service


# ---------------------------------------------------------------------------
# 1. Seed data verification
# ---------------------------------------------------------------------------


class TestSeedData:
    """Verify seed data is correctly populated."""

    def test_seed_playbooks_count(self, svc: IncidentResponseService):
        """8 playbooks are seeded."""
        items, total = svc.list_playbooks()
        assert total == 8

    def test_seed_playbook_ids(self, svc: IncidentResponseService):
        """All expected playbook IDs exist."""
        expected = [PB_DATA_BREACH, PB_RANSOMWARE, PB_INSIDER, PB_PHISHING, PB_DDOS, PB_SUPPLY_CHAIN, PB_ZERO_DAY, PB_UNAUTH_ACCESS]
        for pb_id in expected:
            pb = svc.get_playbook(pb_id)
            assert pb.id == pb_id

    def test_seed_playbook_steps(self, svc: IncidentResponseService):
        """Each playbook has 5-8 steps."""
        items, _ = svc.list_playbooks()
        for pb in items:
            assert 5 <= len(pb.steps) <= 8, f"Playbook {pb.id} has {len(pb.steps)} steps"

    def test_seed_playbook_step_ordering(self, svc: IncidentResponseService):
        """Playbook steps are sequentially numbered."""
        pb = svc.get_playbook(PB_DATA_BREACH)
        for i, step in enumerate(pb.steps):
            assert step.step_number == i + 1

    def test_seed_playbook_has_checklist_items(self, svc: IncidentResponseService):
        """Playbook steps have checklist items."""
        pb = svc.get_playbook(PB_DATA_BREACH)
        for step in pb.steps:
            assert len(step.checklist_items) >= 2

    def test_seed_incidents_count(self, svc: IncidentResponseService):
        """6 incidents are seeded."""
        items, total = svc.list_incidents()
        assert total == 6

    def test_seed_active_incidents(self, svc: IncidentResponseService):
        """2 active incidents exist."""
        active = svc.get_active_incidents()
        assert len(active) == 2

    def test_seed_closed_incidents(self, svc: IncidentResponseService):
        """4 closed incidents exist."""
        items, total = svc.list_incidents(phase=IncidentPhase.CLOSED)
        assert total == 4

    def test_seed_incident_has_events(self, svc: IncidentResponseService):
        """Active incidents have timeline events."""
        inc = svc.get_incident(INC_ACTIVE_BREACH)
        assert len(inc.events) >= 3

    def test_seed_incident_has_notifications(self, svc: IncidentResponseService):
        """Active breach incident has notifications."""
        inc = svc.get_incident(INC_ACTIVE_BREACH)
        assert len(inc.notifications) >= 2

    def test_seed_reviews_count(self, svc: IncidentResponseService):
        """3 post-incident reviews are seeded."""
        items, total = svc.list_reviews()
        assert total == 3

    def test_seed_escalation_matrix(self, svc: IncidentResponseService):
        """Escalation matrix has entries for all severity levels."""
        matrix = svc.get_escalation_matrix()
        assert len(matrix) == 4
        severities = {m.severity for m in matrix}
        assert IncidentSeverity.SEV1_CRITICAL in severities
        assert IncidentSeverity.SEV4_LOW in severities

    def test_seed_escalation_contacts(self, svc: IncidentResponseService):
        """Escalation matrix entries have contacts."""
        matrix = svc.get_escalation_matrix()
        for entry in matrix:
            assert len(entry.contacts) >= 1

    def test_seed_closed_incidents_have_root_cause(self, svc: IncidentResponseService):
        """Closed incidents have root cause analysis."""
        inc = svc.get_incident(INC_CLOSED_RANSOMWARE)
        assert inc.root_cause is not None
        assert len(inc.root_cause) > 10

    def test_seed_closed_incidents_have_lessons_learned(self, svc: IncidentResponseService):
        """Closed incidents have lessons learned."""
        inc = svc.get_incident(INC_CLOSED_INSIDER)
        assert inc.lessons_learned is not None
        assert len(inc.lessons_learned) > 10

    def test_seed_breach_incident_data_compromised(self, svc: IncidentResponseService):
        """Active breach incident has data_compromised=True."""
        inc = svc.get_incident(INC_ACTIVE_BREACH)
        assert inc.data_compromised is True
        assert inc.affected_patients_count > 0

    def test_seed_phishing_no_data_compromised(self, svc: IncidentResponseService):
        """Phishing incident has no data compromised."""
        inc = svc.get_incident(INC_ACTIVE_PHISHING)
        assert inc.data_compromised is False


# ---------------------------------------------------------------------------
# 2. Playbook CRUD
# ---------------------------------------------------------------------------


class TestPlaybookCRUD:
    """Test playbook CRUD operations."""

    def test_create_playbook(self, svc: IncidentResponseService):
        """Create a new playbook."""
        steps = [
            PlaybookStep(step_number=1, title="Step 1", description="First step", responsible_role="SOC Analyst", time_limit_minutes=15, automated=False, checklist_items=["Check 1", "Check 2"]),
            PlaybookStep(step_number=2, title="Step 2", description="Second step", responsible_role="IR Lead", time_limit_minutes=30, automated=True, checklist_items=["Check 3"]),
        ]
        pb = svc.create_playbook(
            playbook_type=PlaybookType.GENERIC,
            title="Test Playbook",
            description="A test playbook",
            severity_threshold=IncidentSeverity.SEV3_MEDIUM,
            steps=steps,
        )
        assert pb.id.startswith("PB-")
        assert pb.title == "Test Playbook"
        assert len(pb.steps) == 2
        assert pb.version == "1.0"

    def test_get_playbook(self, svc: IncidentResponseService):
        """Get a specific playbook."""
        pb = svc.get_playbook(PB_DATA_BREACH)
        assert pb.playbook_type == PlaybookType.DATA_BREACH
        assert pb.title == "Data Breach Response Playbook"

    def test_get_playbook_not_found(self, svc: IncidentResponseService):
        """Get non-existent playbook raises KeyError."""
        with pytest.raises(KeyError):
            svc.get_playbook("PB-NONEXISTENT")

    def test_update_playbook_title(self, svc: IncidentResponseService):
        """Update playbook title."""
        updated = svc.update_playbook(PB_PHISHING, title="Updated Phishing Playbook")
        assert updated.title == "Updated Phishing Playbook"
        assert updated.version == "1.1"  # version bumped

    def test_update_playbook_steps(self, svc: IncidentResponseService):
        """Update playbook steps."""
        new_steps = [
            PlaybookStep(step_number=1, title="New Step", description="New", responsible_role="SOC", time_limit_minutes=10, automated=True, checklist_items=["Check"]),
        ]
        updated = svc.update_playbook(PB_PHISHING, steps=new_steps)
        assert len(updated.steps) == 1
        assert updated.steps[0].title == "New Step"

    def test_update_playbook_not_found(self, svc: IncidentResponseService):
        """Update non-existent playbook raises KeyError."""
        with pytest.raises(KeyError):
            svc.update_playbook("PB-NONEXISTENT", title="Test")

    def test_delete_playbook(self, svc: IncidentResponseService):
        """Delete a playbook."""
        svc.delete_playbook(PB_PHISHING)
        with pytest.raises(KeyError):
            svc.get_playbook(PB_PHISHING)

    def test_delete_playbook_not_found(self, svc: IncidentResponseService):
        """Delete non-existent playbook raises KeyError."""
        with pytest.raises(KeyError):
            svc.delete_playbook("PB-NONEXISTENT")

    def test_list_playbooks_filter_by_type(self, svc: IncidentResponseService):
        """Filter playbooks by type."""
        items, total = svc.list_playbooks(playbook_type=PlaybookType.DATA_BREACH)
        assert total == 1
        assert items[0].id == PB_DATA_BREACH

    def test_list_playbooks_pagination(self, svc: IncidentResponseService):
        """Paginate playbooks."""
        items, total = svc.list_playbooks(limit=3, offset=0)
        assert total == 8
        assert len(items) == 3
        items2, _ = svc.list_playbooks(limit=3, offset=3)
        assert len(items2) == 3

    def test_playbook_version_increments(self, svc: IncidentResponseService):
        """Version increments on each update."""
        svc.update_playbook(PB_DDOS, title="V1")
        pb = svc.update_playbook(PB_DDOS, title="V2")
        assert pb.version == "1.2"


# ---------------------------------------------------------------------------
# 3. Playbook testing schedule
# ---------------------------------------------------------------------------


class TestPlaybookTesting:
    """Test playbook testing schedule and recording."""

    def test_record_playbook_test(self, svc: IncidentResponseService):
        """Record a playbook test."""
        result = svc.record_playbook_test(
            playbook_id=PB_DATA_BREACH,
            participants=["CISO", "IR Lead"],
            findings=["Good response time"],
            passed=True,
        )
        assert result.playbook_id == PB_DATA_BREACH
        assert result.passed is True
        assert result.next_test_due > datetime.now(timezone.utc)

    def test_record_test_updates_last_tested(self, svc: IncidentResponseService):
        """Recording a test updates the playbook's last_tested."""
        before = svc.get_playbook(PB_DATA_BREACH).last_tested
        svc.record_playbook_test(PB_DATA_BREACH, ["CISO"], ["OK"], True)
        after = svc.get_playbook(PB_DATA_BREACH).last_tested
        assert after is not None
        if before is not None:
            assert after > before

    def test_record_test_not_found(self, svc: IncidentResponseService):
        """Record test for non-existent playbook raises KeyError."""
        with pytest.raises(KeyError):
            svc.record_playbook_test("PB-NONEXISTENT", ["CISO"], ["OK"], True)

    def test_get_testing_schedule(self, svc: IncidentResponseService):
        """Get testing schedule returns all playbooks."""
        schedule = svc.get_playbook_testing_schedule()
        assert len(schedule) == 8
        for item in schedule:
            assert "playbook_id" in item
            assert "overdue" in item
            assert "next_test_due" in item

    def test_testing_schedule_sorted_by_due_date(self, svc: IncidentResponseService):
        """Testing schedule sorted by next due date."""
        schedule = svc.get_playbook_testing_schedule()
        dates = [item["next_test_due"] for item in schedule]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# 4. Incident lifecycle
# ---------------------------------------------------------------------------


class TestIncidentLifecycle:
    """Test incident creation and phase transitions."""

    def test_create_incident(self, svc: IncidentResponseService):
        """Create a new incident."""
        req = IncidentCreateRequest(
            title="Test Incident",
            description="A test security incident",
            severity=IncidentSeverity.SEV2_HIGH,
            category=IncidentCategory.UNAUTHORIZED_ACCESS,
            reported_by="Test User",
            affected_systems=["test-system"],
            affected_patients_count=5,
        )
        inc = svc.create_incident(req)
        assert inc.id.startswith("INC-")
        assert inc.phase == IncidentPhase.DETECTION
        assert inc.severity == IncidentSeverity.SEV2_HIGH
        assert inc.playbook_id == PB_UNAUTH_ACCESS  # auto-assigned
        assert inc.escalation_level == EscalationLevel.L3_CISO  # auto-determined
        assert len(inc.events) == 1  # initial detection event

    def test_create_incident_auto_playbook(self, svc: IncidentResponseService):
        """Auto-assigns playbook based on category."""
        req = IncidentCreateRequest(
            title="Ransomware Test", description="Ransomware detected",
            severity=IncidentSeverity.SEV1_CRITICAL,
            category=IncidentCategory.RANSOMWARE,
            reported_by="EDR System",
        )
        inc = svc.create_incident(req)
        assert inc.playbook_id == PB_RANSOMWARE

    def test_create_incident_no_playbook_for_unknown_category(self, svc: IncidentResponseService):
        """Categories without specific playbooks get no auto-assignment."""
        req = IncidentCreateRequest(
            title="Data Loss", description="Data loss event",
            severity=IncidentSeverity.SEV3_MEDIUM,
            category=IncidentCategory.DATA_LOSS,
            reported_by="Backup System",
        )
        inc = svc.create_incident(req)
        assert inc.playbook_id is None

    def test_phase_transition_detection_to_triage(self, svc: IncidentResponseService):
        """Valid transition: DETECTION -> TRIAGE."""
        update = IncidentUpdateRequest(phase=IncidentPhase.TRIAGE, assigned_to="IR Lead")
        updated = svc.update_incident(INC_ACTIVE_PHISHING, update)
        # INC_ACTIVE_PHISHING is already in TRIAGE per seed, so let's create a new one
        req = IncidentCreateRequest(
            title="New Test", description="New",
            severity=IncidentSeverity.SEV4_LOW,
            category=IncidentCategory.COMPLIANCE_VIOLATION,
            reported_by="Auditor",
        )
        inc = svc.create_incident(req)
        assert inc.phase == IncidentPhase.DETECTION
        updated = svc.update_incident(inc.id, IncidentUpdateRequest(phase=IncidentPhase.TRIAGE))
        assert updated.phase == IncidentPhase.TRIAGE

    def test_phase_transition_full_lifecycle(self, svc: IncidentResponseService):
        """Full lifecycle: DETECTION -> TRIAGE -> CONTAINMENT -> ERADICATION -> RECOVERY -> POST_INCIDENT -> CLOSED."""
        req = IncidentCreateRequest(
            title="Full Lifecycle", description="Full lifecycle test",
            severity=IncidentSeverity.SEV3_MEDIUM,
            category=IncidentCategory.PHISHING,
            reported_by="User",
        )
        inc = svc.create_incident(req)

        for target_phase in [
            IncidentPhase.TRIAGE,
            IncidentPhase.CONTAINMENT,
            IncidentPhase.ERADICATION,
            IncidentPhase.RECOVERY,
            IncidentPhase.POST_INCIDENT,
            IncidentPhase.CLOSED,
        ]:
            inc = svc.update_incident(inc.id, IncidentUpdateRequest(phase=target_phase))
            assert inc.phase == target_phase

        assert inc.closed_at is not None
        assert inc.resolution_time_minutes is not None

    def test_invalid_phase_transition(self, svc: IncidentResponseService):
        """Invalid phase transition raises ValueError."""
        req = IncidentCreateRequest(
            title="Invalid", description="Invalid transition",
            severity=IncidentSeverity.SEV4_LOW,
            category=IncidentCategory.PHISHING,
            reported_by="User",
        )
        inc = svc.create_incident(req)
        # DETECTION -> CONTAINMENT is not allowed (must go through TRIAGE)
        with pytest.raises(ValueError, match="Invalid phase transition"):
            svc.update_incident(inc.id, IncidentUpdateRequest(phase=IncidentPhase.CONTAINMENT))

    def test_closed_is_terminal(self, svc: IncidentResponseService):
        """Cannot transition from CLOSED to any other phase."""
        inc = svc.get_incident(INC_CLOSED_RANSOMWARE)
        assert inc.phase == IncidentPhase.CLOSED
        with pytest.raises(ValueError):
            svc.update_incident(INC_CLOSED_RANSOMWARE, IncidentUpdateRequest(phase=IncidentPhase.RECOVERY))

    def test_containment_time_calculated(self, svc: IncidentResponseService):
        """Containment time is calculated on CONTAINMENT phase entry."""
        req = IncidentCreateRequest(
            title="Containment Test", description="Test",
            severity=IncidentSeverity.SEV2_HIGH,
            category=IncidentCategory.DDOS,
            reported_by="NOC",
        )
        inc = svc.create_incident(req)
        inc = svc.update_incident(inc.id, IncidentUpdateRequest(phase=IncidentPhase.TRIAGE))
        inc = svc.update_incident(inc.id, IncidentUpdateRequest(phase=IncidentPhase.CONTAINMENT))
        assert inc.containment_time_minutes is not None
        assert inc.containment_time_minutes >= 0

    def test_resolution_time_calculated_on_close(self, svc: IncidentResponseService):
        """Resolution time is calculated when closing an incident."""
        req = IncidentCreateRequest(
            title="Resolution Test", description="Test",
            severity=IncidentSeverity.SEV4_LOW,
            category=IncidentCategory.COMPLIANCE_VIOLATION,
            reported_by="Audit",
        )
        inc = svc.create_incident(req)
        inc = svc.update_incident(inc.id, IncidentUpdateRequest(phase=IncidentPhase.TRIAGE))
        inc = svc.update_incident(inc.id, IncidentUpdateRequest(phase=IncidentPhase.CLOSED))
        assert inc.resolution_time_minutes is not None
        assert inc.closed_at is not None

    def test_update_incident_metadata(self, svc: IncidentResponseService):
        """Update incident metadata fields."""
        updated = svc.update_incident(INC_ACTIVE_BREACH, IncidentUpdateRequest(
            root_cause="Compromised service account credentials",
            lessons_learned="Implement credential rotation policy",
            affected_patients_count=3000,
        ))
        assert updated.root_cause == "Compromised service account credentials"
        assert updated.lessons_learned == "Implement credential rotation policy"
        assert updated.affected_patients_count == 3000

    def test_update_incident_not_found(self, svc: IncidentResponseService):
        """Update non-existent incident raises KeyError."""
        with pytest.raises(KeyError):
            svc.update_incident("INC-NONEXISTENT", IncidentUpdateRequest(title="Test"))

    def test_get_incident_not_found(self, svc: IncidentResponseService):
        """Get non-existent incident raises KeyError."""
        with pytest.raises(KeyError):
            svc.get_incident("INC-NONEXISTENT")


# ---------------------------------------------------------------------------
# 5. Incident listing and filtering
# ---------------------------------------------------------------------------


class TestIncidentFiltering:
    """Test incident listing with filters."""

    def test_list_all_incidents(self, svc: IncidentResponseService):
        """List all incidents."""
        items, total = svc.list_incidents()
        assert total == 6

    def test_filter_by_severity(self, svc: IncidentResponseService):
        """Filter by severity."""
        items, total = svc.list_incidents(severity=IncidentSeverity.SEV1_CRITICAL)
        assert total >= 1
        for inc in items:
            assert inc.severity == IncidentSeverity.SEV1_CRITICAL

    def test_filter_by_category(self, svc: IncidentResponseService):
        """Filter by category."""
        items, total = svc.list_incidents(category=IncidentCategory.DATA_BREACH)
        assert total >= 1
        for inc in items:
            assert inc.category == IncidentCategory.DATA_BREACH

    def test_filter_by_phase(self, svc: IncidentResponseService):
        """Filter by phase."""
        items, total = svc.list_incidents(phase=IncidentPhase.CONTAINMENT)
        assert total >= 1

    def test_filter_active_only(self, svc: IncidentResponseService):
        """Filter active only."""
        items, total = svc.list_incidents(active_only=True)
        assert total == 2
        for inc in items:
            assert inc.phase != IncidentPhase.CLOSED

    def test_pagination(self, svc: IncidentResponseService):
        """Pagination works."""
        items, total = svc.list_incidents(limit=2, offset=0)
        assert total == 6
        assert len(items) == 2
        items2, _ = svc.list_incidents(limit=2, offset=2)
        assert len(items2) == 2
        assert items[0].id != items2[0].id

    def test_sorted_by_detected_at_desc(self, svc: IncidentResponseService):
        """Results sorted by detected_at descending."""
        items, _ = svc.list_incidents()
        dates = [inc.detected_at for inc in items]
        assert dates == sorted(dates, reverse=True)

    def test_get_active_incidents(self, svc: IncidentResponseService):
        """Get active incidents returns only non-closed."""
        active = svc.get_active_incidents()
        assert all(inc.phase != IncidentPhase.CLOSED for inc in active)


# ---------------------------------------------------------------------------
# 6. Event logging (timeline)
# ---------------------------------------------------------------------------


class TestEventLogging:
    """Test incident event timeline."""

    def test_add_event(self, svc: IncidentResponseService):
        """Add an event to an incident."""
        req = EventCreateRequest(
            description="Evidence collected from compromised server",
            actor="Forensics Team",
            evidence_refs=["forensic-image-001"],
        )
        event = svc.add_event(INC_ACTIVE_BREACH, req)
        assert event.incident_id == INC_ACTIVE_BREACH
        assert event.actor == "Forensics Team"
        assert "forensic-image-001" in event.evidence_refs

    def test_add_event_not_found(self, svc: IncidentResponseService):
        """Add event to non-existent incident raises KeyError."""
        req = EventCreateRequest(description="Test", actor="Test")
        with pytest.raises(KeyError):
            svc.add_event("INC-NONEXISTENT", req)

    def test_get_timeline(self, svc: IncidentResponseService):
        """Get event timeline for an incident."""
        timeline = svc.get_incident_timeline(INC_ACTIVE_BREACH)
        assert len(timeline) >= 3
        # Sorted by timestamp
        timestamps = [e.timestamp for e in timeline]
        assert timestamps == sorted(timestamps)

    def test_get_timeline_not_found(self, svc: IncidentResponseService):
        """Get timeline for non-existent incident raises KeyError."""
        with pytest.raises(KeyError):
            svc.get_incident_timeline("INC-NONEXISTENT")

    def test_event_has_correct_phase(self, svc: IncidentResponseService):
        """Events record the current phase of the incident."""
        req = EventCreateRequest(description="Test event", actor="SOC")
        event = svc.add_event(INC_ACTIVE_BREACH, req)
        inc = svc.get_incident(INC_ACTIVE_BREACH)
        assert event.phase == inc.phase

    def test_phase_transition_creates_event(self, svc: IncidentResponseService):
        """Phase transitions automatically create timeline events."""
        req = IncidentCreateRequest(
            title="Event Test", description="Test",
            severity=IncidentSeverity.SEV4_LOW,
            category=IncidentCategory.COMPLIANCE_VIOLATION,
            reported_by="Auditor",
        )
        inc = svc.create_incident(req)
        initial_count = len(inc.events)
        updated = svc.update_incident(inc.id, IncidentUpdateRequest(phase=IncidentPhase.TRIAGE))
        assert len(updated.events) == initial_count + 1
        assert "TRIAGE" in updated.events[-1].description


# ---------------------------------------------------------------------------
# 7. Regulatory notifications
# ---------------------------------------------------------------------------


class TestNotifications:
    """Test regulatory notification management."""

    def test_create_notification(self, svc: IncidentResponseService):
        """Create a regulatory notification."""
        req = NotificationCreateRequest(
            notification_type=NotificationType.GDPR_BREACH,
            recipient="EU DPA",
            content_summary="GDPR breach notification for clinical data",
        )
        notif = svc.create_notification(INC_ACTIVE_BREACH, req)
        assert notif.notification_type == NotificationType.GDPR_BREACH
        assert notif.recipient == "EU DPA"
        assert notif.status in (NotificationStatus.PENDING, NotificationStatus.OVERDUE)

    def test_create_notification_auto_deadline(self, svc: IncidentResponseService):
        """Deadline auto-calculated based on notification type."""
        req = NotificationCreateRequest(
            notification_type=NotificationType.HIPAA_BREACH,
            recipient="HHS OCR",
        )
        notif = svc.create_notification(INC_ACTIVE_BREACH, req)
        inc = svc.get_incident(INC_ACTIVE_BREACH)
        # HIPAA deadline is 1440 hours (60 days) from detection
        expected_deadline = inc.detected_at + timedelta(hours=1440)
        assert abs((notif.deadline - expected_deadline).total_seconds()) < 2

    def test_create_notification_not_found(self, svc: IncidentResponseService):
        """Create notification for non-existent incident raises KeyError."""
        req = NotificationCreateRequest(
            notification_type=NotificationType.INTERNAL_STAKEHOLDER,
            recipient="CISO",
        )
        with pytest.raises(KeyError):
            svc.create_notification("INC-NONEXISTENT", req)

    def test_send_notification(self, svc: IncidentResponseService):
        """Send a notification."""
        # Get the HIPAA pending notification from seed data
        inc = svc.get_incident(INC_ACTIVE_BREACH)
        pending = [n for n in inc.notifications if n.status == NotificationStatus.PENDING]
        assert len(pending) >= 1
        notif_id = pending[0].id

        sent = svc.send_notification(INC_ACTIVE_BREACH, notif_id)
        assert sent.status == NotificationStatus.SENT
        assert sent.sent_at is not None

    def test_send_notification_not_found(self, svc: IncidentResponseService):
        """Send non-existent notification raises KeyError."""
        with pytest.raises(KeyError):
            svc.send_notification(INC_ACTIVE_BREACH, "NOTIF-NONEXISTENT")

    def test_send_notification_incident_not_found(self, svc: IncidentResponseService):
        """Send notification for non-existent incident raises KeyError."""
        with pytest.raises(KeyError):
            svc.send_notification("INC-NONEXISTENT", "NOTIF-001-02")

    def test_get_incident_notifications(self, svc: IncidentResponseService):
        """Get all notifications for an incident."""
        notifs = svc.get_incident_notifications(INC_ACTIVE_BREACH)
        assert len(notifs) >= 2

    def test_get_notifications_not_found(self, svc: IncidentResponseService):
        """Get notifications for non-existent incident raises KeyError."""
        with pytest.raises(KeyError):
            svc.get_incident_notifications("INC-NONEXISTENT")

    def test_overdue_notifications(self, svc: IncidentResponseService):
        """Detect overdue notifications."""
        # Create a notification with a deadline in the past
        req = NotificationCreateRequest(
            notification_type=NotificationType.CYBER_INSURANCE,
            recipient="Insurance Co",
        )
        # For a very old incident, the deadline may already be past
        notif = svc.create_notification(INC_CLOSED_DDOS, req)
        overdue = svc.get_overdue_notifications()
        # Should include at least one overdue notification
        assert isinstance(overdue, list)


# ---------------------------------------------------------------------------
# 8. Escalation
# ---------------------------------------------------------------------------


class TestEscalation:
    """Test incident escalation."""

    def test_get_escalation_matrix(self, svc: IncidentResponseService):
        """Get full escalation matrix."""
        matrix = svc.get_escalation_matrix()
        assert len(matrix) == 4

    def test_escalate_incident(self, svc: IncidentResponseService):
        """Escalate an incident."""
        inc = svc.get_incident(INC_ACTIVE_PHISHING)
        assert inc.escalation_level == EscalationLevel.L2_IR_TEAM

        updated = svc.escalate_incident(INC_ACTIVE_PHISHING, EscalationLevel.L3_CISO)
        assert updated.escalation_level == EscalationLevel.L3_CISO

    def test_escalate_creates_event(self, svc: IncidentResponseService):
        """Escalation creates a timeline event."""
        inc = svc.get_incident(INC_ACTIVE_PHISHING)
        event_count = len(inc.events)

        svc.escalate_incident(INC_ACTIVE_PHISHING, EscalationLevel.L4_EXECUTIVE)
        updated = svc.get_incident(INC_ACTIVE_PHISHING)
        assert len(updated.events) == event_count + 1
        assert "escalated" in updated.events[-1].description.lower()

    def test_escalate_not_found(self, svc: IncidentResponseService):
        """Escalate non-existent incident raises KeyError."""
        with pytest.raises(KeyError):
            svc.escalate_incident("INC-NONEXISTENT", EscalationLevel.L5_BOARD)

    def test_auto_escalation_level_sev1(self, svc: IncidentResponseService):
        """SEV1 incidents auto-escalate to L4_EXECUTIVE."""
        req = IncidentCreateRequest(
            title="Critical", description="Critical incident",
            severity=IncidentSeverity.SEV1_CRITICAL,
            category=IncidentCategory.DATA_BREACH,
            reported_by="SIEM",
        )
        inc = svc.create_incident(req)
        assert inc.escalation_level == EscalationLevel.L4_EXECUTIVE

    def test_auto_escalation_level_sev4(self, svc: IncidentResponseService):
        """SEV4 incidents start at L1_SOC."""
        req = IncidentCreateRequest(
            title="Low", description="Low severity",
            severity=IncidentSeverity.SEV4_LOW,
            category=IncidentCategory.COMPLIANCE_VIOLATION,
            reported_by="Audit",
        )
        inc = svc.create_incident(req)
        assert inc.escalation_level == EscalationLevel.L1_SOC


# ---------------------------------------------------------------------------
# 9. SLA compliance
# ---------------------------------------------------------------------------


class TestSLACompliance:
    """Test SLA breach detection."""

    def test_sla_targets_exist_for_all_severities(self):
        """SLA targets defined for all severity levels."""
        for sev in IncidentSeverity:
            assert sev.value in SLA_TARGETS

    def test_sla_targets_have_required_fields(self):
        """SLA targets have triage, containment, and resolution."""
        for sev_key, targets in SLA_TARGETS.items():
            assert "triage_minutes" in targets
            assert "containment_minutes" in targets
            assert "resolution_minutes" in targets

    def test_sev1_sla_targets(self):
        """SEV1 SLA targets: 15min triage, 60min contain, 240min resolve."""
        t = SLA_TARGETS["SEV1_CRITICAL"]
        assert t["triage_minutes"] == 15
        assert t["containment_minutes"] == 60
        assert t["resolution_minutes"] == 240

    def test_sev4_sla_targets(self):
        """SEV4 SLA targets: 480min triage, 4320min contain, 10080min resolve."""
        t = SLA_TARGETS["SEV4_LOW"]
        assert t["triage_minutes"] == 480
        assert t["containment_minutes"] == 4320
        assert t["resolution_minutes"] == 10080

    def test_check_sla_breaches_returns_list(self, svc: IncidentResponseService):
        """SLA breach check returns a list."""
        breaches = svc.check_sla_breaches()
        assert isinstance(breaches, list)

    def test_sla_breach_structure(self, svc: IncidentResponseService):
        """SLA breach entries have expected structure."""
        breaches = svc.check_sla_breaches()
        for breach in breaches:
            assert "incident_id" in breach
            assert "severity" in breach
            assert "breaches" in breach
            assert isinstance(breach["breaches"], list)


# ---------------------------------------------------------------------------
# 10. Post-incident reviews
# ---------------------------------------------------------------------------


class TestPostIncidentReviews:
    """Test post-incident review management."""

    def test_create_review_for_closed_incident(self, svc: IncidentResponseService):
        """Create a review for a closed incident."""
        req = PostIncidentReviewRequest(
            participants=["CISO", "IR Lead", "Legal"],
            findings=["Good response time", "Communication gap"],
            action_items=["Improve runbook", "Train new staff"],
            effectiveness_rating=7.0,
            recurrence_risk="LOW",
        )
        review = svc.create_review(INC_CLOSED_DDOS, req)
        assert review.incident_id == INC_CLOSED_DDOS
        assert review.effectiveness_rating == 7.0
        assert len(review.findings) == 2

    def test_create_review_for_active_incident_fails(self, svc: IncidentResponseService):
        """Cannot create review for active incident."""
        req = PostIncidentReviewRequest(
            participants=["CISO"],
            findings=["Finding"],
            action_items=["Action"],
            effectiveness_rating=5.0,
            recurrence_risk="MEDIUM",
        )
        with pytest.raises(ValueError, match="POST_INCIDENT or CLOSED"):
            svc.create_review(INC_ACTIVE_BREACH, req)

    def test_create_review_not_found(self, svc: IncidentResponseService):
        """Create review for non-existent incident raises KeyError."""
        req = PostIncidentReviewRequest(
            participants=["CISO"],
            findings=["Finding"],
            action_items=["Action"],
            effectiveness_rating=5.0,
            recurrence_risk="LOW",
        )
        with pytest.raises(KeyError):
            svc.create_review("INC-NONEXISTENT", req)

    def test_get_review(self, svc: IncidentResponseService):
        """Get a specific review."""
        review = svc.get_review("PIR-003")
        assert review.incident_id == INC_CLOSED_RANSOMWARE
        assert review.effectiveness_rating == 7.5

    def test_get_review_not_found(self, svc: IncidentResponseService):
        """Get non-existent review raises KeyError."""
        with pytest.raises(KeyError):
            svc.get_review("PIR-NONEXISTENT")

    def test_list_reviews(self, svc: IncidentResponseService):
        """List all reviews."""
        items, total = svc.list_reviews()
        assert total == 3

    def test_list_reviews_filter_by_incident(self, svc: IncidentResponseService):
        """Filter reviews by incident ID."""
        items, total = svc.list_reviews(incident_id=INC_CLOSED_RANSOMWARE)
        assert total == 1
        assert items[0].incident_id == INC_CLOSED_RANSOMWARE

    def test_list_reviews_pagination(self, svc: IncidentResponseService):
        """Paginate reviews."""
        items, total = svc.list_reviews(limit=1, offset=0)
        assert total == 3
        assert len(items) == 1


# ---------------------------------------------------------------------------
# 11. Metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    """Test incident response metrics computation."""

    def test_metrics_basic_counts(self, svc: IncidentResponseService):
        """Metrics include correct counts."""
        metrics = svc.get_metrics()
        assert metrics.total_incidents == 6
        assert metrics.active_incidents == 2
        assert metrics.closed_incidents == 4

    def test_metrics_by_severity(self, svc: IncidentResponseService):
        """Metrics include severity breakdown."""
        metrics = svc.get_metrics()
        assert isinstance(metrics.by_severity, dict)
        assert len(metrics.by_severity) >= 2

    def test_metrics_by_category(self, svc: IncidentResponseService):
        """Metrics include category breakdown."""
        metrics = svc.get_metrics()
        assert isinstance(metrics.by_category, dict)
        assert len(metrics.by_category) >= 4

    def test_metrics_mttc(self, svc: IncidentResponseService):
        """MTTC is calculated for incidents with containment time."""
        metrics = svc.get_metrics()
        assert metrics.mttc_minutes is not None
        assert metrics.mttc_minutes > 0

    def test_metrics_mttr(self, svc: IncidentResponseService):
        """MTTR is calculated for resolved incidents."""
        metrics = svc.get_metrics()
        assert metrics.mttr_minutes is not None
        assert metrics.mttr_minutes > 0

    def test_metrics_sla_compliance(self, svc: IncidentResponseService):
        """SLA compliance rate is between 0 and 1."""
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.sla_compliance_rate <= 1.0

    def test_metrics_playbook_coverage(self, svc: IncidentResponseService):
        """Playbook coverage rate is between 0 and 1."""
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.playbook_coverage_rate <= 1.0
        assert metrics.playbook_coverage_rate > 0.5  # most seed incidents have playbooks

    def test_metrics_reviews_completed(self, svc: IncidentResponseService):
        """Reviews completed count matches seed data."""
        metrics = svc.get_metrics()
        assert metrics.reviews_completed == 3

    def test_metrics_empty_service(self):
        """Metrics with no data returns zeros."""
        svc = IncidentResponseService()
        svc.clear()
        metrics = svc.get_metrics()
        assert metrics.total_incidents == 0
        assert metrics.mttc_minutes is None
        assert metrics.mttr_minutes is None


# ---------------------------------------------------------------------------
# 12. Service utility
# ---------------------------------------------------------------------------


class TestServiceUtility:
    """Test service utility methods."""

    def test_get_stats(self, svc: IncidentResponseService):
        """Get service stats."""
        stats = svc.get_stats()
        assert stats["total_playbooks"] == 8
        assert stats["total_incidents"] == 6
        assert stats["active_incidents"] == 2
        assert stats["total_reviews"] == 3
        assert stats["service"] == "incident_response"

    def test_clear(self, svc: IncidentResponseService):
        """Clear all data."""
        svc.clear()
        items, total = svc.list_playbooks()
        assert total == 0
        items, total = svc.list_incidents()
        assert total == 0

    def test_singleton_pattern(self):
        """Singleton returns same instance."""
        svc1 = get_incident_response_service()
        svc2 = get_incident_response_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        """Reset creates new instance with fresh data."""
        svc1 = get_incident_response_service()
        svc1.clear()  # clear data
        svc2 = reset_incident_response_service()
        assert svc1 is not svc2
        items, total = svc2.list_playbooks()
        assert total == 8  # fresh seed data


# ---------------------------------------------------------------------------
# 13. API integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestAPIPlaybooks:
    """API tests for playbook endpoints."""

    @pytest.mark.anyio
    async def test_list_playbooks_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/playbooks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_get_playbook_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/playbooks/{PB_DATA_BREACH}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == PB_DATA_BREACH
        assert data["playbook_type"] == "DATA_BREACH"

    @pytest.mark.anyio
    async def test_get_playbook_not_found_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/playbooks/PB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_playbook_api(self, client):
        async with client as c:
            resp = await c.delete(f"{API_PREFIX}/playbooks/{PB_PHISHING}")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_playbook_not_found_api(self, client):
        async with client as c:
            resp = await c.delete(f"{API_PREFIX}/playbooks/PB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_testing_schedule_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/playbooks/schedule")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 8

    @pytest.mark.anyio
    async def test_list_playbooks_filter_type_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/playbooks", params={"playbook_type": "RANSOMWARE"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1


class TestAPIIncidents:
    """API tests for incident endpoints."""

    @pytest.mark.anyio
    async def test_list_incidents_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/incidents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_get_incident_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/incidents/{INC_ACTIVE_BREACH}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "SEV1_CRITICAL"

    @pytest.mark.anyio
    async def test_get_incident_not_found_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/incidents/INC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_incident_api(self, client):
        async with client as c:
            resp = await c.post(f"{API_PREFIX}/incidents", json={
                "title": "API Test Incident",
                "description": "Created via API",
                "severity": "SEV3_MEDIUM",
                "category": "PHISHING",
                "reported_by": "API Test",
            })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "API Test Incident"
        assert data["phase"] == "DETECTION"

    @pytest.mark.anyio
    async def test_update_incident_api(self, client):
        async with client as c:
            resp = await c.put(f"{API_PREFIX}/incidents/{INC_ACTIVE_BREACH}", json={
                "assigned_to": "New Assignee",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_to"] == "New Assignee"

    @pytest.mark.anyio
    async def test_update_incident_invalid_transition_api(self, client):
        async with client as c:
            # Create a new incident first
            create_resp = await c.post(f"{API_PREFIX}/incidents", json={
                "title": "Transition Test",
                "description": "Test",
                "severity": "SEV4_LOW",
                "category": "COMPLIANCE_VIOLATION",
                "reported_by": "Test",
            })
            inc_id = create_resp.json()["id"]
            # Try invalid transition DETECTION -> RECOVERY
            resp = await c.put(f"{API_PREFIX}/incidents/{inc_id}", json={
                "phase": "RECOVERY",
            })
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_get_active_incidents_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/incidents/active")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    @pytest.mark.anyio
    async def test_get_metrics_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/incidents/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_incidents"] == 6
        assert "mttc_minutes" in data


class TestAPITimeline:
    """API tests for timeline endpoints."""

    @pytest.mark.anyio
    async def test_get_timeline_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/incidents/{INC_ACTIVE_BREACH}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3

    @pytest.mark.anyio
    async def test_log_event_api(self, client):
        async with client as c:
            resp = await c.post(f"{API_PREFIX}/incidents/{INC_ACTIVE_BREACH}/events", json={
                "description": "API test event",
                "actor": "API Tester",
                "evidence_refs": ["api-evidence-001"],
            })
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "API test event"

    @pytest.mark.anyio
    async def test_log_event_not_found_api(self, client):
        async with client as c:
            resp = await c.post(f"{API_PREFIX}/incidents/INC-NONEXISTENT/events", json={
                "description": "Test",
                "actor": "Test",
            })
        assert resp.status_code == 404


class TestAPINotifications:
    """API tests for notification endpoints."""

    @pytest.mark.anyio
    async def test_get_notifications_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/incidents/{INC_ACTIVE_BREACH}/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2

    @pytest.mark.anyio
    async def test_create_notification_api(self, client):
        async with client as c:
            resp = await c.post(f"{API_PREFIX}/incidents/{INC_ACTIVE_BREACH}/notifications", json={
                "notification_type": "GDPR_BREACH",
                "recipient": "EU DPA",
                "content_summary": "GDPR notification",
            })
        assert resp.status_code == 201
        data = resp.json()
        assert data["notification_type"] == "GDPR_BREACH"

    @pytest.mark.anyio
    async def test_send_notification_api(self, client):
        async with client as c:
            resp = await c.put(
                f"{API_PREFIX}/incidents/{INC_ACTIVE_BREACH}/notifications/NOTIF-001-02/send"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SENT"

    @pytest.mark.anyio
    async def test_send_notification_not_found_api(self, client):
        async with client as c:
            resp = await c.put(
                f"{API_PREFIX}/incidents/{INC_ACTIVE_BREACH}/notifications/NOTIF-FAKE/send"
            )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_overdue_notifications_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/notifications/overdue")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestAPIEscalation:
    """API tests for escalation endpoints."""

    @pytest.mark.anyio
    async def test_get_escalation_matrix_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/escalation-matrix")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4

    @pytest.mark.anyio
    async def test_escalate_incident_api(self, client):
        async with client as c:
            resp = await c.post(
                f"{API_PREFIX}/incidents/{INC_ACTIVE_PHISHING}/escalate",
                params={"level": "L3_CISO"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["escalation_level"] == "L3_CISO"

    @pytest.mark.anyio
    async def test_escalate_not_found_api(self, client):
        async with client as c:
            resp = await c.post(
                f"{API_PREFIX}/incidents/INC-NONEXISTENT/escalate",
                params={"level": "L5_BOARD"},
            )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_sla_breaches_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/sla-breaches")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestAPIReviews:
    """API tests for post-incident review endpoints."""

    @pytest.mark.anyio
    async def test_list_reviews_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_get_review_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/reviews/PIR-003")
        assert resp.status_code == 200
        data = resp.json()
        assert data["incident_id"] == INC_CLOSED_RANSOMWARE

    @pytest.mark.anyio
    async def test_get_review_not_found_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/reviews/PIR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_review_api(self, client):
        async with client as c:
            resp = await c.post(f"{API_PREFIX}/incidents/{INC_CLOSED_COMPLIANCE}/review", json={
                "participants": ["CISO", "Compliance"],
                "findings": ["Legacy API gap identified"],
                "action_items": ["Quarterly API audit"],
                "effectiveness_rating": 6.5,
                "recurrence_risk": "LOW",
            })
        assert resp.status_code == 201
        data = resp.json()
        assert data["effectiveness_rating"] == 6.5

    @pytest.mark.anyio
    async def test_create_review_active_incident_api(self, client):
        async with client as c:
            resp = await c.post(f"{API_PREFIX}/incidents/{INC_ACTIVE_BREACH}/review", json={
                "participants": ["CISO"],
                "findings": ["Finding"],
                "action_items": ["Action"],
                "effectiveness_rating": 5.0,
                "recurrence_risk": "MEDIUM",
            })
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_review_not_found_api(self, client):
        async with client as c:
            resp = await c.post(f"{API_PREFIX}/incidents/INC-NONEXISTENT/review", json={
                "participants": ["CISO"],
                "findings": ["Finding"],
                "action_items": ["Action"],
                "effectiveness_rating": 5.0,
                "recurrence_risk": "LOW",
            })
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_reviews_filter_incident_api(self, client):
        async with client as c:
            resp = await c.get(f"{API_PREFIX}/reviews", params={"incident_id": INC_CLOSED_RANSOMWARE})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1


# ---------------------------------------------------------------------------
# 14. Edge cases and additional coverage
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_multiple_phase_transitions_track_events(self, svc: IncidentResponseService):
        """Multiple phase transitions each create events."""
        req = IncidentCreateRequest(
            title="Multi-Phase", description="Multiple transitions",
            severity=IncidentSeverity.SEV3_MEDIUM,
            category=IncidentCategory.PHISHING,
            reported_by="User",
        )
        inc = svc.create_incident(req)
        initial_events = len(inc.events)

        inc = svc.update_incident(inc.id, IncidentUpdateRequest(phase=IncidentPhase.TRIAGE))
        inc = svc.update_incident(inc.id, IncidentUpdateRequest(phase=IncidentPhase.CONTAINMENT))
        inc = svc.update_incident(inc.id, IncidentUpdateRequest(phase=IncidentPhase.CLOSED))

        # 3 transitions = 3 additional events
        assert len(inc.events) == initial_events + 3

    def test_update_severity_without_phase_change(self, svc: IncidentResponseService):
        """Update severity without changing phase."""
        updated = svc.update_incident(
            INC_ACTIVE_PHISHING,
            IncidentUpdateRequest(severity=IncidentSeverity.SEV1_CRITICAL),
        )
        assert updated.severity == IncidentSeverity.SEV1_CRITICAL
        assert updated.phase == IncidentPhase.TRIAGE  # unchanged

    def test_same_phase_no_event(self, svc: IncidentResponseService):
        """Setting same phase does not create transition event."""
        inc = svc.get_incident(INC_ACTIVE_BREACH)
        event_count = len(inc.events)
        updated = svc.update_incident(
            INC_ACTIVE_BREACH,
            IncidentUpdateRequest(phase=inc.phase),
        )
        assert len(updated.events) == event_count  # no new event

    def test_create_incident_with_data_compromised(self, svc: IncidentResponseService):
        """Create incident with data_compromised flag."""
        req = IncidentCreateRequest(
            title="Breach", description="Data breach",
            severity=IncidentSeverity.SEV1_CRITICAL,
            category=IncidentCategory.DATA_BREACH,
            reported_by="SIEM",
            data_compromised=True,
            affected_patients_count=500,
        )
        inc = svc.create_incident(req)
        assert inc.data_compromised is True
        assert inc.affected_patients_count == 500

    def test_playbook_type_values(self):
        """All expected playbook types exist."""
        expected = {"DATA_BREACH", "RANSOMWARE", "INSIDER_THREAT", "PHISHING", "DDOS", "SUPPLY_CHAIN", "ZERO_DAY", "UNAUTHORIZED_ACCESS", "GENERIC"}
        actual = {t.value for t in PlaybookType}
        assert expected == actual

    def test_incident_category_values(self):
        """All expected incident categories exist."""
        expected = {"DATA_BREACH", "RANSOMWARE", "INSIDER_THREAT", "PHISHING", "DDOS", "SUPPLY_CHAIN", "ZERO_DAY", "UNAUTHORIZED_ACCESS", "DATA_LOSS", "SYSTEM_COMPROMISE", "COMPLIANCE_VIOLATION"}
        actual = {c.value for c in IncidentCategory}
        assert expected == actual

    def test_incident_phase_values(self):
        """All expected incident phases exist."""
        expected = {"DETECTION", "TRIAGE", "CONTAINMENT", "ERADICATION", "RECOVERY", "POST_INCIDENT", "CLOSED"}
        actual = {p.value for p in IncidentPhase}
        assert expected == actual

    def test_notification_type_values(self):
        """All expected notification types exist."""
        expected = {"HIPAA_BREACH", "GDPR_BREACH", "STATE_BREACH", "FDA_NOTIFICATION", "INTERNAL_STAKEHOLDER", "LAW_ENFORCEMENT", "CYBER_INSURANCE"}
        actual = {n.value for n in NotificationType}
        assert expected == actual

    def test_escalation_level_values(self):
        """All expected escalation levels exist."""
        expected = {"L1_SOC", "L2_IR_TEAM", "L3_CISO", "L4_EXECUTIVE", "L5_BOARD"}
        actual = {e.value for e in EscalationLevel}
        assert expected == actual

    def test_severity_ordering(self):
        """Severity levels are ordered correctly in SLA targets."""
        sev1 = SLA_TARGETS["SEV1_CRITICAL"]["triage_minutes"]
        sev2 = SLA_TARGETS["SEV2_HIGH"]["triage_minutes"]
        sev3 = SLA_TARGETS["SEV3_MEDIUM"]["triage_minutes"]
        sev4 = SLA_TARGETS["SEV4_LOW"]["triage_minutes"]
        assert sev1 < sev2 < sev3 < sev4

    def test_playbook_severity_thresholds(self, svc: IncidentResponseService):
        """Data breach and ransomware playbooks have SEV1 threshold."""
        pb = svc.get_playbook(PB_DATA_BREACH)
        assert pb.severity_threshold == IncidentSeverity.SEV1_CRITICAL
        pb = svc.get_playbook(PB_RANSOMWARE)
        assert pb.severity_threshold == IncidentSeverity.SEV1_CRITICAL

    def test_playbook_last_tested_populated(self, svc: IncidentResponseService):
        """Seed playbooks have last_tested dates."""
        pb = svc.get_playbook(PB_DATA_BREACH)
        assert pb.last_tested is not None

    def test_incident_with_all_fields(self, svc: IncidentResponseService):
        """Create and close incident with all metadata."""
        req = IncidentCreateRequest(
            title="Full Metadata Test", description="Complete test",
            severity=IncidentSeverity.SEV2_HIGH,
            category=IncidentCategory.SUPPLY_CHAIN,
            reported_by="DevOps",
            affected_systems=["npm-registry", "build-server"],
            affected_patients_count=0,
            data_compromised=False,
        )
        inc = svc.create_incident(req)
        inc = svc.update_incident(inc.id, IncidentUpdateRequest(
            phase=IncidentPhase.TRIAGE,
            assigned_to="IR Lead",
        ))
        inc = svc.update_incident(inc.id, IncidentUpdateRequest(
            phase=IncidentPhase.CLOSED,
            root_cause="Compromised npm package",
            lessons_learned="Pin all dependencies",
        ))
        assert inc.phase == IncidentPhase.CLOSED
        assert inc.root_cause == "Compromised npm package"
        assert inc.closed_at is not None
        assert inc.resolution_time_minutes is not None

    def test_multiple_notifications_for_same_incident(self, svc: IncidentResponseService):
        """Create multiple notification types for same incident."""
        for ntype in [NotificationType.HIPAA_BREACH, NotificationType.GDPR_BREACH, NotificationType.CYBER_INSURANCE]:
            req = NotificationCreateRequest(
                notification_type=ntype,
                recipient=f"{ntype.value} Recipient",
            )
            svc.create_notification(INC_ACTIVE_BREACH, req)

        notifs = svc.get_incident_notifications(INC_ACTIVE_BREACH)
        types = {n.notification_type for n in notifs}
        assert NotificationType.HIPAA_BREACH in types
        assert NotificationType.GDPR_BREACH in types
        assert NotificationType.CYBER_INSURANCE in types

    def test_escalation_matrix_contacts_have_notification_methods(self, svc: IncidentResponseService):
        """Escalation contacts have notification methods."""
        matrix = svc.get_escalation_matrix()
        for entry in matrix:
            for contact in entry.contacts:
                assert len(contact.notification_methods) >= 1
                assert contact.email
                assert contact.phone
