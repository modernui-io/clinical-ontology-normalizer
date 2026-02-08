"""Tests for CISO-11 Incident Response service and API endpoints.

Tests cover:
- Incident lifecycle (create -> triage -> contain -> eradicate -> recover -> close)
- Severity classification
- Timeline event tracking
- Auto-escalation logic for SEV1 incidents
- Incident listing and filtering
- API endpoints via FastAPI test client
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services.incident_service import (
    Incident,
    IncidentSeverity,
    IncidentService,
    IncidentStatus,
    IncidentType,
    SEV1_ACKNOWLEDGE_TIMEOUT_MINUTES,
    TimelineEvent,
    get_incident_service,
    reset_incident_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _reset_service():
    """Reset the singleton service before each test."""
    reset_incident_service()
    yield
    reset_incident_service()


@pytest.fixture
def service() -> IncidentService:
    """Get a fresh incident service instance."""
    return get_incident_service()


@pytest.fixture
def sample_incident(service: IncidentService) -> Incident:
    """Create a sample SEV2 incident for testing."""
    return service.create_incident(
        title="Unauthorized API access detected",
        description="Multiple failed auth attempts followed by a successful login from an unusual IP.",
        severity=IncidentSeverity.SEV2,
        incident_type=IncidentType.UNAUTHORIZED_ACCESS,
        reported_by="security-analyst-1",
        affected_systems=["api-gateway", "auth-service"],
        phi_involved=False,
    )


@pytest.fixture
def sev1_incident(service: IncidentService) -> Incident:
    """Create a sample SEV1 PHI breach incident for testing."""
    return service.create_incident(
        title="Potential PHI data exfiltration",
        description="Audit logs show bulk patient record exports from an unknown service account.",
        severity=IncidentSeverity.SEV1,
        incident_type=IncidentType.PHI_BREACH,
        reported_by="siem-alert",
        affected_systems=["postgresql-primary", "api-backend", "fhir-endpoint"],
        phi_involved=True,
        incident_commander="security-lead",
    )


# ============================================================================
# Incident Creation Tests
# ============================================================================


class TestIncidentCreation:
    """Tests for creating incidents."""

    def test_create_incident_basic(self, service: IncidentService) -> None:
        """Test basic incident creation with required fields."""
        incident = service.create_incident(
            title="Test incident",
            description="Test description",
            severity=IncidentSeverity.SEV3,
            incident_type=IncidentType.CONFIGURATION_ERROR,
            reported_by="tester",
        )

        assert incident.id is not None
        assert incident.title == "Test incident"
        assert incident.description == "Test description"
        assert incident.severity == IncidentSeverity.SEV3
        assert incident.status == IncidentStatus.DETECTED
        assert incident.incident_type == IncidentType.CONFIGURATION_ERROR
        assert incident.reported_by == "tester"
        assert incident.reported_at is not None
        assert incident.phi_involved is False
        assert incident.escalated is False

    def test_create_incident_with_all_fields(self, service: IncidentService) -> None:
        """Test incident creation with all optional fields."""
        incident = service.create_incident(
            title="Full incident",
            description="Full description with details",
            severity=IncidentSeverity.SEV1,
            incident_type=IncidentType.PHI_BREACH,
            reported_by="analyst",
            affected_systems=["db-primary", "api-server"],
            phi_involved=True,
            incident_commander="ic-person",
        )

        assert incident.affected_systems == ["db-primary", "api-server"]
        assert incident.phi_involved is True
        assert incident.incident_commander == "ic-person"

    def test_create_incident_adds_creation_timeline_event(self, service: IncidentService) -> None:
        """Test that incident creation automatically adds a timeline event."""
        incident = service.create_incident(
            title="Timeline test",
            description="Testing creation event",
            severity=IncidentSeverity.SEV4,
            incident_type=IncidentType.OTHER,
            reported_by="tester",
        )

        assert len(incident.timeline) == 1
        event = incident.timeline[0]
        assert event.event_type == "created"
        assert "SEV4" in event.description
        assert event.actor == "tester"

    def test_create_incident_unique_ids(self, service: IncidentService) -> None:
        """Test that each incident gets a unique ID."""
        ids = set()
        for i in range(10):
            incident = service.create_incident(
                title=f"Incident {i}",
                description="Test",
                severity=IncidentSeverity.SEV4,
                incident_type=IncidentType.OTHER,
                reported_by="tester",
            )
            ids.add(incident.id)

        assert len(ids) == 10


# ============================================================================
# Incident Lifecycle Tests
# ============================================================================


class TestIncidentLifecycle:
    """Tests for incident state transitions."""

    def test_full_lifecycle(self, service: IncidentService, sample_incident: Incident) -> None:
        """Test the complete incident lifecycle from DETECTED to CLOSED."""
        incident_id = sample_incident.id

        # DETECTED -> TRIAGING
        updated = service.update_incident(incident_id, status=IncidentStatus.TRIAGING, updated_by="ic")
        assert updated.status == IncidentStatus.TRIAGING
        assert updated.acknowledged_at is not None

        # TRIAGING -> CONTAINED
        updated = service.update_incident(incident_id, status=IncidentStatus.CONTAINED, updated_by="ic")
        assert updated.status == IncidentStatus.CONTAINED
        assert updated.contained_at is not None

        # CONTAINED -> ERADICATING
        updated = service.update_incident(incident_id, status=IncidentStatus.ERADICATING, updated_by="eng")
        assert updated.status == IncidentStatus.ERADICATING

        # ERADICATING -> RECOVERING
        updated = service.update_incident(incident_id, status=IncidentStatus.RECOVERING, updated_by="eng")
        assert updated.status == IncidentStatus.RECOVERING

        # RECOVERING -> CLOSED
        updated = service.update_incident(incident_id, status=IncidentStatus.CLOSED, updated_by="ic")
        assert updated.status == IncidentStatus.CLOSED
        assert updated.closed_at is not None
        assert updated.resolved_at is not None

    def test_invalid_state_transition(self, service: IncidentService, sample_incident: Incident) -> None:
        """Test that invalid state transitions raise ValueError."""
        with pytest.raises(ValueError, match="Invalid status transition"):
            # Cannot go directly from DETECTED to ERADICATING
            service.update_incident(
                sample_incident.id,
                status=IncidentStatus.ERADICATING,
            )

    def test_closed_is_terminal(self, service: IncidentService, sample_incident: Incident) -> None:
        """Test that CLOSED is a terminal state with no valid transitions."""
        # Move to CLOSED
        service.update_incident(sample_incident.id, status=IncidentStatus.TRIAGING)
        service.update_incident(sample_incident.id, status=IncidentStatus.CONTAINED)
        service.update_incident(sample_incident.id, status=IncidentStatus.CLOSED)

        with pytest.raises(ValueError, match="Invalid status transition"):
            service.update_incident(
                sample_incident.id,
                status=IncidentStatus.TRIAGING,
            )

    def test_eradicating_can_return_to_contained(self, service: IncidentService, sample_incident: Incident) -> None:
        """Test that ERADICATING can go back to CONTAINED (if eradication fails)."""
        service.update_incident(sample_incident.id, status=IncidentStatus.TRIAGING)
        service.update_incident(sample_incident.id, status=IncidentStatus.CONTAINED)
        service.update_incident(sample_incident.id, status=IncidentStatus.ERADICATING)

        updated = service.update_incident(
            sample_incident.id,
            status=IncidentStatus.CONTAINED,
            updated_by="sec-lead",
        )
        assert updated.status == IncidentStatus.CONTAINED

    def test_status_change_adds_timeline_event(self, service: IncidentService, sample_incident: Incident) -> None:
        """Test that status transitions automatically create timeline events."""
        initial_events = len(sample_incident.timeline)

        service.update_incident(
            sample_incident.id,
            status=IncidentStatus.TRIAGING,
            updated_by="ic",
        )

        incident = service.get_incident(sample_incident.id)
        assert incident is not None
        assert len(incident.timeline) == initial_events + 1

        latest_event = incident.timeline[-1]
        assert latest_event.event_type == "status_change"
        assert "DETECTED" in latest_event.description
        assert "TRIAGING" in latest_event.description
        assert latest_event.actor == "ic"


# ============================================================================
# Severity Classification Tests
# ============================================================================


class TestSeverityClassification:
    """Tests for severity classification and changes."""

    def test_all_severity_levels(self, service: IncidentService) -> None:
        """Test creating incidents at all severity levels."""
        for sev in IncidentSeverity:
            incident = service.create_incident(
                title=f"{sev.value} incident",
                description="Test",
                severity=sev,
                incident_type=IncidentType.OTHER,
                reported_by="tester",
            )
            assert incident.severity == sev

    def test_severity_change_tracked(self, service: IncidentService, sample_incident: Incident) -> None:
        """Test that severity changes are tracked with original severity."""
        assert sample_incident.severity == IncidentSeverity.SEV2
        assert sample_incident.original_severity is None

        updated = service.update_incident(
            sample_incident.id,
            severity=IncidentSeverity.SEV1,
            updated_by="ic",
        )

        assert updated.severity == IncidentSeverity.SEV1
        assert updated.original_severity == IncidentSeverity.SEV2

    def test_severity_change_adds_timeline_event(self, service: IncidentService, sample_incident: Incident) -> None:
        """Test that severity changes create timeline events."""
        initial_count = len(sample_incident.timeline)

        service.update_incident(
            sample_incident.id,
            severity=IncidentSeverity.SEV1,
            updated_by="ic",
        )

        incident = service.get_incident(sample_incident.id)
        assert incident is not None
        assert len(incident.timeline) == initial_count + 1
        event = incident.timeline[-1]
        assert event.event_type == "severity_change"
        assert "SEV2" in event.description
        assert "SEV1" in event.description


# ============================================================================
# Timeline Event Tests
# ============================================================================


class TestTimelineEvents:
    """Tests for timeline event tracking."""

    def test_add_timeline_event(self, service: IncidentService, sample_incident: Incident) -> None:
        """Test adding a custom timeline event."""
        event = service.add_timeline_event(
            incident_id=sample_incident.id,
            event_type="note",
            description="Forensic analysis shows no data exfiltration",
            actor="forensics-analyst",
            metadata={"analysis_tool": "volatility", "confidence": "high"},
        )

        assert event.id is not None
        assert event.event_type == "note"
        assert event.description == "Forensic analysis shows no data exfiltration"
        assert event.actor == "forensics-analyst"
        assert event.metadata["analysis_tool"] == "volatility"

    def test_add_timeline_event_nonexistent_incident(self, service: IncidentService) -> None:
        """Test adding a timeline event to a non-existent incident."""
        with pytest.raises(ValueError, match="Incident not found"):
            service.add_timeline_event(
                incident_id="nonexistent-id",
                event_type="note",
                description="This should fail",
            )

    def test_timeline_events_ordered(self, service: IncidentService, sample_incident: Incident) -> None:
        """Test that timeline events maintain chronological order."""
        for i in range(5):
            service.add_timeline_event(
                incident_id=sample_incident.id,
                event_type="action",
                description=f"Action {i}",
            )

        incident = service.get_incident(sample_incident.id)
        assert incident is not None
        # 1 creation event + 5 added events
        assert len(incident.timeline) == 6

        # Verify events are in order (each timestamp >= previous)
        for i in range(1, len(incident.timeline)):
            assert incident.timeline[i].timestamp >= incident.timeline[i - 1].timestamp


# ============================================================================
# Auto-Escalation Tests
# ============================================================================


class TestAutoEscalation:
    """Tests for SEV1 auto-escalation logic."""

    def test_sev1_auto_escalation_triggered(self, service: IncidentService) -> None:
        """Test that unacknowledged SEV1 incidents are auto-escalated."""
        # Create a SEV1 incident with a past timestamp
        incident = service.create_incident(
            title="Unacknowledged SEV1",
            description="This should be escalated",
            severity=IncidentSeverity.SEV1,
            incident_type=IncidentType.PHI_BREACH,
            reported_by="siem",
        )

        # Backdate the reported_at to exceed the threshold
        incident.reported_at = datetime.now(timezone.utc) - timedelta(
            minutes=SEV1_ACKNOWLEDGE_TIMEOUT_MINUTES + 1
        )

        escalated = service.check_auto_escalation()
        assert len(escalated) == 1
        assert escalated[0].id == incident.id
        assert escalated[0].escalated is True

        # Check that escalation event was added to timeline
        escalation_events = [
            e for e in escalated[0].timeline if e.event_type == "auto_escalation"
        ]
        assert len(escalation_events) == 1
        assert "AUTO-ESCALATION" in escalation_events[0].description

    def test_sev1_no_escalation_when_acknowledged(self, service: IncidentService) -> None:
        """Test that acknowledged SEV1 incidents are not auto-escalated."""
        incident = service.create_incident(
            title="Acknowledged SEV1",
            description="This has been triaged",
            severity=IncidentSeverity.SEV1,
            incident_type=IncidentType.RANSOMWARE,
            reported_by="siem",
        )

        # Acknowledge by moving to TRIAGING
        service.update_incident(incident.id, status=IncidentStatus.TRIAGING)

        # Backdate
        incident.reported_at = datetime.now(timezone.utc) - timedelta(
            minutes=SEV1_ACKNOWLEDGE_TIMEOUT_MINUTES + 1
        )

        escalated = service.check_auto_escalation()
        assert len(escalated) == 0

    def test_sev2_not_auto_escalated(self, service: IncidentService) -> None:
        """Test that SEV2 incidents are not auto-escalated regardless of time."""
        incident = service.create_incident(
            title="SEV2 incident",
            description="Should not be escalated",
            severity=IncidentSeverity.SEV2,
            incident_type=IncidentType.SERVICE_OUTAGE,
            reported_by="monitoring",
        )

        # Backdate well past the threshold
        incident.reported_at = datetime.now(timezone.utc) - timedelta(hours=24)

        escalated = service.check_auto_escalation()
        assert len(escalated) == 0

    def test_sev1_not_escalated_twice(self, service: IncidentService) -> None:
        """Test that an already-escalated incident is not escalated again."""
        incident = service.create_incident(
            title="SEV1 incident",
            description="Will be escalated once",
            severity=IncidentSeverity.SEV1,
            incident_type=IncidentType.DATA_EXFILTRATION,
            reported_by="siem",
        )

        incident.reported_at = datetime.now(timezone.utc) - timedelta(
            minutes=SEV1_ACKNOWLEDGE_TIMEOUT_MINUTES + 1
        )

        # First escalation check
        escalated1 = service.check_auto_escalation()
        assert len(escalated1) == 1

        # Second check should not escalate again
        escalated2 = service.check_auto_escalation()
        assert len(escalated2) == 0


# ============================================================================
# Incident Listing and Filtering Tests
# ============================================================================


class TestIncidentListingAndFiltering:
    """Tests for listing and filtering incidents."""

    def test_list_all_incidents(self, service: IncidentService) -> None:
        """Test listing all incidents."""
        for i in range(5):
            service.create_incident(
                title=f"Incident {i}",
                description="Test",
                severity=IncidentSeverity.SEV3,
                incident_type=IncidentType.OTHER,
                reported_by="tester",
            )

        incidents, total = service.list_incidents()
        assert total == 5
        assert len(incidents) == 5

    def test_filter_by_severity(self, service: IncidentService) -> None:
        """Test filtering incidents by severity level."""
        service.create_incident(
            title="SEV1", description="Critical", severity=IncidentSeverity.SEV1,
            incident_type=IncidentType.PHI_BREACH, reported_by="tester",
        )
        service.create_incident(
            title="SEV2", description="High", severity=IncidentSeverity.SEV2,
            incident_type=IncidentType.SERVICE_OUTAGE, reported_by="tester",
        )
        service.create_incident(
            title="SEV3", description="Medium", severity=IncidentSeverity.SEV3,
            incident_type=IncidentType.CONFIGURATION_ERROR, reported_by="tester",
        )

        sev1_incidents, total = service.list_incidents(severity=IncidentSeverity.SEV1)
        assert total == 1
        assert sev1_incidents[0].title == "SEV1"

    def test_filter_by_status(self, service: IncidentService, sample_incident: Incident) -> None:
        """Test filtering incidents by status."""
        service.update_incident(sample_incident.id, status=IncidentStatus.TRIAGING)

        detected, detected_total = service.list_incidents(status=IncidentStatus.DETECTED)
        triaging, triaging_total = service.list_incidents(status=IncidentStatus.TRIAGING)

        assert detected_total == 0
        assert triaging_total == 1

    def test_filter_by_phi_involved(self, service: IncidentService) -> None:
        """Test filtering incidents by PHI involvement."""
        service.create_incident(
            title="PHI incident", description="Has PHI", severity=IncidentSeverity.SEV1,
            incident_type=IncidentType.PHI_BREACH, reported_by="tester", phi_involved=True,
        )
        service.create_incident(
            title="Non-PHI incident", description="No PHI", severity=IncidentSeverity.SEV3,
            incident_type=IncidentType.DDOS, reported_by="tester", phi_involved=False,
        )

        phi_incidents, total = service.list_incidents(phi_involved=True)
        assert total == 1
        assert phi_incidents[0].phi_involved is True

    def test_pagination(self, service: IncidentService) -> None:
        """Test incident list pagination."""
        for i in range(10):
            service.create_incident(
                title=f"Incident {i}", description="Test", severity=IncidentSeverity.SEV4,
                incident_type=IncidentType.OTHER, reported_by="tester",
            )

        page1, total = service.list_incidents(limit=3, offset=0)
        assert total == 10
        assert len(page1) == 3

        page2, _ = service.list_incidents(limit=3, offset=3)
        assert len(page2) == 3

        # Ensure no overlap between pages
        page1_ids = {i.id for i in page1}
        page2_ids = {i.id for i in page2}
        assert page1_ids.isdisjoint(page2_ids)


# ============================================================================
# Incident Update Tests
# ============================================================================


class TestIncidentUpdate:
    """Tests for updating incident fields."""

    def test_update_nonexistent_incident(self, service: IncidentService) -> None:
        """Test updating a non-existent incident raises ValueError."""
        with pytest.raises(ValueError, match="Incident not found"):
            service.update_incident("nonexistent-id", title="New title")

    def test_update_multiple_fields(self, service: IncidentService, sample_incident: Incident) -> None:
        """Test updating multiple fields at once."""
        updated = service.update_incident(
            sample_incident.id,
            title="Updated title",
            description="Updated description",
            incident_commander="new-ic",
            assigned_responders=["responder-1", "responder-2"],
            affected_systems=["system-a", "system-b", "system-c"],
            evidence_links=["https://logs.example.com/evidence/123"],
            estimated_affected_records=500,
        )

        assert updated.title == "Updated title"
        assert updated.description == "Updated description"
        assert updated.incident_commander == "new-ic"
        assert updated.assigned_responders == ["responder-1", "responder-2"]
        assert updated.affected_systems == ["system-a", "system-b", "system-c"]
        assert updated.evidence_links == ["https://logs.example.com/evidence/123"]
        assert updated.estimated_affected_records == 500

    def test_get_stats(self, service: IncidentService) -> None:
        """Test the statistics endpoint."""
        service.create_incident(
            title="SEV1", description="D", severity=IncidentSeverity.SEV1,
            incident_type=IncidentType.PHI_BREACH, reported_by="t", phi_involved=True,
        )
        service.create_incident(
            title="SEV2", description="D", severity=IncidentSeverity.SEV2,
            incident_type=IncidentType.SERVICE_OUTAGE, reported_by="t",
        )

        stats = service.get_stats()
        assert stats["total_incidents"] == 2
        assert stats["open_incidents"] == 2
        assert stats["by_severity"]["SEV1"] == 1
        assert stats["by_severity"]["SEV2"] == 1
        assert stats["phi_involved_count"] == 1


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestIncidentAPI:
    """Tests for incident API endpoints via FastAPI test client."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client."""
        from app.main import app
        return TestClient(app)

    def test_create_incident_endpoint(self, client: TestClient) -> None:
        """Test POST /api/v1/security/incidents."""
        response = client.post(
            "/api/v1/security/incidents",
            json={
                "title": "API test incident",
                "description": "Created via API test",
                "severity": "SEV2",
                "incident_type": "UNAUTHORIZED_ACCESS",
                "reported_by": "api-tester",
                "affected_systems": ["api-server"],
                "phi_involved": False,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "API test incident"
        assert data["severity"] == "SEV2"
        assert data["status"] == "DETECTED"
        assert data["incident_type"] == "UNAUTHORIZED_ACCESS"
        assert len(data["timeline"]) >= 1

    def test_get_incident_endpoint(self, client: TestClient) -> None:
        """Test GET /api/v1/security/incidents/{id}."""
        # Create first
        create_resp = client.post(
            "/api/v1/security/incidents",
            json={
                "title": "Get test",
                "description": "For get endpoint test",
                "severity": "SEV3",
                "incident_type": "CONFIGURATION_ERROR",
                "reported_by": "tester",
            },
        )
        incident_id = create_resp.json()["id"]

        # Get it
        response = client.get(f"/api/v1/security/incidents/{incident_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == incident_id
        assert data["title"] == "Get test"

    def test_get_nonexistent_incident_endpoint(self, client: TestClient) -> None:
        """Test GET /api/v1/security/incidents/{id} with non-existent ID."""
        response = client.get("/api/v1/security/incidents/nonexistent-id")
        assert response.status_code == 404

    def test_list_incidents_endpoint(self, client: TestClient) -> None:
        """Test GET /api/v1/security/incidents with filters."""
        # Create multiple incidents
        for sev in ["SEV1", "SEV2", "SEV3"]:
            client.post(
                "/api/v1/security/incidents",
                json={
                    "title": f"{sev} list test",
                    "description": "For list test",
                    "severity": sev,
                    "incident_type": "OTHER",
                    "reported_by": "tester",
                },
            )

        # List all
        response = client.get("/api/v1/security/incidents")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 3

        # Filter by severity
        response = client.get("/api/v1/security/incidents?severity=SEV1")
        assert response.status_code == 200
        data = response.json()
        assert all(i["severity"] == "SEV1" for i in data["incidents"])

    def test_update_incident_endpoint(self, client: TestClient) -> None:
        """Test PUT /api/v1/security/incidents/{id}."""
        # Create
        create_resp = client.post(
            "/api/v1/security/incidents",
            json={
                "title": "Update test",
                "description": "For update test",
                "severity": "SEV2",
                "incident_type": "SERVICE_OUTAGE",
                "reported_by": "tester",
            },
        )
        incident_id = create_resp.json()["id"]

        # Update status
        response = client.put(
            f"/api/v1/security/incidents/{incident_id}",
            json={
                "status": "TRIAGING",
                "updated_by": "ic",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "TRIAGING"
        assert data["acknowledged_at"] is not None

    def test_update_incident_invalid_transition(self, client: TestClient) -> None:
        """Test PUT with invalid state transition returns 400."""
        create_resp = client.post(
            "/api/v1/security/incidents",
            json={
                "title": "Invalid transition test",
                "description": "Test",
                "severity": "SEV3",
                "incident_type": "OTHER",
                "reported_by": "tester",
            },
        )
        incident_id = create_resp.json()["id"]

        response = client.put(
            f"/api/v1/security/incidents/{incident_id}",
            json={"status": "RECOVERING"},
        )
        assert response.status_code == 400

    def test_add_timeline_event_endpoint(self, client: TestClient) -> None:
        """Test POST /api/v1/security/incidents/{id}/timeline."""
        create_resp = client.post(
            "/api/v1/security/incidents",
            json={
                "title": "Timeline test",
                "description": "Test",
                "severity": "SEV2",
                "incident_type": "UNAUTHORIZED_ACCESS",
                "reported_by": "tester",
            },
        )
        incident_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/security/incidents/{incident_id}/timeline",
            json={
                "event_type": "note",
                "description": "Investigation shows limited scope",
                "actor": "analyst",
                "metadata": {"scope": "limited"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["event_type"] == "note"
        assert data["actor"] == "analyst"
        assert data["metadata"]["scope"] == "limited"

    def test_get_stats_endpoint(self, client: TestClient) -> None:
        """Test GET /api/v1/security/incidents/stats."""
        # Create some incidents
        client.post(
            "/api/v1/security/incidents",
            json={
                "title": "Stats test",
                "description": "Test",
                "severity": "SEV1",
                "incident_type": "PHI_BREACH",
                "reported_by": "tester",
                "phi_involved": True,
            },
        )

        response = client.get("/api/v1/security/incidents/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_incidents" in data
        assert "by_severity" in data
        assert "by_status" in data
        assert "phi_involved_count" in data
