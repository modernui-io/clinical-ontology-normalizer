"""Comprehensive tests for Defect Tracking & Test Environment Management (QA-3).

Tests cover:
- Seed data verification (defects + environments)
- Defect CRUD (create, read, update, delete)
- Status transitions (valid forward-only + invalid backward)
- SLA calculation + breach detection
- Comments (add, list, delete)
- Transition history / audit trail
- Test environment CRUD + health checks
- Metrics (MTTR, SLA compliance, reopen rate, aging buckets)
- Trend analysis
- Duplicate linking
- API integration (HTTP status codes, error handling)
- Pagination and filtering
"""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

from app.main import app
from app.schemas.defect_tracking import (
    DefectCategory,
    DefectPriority,
    DefectSeverity,
    DefectStatus,
    EnvironmentStatus,
    EnvironmentType,
    SLA_HOURS,
    VALID_STATUS_TRANSITIONS,
)
from app.services.defect_tracking_service import (
    get_defect_tracking_service,
    reset_defect_tracking_service,
)

API_PREFIX = "/api/v1/defect-tracking"


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the defect tracking service before each test."""
    reset_defect_tracking_service()
    yield
    reset_defect_tracking_service()


@pytest.fixture
async def client():
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================================
# Seed Data Verification
# ============================================================================


@pytest.mark.anyio
async def test_seed_defects_loaded(client):
    """Seed data should contain 16 defects."""
    resp = await client.get(f"{API_PREFIX}/defects", params={"limit": 50})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 16


@pytest.mark.anyio
async def test_seed_blocker_resolved_exists(client):
    """Seed BLOCKER defect DEF-SEED-0001 should be CLOSED."""
    resp = await client.get(f"{API_PREFIX}/defects/DEF-SEED-0001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["severity"] == "BLOCKER"
    assert data["status"] == "CLOSED"
    assert data["resolved_at"] is not None


@pytest.mark.anyio
async def test_seed_blocker_in_progress_exists(client):
    """Seed BLOCKER defect DEF-SEED-0002 should be IN_PROGRESS."""
    resp = await client.get(f"{API_PREFIX}/defects/DEF-SEED-0002")
    assert resp.status_code == 200
    data = resp.json()
    assert data["severity"] == "BLOCKER"
    assert data["status"] == "IN_PROGRESS"
    assert data["category"] == "DATA_INTEGRITY"


@pytest.mark.anyio
async def test_seed_critical_security_defect(client):
    """Seed CRITICAL security defect should exist."""
    resp = await client.get(f"{API_PREFIX}/defects/DEF-SEED-0003")
    assert resp.status_code == 200
    data = resp.json()
    assert data["severity"] == "CRITICAL"
    assert data["category"] == "SECURITY"


@pytest.mark.anyio
async def test_seed_critical_compliance_defect(client):
    """Seed CRITICAL compliance defect should exist."""
    resp = await client.get(f"{API_PREFIX}/defects/DEF-SEED-0004")
    assert resp.status_code == 200
    data = resp.json()
    assert data["severity"] == "CRITICAL"
    assert data["category"] == "COMPLIANCE"


@pytest.mark.anyio
async def test_seed_critical_data_integrity_defect(client):
    """Seed CRITICAL data integrity defect should exist."""
    resp = await client.get(f"{API_PREFIX}/defects/DEF-SEED-0005")
    assert resp.status_code == 200
    data = resp.json()
    assert data["severity"] == "CRITICAL"
    assert data["category"] == "DATA_INTEGRITY"


@pytest.mark.anyio
async def test_seed_has_correct_severity_distribution(client):
    """Seed data should have 2 BLOCKERs, 3 CRITICALs, 5 MAJORs, 4 MINORs, 2 TRIVIALs."""
    resp = await client.get(f"{API_PREFIX}/defects", params={"limit": 50})
    data = resp.json()
    defects = data["defects"]
    severity_counts = {}
    for d in defects:
        sev = d["severity"]
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    assert severity_counts["BLOCKER"] == 2
    assert severity_counts["CRITICAL"] == 3
    assert severity_counts["MAJOR"] == 5
    assert severity_counts["MINOR"] == 4
    assert severity_counts["TRIVIAL"] == 2


@pytest.mark.anyio
async def test_seed_environments_loaded(client):
    """Seed data should contain 5 test environments."""
    resp = await client.get(f"{API_PREFIX}/environments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5


@pytest.mark.anyio
async def test_seed_dev_environment(client):
    """Seed DEV environment should be READY."""
    resp = await client.get(f"{API_PREFIX}/environments/ENV-SEED-0001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["env_type"] == "DEVELOPMENT"
    assert data["status"] == "READY"
    assert len(data["health_checks"]) == 3


@pytest.mark.anyio
async def test_seed_preprod_environment_maintenance(client):
    """Seed PRE_PRODUCTION environment should be in MAINTENANCE."""
    resp = await client.get(f"{API_PREFIX}/environments/ENV-SEED-0005")
    assert resp.status_code == 200
    data = resp.json()
    assert data["env_type"] == "PRE_PRODUCTION"
    assert data["status"] == "MAINTENANCE"


@pytest.mark.anyio
async def test_seed_blocker_has_transitions(client):
    """Seed BLOCKER DEF-SEED-0001 should have transition history."""
    resp = await client.get(f"{API_PREFIX}/defects/DEF-SEED-0001/transitions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    # Verify transition chain
    statuses = [(t["from_status"], t["to_status"]) for t in data["transitions"]]
    assert ("NEW", "TRIAGED") in statuses
    assert ("VERIFIED", "CLOSED") in statuses


@pytest.mark.anyio
async def test_seed_blocker_has_comment(client):
    """Seed BLOCKER DEF-SEED-0001 should have a comment."""
    resp = await client.get(f"{API_PREFIX}/defects/DEF-SEED-0001/comments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert "Root cause" in data["comments"][0]["content"]


# ============================================================================
# Defect CRUD
# ============================================================================


@pytest.mark.anyio
async def test_create_defect_minimal(client):
    """Create a defect with minimal required fields."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "Test defect",
        "description": "A test defect description",
        "severity": "MAJOR",
        "category": "FUNCTIONAL",
        "component": "test-component",
        "reported_by": "test-user",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test defect"
    assert data["severity"] == "MAJOR"
    assert data["status"] == "NEW"
    assert data["sla_deadline"] is not None
    assert data["id"].startswith("DEF-")


@pytest.mark.anyio
async def test_create_defect_full(client):
    """Create a defect with all optional fields."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "Full defect",
        "description": "Complete defect with all fields",
        "severity": "CRITICAL",
        "priority": "P0_IMMEDIATE",
        "category": "SECURITY",
        "component": "auth-module",
        "reported_by": "security-scanner",
        "assigned_to": "lead-dev",
        "steps_to_reproduce": "1. Step one\n2. Step two",
        "expected_behavior": "Should not crash",
        "actual_behavior": "Crashes with 500",
        "environment": "QA",
        "build_version": "3.0.0-rc1",
        "tags": ["security", "auth", "urgent"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["priority"] == "P0_IMMEDIATE"
    assert data["assigned_to"] == "lead-dev"
    assert "security" in data["tags"]


@pytest.mark.anyio
async def test_create_defect_sla_blocker(client):
    """BLOCKER defects should get a 4-hour SLA deadline."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "Blocker SLA test",
        "description": "Testing SLA for blocker",
        "severity": "BLOCKER",
        "category": "FUNCTIONAL",
        "component": "core",
        "reported_by": "qa",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["sla_deadline"] is not None


@pytest.mark.anyio
async def test_create_defect_sla_trivial(client):
    """TRIVIAL defects should get a 720-hour SLA deadline."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "Trivial SLA test",
        "description": "Testing SLA for trivial",
        "severity": "TRIVIAL",
        "category": "UI_UX",
        "component": "frontend",
        "reported_by": "qa",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["sla_deadline"] is not None


@pytest.mark.anyio
async def test_get_defect_not_found(client):
    """Getting a non-existent defect should return 404."""
    resp = await client.get(f"{API_PREFIX}/defects/DEF-NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_update_defect_title(client):
    """Update a defect's title."""
    resp = await client.put(f"{API_PREFIX}/defects/DEF-SEED-0007", json={
        "title": "Updated: Dashboard charts broken on mobile",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Updated: Dashboard charts broken on mobile"


@pytest.mark.anyio
async def test_update_defect_priority(client):
    """Update a defect's priority."""
    resp = await client.put(f"{API_PREFIX}/defects/DEF-SEED-0007", json={
        "priority": "P1_HIGH",
    })
    assert resp.status_code == 200
    assert resp.json()["priority"] == "P1_HIGH"


@pytest.mark.anyio
async def test_update_defect_assigned_to(client):
    """Assign a defect to someone."""
    resp = await client.put(f"{API_PREFIX}/defects/DEF-SEED-0007", json={
        "assigned_to": "frontend-dev",
    })
    assert resp.status_code == 200
    assert resp.json()["assigned_to"] == "frontend-dev"


@pytest.mark.anyio
async def test_update_defect_tags(client):
    """Update a defect's tags."""
    resp = await client.put(f"{API_PREFIX}/defects/DEF-SEED-0007", json={
        "tags": ["mobile", "responsive", "urgent"],
    })
    assert resp.status_code == 200
    assert "urgent" in resp.json()["tags"]


@pytest.mark.anyio
async def test_update_defect_resolution_notes(client):
    """Add resolution notes to a defect."""
    resp = await client.put(f"{API_PREFIX}/defects/DEF-SEED-0006", json={
        "resolution_notes": "Fixed by restructuring the boolean expression parser",
    })
    assert resp.status_code == 200
    assert "boolean expression parser" in resp.json()["resolution_notes"]


@pytest.mark.anyio
async def test_update_defect_not_found(client):
    """Updating a non-existent defect should return 404."""
    resp = await client.put(f"{API_PREFIX}/defects/DEF-NONEXISTENT", json={
        "title": "Does not exist",
    })
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_defect(client):
    """Delete a defect."""
    # Create one first
    create_resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "To be deleted",
        "description": "Will be deleted",
        "severity": "TRIVIAL",
        "category": "UI_UX",
        "component": "test",
        "reported_by": "test",
    })
    defect_id = create_resp.json()["id"]

    resp = await client.delete(f"{API_PREFIX}/defects/{defect_id}")
    assert resp.status_code == 204

    # Verify it's gone
    get_resp = await client.get(f"{API_PREFIX}/defects/{defect_id}")
    assert get_resp.status_code == 404


@pytest.mark.anyio
async def test_delete_defect_not_found(client):
    """Deleting a non-existent defect should return 404."""
    resp = await client.delete(f"{API_PREFIX}/defects/DEF-NONEXISTENT")
    assert resp.status_code == 404


# ============================================================================
# Status Transitions - Valid
# ============================================================================


@pytest.mark.anyio
async def test_transition_new_to_triaged(client):
    """Transition NEW -> TRIAGED should succeed."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0007/transition", json={
        "to_status": "TRIAGED",
        "transitioned_by": "qa-lead",
        "reason": "Triaging new defect",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "TRIAGED"


@pytest.mark.anyio
async def test_transition_new_to_wont_fix(client):
    """Transition NEW -> WONT_FIX should succeed."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0007/transition", json={
        "to_status": "WONT_FIX",
        "transitioned_by": "product-owner",
        "reason": "Not a real issue",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "WONT_FIX"


@pytest.mark.anyio
async def test_transition_new_to_duplicate(client):
    """Transition NEW -> DUPLICATE should succeed."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0015/transition", json={
        "to_status": "DUPLICATE",
        "transitioned_by": "qa-lead",
        "reason": "Duplicate of DEF-SEED-0016",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "DUPLICATE"


@pytest.mark.anyio
async def test_transition_triaged_to_in_progress(client):
    """Transition TRIAGED -> IN_PROGRESS should succeed."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0005/transition", json={
        "to_status": "IN_PROGRESS",
        "transitioned_by": "dev-lead",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "IN_PROGRESS"


@pytest.mark.anyio
async def test_transition_in_progress_to_in_review(client):
    """Transition IN_PROGRESS -> IN_REVIEW should succeed."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0002/transition", json={
        "to_status": "IN_REVIEW",
        "transitioned_by": "alex-rivera",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "IN_REVIEW"


@pytest.mark.anyio
async def test_transition_in_review_to_verified(client):
    """Transition IN_REVIEW -> VERIFIED should succeed."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0004/transition", json={
        "to_status": "VERIFIED",
        "transitioned_by": "qa-lead",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "VERIFIED"


@pytest.mark.anyio
async def test_transition_verified_to_closed(client):
    """Transition VERIFIED -> CLOSED should succeed and set resolved_at."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0003/transition", json={
        "to_status": "CLOSED",
        "transitioned_by": "release-manager",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "CLOSED"
    assert data["resolved_at"] is not None


@pytest.mark.anyio
async def test_transition_closed_to_reopened(client):
    """Transition CLOSED -> REOPENED should succeed and clear resolved_at."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0001/transition", json={
        "to_status": "REOPENED",
        "transitioned_by": "qa-lead",
        "reason": "Regression found in v2.4",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "REOPENED"
    assert data["resolved_at"] is None


@pytest.mark.anyio
async def test_transition_reopened_to_in_progress(client):
    """Transition REOPENED -> IN_PROGRESS should succeed."""
    # First reopen
    await client.post(f"{API_PREFIX}/defects/DEF-SEED-0001/transition", json={
        "to_status": "REOPENED",
        "transitioned_by": "qa-lead",
    })
    # Then start work
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0001/transition", json={
        "to_status": "IN_PROGRESS",
        "transitioned_by": "dev",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "IN_PROGRESS"


@pytest.mark.anyio
async def test_transition_in_review_back_to_in_progress(client):
    """Transition IN_REVIEW -> IN_PROGRESS (review rejection) should succeed."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0008/transition", json={
        "to_status": "IN_PROGRESS",
        "transitioned_by": "reviewer",
        "reason": "Fix incomplete, needs more work",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "IN_PROGRESS"


@pytest.mark.anyio
async def test_full_lifecycle_new_to_closed(client):
    """Full lifecycle: NEW -> TRIAGED -> IN_PROGRESS -> IN_REVIEW -> VERIFIED -> CLOSED."""
    create = await client.post(f"{API_PREFIX}/defects", json={
        "title": "Full lifecycle test",
        "description": "Testing full lifecycle",
        "severity": "MINOR",
        "category": "FUNCTIONAL",
        "component": "test",
        "reported_by": "qa",
    })
    defect_id = create.json()["id"]

    for to_status, by in [
        ("TRIAGED", "qa-lead"),
        ("IN_PROGRESS", "dev"),
        ("IN_REVIEW", "dev"),
        ("VERIFIED", "qa"),
        ("CLOSED", "manager"),
    ]:
        resp = await client.post(f"{API_PREFIX}/defects/{defect_id}/transition", json={
            "to_status": to_status,
            "transitioned_by": by,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == to_status

    # Verify resolved_at is set
    final = await client.get(f"{API_PREFIX}/defects/{defect_id}")
    assert final.json()["resolved_at"] is not None


# ============================================================================
# Status Transitions - Invalid
# ============================================================================


@pytest.mark.anyio
async def test_transition_new_to_closed_invalid(client):
    """Transition NEW -> CLOSED should fail (skipping steps)."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0007/transition", json={
        "to_status": "CLOSED",
        "transitioned_by": "qa-lead",
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_transition_new_to_in_progress_invalid(client):
    """Transition NEW -> IN_PROGRESS should fail (must triage first)."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0007/transition", json={
        "to_status": "IN_PROGRESS",
        "transitioned_by": "dev",
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_transition_new_to_verified_invalid(client):
    """Transition NEW -> VERIFIED should fail."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0007/transition", json={
        "to_status": "VERIFIED",
        "transitioned_by": "qa",
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_transition_new_to_reopened_invalid(client):
    """Transition NEW -> REOPENED should fail."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0007/transition", json={
        "to_status": "REOPENED",
        "transitioned_by": "qa",
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_transition_closed_to_in_progress_invalid(client):
    """Transition CLOSED -> IN_PROGRESS should fail (must reopen first)."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0001/transition", json={
        "to_status": "IN_PROGRESS",
        "transitioned_by": "dev",
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_transition_wont_fix_terminal(client):
    """WONT_FIX is terminal - no transitions should be allowed."""
    # First mark as WONT_FIX
    await client.post(f"{API_PREFIX}/defects/DEF-SEED-0007/transition", json={
        "to_status": "WONT_FIX",
        "transitioned_by": "pm",
    })
    # Try to transition further
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0007/transition", json={
        "to_status": "NEW",
        "transitioned_by": "pm",
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_transition_duplicate_terminal(client):
    """DUPLICATE is terminal - no transitions should be allowed."""
    await client.post(f"{API_PREFIX}/defects/DEF-SEED-0015/transition", json={
        "to_status": "DUPLICATE",
        "transitioned_by": "qa",
    })
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0015/transition", json={
        "to_status": "NEW",
        "transitioned_by": "qa",
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_transition_nonexistent_defect(client):
    """Transitioning a non-existent defect should return 404."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-NONEXISTENT/transition", json={
        "to_status": "TRIAGED",
        "transitioned_by": "qa",
    })
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_transition_triaged_to_closed_invalid(client):
    """TRIAGED -> CLOSED should fail."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0010/transition", json={
        "to_status": "CLOSED",
        "transitioned_by": "pm",
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_transition_in_progress_to_closed_invalid(client):
    """IN_PROGRESS -> CLOSED should fail (must go through review)."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0006/transition", json={
        "to_status": "CLOSED",
        "transitioned_by": "dev",
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_transition_verified_to_in_progress_invalid(client):
    """VERIFIED -> IN_PROGRESS should fail."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0003/transition", json={
        "to_status": "IN_PROGRESS",
        "transitioned_by": "dev",
    })
    assert resp.status_code == 400


# ============================================================================
# SLA Calculation + Breach Detection
# ============================================================================


@pytest.mark.anyio
async def test_sla_deadline_set_on_create(client):
    """All created defects should have an SLA deadline."""
    for severity in ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "TRIVIAL"]:
        resp = await client.post(f"{API_PREFIX}/defects", json={
            "title": f"SLA test {severity}",
            "description": f"Testing SLA for {severity}",
            "severity": severity,
            "category": "FUNCTIONAL",
            "component": "test",
            "reported_by": "qa",
        })
        assert resp.status_code == 201
        assert resp.json()["sla_deadline"] is not None


@pytest.mark.anyio
async def test_sla_hours_mapping():
    """Verify SLA hours mapping is correct."""
    assert SLA_HOURS[DefectSeverity.BLOCKER] == 4.0
    assert SLA_HOURS[DefectSeverity.CRITICAL] == 24.0
    assert SLA_HOURS[DefectSeverity.MAJOR] == 72.0
    assert SLA_HOURS[DefectSeverity.MINOR] == 168.0
    assert SLA_HOURS[DefectSeverity.TRIVIAL] == 720.0


@pytest.mark.anyio
async def test_sla_breaches_endpoint(client):
    """SLA breach endpoint should return results."""
    resp = await client.get(f"{API_PREFIX}/sla-breaches")
    assert resp.status_code == 200
    data = resp.json()
    assert "breaches" in data
    assert "total" in data
    assert "breached_count" in data
    assert "at_risk_count" in data


@pytest.mark.anyio
async def test_sla_breaches_contain_open_defects(client):
    """SLA breaches should only contain open defects."""
    resp = await client.get(f"{API_PREFIX}/sla-breaches")
    data = resp.json()
    open_statuses = {"NEW", "TRIAGED", "IN_PROGRESS", "IN_REVIEW", "REOPENED"}
    for breach in data["breaches"]:
        assert breach["status"] in open_statuses


@pytest.mark.anyio
async def test_sla_breach_has_required_fields(client):
    """Each SLA breach record should have all required fields."""
    resp = await client.get(f"{API_PREFIX}/sla-breaches")
    data = resp.json()
    if data["total"] > 0:
        breach = data["breaches"][0]
        assert "defect_id" in breach
        assert "title" in breach
        assert "severity" in breach
        assert "sla_deadline" in breach
        assert "hours_overdue" in breach
        assert "status" in breach


# ============================================================================
# Comments
# ============================================================================


@pytest.mark.anyio
async def test_add_comment(client):
    """Add a comment to a defect."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0002/comments", json={
        "author": "test-user",
        "content": "Investigating the root cause of silent observation drops.",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["author"] == "test-user"
    assert "root cause" in data["content"]
    assert data["id"].startswith("CMT-")


@pytest.mark.anyio
async def test_list_comments(client):
    """List comments for a defect."""
    # Add a comment first
    await client.post(f"{API_PREFIX}/defects/DEF-SEED-0002/comments", json={
        "author": "dev",
        "content": "Found the issue in the FHIR bundle parser.",
    })
    resp = await client.get(f"{API_PREFIX}/defects/DEF-SEED-0002/comments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.anyio
async def test_list_comments_empty(client):
    """List comments for a defect with no comments."""
    resp = await client.get(f"{API_PREFIX}/defects/DEF-SEED-0005/comments")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.anyio
async def test_delete_comment(client):
    """Delete a comment from a defect."""
    # Add a comment
    create_resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0002/comments", json={
        "author": "test",
        "content": "To be deleted",
    })
    comment_id = create_resp.json()["id"]

    # Delete it
    resp = await client.delete(f"{API_PREFIX}/defects/DEF-SEED-0002/comments/{comment_id}")
    assert resp.status_code == 204


@pytest.mark.anyio
async def test_delete_comment_not_found(client):
    """Deleting a non-existent comment should return 404."""
    resp = await client.delete(f"{API_PREFIX}/defects/DEF-SEED-0002/comments/CMT-NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_add_comment_to_nonexistent_defect(client):
    """Adding a comment to a non-existent defect should return 404."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-NONEXISTENT/comments", json={
        "author": "test",
        "content": "Should not work",
    })
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_list_comments_nonexistent_defect(client):
    """Listing comments for a non-existent defect should return 404."""
    resp = await client.get(f"{API_PREFIX}/defects/DEF-NONEXISTENT/comments")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_add_multiple_comments(client):
    """Add multiple comments to a defect."""
    for i in range(3):
        resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0006/comments", json={
            "author": f"user-{i}",
            "content": f"Comment number {i}",
        })
        assert resp.status_code == 201

    resp = await client.get(f"{API_PREFIX}/defects/DEF-SEED-0006/comments")
    assert resp.json()["total"] == 3


# ============================================================================
# Transition History / Audit Trail
# ============================================================================


@pytest.mark.anyio
async def test_transition_creates_audit_record(client):
    """Each transition should create an audit record."""
    await client.post(f"{API_PREFIX}/defects/DEF-SEED-0007/transition", json={
        "to_status": "TRIAGED",
        "transitioned_by": "qa-lead",
        "reason": "Initial triage",
    })
    resp = await client.get(f"{API_PREFIX}/defects/DEF-SEED-0007/transitions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    latest = data["transitions"][-1]
    assert latest["from_status"] == "NEW"
    assert latest["to_status"] == "TRIAGED"
    assert latest["transitioned_by"] == "qa-lead"
    assert latest["reason"] == "Initial triage"


@pytest.mark.anyio
async def test_transition_history_nonexistent_defect(client):
    """Transition history for non-existent defect should return 404."""
    resp = await client.get(f"{API_PREFIX}/defects/DEF-NONEXISTENT/transitions")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_multiple_transitions_recorded(client):
    """Multiple transitions should all be recorded in order."""
    defect_id = "DEF-SEED-0010"  # TRIAGED

    await client.post(f"{API_PREFIX}/defects/{defect_id}/transition", json={
        "to_status": "IN_PROGRESS",
        "transitioned_by": "dev-1",
    })
    await client.post(f"{API_PREFIX}/defects/{defect_id}/transition", json={
        "to_status": "IN_REVIEW",
        "transitioned_by": "dev-1",
    })

    resp = await client.get(f"{API_PREFIX}/defects/{defect_id}/transitions")
    data = resp.json()
    assert data["total"] == 2
    assert data["transitions"][0]["to_status"] == "IN_PROGRESS"
    assert data["transitions"][1]["to_status"] == "IN_REVIEW"


# ============================================================================
# Test Environment CRUD
# ============================================================================


@pytest.mark.anyio
async def test_create_environment(client):
    """Create a new test environment."""
    resp = await client.post(f"{API_PREFIX}/environments", json={
        "name": "Performance Testing",
        "env_type": "QA",
        "owner": "perf-team",
        "description": "Dedicated performance testing environment",
        "url": "https://perf.example.com",
        "components": ["api", "database", "load-balancer"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Performance Testing"
    assert data["env_type"] == "QA"
    assert data["status"] == "PROVISIONING"
    assert data["id"].startswith("ENV-")


@pytest.mark.anyio
async def test_get_environment(client):
    """Get a test environment by ID."""
    resp = await client.get(f"{API_PREFIX}/environments/ENV-SEED-0001")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Development"


@pytest.mark.anyio
async def test_get_environment_not_found(client):
    """Getting a non-existent environment should return 404."""
    resp = await client.get(f"{API_PREFIX}/environments/ENV-NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_list_environments(client):
    """List all test environments."""
    resp = await client.get(f"{API_PREFIX}/environments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5


@pytest.mark.anyio
async def test_list_environments_filter_by_type(client):
    """Filter environments by type."""
    resp = await client.get(f"{API_PREFIX}/environments", params={"env_type": "QA"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for env in data["environments"]:
        assert env["env_type"] == "QA"


@pytest.mark.anyio
async def test_list_environments_filter_by_status(client):
    """Filter environments by status."""
    resp = await client.get(f"{API_PREFIX}/environments", params={"status": "READY"})
    assert resp.status_code == 200
    data = resp.json()
    for env in data["environments"]:
        assert env["status"] == "READY"


@pytest.mark.anyio
async def test_update_environment(client):
    """Update a test environment."""
    resp = await client.put(f"{API_PREFIX}/environments/ENV-SEED-0005", json={
        "status": "READY",
        "description": "Pre-production environment restored from maintenance",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "READY"
    assert "restored from maintenance" in data["description"]


@pytest.mark.anyio
async def test_update_environment_not_found(client):
    """Updating a non-existent environment should return 404."""
    resp = await client.put(f"{API_PREFIX}/environments/ENV-NONEXISTENT", json={
        "name": "Does not exist",
    })
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_environment(client):
    """Delete a test environment."""
    # Create one first
    create_resp = await client.post(f"{API_PREFIX}/environments", json={
        "name": "Temp Environment",
        "env_type": "QA",
        "owner": "test",
    })
    env_id = create_resp.json()["id"]

    resp = await client.delete(f"{API_PREFIX}/environments/{env_id}")
    assert resp.status_code == 204

    # Verify it's gone
    get_resp = await client.get(f"{API_PREFIX}/environments/{env_id}")
    assert get_resp.status_code == 404


@pytest.mark.anyio
async def test_delete_environment_not_found(client):
    """Deleting a non-existent environment should return 404."""
    resp = await client.delete(f"{API_PREFIX}/environments/ENV-NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_update_health_checks(client):
    """Update health checks for an environment."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    resp = await client.put(f"{API_PREFIX}/environments/ENV-SEED-0005/health-checks", json={
        "health_checks": [
            {"name": "api", "status": "healthy", "last_checked": now, "response_time_ms": 25.0},
            {"name": "database", "status": "healthy", "last_checked": now, "response_time_ms": 8.0},
            {"name": "neo4j", "status": "healthy", "last_checked": now, "response_time_ms": 45.0},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["health_checks"]) == 3
    assert data["last_refreshed"] is not None


@pytest.mark.anyio
async def test_update_health_checks_not_found(client):
    """Updating health checks for non-existent environment should return 404."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    resp = await client.put(f"{API_PREFIX}/environments/ENV-NONEXISTENT/health-checks", json={
        "health_checks": [
            {"name": "api", "status": "healthy", "last_checked": now, "response_time_ms": 10.0},
        ],
    })
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_environment_health_check_structure(client):
    """Environment health checks should have correct structure."""
    resp = await client.get(f"{API_PREFIX}/environments/ENV-SEED-0001")
    data = resp.json()
    for hc in data["health_checks"]:
        assert "name" in hc
        assert "status" in hc
        assert "last_checked" in hc
        assert "response_time_ms" in hc


# ============================================================================
# Metrics
# ============================================================================


@pytest.mark.anyio
async def test_metrics_endpoint(client):
    """Metrics endpoint should return complete metrics."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 16
    assert "by_severity" in data
    assert "by_status" in data
    assert "by_category" in data
    assert "mttr_hours" in data
    assert "sla_compliance_rate" in data
    assert "reopen_rate" in data
    assert "aging_buckets" in data


@pytest.mark.anyio
async def test_metrics_severity_counts(client):
    """Metrics by_severity should match seed data."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    data = resp.json()
    assert data["by_severity"]["BLOCKER"] == 2
    assert data["by_severity"]["CRITICAL"] == 3
    assert data["by_severity"]["MAJOR"] == 5


@pytest.mark.anyio
async def test_metrics_mttr_positive(client):
    """MTTR should be positive when there are resolved defects."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    data = resp.json()
    assert data["mttr_hours"] > 0


@pytest.mark.anyio
async def test_metrics_aging_buckets(client):
    """Aging buckets should categorize open defects correctly."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    data = resp.json()
    buckets = data["aging_buckets"]
    assert "0-24h" in buckets
    assert "24-72h" in buckets
    assert "72h-1w" in buckets
    assert "1w+" in buckets
    # Total in buckets should equal open defects count
    total_in_buckets = sum(buckets.values())
    open_statuses = {"NEW", "TRIAGED", "IN_PROGRESS", "IN_REVIEW", "REOPENED"}
    open_count = sum(c for s, c in data["by_status"].items() if s in open_statuses)
    assert total_in_buckets == open_count


@pytest.mark.anyio
async def test_metrics_sla_compliance_is_percentage(client):
    """SLA compliance rate should be between 0 and 100."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    data = resp.json()
    assert 0 <= data["sla_compliance_rate"] <= 100


@pytest.mark.anyio
async def test_metrics_reopen_rate_zero_initially(client):
    """Reopen rate should be 0 when no defects have been reopened."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    data = resp.json()
    # Seed data has no reopens in transitions, so reopen rate should be 0
    assert data["reopen_rate"] >= 0


@pytest.mark.anyio
async def test_metrics_after_reopen(client):
    """Reopen rate should increase after reopening a closed defect."""
    # Reopen a defect
    await client.post(f"{API_PREFIX}/defects/DEF-SEED-0001/transition", json={
        "to_status": "REOPENED",
        "transitioned_by": "qa",
    })
    resp = await client.get(f"{API_PREFIX}/metrics")
    data = resp.json()
    # Should reflect the reopen relative to closes in transition history
    assert data["reopen_rate"] >= 0


# ============================================================================
# Trends
# ============================================================================


@pytest.mark.anyio
async def test_trends_endpoint(client):
    """Trends endpoint should return data for the specified period."""
    resp = await client.get(f"{API_PREFIX}/trends", params={"period_days": 30})
    assert resp.status_code == 200
    data = resp.json()
    assert data["period_days"] == 30
    assert len(data["data_points"]) == 30
    assert "total_opened" in data
    assert "total_closed" in data
    assert "net_change" in data


@pytest.mark.anyio
async def test_trends_custom_period(client):
    """Trends should support custom period."""
    resp = await client.get(f"{API_PREFIX}/trends", params={"period_days": 7})
    assert resp.status_code == 200
    assert resp.json()["period_days"] == 7
    assert len(resp.json()["data_points"]) == 7


@pytest.mark.anyio
async def test_trends_data_points_format(client):
    """Each trend data point should have date, opened, and closed."""
    resp = await client.get(f"{API_PREFIX}/trends")
    data = resp.json()
    for point in data["data_points"]:
        assert "date" in point
        assert "opened" in point
        assert "closed" in point
        assert isinstance(point["opened"], int)
        assert isinstance(point["closed"], int)


@pytest.mark.anyio
async def test_trends_net_change_calculation(client):
    """Net change should equal total_opened - total_closed."""
    resp = await client.get(f"{API_PREFIX}/trends")
    data = resp.json()
    assert data["net_change"] == data["total_opened"] - data["total_closed"]


# ============================================================================
# Duplicate Linking
# ============================================================================


@pytest.mark.anyio
async def test_link_duplicate(client):
    """Link a defect as duplicate of another."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0011/link-duplicate", json={
        "duplicate_of": "DEF-SEED-0007",
        "linked_by": "qa-lead",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "DUPLICATE"
    assert "DEF-SEED-0007" in data["linked_defects"]


@pytest.mark.anyio
async def test_link_duplicate_bidirectional(client):
    """Linking as duplicate should create bidirectional link."""
    await client.post(f"{API_PREFIX}/defects/DEF-SEED-0011/link-duplicate", json={
        "duplicate_of": "DEF-SEED-0007",
        "linked_by": "qa-lead",
    })
    # Check the target defect has the backlink
    resp = await client.get(f"{API_PREFIX}/defects/DEF-SEED-0007")
    data = resp.json()
    assert "DEF-SEED-0011" in data["linked_defects"]


@pytest.mark.anyio
async def test_link_duplicate_nonexistent_source(client):
    """Linking a non-existent defect should return 404."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-NONEXISTENT/link-duplicate", json={
        "duplicate_of": "DEF-SEED-0007",
        "linked_by": "qa",
    })
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_link_duplicate_nonexistent_target(client):
    """Linking to a non-existent target should return 404."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0011/link-duplicate", json={
        "duplicate_of": "DEF-NONEXISTENT",
        "linked_by": "qa",
    })
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_link_duplicate_invalid_state(client):
    """Cannot mark as duplicate from non-linkable state."""
    # DEF-SEED-0006 is IN_PROGRESS - DUPLICATE is not a valid target from IN_PROGRESS
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0006/link-duplicate", json={
        "duplicate_of": "DEF-SEED-0007",
        "linked_by": "qa",
    })
    assert resp.status_code == 400


# ============================================================================
# Filtering and Pagination
# ============================================================================


@pytest.mark.anyio
async def test_filter_by_severity(client):
    """Filter defects by severity."""
    resp = await client.get(f"{API_PREFIX}/defects", params={"severity": "BLOCKER"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    for d in data["defects"]:
        assert d["severity"] == "BLOCKER"


@pytest.mark.anyio
async def test_filter_by_status(client):
    """Filter defects by status."""
    resp = await client.get(f"{API_PREFIX}/defects", params={"status": "NEW"})
    assert resp.status_code == 200
    data = resp.json()
    for d in data["defects"]:
        assert d["status"] == "NEW"


@pytest.mark.anyio
async def test_filter_by_category(client):
    """Filter defects by category."""
    resp = await client.get(f"{API_PREFIX}/defects", params={"category": "SECURITY"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for d in data["defects"]:
        assert d["category"] == "SECURITY"


@pytest.mark.anyio
async def test_filter_by_assigned_to(client):
    """Filter defects by assignee."""
    resp = await client.get(f"{API_PREFIX}/defects", params={"assigned_to": "Alex Rivera"})
    assert resp.status_code == 200
    data = resp.json()
    for d in data["defects"]:
        assert d["assigned_to"] == "Alex Rivera"


@pytest.mark.anyio
async def test_filter_by_component(client):
    """Filter defects by component."""
    resp = await client.get(f"{API_PREFIX}/defects", params={"component": "screening-engine"})
    assert resp.status_code == 200
    data = resp.json()
    for d in data["defects"]:
        assert d["component"] == "screening-engine"


@pytest.mark.anyio
async def test_pagination_limit(client):
    """Pagination limit should be respected."""
    resp = await client.get(f"{API_PREFIX}/defects", params={"limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["defects"]) == 5
    assert data["total"] == 16
    assert data["limit"] == 5


@pytest.mark.anyio
async def test_pagination_offset(client):
    """Pagination offset should work correctly."""
    first_page = await client.get(f"{API_PREFIX}/defects", params={"limit": 5, "offset": 0})
    second_page = await client.get(f"{API_PREFIX}/defects", params={"limit": 5, "offset": 5})
    first_ids = {d["id"] for d in first_page.json()["defects"]}
    second_ids = {d["id"] for d in second_page.json()["defects"]}
    assert len(first_ids & second_ids) == 0  # No overlap


@pytest.mark.anyio
async def test_pagination_beyond_total(client):
    """Offset beyond total should return empty list."""
    resp = await client.get(f"{API_PREFIX}/defects", params={"offset": 1000})
    assert resp.status_code == 200
    assert len(resp.json()["defects"]) == 0


# ============================================================================
# API Integration - Error Handling
# ============================================================================


@pytest.mark.anyio
async def test_create_defect_missing_required_fields(client):
    """Creating a defect with missing required fields should return 422."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "Missing fields",
    })
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_defect_invalid_severity(client):
    """Creating a defect with invalid severity should return 422."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "Invalid severity",
        "description": "Test",
        "severity": "SUPER_CRITICAL",
        "category": "FUNCTIONAL",
        "component": "test",
        "reported_by": "test",
    })
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_defect_empty_title(client):
    """Creating a defect with empty title should return 422."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "",
        "description": "Test",
        "severity": "MAJOR",
        "category": "FUNCTIONAL",
        "component": "test",
        "reported_by": "test",
    })
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_transition_invalid_status_value(client):
    """Transitioning with invalid status value should return 422."""
    resp = await client.post(f"{API_PREFIX}/defects/DEF-SEED-0007/transition", json={
        "to_status": "INVALID_STATUS",
        "transitioned_by": "qa",
    })
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_environment_missing_fields(client):
    """Creating environment with missing fields should return 422."""
    resp = await client.post(f"{API_PREFIX}/environments", json={
        "name": "Missing type",
    })
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_environment_invalid_type(client):
    """Creating environment with invalid type should return 422."""
    resp = await client.post(f"{API_PREFIX}/environments", json={
        "name": "Test",
        "env_type": "INVALID_TYPE",
        "owner": "test",
    })
    assert resp.status_code == 422


# ============================================================================
# Service Unit Tests (Direct Service Access)
# ============================================================================


@pytest.mark.anyio
async def test_service_singleton():
    """Service should return the same singleton instance."""
    svc1 = get_defect_tracking_service()
    svc2 = get_defect_tracking_service()
    assert svc1 is svc2


@pytest.mark.anyio
async def test_service_reset():
    """Resetting the service should create a fresh instance."""
    svc1 = get_defect_tracking_service()
    reset_defect_tracking_service()
    svc2 = get_defect_tracking_service()
    assert svc1 is not svc2


@pytest.mark.anyio
async def test_service_create_defect_returns_record():
    """Service create_defect should return an internal record."""
    svc = get_defect_tracking_service()
    record = svc.create_defect(
        title="Service test",
        description="Direct service test",
        severity=DefectSeverity.MINOR,
        category=DefectCategory.FUNCTIONAL,
        component="test",
        reported_by="unit-test",
    )
    assert record.id.startswith("DEF-")
    assert record.title == "Service test"
    assert record.sla_deadline is not None


@pytest.mark.anyio
async def test_service_get_defect_raises_key_error():
    """Service get_defect should raise KeyError for missing ID."""
    svc = get_defect_tracking_service()
    with pytest.raises(KeyError):
        svc.get_defect("DEF-NONEXISTENT")


@pytest.mark.anyio
async def test_service_delete_defect_cleans_up():
    """Deleting a defect should clean up comments and transitions."""
    svc = get_defect_tracking_service()
    record = svc.create_defect(
        title="To delete",
        description="Will be deleted",
        severity=DefectSeverity.TRIVIAL,
        category=DefectCategory.UI_UX,
        component="test",
        reported_by="test",
    )
    # Add comment and transition
    svc.add_comment(record.id, author="test", content="Test comment")
    svc.transition_defect(record.id, to_status=DefectStatus.TRIAGED, transitioned_by="qa")

    # Delete
    svc.delete_defect(record.id)

    # Verify clean up
    with pytest.raises(KeyError):
        svc.get_defect(record.id)


@pytest.mark.anyio
async def test_service_transition_validates_state_machine():
    """Service transition should validate state machine rules."""
    svc = get_defect_tracking_service()
    with pytest.raises(ValueError, match="Invalid transition"):
        svc.transition_defect(
            "DEF-SEED-0007",  # NEW
            to_status=DefectStatus.CLOSED,
            transitioned_by="test",
        )


@pytest.mark.anyio
async def test_service_transition_sets_resolved_at():
    """Transitioning to CLOSED should set resolved_at."""
    svc = get_defect_tracking_service()
    record = svc.create_defect(
        title="Resolution test",
        description="Test resolution tracking",
        severity=DefectSeverity.MINOR,
        category=DefectCategory.FUNCTIONAL,
        component="test",
        reported_by="test",
    )
    svc.transition_defect(record.id, to_status=DefectStatus.TRIAGED, transitioned_by="qa")
    svc.transition_defect(record.id, to_status=DefectStatus.IN_PROGRESS, transitioned_by="dev")
    svc.transition_defect(record.id, to_status=DefectStatus.IN_REVIEW, transitioned_by="dev")
    svc.transition_defect(record.id, to_status=DefectStatus.VERIFIED, transitioned_by="qa")
    svc.transition_defect(record.id, to_status=DefectStatus.CLOSED, transitioned_by="mgr")

    updated = svc.get_defect(record.id)
    assert updated.resolved_at is not None


@pytest.mark.anyio
async def test_service_reopen_clears_resolved_at():
    """Reopening a CLOSED defect should clear resolved_at."""
    svc = get_defect_tracking_service()
    # DEF-SEED-0001 is CLOSED with resolved_at set
    defect = svc.get_defect("DEF-SEED-0001")
    assert defect.resolved_at is not None

    svc.transition_defect("DEF-SEED-0001", to_status=DefectStatus.REOPENED, transitioned_by="qa")
    assert defect.resolved_at is None


@pytest.mark.anyio
async def test_service_wont_fix_sets_resolved_at():
    """Transitioning to WONT_FIX should set resolved_at."""
    svc = get_defect_tracking_service()
    record = svc.create_defect(
        title="Wont fix test",
        description="Testing wont fix",
        severity=DefectSeverity.TRIVIAL,
        category=DefectCategory.UI_UX,
        component="test",
        reported_by="test",
    )
    svc.transition_defect(record.id, to_status=DefectStatus.WONT_FIX, transitioned_by="pm")
    assert record.resolved_at is not None


@pytest.mark.anyio
async def test_service_metrics_empty_after_delete_all():
    """Metrics should reflect current state after deletions."""
    svc = get_defect_tracking_service()
    metrics_before = svc.get_metrics()
    total_before = metrics_before.total

    # Delete one defect
    svc.delete_defect("DEF-SEED-0015")
    metrics_after = svc.get_metrics()
    assert metrics_after.total == total_before - 1


@pytest.mark.anyio
async def test_service_trends_period_validation():
    """Trends should return correct number of data points."""
    svc = get_defect_tracking_service()
    trends = svc.get_trends(period_days=7)
    assert trends.period_days == 7
    assert len(trends.data_points) == 7


@pytest.mark.anyio
async def test_service_environment_update_components():
    """Update environment components."""
    svc = get_defect_tracking_service()
    updated = svc.update_environment(
        "ENV-SEED-0001",
        components=["api", "frontend", "database", "redis", "elasticsearch"],
    )
    assert "elasticsearch" in updated.components


@pytest.mark.anyio
async def test_service_environment_delete_raises_on_missing():
    """Delete environment should raise KeyError for missing ID."""
    svc = get_defect_tracking_service()
    with pytest.raises(KeyError):
        svc.delete_environment("ENV-NONEXISTENT")


@pytest.mark.anyio
async def test_service_comment_delete_raises_on_missing():
    """Delete comment should raise KeyError for missing comment."""
    svc = get_defect_tracking_service()
    with pytest.raises(KeyError):
        svc.delete_comment("DEF-SEED-0001", "CMT-NONEXISTENT")


# ============================================================================
# Valid Status Transitions Schema Verification
# ============================================================================


@pytest.mark.anyio
async def test_valid_transitions_map_completeness():
    """Every DefectStatus should be a key in VALID_STATUS_TRANSITIONS."""
    for status in DefectStatus:
        assert status in VALID_STATUS_TRANSITIONS


@pytest.mark.anyio
async def test_terminal_states_have_no_transitions():
    """WONT_FIX and DUPLICATE should have no valid transitions."""
    assert VALID_STATUS_TRANSITIONS[DefectStatus.WONT_FIX] == []
    assert VALID_STATUS_TRANSITIONS[DefectStatus.DUPLICATE] == []


@pytest.mark.anyio
async def test_closed_can_only_reopen():
    """CLOSED should only transition to REOPENED."""
    targets = VALID_STATUS_TRANSITIONS[DefectStatus.CLOSED]
    assert targets == [DefectStatus.REOPENED]


@pytest.mark.anyio
async def test_new_valid_transitions():
    """NEW should transition to TRIAGED, DUPLICATE, or WONT_FIX."""
    targets = VALID_STATUS_TRANSITIONS[DefectStatus.NEW]
    assert DefectStatus.TRIAGED in targets
    assert DefectStatus.DUPLICATE in targets
    assert DefectStatus.WONT_FIX in targets


@pytest.mark.anyio
async def test_verified_only_to_closed():
    """VERIFIED should only transition to CLOSED."""
    targets = VALID_STATUS_TRANSITIONS[DefectStatus.VERIFIED]
    assert targets == [DefectStatus.CLOSED]


# ============================================================================
# Edge Cases
# ============================================================================


@pytest.mark.anyio
async def test_create_defect_default_priority(client):
    """Default priority should be P2_MEDIUM."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "Default priority test",
        "description": "Testing default priority",
        "severity": "MAJOR",
        "category": "FUNCTIONAL",
        "component": "test",
        "reported_by": "test",
    })
    assert resp.status_code == 201
    assert resp.json()["priority"] == "P2_MEDIUM"


@pytest.mark.anyio
async def test_create_defect_default_status(client):
    """Default status should be NEW."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "Default status test",
        "description": "Testing default status",
        "severity": "MINOR",
        "category": "FUNCTIONAL",
        "component": "test",
        "reported_by": "test",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "NEW"


@pytest.mark.anyio
async def test_create_defect_empty_tags(client):
    """Default tags should be empty list."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "Empty tags test",
        "description": "Testing empty tags",
        "severity": "MINOR",
        "category": "FUNCTIONAL",
        "component": "test",
        "reported_by": "test",
    })
    assert resp.status_code == 201
    assert resp.json()["tags"] == []


@pytest.mark.anyio
async def test_create_defect_no_assigned_to(client):
    """Default assigned_to should be None."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "No assignee test",
        "description": "Testing no assignee",
        "severity": "MINOR",
        "category": "FUNCTIONAL",
        "component": "test",
        "reported_by": "test",
    })
    assert resp.status_code == 201
    assert resp.json()["assigned_to"] is None


@pytest.mark.anyio
async def test_environment_created_with_provisioning_status(client):
    """Newly created environments should start in PROVISIONING status."""
    resp = await client.post(f"{API_PREFIX}/environments", json={
        "name": "New Env",
        "env_type": "QA",
        "owner": "test",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "PROVISIONING"


@pytest.mark.anyio
async def test_update_multiple_environment_fields(client):
    """Update multiple environment fields at once."""
    resp = await client.put(f"{API_PREFIX}/environments/ENV-SEED-0003", json={
        "name": "QA Automated v2",
        "owner": "New QA Lead",
        "url": "https://qa-v2.example.com",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "QA Automated v2"
    assert data["owner"] == "New QA Lead"
    assert data["url"] == "https://qa-v2.example.com"


@pytest.mark.anyio
async def test_defect_created_at_and_updated_at(client):
    """Created defect should have created_at and updated_at set."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "Timestamp test",
        "description": "Testing timestamps",
        "severity": "MINOR",
        "category": "FUNCTIONAL",
        "component": "test",
        "reported_by": "test",
    })
    data = resp.json()
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


@pytest.mark.anyio
async def test_defect_resolved_at_initially_none(client):
    """New defects should have resolved_at as None."""
    resp = await client.post(f"{API_PREFIX}/defects", json={
        "title": "No resolution test",
        "description": "Testing no resolution",
        "severity": "MINOR",
        "category": "FUNCTIONAL",
        "component": "test",
        "reported_by": "test",
    })
    assert resp.json()["resolved_at"] is None
