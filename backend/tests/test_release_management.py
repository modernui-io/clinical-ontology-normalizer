"""Comprehensive tests for Release Management & Deployment Tracking (VPE-8).

Tests cover:
- Seed data verification
- Release CRUD (create, read, update, delete)
- Deployment operations (deploy, list, get)
- Rollback handling
- Release gate management
- Release readiness checking
- SemVer validation and next version suggestions
- DORA metrics computation
- Changelog generation
- Release history
- Error handling (404s, 400s, validation errors)
"""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

from app.main import app
from app.services.release_management_service import (
    get_release_management_service,
    reset_release_management_service,
)

API_PREFIX = "/api/v1/release-management"


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the release management service before each test."""
    reset_release_management_service()
    yield
    reset_release_management_service()


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
async def test_seed_releases_loaded(client):
    """Seed data should contain 6 releases."""
    resp = await client.get(f"{API_PREFIX}/releases", params={"limit": 50})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 6
    assert len(data["releases"]) == 6


@pytest.mark.anyio
async def test_seed_release_v200_exists(client):
    """Seed release v2.0.0 should be retrievable."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.0.0"
    assert data["status"] == "DEPLOYED"
    assert data["release_type"] == "MAJOR"


@pytest.mark.anyio
async def test_seed_release_v210_exists(client):
    """Seed release v2.1.0 should be retrievable."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0002")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.1.0"
    assert data["status"] == "DEPLOYED"


@pytest.mark.anyio
async def test_seed_release_v220_rolled_back(client):
    """Seed release v2.2.0 should be in ROLLED_BACK status."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0003")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.2.0"
    assert data["status"] == "ROLLED_BACK"


@pytest.mark.anyio
async def test_seed_release_v221_hotfix(client):
    """Seed release v2.2.1 should be a HOTFIX."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0004")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.2.1"
    assert data["release_type"] == "HOTFIX"
    assert data["status"] == "DEPLOYED"


@pytest.mark.anyio
async def test_seed_release_v230_testing(client):
    """Seed release v2.3.0 should be in TESTING status."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0005")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.3.0"
    assert data["status"] == "TESTING"


@pytest.mark.anyio
async def test_seed_release_v240_planning(client):
    """Seed release v2.4.0 should be in PLANNING status."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0006")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.4.0"
    assert data["status"] == "PLANNING"


@pytest.mark.anyio
async def test_seed_deployments_exist(client):
    """Seed data should contain deployments."""
    resp = await client.get(f"{API_PREFIX}/deployments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 6


@pytest.mark.anyio
async def test_seed_deployment_detail(client):
    """Seed deployment DEP-SEED-0001 should be retrievable."""
    resp = await client.get(f"{API_PREFIX}/deployments/DEP-SEED-0001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["release_id"] == "REL-SEED-0001"
    assert data["environment"] == "STAGING"
    assert data["status"] == "COMPLETED"


@pytest.mark.anyio
async def test_seed_gates_for_v230(client):
    """Seed release v2.3.0 should have 6 gates (3 passed, 3 pending)."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0005/gates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 6
    passed = [g for g in data["gates"] if g["status"] == "PASSED"]
    pending = [g for g in data["gates"] if g["status"] == "PENDING"]
    assert len(passed) == 3
    assert len(pending) == 3


@pytest.mark.anyio
async def test_seed_gates_for_v200_all_passed(client):
    """Seed release v2.0.0 should have all 6 gates passed."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0001/gates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 6
    for gate in data["gates"]:
        assert gate["status"] == "PASSED"


# ============================================================================
# Release CRUD
# ============================================================================


@pytest.mark.anyio
async def test_create_release(client):
    """Should create a new release with valid semver."""
    payload = {
        "version": "3.0.0",
        "title": "Major Platform Upgrade",
        "description": "Complete platform rewrite",
        "release_type": "MAJOR",
        "release_manager": "Test Manager",
        "features": ["New UI", "New API"],
        "bug_fixes": ["Fixed crash"],
        "breaking_changes": ["New auth required"],
    }
    resp = await client.post(f"{API_PREFIX}/releases", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == "3.0.0"
    assert data["title"] == "Major Platform Upgrade"
    assert data["status"] == "PLANNING"
    assert data["release_type"] == "MAJOR"
    assert data["release_manager"] == "Test Manager"
    assert len(data["features"]) == 2
    assert len(data["bug_fixes"]) == 1
    assert len(data["breaking_changes"]) == 1
    assert data["id"].startswith("REL-")


@pytest.mark.anyio
async def test_create_release_minimal(client):
    """Should create a release with only required fields."""
    payload = {
        "version": "3.1.0",
        "title": "Minor Update",
        "release_type": "MINOR",
        "release_manager": "Manager A",
    }
    resp = await client.post(f"{API_PREFIX}/releases", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == "3.1.0"
    assert data["features"] == []
    assert data["bug_fixes"] == []
    assert data["breaking_changes"] == []
    assert data["description"] is None


@pytest.mark.anyio
async def test_create_release_auto_generates_gates(client):
    """Creating a release should auto-generate 6 gates."""
    payload = {
        "version": "3.2.0",
        "title": "Feature Release",
        "release_type": "MINOR",
        "release_manager": "Manager B",
    }
    resp = await client.post(f"{API_PREFIX}/releases", json=payload)
    assert resp.status_code == 201
    release_id = resp.json()["id"]

    gates_resp = await client.get(f"{API_PREFIX}/releases/{release_id}/gates")
    assert gates_resp.status_code == 200
    gates = gates_resp.json()
    assert gates["total"] == 6
    for gate in gates["gates"]:
        assert gate["status"] == "PENDING"


@pytest.mark.anyio
async def test_create_release_duplicate_version_400(client):
    """Should reject duplicate version."""
    payload = {
        "version": "2.0.0",  # Already exists in seed
        "title": "Duplicate Version",
        "release_type": "MAJOR",
        "release_manager": "Manager",
    }
    resp = await client.post(f"{API_PREFIX}/releases", json=payload)
    assert resp.status_code == 400
    body = resp.json()
    error_msg = body.get("detail") or body.get("message", "")
    assert "already exists" in error_msg


@pytest.mark.anyio
async def test_create_release_invalid_semver_400(client):
    """Should reject invalid semantic version."""
    payload = {
        "version": "not-a-version",
        "title": "Bad Version",
        "release_type": "MINOR",
        "release_manager": "Manager",
    }
    resp = await client.post(f"{API_PREFIX}/releases", json=payload)
    assert resp.status_code == 400
    body = resp.json()
    error_msg = body.get("detail") or body.get("message", "")
    assert "Invalid semantic version" in error_msg


@pytest.mark.anyio
async def test_get_release_not_found(client):
    """Should return 404 for nonexistent release."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_update_release_title(client):
    """Should update release title."""
    payload = {"title": "Updated Title"}
    resp = await client.put(f"{API_PREFIX}/releases/REL-SEED-0006", json=payload)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"


@pytest.mark.anyio
async def test_update_release_description(client):
    """Should update release description."""
    payload = {"description": "New description"}
    resp = await client.put(f"{API_PREFIX}/releases/REL-SEED-0006", json=payload)
    assert resp.status_code == 200
    assert resp.json()["description"] == "New description"


@pytest.mark.anyio
async def test_update_release_features(client):
    """Should update features list."""
    payload = {"features": ["Feature A", "Feature B", "Feature C"]}
    resp = await client.put(f"{API_PREFIX}/releases/REL-SEED-0006", json=payload)
    assert resp.status_code == 200
    assert len(resp.json()["features"]) == 3


@pytest.mark.anyio
async def test_update_release_status_valid_transition(client):
    """Should allow valid status transitions (PLANNING -> DEVELOPMENT)."""
    payload = {"status": "DEVELOPMENT"}
    resp = await client.put(f"{API_PREFIX}/releases/REL-SEED-0006", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "DEVELOPMENT"


@pytest.mark.anyio
async def test_update_release_status_invalid_transition_400(client):
    """Should reject invalid status transitions (PLANNING -> DEPLOYED)."""
    payload = {"status": "DEPLOYED"}
    resp = await client.put(f"{API_PREFIX}/releases/REL-SEED-0006", json=payload)
    assert resp.status_code == 400
    body = resp.json()
    error_msg = body.get("detail") or body.get("message", "")
    assert "Invalid status transition" in error_msg


@pytest.mark.anyio
async def test_update_release_status_cancelled(client):
    """Should allow transitioning to CANCELLED from PLANNING."""
    payload = {"status": "CANCELLED"}
    resp = await client.put(f"{API_PREFIX}/releases/REL-SEED-0006", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


@pytest.mark.anyio
async def test_update_release_not_found(client):
    """Should return 404 for updating nonexistent release."""
    payload = {"title": "X"}
    resp = await client.put(f"{API_PREFIX}/releases/REL-NONEXISTENT", json=payload)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_release(client):
    """Should delete a release."""
    resp = await client.delete(f"{API_PREFIX}/releases/REL-SEED-0006")
    assert resp.status_code == 204

    # Verify it is gone
    resp2 = await client.get(f"{API_PREFIX}/releases/REL-SEED-0006")
    assert resp2.status_code == 404


@pytest.mark.anyio
async def test_delete_release_not_found(client):
    """Should return 404 for deleting nonexistent release."""
    resp = await client.delete(f"{API_PREFIX}/releases/REL-NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_release_cleans_up_gates(client):
    """Deleting a release should remove its gates."""
    # v2.3.0 has gates
    gates_before = await client.get(f"{API_PREFIX}/releases/REL-SEED-0005/gates")
    assert gates_before.status_code == 200
    assert gates_before.json()["total"] == 6

    await client.delete(f"{API_PREFIX}/releases/REL-SEED-0005")

    # Release should be gone
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0005")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_release_cleans_up_deployments(client):
    """Deleting a release should remove its deployments."""
    # v2.0.0 has deployments
    deps_before = await client.get(
        f"{API_PREFIX}/releases/REL-SEED-0001/deployments"
    )
    assert deps_before.status_code == 200
    assert deps_before.json()["total"] >= 2

    await client.delete(f"{API_PREFIX}/releases/REL-SEED-0001")

    # Verify deployments for that release are gone
    resp = await client.get(
        f"{API_PREFIX}/deployments", params={"release_id": "REL-SEED-0001"}
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ============================================================================
# Release List Filtering
# ============================================================================


@pytest.mark.anyio
async def test_list_releases_filter_by_status(client):
    """Should filter releases by status."""
    resp = await client.get(f"{API_PREFIX}/releases", params={"status": "DEPLOYED"})
    assert resp.status_code == 200
    data = resp.json()
    for r in data["releases"]:
        assert r["status"] == "DEPLOYED"
    assert data["total"] == 3  # v2.0.0, v2.1.0, v2.2.1


@pytest.mark.anyio
async def test_list_releases_filter_by_type(client):
    """Should filter releases by type."""
    resp = await client.get(f"{API_PREFIX}/releases", params={"release_type": "HOTFIX"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["releases"][0]["release_type"] == "HOTFIX"


@pytest.mark.anyio
async def test_list_releases_filter_by_status_and_type(client):
    """Should filter releases by both status and type."""
    resp = await client.get(
        f"{API_PREFIX}/releases",
        params={"status": "DEPLOYED", "release_type": "MAJOR"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["releases"][0]["version"] == "2.0.0"


@pytest.mark.anyio
async def test_list_releases_pagination(client):
    """Should paginate releases."""
    resp = await client.get(f"{API_PREFIX}/releases", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["releases"]) == 2
    assert data["total"] == 6
    assert data["limit"] == 2
    assert data["offset"] == 0


@pytest.mark.anyio
async def test_list_releases_pagination_offset(client):
    """Should offset pagination correctly."""
    resp = await client.get(f"{API_PREFIX}/releases", params={"limit": 2, "offset": 4})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["releases"]) == 2
    assert data["offset"] == 4


@pytest.mark.anyio
async def test_list_releases_no_results(client):
    """Should return empty list for non-matching filter."""
    resp = await client.get(
        f"{API_PREFIX}/releases", params={"status": "DEPLOYING"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["releases"] == []


# ============================================================================
# Deployment Operations
# ============================================================================


@pytest.mark.anyio
async def test_deploy_release(client):
    """Should deploy a release to an environment."""
    payload = {
        "environment": "STAGING",
        "deployment_type": "CANARY",
        "deployed_by": "CI/CD",
        "notes": "Automated deployment",
    }
    resp = await client.post(
        f"{API_PREFIX}/releases/REL-SEED-0005/deploy", json=payload
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["release_id"] == "REL-SEED-0005"
    assert data["environment"] == "STAGING"
    assert data["deployment_type"] == "CANARY"
    assert data["deployed_by"] == "CI/CD"
    assert data["id"].startswith("DEP-")
    assert data["status"] in ["COMPLETED", "FAILED"]


@pytest.mark.anyio
async def test_deploy_release_not_found(client):
    """Should return 404 for deploying nonexistent release."""
    payload = {
        "environment": "STAGING",
        "deployed_by": "CI/CD",
    }
    resp = await client.post(
        f"{API_PREFIX}/releases/REL-NONEXISTENT/deploy", json=payload
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_deploy_release_default_strategy(client):
    """Should use BLUE_GREEN as default deployment type."""
    payload = {
        "environment": "DEVELOPMENT",
        "deployed_by": "Dev Team",
    }
    resp = await client.post(
        f"{API_PREFIX}/releases/REL-SEED-0005/deploy", json=payload
    )
    assert resp.status_code == 201
    assert resp.json()["deployment_type"] == "BLUE_GREEN"


@pytest.mark.anyio
async def test_list_all_deployments(client):
    """Should list all deployments."""
    resp = await client.get(f"{API_PREFIX}/deployments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 6


@pytest.mark.anyio
async def test_list_deployments_filter_by_environment(client):
    """Should filter deployments by environment."""
    resp = await client.get(
        f"{API_PREFIX}/deployments", params={"environment": "PRODUCTION"}
    )
    assert resp.status_code == 200
    data = resp.json()
    for d in data["deployments"]:
        assert d["environment"] == "PRODUCTION"


@pytest.mark.anyio
async def test_list_deployments_filter_by_status(client):
    """Should filter deployments by status."""
    resp = await client.get(
        f"{API_PREFIX}/deployments", params={"status": "COMPLETED"}
    )
    assert resp.status_code == 200
    data = resp.json()
    for d in data["deployments"]:
        assert d["status"] == "COMPLETED"


@pytest.mark.anyio
async def test_list_deployments_filter_by_release_id(client):
    """Should filter deployments by release_id."""
    resp = await client.get(
        f"{API_PREFIX}/deployments", params={"release_id": "REL-SEED-0001"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    for d in data["deployments"]:
        assert d["release_id"] == "REL-SEED-0001"


@pytest.mark.anyio
async def test_list_release_deployments(client):
    """Should list deployments for a specific release."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0001/deployments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.anyio
async def test_list_release_deployments_not_found(client):
    """Should return 404 for deployments of nonexistent release."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-NONEXISTENT/deployments")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_deployment(client):
    """Should get a deployment by ID."""
    resp = await client.get(f"{API_PREFIX}/deployments/DEP-SEED-0002")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "DEP-SEED-0002"
    assert data["environment"] == "PRODUCTION"
    assert data["status"] == "COMPLETED"


@pytest.mark.anyio
async def test_get_deployment_not_found(client):
    """Should return 404 for nonexistent deployment."""
    resp = await client.get(f"{API_PREFIX}/deployments/DEP-NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_deployment_has_duration(client):
    """Seed deployment should have duration info."""
    resp = await client.get(f"{API_PREFIX}/deployments/DEP-SEED-0001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["duration_seconds"] == 720
    assert data["health_check_passed"] is True


# ============================================================================
# Rollback Operations
# ============================================================================


@pytest.mark.anyio
async def test_rollback_deployment(client):
    """Should create a rollback deployment."""
    # DEP-SEED-0002 is a completed production deployment with rollback available
    payload = {
        "rolled_back_by": "Ops Team",
        "reason": "Performance regression detected",
    }
    resp = await client.post(
        f"{API_PREFIX}/deployments/DEP-SEED-0002/rollback", json=payload
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["deployment_type"] == "ROLLBACK"
    assert data["status"] == "COMPLETED"
    assert data["deployed_by"] == "Ops Team"


@pytest.mark.anyio
async def test_rollback_already_rolled_back(client):
    """Should reject rollback of already rolled-back deployment."""
    # DEP-SEED-0004 is already ROLLED_BACK
    payload = {
        "rolled_back_by": "Ops Team",
        "reason": "Double rollback",
    }
    resp = await client.post(
        f"{API_PREFIX}/deployments/DEP-SEED-0004/rollback", json=payload
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_rollback_not_available(client):
    """Should reject rollback when rollback_available is False."""
    # DEP-SEED-0005 is a rollback deployment with rollback_available=False
    payload = {
        "rolled_back_by": "Ops Team",
    }
    resp = await client.post(
        f"{API_PREFIX}/deployments/DEP-SEED-0005/rollback", json=payload
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_rollback_deployment_not_found(client):
    """Should return 404 for rollback of nonexistent deployment."""
    payload = {"rolled_back_by": "Ops Team"}
    resp = await client.post(
        f"{API_PREFIX}/deployments/DEP-NONEXISTENT/rollback", json=payload
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_rollback_updates_original_status(client):
    """Rollback should update original deployment status to ROLLED_BACK."""
    payload = {"rolled_back_by": "Ops Team"}
    await client.post(
        f"{API_PREFIX}/deployments/DEP-SEED-0003/rollback", json=payload
    )

    # Original should now be rolled back
    resp = await client.get(f"{API_PREFIX}/deployments/DEP-SEED-0003")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ROLLED_BACK"
    assert resp.json()["rollback_available"] is False


# ============================================================================
# Release Gates
# ============================================================================


@pytest.mark.anyio
async def test_list_gates(client):
    """Should list all gates for a release."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0005/gates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 6
    gate_names = [g["gate_name"] for g in data["gates"]]
    assert "CODE_REVIEW" in gate_names
    assert "QA_SIGN_OFF" in gate_names
    assert "SECURITY_SCAN" in gate_names
    assert "PERFORMANCE_TEST" in gate_names
    assert "COMPLIANCE_REVIEW" in gate_names
    assert "STAKEHOLDER_APPROVAL" in gate_names


@pytest.mark.anyio
async def test_list_gates_not_found(client):
    """Should return 404 for gates of nonexistent release."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-NONEXISTENT/gates")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_update_gate_pass(client):
    """Should update a gate to PASSED."""
    payload = {
        "status": "PASSED",
        "reviewer": "Security Team",
        "comments": "All security checks passed",
    }
    resp = await client.put(
        f"{API_PREFIX}/releases/REL-SEED-0005/gates/PERFORMANCE_TEST",
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PASSED"
    assert data["reviewer"] == "Security Team"
    assert data["comments"] == "All security checks passed"
    assert data["reviewed_at"] is not None


@pytest.mark.anyio
async def test_update_gate_fail(client):
    """Should update a gate to FAILED."""
    payload = {
        "status": "FAILED",
        "reviewer": "QA",
        "comments": "Performance regression found",
    }
    resp = await client.put(
        f"{API_PREFIX}/releases/REL-SEED-0005/gates/PERFORMANCE_TEST",
        json=payload,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "FAILED"


@pytest.mark.anyio
async def test_update_gate_waive(client):
    """Should update a gate to WAIVED."""
    payload = {
        "status": "WAIVED",
        "reviewer": "VP Engineering",
        "comments": "Waived for emergency release",
    }
    resp = await client.put(
        f"{API_PREFIX}/releases/REL-SEED-0005/gates/STAKEHOLDER_APPROVAL",
        json=payload,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "WAIVED"


@pytest.mark.anyio
async def test_update_gate_release_not_found(client):
    """Should return 404 for gate update on nonexistent release."""
    payload = {"status": "PASSED", "reviewer": "QA"}
    resp = await client.put(
        f"{API_PREFIX}/releases/REL-NONEXISTENT/gates/CODE_REVIEW",
        json=payload,
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_update_gate_not_found_on_release(client):
    """Should return 404 for nonexistent gate on existing release.

    Release v2.4.0 (PLANNING) has no gates created via seed; only releases
    that go through create_release get auto-gates. But seed data doesn't
    call create_release so there are no gates for REL-SEED-0006.
    """
    payload = {"status": "PASSED", "reviewer": "QA"}
    resp = await client.put(
        f"{API_PREFIX}/releases/REL-SEED-0006/gates/CODE_REVIEW",
        json=payload,
    )
    assert resp.status_code == 404


# ============================================================================
# Release Readiness
# ============================================================================


@pytest.mark.anyio
async def test_readiness_not_ready(client):
    """v2.3.0 should NOT be ready (only 3 of 6 gates passed)."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0005/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready"] is False
    assert data["passed_count"] == 3
    assert data["total_count"] == 6
    assert len(data["blocking_gates"]) == 3
    assert data["version"] == "2.3.0"


@pytest.mark.anyio
async def test_readiness_ready(client):
    """v2.0.0 should be ready (all gates passed)."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0001/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready"] is True
    assert data["passed_count"] == 6
    assert data["total_count"] == 6
    assert data["blocking_gates"] == []


@pytest.mark.anyio
async def test_readiness_not_found(client):
    """Should return 404 for readiness of nonexistent release."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-NONEXISTENT/readiness")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_readiness_after_passing_all_gates(client):
    """After passing all pending gates, readiness should be True."""
    # Pass the 3 remaining pending gates for v2.3.0
    pending_gates = ["PERFORMANCE_TEST", "COMPLIANCE_REVIEW", "STAKEHOLDER_APPROVAL"]
    for gate in pending_gates:
        payload = {"status": "PASSED", "reviewer": "Auto QA"}
        resp = await client.put(
            f"{API_PREFIX}/releases/REL-SEED-0005/gates/{gate}",
            json=payload,
        )
        assert resp.status_code == 200

    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0005/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready"] is True
    assert data["passed_count"] == 6


@pytest.mark.anyio
async def test_readiness_with_waived_gates(client):
    """Waived gates should count as non-blocking."""
    # Waive all pending gates
    pending_gates = ["PERFORMANCE_TEST", "COMPLIANCE_REVIEW", "STAKEHOLDER_APPROVAL"]
    for gate in pending_gates:
        payload = {"status": "WAIVED", "reviewer": "VP Eng"}
        resp = await client.put(
            f"{API_PREFIX}/releases/REL-SEED-0005/gates/{gate}",
            json=payload,
        )
        assert resp.status_code == 200

    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0005/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready"] is True


# ============================================================================
# SemVer Validation
# ============================================================================


@pytest.mark.anyio
async def test_validate_version_valid(client):
    """Should validate a correct semver string."""
    resp = await client.get(
        f"{API_PREFIX}/versions/validate", params={"version": "1.2.3"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["major"] == 1
    assert data["minor"] == 2
    assert data["patch"] == 3


@pytest.mark.anyio
async def test_validate_version_with_prerelease(client):
    """Should validate semver with prerelease tag."""
    resp = await client.get(
        f"{API_PREFIX}/versions/validate", params={"version": "2.0.0-beta.1"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["prerelease"] == "beta.1"


@pytest.mark.anyio
async def test_validate_version_with_build(client):
    """Should validate semver with build metadata."""
    resp = await client.get(
        f"{API_PREFIX}/versions/validate", params={"version": "1.0.0+build.123"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["build"] == "build.123"


@pytest.mark.anyio
async def test_validate_version_invalid(client):
    """Should report invalid version."""
    resp = await client.get(
        f"{API_PREFIX}/versions/validate", params={"version": "not-valid"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False


@pytest.mark.anyio
async def test_validate_version_zero(client):
    """Should validate 0.0.0 as valid."""
    resp = await client.get(
        f"{API_PREFIX}/versions/validate", params={"version": "0.0.0"}
    )
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


@pytest.mark.anyio
async def test_validate_version_partial_invalid(client):
    """Should reject partial version like '1.2'."""
    resp = await client.get(
        f"{API_PREFIX}/versions/validate", params={"version": "1.2"}
    )
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


# ============================================================================
# Next Version Suggestion
# ============================================================================


@pytest.mark.anyio
async def test_next_version_major(client):
    """Should suggest next major version."""
    resp = await client.get(
        f"{API_PREFIX}/versions/next",
        params={"current": "2.3.1", "bump": "MAJOR"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["next"] == "3.0.0"
    assert data["bump"] == "MAJOR"


@pytest.mark.anyio
async def test_next_version_minor(client):
    """Should suggest next minor version."""
    resp = await client.get(
        f"{API_PREFIX}/versions/next",
        params={"current": "2.3.1", "bump": "MINOR"},
    )
    assert resp.status_code == 200
    assert resp.json()["next"] == "2.4.0"


@pytest.mark.anyio
async def test_next_version_patch(client):
    """Should suggest next patch version."""
    resp = await client.get(
        f"{API_PREFIX}/versions/next",
        params={"current": "2.3.1", "bump": "PATCH"},
    )
    assert resp.status_code == 200
    assert resp.json()["next"] == "2.3.2"


@pytest.mark.anyio
async def test_next_version_hotfix(client):
    """Should suggest next hotfix version (same as patch)."""
    resp = await client.get(
        f"{API_PREFIX}/versions/next",
        params={"current": "2.3.1", "bump": "HOTFIX"},
    )
    assert resp.status_code == 200
    assert resp.json()["next"] == "2.3.2"


@pytest.mark.anyio
async def test_next_version_invalid_current(client):
    """Should return 400 for invalid current version."""
    resp = await client.get(
        f"{API_PREFIX}/versions/next",
        params={"current": "bad", "bump": "MINOR"},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_next_version_from_zero(client):
    """Should suggest next version from 0.0.0."""
    resp = await client.get(
        f"{API_PREFIX}/versions/next",
        params={"current": "0.0.0", "bump": "MINOR"},
    )
    assert resp.status_code == 200
    assert resp.json()["next"] == "0.1.0"


# ============================================================================
# DORA Metrics
# ============================================================================


@pytest.mark.anyio
async def test_dora_metrics(client):
    """Should return DORA metrics."""
    resp = await client.get(f"{API_PREFIX}/metrics/dora")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_releases"] == 6
    assert "deployment_frequency_per_month" in data
    assert "mean_lead_time_days" in data
    assert "change_failure_rate_pct" in data
    assert "mean_time_to_recovery_minutes" in data
    assert isinstance(data["by_type"], dict)
    assert isinstance(data["by_status"], dict)


@pytest.mark.anyio
async def test_dora_metrics_by_type(client):
    """DORA metrics should include type breakdown."""
    resp = await client.get(f"{API_PREFIX}/metrics/dora")
    data = resp.json()
    assert "MAJOR" in data["by_type"]
    assert "MINOR" in data["by_type"]
    assert "HOTFIX" in data["by_type"]
    assert data["by_type"]["MAJOR"] == 1
    assert data["by_type"]["HOTFIX"] == 1


@pytest.mark.anyio
async def test_dora_metrics_by_status(client):
    """DORA metrics should include status breakdown."""
    resp = await client.get(f"{API_PREFIX}/metrics/dora")
    data = resp.json()
    assert "DEPLOYED" in data["by_status"]
    assert "ROLLED_BACK" in data["by_status"]
    assert data["by_status"]["DEPLOYED"] == 3


@pytest.mark.anyio
async def test_dora_metrics_rollback_count(client):
    """DORA metrics should count rollbacks."""
    resp = await client.get(f"{API_PREFIX}/metrics/dora")
    data = resp.json()
    # Seed has 1 rollback deployment (DEP-SEED-0005)
    assert data["rollback_count"] >= 1


@pytest.mark.anyio
async def test_dora_metrics_hotfix_count(client):
    """DORA metrics should count hotfixes."""
    resp = await client.get(f"{API_PREFIX}/metrics/dora")
    data = resp.json()
    assert data["hotfix_count"] == 1


@pytest.mark.anyio
async def test_dora_metrics_change_failure_rate(client):
    """DORA change failure rate should be positive (seed has failures)."""
    resp = await client.get(f"{API_PREFIX}/metrics/dora")
    data = resp.json()
    assert data["change_failure_rate_pct"] > 0


@pytest.mark.anyio
async def test_dora_metrics_lead_time(client):
    """DORA mean lead time should be positive."""
    resp = await client.get(f"{API_PREFIX}/metrics/dora")
    data = resp.json()
    assert data["mean_lead_time_days"] > 0


# ============================================================================
# Changelog Generation
# ============================================================================


@pytest.mark.anyio
async def test_generate_changelog(client):
    """Should generate a changelog for a release."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0005/changelog")
    assert resp.status_code == 200
    data = resp.json()
    assert data["release_id"] == "REL-SEED-0005"
    assert data["version"] == "2.3.0"
    assert "changelog" in data
    assert "## 2.3.0" in data["changelog"]
    assert "Features" in data["changelog"]
    assert "ROI dashboard" in data["changelog"]


@pytest.mark.anyio
async def test_generate_changelog_with_bug_fixes(client):
    """Changelog should include bug fixes section."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0005/changelog")
    data = resp.json()
    assert "Bug Fixes" in data["changelog"]
    assert "search performance" in data["changelog"]


@pytest.mark.anyio
async def test_generate_changelog_with_breaking_changes(client):
    """Changelog for v2.0.0 should include breaking changes."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0001/changelog")
    data = resp.json()
    assert "Breaking Changes" in data["changelog"]
    assert "migration required" in data["changelog"]


@pytest.mark.anyio
async def test_generate_changelog_not_found(client):
    """Should return 404 for changelog of nonexistent release."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-NONEXISTENT/changelog")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_generate_changelog_hotfix(client):
    """Changelog for hotfix should have bug fixes only."""
    resp = await client.get(f"{API_PREFIX}/releases/REL-SEED-0004/changelog")
    data = resp.json()
    assert "Bug Fixes" in data["changelog"]
    assert "pipeline timeout" in data["changelog"]


# ============================================================================
# Release History
# ============================================================================


@pytest.mark.anyio
async def test_release_history(client):
    """Should return release history with deployment details."""
    resp = await client.get(f"{API_PREFIX}/history")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert data["total"] >= 1

    for entry in data["entries"]:
        assert "release" in entry
        assert "deployments" in entry
        assert "gates_passed" in entry
        assert "gates_total" in entry


@pytest.mark.anyio
async def test_release_history_limit(client):
    """Should respect the limit parameter."""
    resp = await client.get(f"{API_PREFIX}/history", params={"limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 2


@pytest.mark.anyio
async def test_release_history_contains_deployments(client):
    """History entries should include deployment details."""
    resp = await client.get(f"{API_PREFIX}/history")
    data = resp.json()
    # Find v2.0.0 entry (has deployments)
    v200_entry = None
    for e in data["entries"]:
        if e["release"]["version"] == "2.0.0":
            v200_entry = e
            break
    assert v200_entry is not None
    assert len(v200_entry["deployments"]) >= 2


@pytest.mark.anyio
async def test_release_history_contains_gate_counts(client):
    """History entries should include gate counts."""
    resp = await client.get(f"{API_PREFIX}/history")
    data = resp.json()
    # Find v2.3.0 entry (has gates)
    v230_entry = None
    for e in data["entries"]:
        if e["release"]["version"] == "2.3.0":
            v230_entry = e
            break
    assert v230_entry is not None
    assert v230_entry["gates_total"] == 6
    assert v230_entry["gates_passed"] == 3


# ============================================================================
# Additional Error Handling
# ============================================================================


@pytest.mark.anyio
async def test_create_release_missing_required_fields(client):
    """Should return 422 for missing required fields."""
    payload = {"version": "5.0.0"}  # Missing title, release_type, release_manager
    resp = await client.post(f"{API_PREFIX}/releases", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_release_empty_version(client):
    """Should return 422 for empty version string."""
    payload = {
        "version": "",
        "title": "Test",
        "release_type": "MINOR",
        "release_manager": "Mgr",
    }
    resp = await client.post(f"{API_PREFIX}/releases", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_release_empty_title(client):
    """Should return 422 for empty title."""
    payload = {
        "version": "9.0.0",
        "title": "",
        "release_type": "MINOR",
        "release_manager": "Mgr",
    }
    resp = await client.post(f"{API_PREFIX}/releases", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_deploy_missing_required_fields(client):
    """Should return 422 for deploy with missing fields."""
    payload = {"environment": "STAGING"}  # Missing deployed_by
    resp = await client.post(
        f"{API_PREFIX}/releases/REL-SEED-0005/deploy", json=payload
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_rollback_missing_required_fields(client):
    """Should return 422 for rollback with missing fields."""
    payload = {}  # Missing rolled_back_by
    resp = await client.post(
        f"{API_PREFIX}/deployments/DEP-SEED-0002/rollback", json=payload
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_update_gate_missing_required_fields(client):
    """Should return 422 for gate update with missing fields."""
    payload = {"status": "PASSED"}  # Missing reviewer
    resp = await client.put(
        f"{API_PREFIX}/releases/REL-SEED-0005/gates/CODE_REVIEW",
        json=payload,
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_invalid_status_enum(client):
    """Should return 422 for invalid status enum value."""
    payload = {"status": "INVALID_STATUS"}
    resp = await client.put(f"{API_PREFIX}/releases/REL-SEED-0006", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_invalid_environment_enum(client):
    """Should return 422 for invalid environment enum."""
    payload = {
        "environment": "INVALID",
        "deployed_by": "CI/CD",
    }
    resp = await client.post(
        f"{API_PREFIX}/releases/REL-SEED-0005/deploy", json=payload
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_invalid_gate_name_enum(client):
    """Should return 422 for invalid gate name."""
    payload = {"status": "PASSED", "reviewer": "QA"}
    resp = await client.put(
        f"{API_PREFIX}/releases/REL-SEED-0005/gates/INVALID_GATE",
        json=payload,
    )
    assert resp.status_code == 422


# ============================================================================
# Complex Workflow Tests
# ============================================================================


@pytest.mark.anyio
async def test_full_release_lifecycle(client):
    """Test a complete release lifecycle: create -> gates -> deploy."""
    # 1. Create release
    create_payload = {
        "version": "4.0.0",
        "title": "Full Lifecycle Test",
        "release_type": "MAJOR",
        "release_manager": "Test Manager",
        "features": ["Feature X"],
    }
    resp = await client.post(f"{API_PREFIX}/releases", json=create_payload)
    assert resp.status_code == 201
    release_id = resp.json()["id"]

    # 2. Check initial readiness (should not be ready)
    resp = await client.get(f"{API_PREFIX}/releases/{release_id}/readiness")
    assert resp.status_code == 200
    assert resp.json()["ready"] is False

    # 3. Pass all gates
    gates = [
        "CODE_REVIEW", "QA_SIGN_OFF", "SECURITY_SCAN",
        "PERFORMANCE_TEST", "COMPLIANCE_REVIEW", "STAKEHOLDER_APPROVAL",
    ]
    for gate in gates:
        resp = await client.put(
            f"{API_PREFIX}/releases/{release_id}/gates/{gate}",
            json={"status": "PASSED", "reviewer": "Auto"},
        )
        assert resp.status_code == 200

    # 4. Check readiness (should be ready now)
    resp = await client.get(f"{API_PREFIX}/releases/{release_id}/readiness")
    assert resp.status_code == 200
    assert resp.json()["ready"] is True

    # 5. Transition through statuses
    for status in ["DEVELOPMENT", "CODE_FREEZE", "TESTING", "STAGING", "APPROVED", "DEPLOYING", "DEPLOYED"]:
        resp = await client.put(
            f"{API_PREFIX}/releases/{release_id}",
            json={"status": status},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == status

    # 6. Deploy to staging then production
    resp = await client.post(
        f"{API_PREFIX}/releases/{release_id}/deploy",
        json={"environment": "PRODUCTION", "deployed_by": "CI/CD"},
    )
    assert resp.status_code == 201

    # 7. Verify in history
    resp = await client.get(f"{API_PREFIX}/history", params={"limit": 10})
    assert resp.status_code == 200
    versions = [e["release"]["version"] for e in resp.json()["entries"]]
    assert "4.0.0" in versions


@pytest.mark.anyio
async def test_multiple_deployments_per_release(client):
    """A release can have multiple deployments (staging + production)."""
    # Deploy v2.3.0 to staging
    resp1 = await client.post(
        f"{API_PREFIX}/releases/REL-SEED-0005/deploy",
        json={"environment": "STAGING", "deployed_by": "CI/CD"},
    )
    assert resp1.status_code == 201

    # Deploy v2.3.0 to production
    resp2 = await client.post(
        f"{API_PREFIX}/releases/REL-SEED-0005/deploy",
        json={"environment": "PRODUCTION", "deployed_by": "CI/CD"},
    )
    assert resp2.status_code == 201

    # List deployments for the release
    resp3 = await client.get(
        f"{API_PREFIX}/releases/REL-SEED-0005/deployments"
    )
    assert resp3.status_code == 200
    assert resp3.json()["total"] >= 2


@pytest.mark.anyio
async def test_update_release_changelog(client):
    """Should update the changelog field directly."""
    payload = {"changelog": "## v2.4.0\n- Custom changelog entry"}
    resp = await client.put(f"{API_PREFIX}/releases/REL-SEED-0006", json=payload)
    assert resp.status_code == 200
    assert resp.json()["changelog"] == "## v2.4.0\n- Custom changelog entry"


@pytest.mark.anyio
async def test_create_and_delete_round_trip(client):
    """Create then delete a release and verify clean state."""
    payload = {
        "version": "99.0.0",
        "title": "Temp Release",
        "release_type": "PATCH",
        "release_manager": "Temp",
    }
    resp = await client.post(f"{API_PREFIX}/releases", json=payload)
    assert resp.status_code == 201
    release_id = resp.json()["id"]

    # Gates should exist
    gates_resp = await client.get(f"{API_PREFIX}/releases/{release_id}/gates")
    assert gates_resp.json()["total"] == 6

    # Delete
    del_resp = await client.delete(f"{API_PREFIX}/releases/{release_id}")
    assert del_resp.status_code == 204

    # Verify gone
    get_resp = await client.get(f"{API_PREFIX}/releases/{release_id}")
    assert get_resp.status_code == 404


@pytest.mark.anyio
async def test_cancelled_release_is_terminal(client):
    """CANCELLED status should not allow further transitions."""
    # Cancel v2.4.0 (currently PLANNING)
    resp = await client.put(
        f"{API_PREFIX}/releases/REL-SEED-0006",
        json={"status": "CANCELLED"},
    )
    assert resp.status_code == 200

    # Try to move to DEVELOPMENT - should fail
    resp2 = await client.put(
        f"{API_PREFIX}/releases/REL-SEED-0006",
        json={"status": "DEVELOPMENT"},
    )
    assert resp2.status_code == 400
    body = resp2.json()
    error_msg = body.get("detail") or body.get("message", "")
    assert "Invalid status transition" in error_msg
