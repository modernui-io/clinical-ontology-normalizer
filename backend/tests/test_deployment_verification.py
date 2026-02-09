"""Comprehensive tests for Deployment Verification & API Contract Testing (VPE-9).

Tests cover:
- Seed data verification (verifications, contracts, budgets, SLIs)
- Deployment verification CRUD
- Smoke test execution
- API contract CRUD
- Contract testing (schema diff, breaking change detection)
- Error budget CRUD and burn rate calculation
- SLI definition CRUD and measurement
- Deployment gate evaluation
- Historical verification trending
- Aggregate metrics
- Error handling (404s, validation errors)
- Pagination and filtering
"""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

from app.main import app
from app.services.deployment_verification_service import (
    get_deployment_verification_service,
    reset_deployment_verification_service,
)

API_PREFIX = "/api/v1/deployment-verification"


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the deployment verification service before each test."""
    reset_deployment_verification_service()
    yield
    reset_deployment_verification_service()


@pytest.fixture
async def client():
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================================
# Seed Data Verification - Deployment Verifications
# ============================================================================


@pytest.mark.anyio
async def test_seed_verifications_loaded(client):
    """Seed data should contain 5 deployment verifications."""
    resp = await client.get(f"{API_PREFIX}/verifications", params={"limit": 50})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["verifications"]) == 5


@pytest.mark.anyio
async def test_seed_verification_dv1_passed(client):
    """DV-SEED-0001 should be PASSED for v2.0.0 production."""
    resp = await client.get(f"{API_PREFIX}/verifications/DV-SEED-0001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.0.0"
    assert data["overall_status"] == "PASSED"
    assert data["environment"] == "PRODUCTION"
    assert data["rollback_recommended"] is False


@pytest.mark.anyio
async def test_seed_verification_dv2_passed(client):
    """DV-SEED-0002 should be PASSED for v2.1.0 staging."""
    resp = await client.get(f"{API_PREFIX}/verifications/DV-SEED-0002")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.1.0"
    assert data["overall_status"] == "PASSED"
    assert data["environment"] == "STAGING"


@pytest.mark.anyio
async def test_seed_verification_dv3_passed(client):
    """DV-SEED-0003 should be PASSED for v2.1.0 production."""
    resp = await client.get(f"{API_PREFIX}/verifications/DV-SEED-0003")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.1.0"
    assert data["overall_status"] == "PASSED"
    assert data["environment"] == "PRODUCTION"


@pytest.mark.anyio
async def test_seed_verification_dv4_failed(client):
    """DV-SEED-0004 should be FAILED for v2.2.0 production."""
    resp = await client.get(f"{API_PREFIX}/verifications/DV-SEED-0004")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.2.0"
    assert data["overall_status"] == "FAILED"
    assert data["rollback_recommended"] is True


@pytest.mark.anyio
async def test_seed_verification_dv5_running(client):
    """DV-SEED-0005 should be RUNNING for v2.3.0 staging."""
    resp = await client.get(f"{API_PREFIX}/verifications/DV-SEED-0005")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.3.0"
    assert data["overall_status"] == "RUNNING"
    assert data["completed_at"] is None


@pytest.mark.anyio
async def test_seed_verification_has_checks(client):
    """Each verification should have associated checks."""
    resp = await client.get(f"{API_PREFIX}/verifications/DV-SEED-0001")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["checks"]) == 7
    check_types = {c["verification_type"] for c in data["checks"]}
    assert "HEALTH_CHECK" in check_types
    assert "SMOKE_TEST" in check_types


@pytest.mark.anyio
async def test_seed_failed_verification_has_failed_checks(client):
    """Failed verification should have failed checks."""
    resp = await client.get(f"{API_PREFIX}/verifications/DV-SEED-0004")
    assert resp.status_code == 200
    data = resp.json()
    failed = [c for c in data["checks"] if c["status"] == "FAILED"]
    assert len(failed) >= 1
    for c in failed:
        assert c["error_message"] is not None


@pytest.mark.anyio
async def test_seed_running_verification_has_mixed_checks(client):
    """Running verification should have mix of passed, running, pending checks."""
    resp = await client.get(f"{API_PREFIX}/verifications/DV-SEED-0005")
    data = resp.json()
    statuses = {c["status"] for c in data["checks"]}
    assert "PASSED" in statuses
    assert "RUNNING" in statuses or "PENDING" in statuses


# ============================================================================
# Seed Data Verification - API Contracts
# ============================================================================


@pytest.mark.anyio
async def test_seed_contracts_loaded(client):
    """Seed data should contain 15 API contracts."""
    resp = await client.get(f"{API_PREFIX}/contracts", params={"limit": 50})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 15


@pytest.mark.anyio
async def test_seed_contract_patients_get(client):
    """Contract for GET /patients should exist."""
    resp = await client.get(f"{API_PREFIX}/contracts/CTR-SEED-0001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["endpoint_path"] == "/api/v1/patients"
    assert data["method"] == "GET"
    assert data["deprecated"] is False


@pytest.mark.anyio
async def test_seed_contract_deprecated(client):
    """CTR-SEED-0014 should be deprecated."""
    resp = await client.get(f"{API_PREFIX}/contracts/CTR-SEED-0014")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deprecated"] is True
    assert data["replacement_endpoint"] == "/api/v1/documents/query"


@pytest.mark.anyio
async def test_seed_contract_has_schemas(client):
    """POST contracts should have request schemas."""
    resp = await client.get(f"{API_PREFIX}/contracts/CTR-SEED-0002")
    assert resp.status_code == 200
    data = resp.json()
    assert data["request_schema"] is not None
    assert data["response_schema"] is not None


# ============================================================================
# Seed Data Verification - Contract Test Results
# ============================================================================


@pytest.mark.anyio
async def test_seed_contract_test_results_loaded(client):
    """Seed data should contain 10 contract test results."""
    resp = await client.get(f"{API_PREFIX}/contract-tests", params={"limit": 50})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 10


@pytest.mark.anyio
async def test_seed_contract_tests_pass_fail_distribution(client):
    """8 tests should pass and 2 should fail."""
    resp = await client.get(f"{API_PREFIX}/contract-tests", params={"limit": 50})
    data = resp.json()
    passed = [r for r in data["results"] if r["status"] == "PASSED"]
    failed = [r for r in data["results"] if r["status"] == "FAILED"]
    assert len(passed) == 8
    assert len(failed) == 2


@pytest.mark.anyio
async def test_seed_failed_contract_has_breaking_changes(client):
    """Failed contract test results should have breaking changes."""
    resp = await client.get(
        f"{API_PREFIX}/contract-tests",
        params={"status": "FAILED", "limit": 50},
    )
    data = resp.json()
    for result in data["results"]:
        assert len(result["breaking_changes"]) > 0


# ============================================================================
# Seed Data Verification - Error Budgets
# ============================================================================


@pytest.mark.anyio
async def test_seed_error_budgets_loaded(client):
    """Seed data should contain 6 error budgets."""
    resp = await client.get(f"{API_PREFIX}/error-budgets", params={"limit": 50})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 6


@pytest.mark.anyio
async def test_seed_error_budget_healthy(client):
    """EB-SEED-0001 should be HEALTHY."""
    resp = await client.get(f"{API_PREFIX}/error-budgets/EB-SEED-0001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert data["service_name"] == "api-gateway"


@pytest.mark.anyio
async def test_seed_error_budget_warning(client):
    """EB-SEED-0002 should be WARNING."""
    resp = await client.get(f"{API_PREFIX}/error-budgets/EB-SEED-0002")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "WARNING"
    assert len(data["violations"]) == 1


@pytest.mark.anyio
async def test_seed_error_budget_critical(client):
    """EB-SEED-0004 should be CRITICAL."""
    resp = await client.get(f"{API_PREFIX}/error-budgets/EB-SEED-0004")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "CRITICAL"
    assert len(data["violations"]) == 2


@pytest.mark.anyio
async def test_seed_error_budget_exhausted(client):
    """EB-SEED-0006 should be EXHAUSTED."""
    resp = await client.get(f"{API_PREFIX}/error-budgets/EB-SEED-0006")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "EXHAUSTED"
    assert data["remaining_budget_percent"] == 0.0


# ============================================================================
# Seed Data Verification - SLI Definitions
# ============================================================================


@pytest.mark.anyio
async def test_seed_sli_definitions_loaded(client):
    """Seed data should contain 8 SLI definitions."""
    resp = await client.get(f"{API_PREFIX}/sli-definitions", params={"limit": 50})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 8


@pytest.mark.anyio
async def test_seed_sli_definition_detail(client):
    """SLI-SEED-0001 should be api-gateway availability."""
    resp = await client.get(f"{API_PREFIX}/sli-definitions/SLI-SEED-0001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service_name"] == "api-gateway"
    assert data["sli_name"] == "availability"
    assert data["target_percent"] == 99.9


# ============================================================================
# Verification CRUD
# ============================================================================


@pytest.mark.anyio
async def test_create_verification(client):
    """Should create a new deployment verification."""
    payload = {
        "deployment_id": "DEP-NEW-001",
        "environment": "STAGING",
        "version": "3.0.0",
        "triggered_by": "test-user",
    }
    resp = await client.post(f"{API_PREFIX}/verifications", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["deployment_id"] == "DEP-NEW-001"
    assert data["version"] == "3.0.0"
    assert data["overall_status"] == "PENDING"
    assert data["environment"] == "STAGING"
    assert data["triggered_by"] == "test-user"


@pytest.mark.anyio
async def test_create_verification_has_id(client):
    """Created verification should have a generated ID."""
    payload = {
        "deployment_id": "DEP-NEW-002",
        "environment": "PRODUCTION",
        "version": "3.1.0",
    }
    resp = await client.post(f"{API_PREFIX}/verifications", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"].startswith("DV-")


@pytest.mark.anyio
async def test_delete_verification(client):
    """Should delete a verification."""
    resp = await client.delete(f"{API_PREFIX}/verifications/DV-SEED-0001")
    assert resp.status_code == 204

    resp2 = await client.get(f"{API_PREFIX}/verifications/DV-SEED-0001")
    assert resp2.status_code == 404


@pytest.mark.anyio
async def test_delete_nonexistent_verification(client):
    """Deleting nonexistent verification should return 404."""
    resp = await client.delete(f"{API_PREFIX}/verifications/NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_nonexistent_verification(client):
    """Getting nonexistent verification should return 404."""
    resp = await client.get(f"{API_PREFIX}/verifications/NONEXISTENT")
    assert resp.status_code == 404


# ============================================================================
# Verification Filtering
# ============================================================================


@pytest.mark.anyio
async def test_filter_verifications_by_environment(client):
    """Should filter verifications by environment."""
    resp = await client.get(
        f"{API_PREFIX}/verifications",
        params={"environment": "PRODUCTION"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for v in data["verifications"]:
        assert v["environment"] == "PRODUCTION"


@pytest.mark.anyio
async def test_filter_verifications_by_status(client):
    """Should filter verifications by status."""
    resp = await client.get(
        f"{API_PREFIX}/verifications",
        params={"status": "PASSED"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for v in data["verifications"]:
        assert v["overall_status"] == "PASSED"


@pytest.mark.anyio
async def test_verifications_pagination(client):
    """Should paginate verification results."""
    resp = await client.get(
        f"{API_PREFIX}/verifications",
        params={"limit": 2, "offset": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["verifications"]) == 2
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 0


@pytest.mark.anyio
async def test_verifications_pagination_offset(client):
    """Should handle offset in pagination."""
    resp = await client.get(
        f"{API_PREFIX}/verifications",
        params={"limit": 2, "offset": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["verifications"]) == 2
    assert data["offset"] == 3


# ============================================================================
# Smoke Tests
# ============================================================================


@pytest.mark.anyio
async def test_run_smoke_tests_default_endpoints(client):
    """Should run smoke tests against default endpoints."""
    payload = {
        "deployment_id": "DEP-SMOKE-001",
        "environment": "STAGING",
        "version": "3.0.0",
    }
    resp = await client.post(f"{API_PREFIX}/smoke-tests", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["deployment_id"] == "DEP-SMOKE-001"
    assert len(data["checks"]) == 6  # default endpoints
    assert data["overall_status"] in ["PASSED", "FAILED"]


@pytest.mark.anyio
async def test_run_smoke_tests_custom_endpoints(client):
    """Should run smoke tests against custom endpoints."""
    payload = {
        "deployment_id": "DEP-SMOKE-002",
        "environment": "QA",
        "version": "3.0.0",
        "endpoints": ["/api/v1/health", "/api/v1/patients"],
    }
    resp = await client.post(f"{API_PREFIX}/smoke-tests", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["checks"]) == 2


@pytest.mark.anyio
async def test_smoke_test_checks_have_details(client):
    """Smoke test checks should have endpoint URLs and results."""
    payload = {
        "deployment_id": "DEP-SMOKE-003",
        "environment": "STAGING",
        "version": "3.0.0",
        "endpoints": ["/api/v1/health"],
    }
    resp = await client.post(f"{API_PREFIX}/smoke-tests", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    check = data["checks"][0]
    assert check["endpoint_url"] == "/api/v1/health"
    assert check["verification_type"] == "SMOKE_TEST"
    assert check["duration_ms"] is not None


@pytest.mark.anyio
async def test_smoke_test_completed_at_is_set(client):
    """Completed smoke tests should have completed_at timestamp."""
    payload = {
        "deployment_id": "DEP-SMOKE-004",
        "environment": "PRODUCTION",
        "version": "3.0.0",
        "endpoints": ["/api/v1/health"],
    }
    resp = await client.post(f"{API_PREFIX}/smoke-tests", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["completed_at"] is not None


# ============================================================================
# API Contract CRUD
# ============================================================================


@pytest.mark.anyio
async def test_create_contract(client):
    """Should create a new API contract."""
    payload = {
        "endpoint_path": "/api/v2/analytics",
        "method": "GET",
        "version": "v2",
        "response_schema": {"type": "object", "properties": {"data": {"type": "array"}}},
        "required_headers": ["Authorization"],
    }
    resp = await client.post(f"{API_PREFIX}/contracts", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["endpoint_path"] == "/api/v2/analytics"
    assert data["method"] == "GET"
    assert data["version"] == "v2"
    assert data["deprecated"] is False


@pytest.mark.anyio
async def test_create_contract_with_request_schema(client):
    """Should create a contract with both request and response schemas."""
    payload = {
        "endpoint_path": "/api/v2/reports",
        "method": "POST",
        "request_schema": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
        "response_schema": {"type": "object", "properties": {"id": {"type": "string"}}},
    }
    resp = await client.post(f"{API_PREFIX}/contracts", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["request_schema"] is not None
    assert data["response_schema"] is not None


@pytest.mark.anyio
async def test_update_contract(client):
    """Should update an existing contract."""
    payload = {"deprecated": True, "replacement_endpoint": "/api/v2/patients"}
    resp = await client.put(f"{API_PREFIX}/contracts/CTR-SEED-0001", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["deprecated"] is True
    assert data["replacement_endpoint"] == "/api/v2/patients"


@pytest.mark.anyio
async def test_update_contract_method(client):
    """Should update contract method."""
    payload = {"method": "PATCH"}
    resp = await client.put(f"{API_PREFIX}/contracts/CTR-SEED-0001", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "PATCH"


@pytest.mark.anyio
async def test_update_nonexistent_contract(client):
    """Updating nonexistent contract should return 404."""
    resp = await client.put(
        f"{API_PREFIX}/contracts/NONEXISTENT",
        json={"method": "DELETE"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_contract(client):
    """Should delete a contract."""
    resp = await client.delete(f"{API_PREFIX}/contracts/CTR-SEED-0001")
    assert resp.status_code == 204

    resp2 = await client.get(f"{API_PREFIX}/contracts/CTR-SEED-0001")
    assert resp2.status_code == 404


@pytest.mark.anyio
async def test_delete_nonexistent_contract(client):
    """Deleting nonexistent contract should return 404."""
    resp = await client.delete(f"{API_PREFIX}/contracts/NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_nonexistent_contract(client):
    """Getting nonexistent contract should return 404."""
    resp = await client.get(f"{API_PREFIX}/contracts/NONEXISTENT")
    assert resp.status_code == 404


# ============================================================================
# Contract Filtering
# ============================================================================


@pytest.mark.anyio
async def test_filter_contracts_by_method(client):
    """Should filter contracts by HTTP method."""
    resp = await client.get(f"{API_PREFIX}/contracts", params={"method": "POST"})
    assert resp.status_code == 200
    data = resp.json()
    for c in data["contracts"]:
        assert c["method"] == "POST"


@pytest.mark.anyio
async def test_filter_contracts_by_deprecated(client):
    """Should filter contracts by deprecation status."""
    resp = await client.get(f"{API_PREFIX}/contracts", params={"deprecated": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for c in data["contracts"]:
        assert c["deprecated"] is True


@pytest.mark.anyio
async def test_contracts_pagination(client):
    """Should paginate contract results."""
    resp = await client.get(
        f"{API_PREFIX}/contracts",
        params={"limit": 5, "offset": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["contracts"]) == 5
    assert data["total"] == 15


# ============================================================================
# Contract Testing
# ============================================================================


@pytest.mark.anyio
async def test_run_contract_test_response_schema(client):
    """Should run a response schema test."""
    resp = await client.post(
        f"{API_PREFIX}/contracts/CTR-SEED-0001/test",
        params={"test_type": "RESPONSE_SCHEMA"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["contract_id"] == "CTR-SEED-0001"
    assert data["test_type"] == "RESPONSE_SCHEMA"
    assert data["status"] in ["PASSED", "FAILED"]


@pytest.mark.anyio
async def test_run_contract_test_backward_compatibility(client):
    """Should run a backward compatibility test."""
    resp = await client.post(
        f"{API_PREFIX}/contracts/CTR-SEED-0004/test",
        params={"test_type": "BACKWARD_COMPATIBILITY"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["test_type"] == "BACKWARD_COMPATIBILITY"


@pytest.mark.anyio
async def test_run_contract_test_deprecation(client):
    """Should run a deprecation test on a deprecated contract."""
    resp = await client.post(
        f"{API_PREFIX}/contracts/CTR-SEED-0014/test",
        params={"test_type": "DEPRECATION"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["test_type"] == "DEPRECATION"
    assert data["status"] == "PASSED"
    assert "Deprecated: True" in data["details"]


@pytest.mark.anyio
async def test_run_contract_test_nonexistent(client):
    """Testing nonexistent contract should return 404."""
    resp = await client.post(
        f"{API_PREFIX}/contracts/NONEXISTENT/test",
        params={"test_type": "RESPONSE_SCHEMA"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_list_contract_tests_filter_by_contract(client):
    """Should filter contract test results by contract ID."""
    resp = await client.get(
        f"{API_PREFIX}/contract-tests",
        params={"contract_id": "CTR-SEED-0001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for r in data["results"]:
        assert r["contract_id"] == "CTR-SEED-0001"


@pytest.mark.anyio
async def test_list_contract_tests_filter_by_status(client):
    """Should filter contract test results by status."""
    resp = await client.get(
        f"{API_PREFIX}/contract-tests",
        params={"status": "FAILED"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for r in data["results"]:
        assert r["status"] == "FAILED"


# ============================================================================
# Breaking Change Detection
# ============================================================================


@pytest.mark.anyio
async def test_detect_breaking_changes_field_removed(client):
    """Should detect removed fields as breaking changes."""
    new_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            # "name" removed, "status" removed
        },
    }
    resp = await client.post(
        f"{API_PREFIX}/contracts/CTR-SEED-0001/breaking-changes",
        json=new_schema,
    )
    assert resp.status_code == 200
    data = resp.json()
    removed = [c for c in data if c["change_type"] == "removed"]
    assert len(removed) >= 1


@pytest.mark.anyio
async def test_detect_breaking_changes_type_changed(client):
    """Should detect type changes as breaking changes."""
    new_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},  # was string
            "name": {"type": "string"},
            "status": {"type": "string"},
        },
    }
    resp = await client.post(
        f"{API_PREFIX}/contracts/CTR-SEED-0001/breaking-changes",
        json=new_schema,
    )
    assert resp.status_code == 200
    data = resp.json()
    type_changes = [c for c in data if c["change_type"] == "type_changed"]
    assert len(type_changes) >= 1
    assert type_changes[0]["old_value"] == "string"
    assert type_changes[0]["new_value"] == "integer"


@pytest.mark.anyio
async def test_detect_breaking_changes_required_added(client):
    """Should detect new required fields as breaking changes."""
    new_schema = {
        "type": "object",
        "required": ["id", "name", "new_required_field"],
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "status": {"type": "string"},
            "new_required_field": {"type": "string"},
        },
    }
    resp = await client.post(
        f"{API_PREFIX}/contracts/CTR-SEED-0001/breaking-changes",
        json=new_schema,
    )
    assert resp.status_code == 200
    data = resp.json()
    required_added = [c for c in data if c["change_type"] == "required_added"]
    assert len(required_added) >= 1


@pytest.mark.anyio
async def test_detect_breaking_changes_no_changes(client):
    """Should return empty list when no breaking changes detected."""
    new_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "status": {"type": "string"},
            "extra_field": {"type": "string"},  # additive, not breaking
        },
    }
    resp = await client.post(
        f"{API_PREFIX}/contracts/CTR-SEED-0001/breaking-changes",
        json=new_schema,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0


@pytest.mark.anyio
async def test_detect_breaking_changes_nonexistent_contract(client):
    """Detecting breaking changes for nonexistent contract should return 404."""
    resp = await client.post(
        f"{API_PREFIX}/contracts/NONEXISTENT/breaking-changes",
        json={"type": "object"},
    )
    assert resp.status_code == 404


# ============================================================================
# Error Budget CRUD
# ============================================================================


@pytest.mark.anyio
async def test_create_error_budget(client):
    """Should create a new error budget."""
    payload = {
        "service_name": "new-service",
        "sli_name": "availability",
        "target_percent": 99.95,
        "window_hours": 720,
    }
    resp = await client.post(f"{API_PREFIX}/error-budgets", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["service_name"] == "new-service"
    assert data["sli_name"] == "availability"
    assert data["target_percent"] == 99.95
    assert data["status"] == "HEALTHY"
    assert data["remaining_budget_percent"] == 100.0


@pytest.mark.anyio
async def test_delete_error_budget(client):
    """Should delete an error budget."""
    resp = await client.delete(f"{API_PREFIX}/error-budgets/EB-SEED-0001")
    assert resp.status_code == 204

    resp2 = await client.get(f"{API_PREFIX}/error-budgets/EB-SEED-0001")
    assert resp2.status_code == 404


@pytest.mark.anyio
async def test_delete_nonexistent_error_budget(client):
    """Deleting nonexistent budget should return 404."""
    resp = await client.delete(f"{API_PREFIX}/error-budgets/NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_nonexistent_error_budget(client):
    """Getting nonexistent budget should return 404."""
    resp = await client.get(f"{API_PREFIX}/error-budgets/NONEXISTENT")
    assert resp.status_code == 404


# ============================================================================
# Error Budget Filtering
# ============================================================================


@pytest.mark.anyio
async def test_filter_budgets_by_service(client):
    """Should filter budgets by service name."""
    resp = await client.get(
        f"{API_PREFIX}/error-budgets",
        params={"service_name": "api-gateway"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for b in data["budgets"]:
        assert b["service_name"] == "api-gateway"


@pytest.mark.anyio
async def test_filter_budgets_by_status(client):
    """Should filter budgets by status."""
    resp = await client.get(
        f"{API_PREFIX}/error-budgets",
        params={"status": "HEALTHY"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for b in data["budgets"]:
        assert b["status"] == "HEALTHY"


@pytest.mark.anyio
async def test_budgets_pagination(client):
    """Should paginate budget results."""
    resp = await client.get(
        f"{API_PREFIX}/error-budgets",
        params={"limit": 3, "offset": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["budgets"]) == 3
    assert data["total"] == 6


# ============================================================================
# Burn Rate Calculation
# ============================================================================


@pytest.mark.anyio
async def test_burn_rate_healthy(client):
    """Should return burn rate for a healthy budget."""
    resp = await client.get(f"{API_PREFIX}/error-budgets/EB-SEED-0001/burn-rate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["budget_id"] == "EB-SEED-0001"
    assert "burn_rate" in data
    assert "remaining_budget_percent" in data
    assert data["status"] == "HEALTHY"


@pytest.mark.anyio
async def test_burn_rate_exhausted(client):
    """Should return burn rate for an exhausted budget."""
    resp = await client.get(f"{API_PREFIX}/error-budgets/EB-SEED-0006/burn-rate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["remaining_budget_percent"] == 0.0
    assert data["status"] == "EXHAUSTED"


@pytest.mark.anyio
async def test_burn_rate_nonexistent(client):
    """Getting burn rate for nonexistent budget should return 404."""
    resp = await client.get(f"{API_PREFIX}/error-budgets/NONEXISTENT/burn-rate")
    assert resp.status_code == 404


# ============================================================================
# SLI Definition CRUD
# ============================================================================


@pytest.mark.anyio
async def test_create_sli_definition(client):
    """Should create a new SLI definition."""
    payload = {
        "service_name": "auth-service",
        "sli_name": "login_success_rate",
        "description": "Percentage of login attempts that succeed",
        "target_percent": 99.5,
        "measurement_query": "successful_logins / total_logins * 100",
        "window_hours": 168,
    }
    resp = await client.post(f"{API_PREFIX}/sli-definitions", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["service_name"] == "auth-service"
    assert data["sli_name"] == "login_success_rate"
    assert data["target_percent"] == 99.5
    assert data["window_hours"] == 168


@pytest.mark.anyio
async def test_delete_sli_definition(client):
    """Should delete an SLI definition."""
    resp = await client.delete(f"{API_PREFIX}/sli-definitions/SLI-SEED-0001")
    assert resp.status_code == 204

    resp2 = await client.get(f"{API_PREFIX}/sli-definitions/SLI-SEED-0001")
    assert resp2.status_code == 404


@pytest.mark.anyio
async def test_delete_nonexistent_sli(client):
    """Deleting nonexistent SLI should return 404."""
    resp = await client.delete(f"{API_PREFIX}/sli-definitions/NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_nonexistent_sli(client):
    """Getting nonexistent SLI should return 404."""
    resp = await client.get(f"{API_PREFIX}/sli-definitions/NONEXISTENT")
    assert resp.status_code == 404


# ============================================================================
# SLI Filtering
# ============================================================================


@pytest.mark.anyio
async def test_filter_sli_by_service(client):
    """Should filter SLI definitions by service name."""
    resp = await client.get(
        f"{API_PREFIX}/sli-definitions",
        params={"service_name": "api-gateway"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for s in data["definitions"]:
        assert s["service_name"] == "api-gateway"


@pytest.mark.anyio
async def test_sli_pagination(client):
    """Should paginate SLI results."""
    resp = await client.get(
        f"{API_PREFIX}/sli-definitions",
        params={"limit": 4, "offset": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["definitions"]) == 4
    assert data["total"] == 8


# ============================================================================
# SLI Measurement
# ============================================================================


@pytest.mark.anyio
async def test_measure_sli(client):
    """Should measure an SLI and return current value."""
    resp = await client.get(f"{API_PREFIX}/sli-definitions/SLI-SEED-0001/measure")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sli_id"] == "SLI-SEED-0001"
    assert data["service_name"] == "api-gateway"
    assert data["sli_name"] == "availability"
    assert "current_value" in data
    assert "meeting_target" in data
    assert "measured_at" in data


@pytest.mark.anyio
async def test_measure_nonexistent_sli(client):
    """Measuring nonexistent SLI should return 404."""
    resp = await client.get(f"{API_PREFIX}/sli-definitions/NONEXISTENT/measure")
    assert resp.status_code == 404


# ============================================================================
# Deployment Gate Evaluation
# ============================================================================


@pytest.mark.anyio
async def test_evaluate_deployment_gate(client):
    """Should evaluate deployment gates and return aggregate result."""
    resp = await client.get(f"{API_PREFIX}/gate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] in ["PASS", "FAIL", "WARN"]
    assert "verification_status" in data
    assert "contract_pass_rate" in data
    assert "error_budgets_healthy" in data
    assert "evaluated_at" in data


@pytest.mark.anyio
async def test_deployment_gate_has_failing_checks(client):
    """Deployment gate should report failing checks when present."""
    resp = await client.get(f"{API_PREFIX}/gate")
    assert resp.status_code == 200
    data = resp.json()
    # With seed data: exhausted budget + failed verification = FAIL or WARN
    assert data["result"] in ["FAIL", "WARN"]
    assert len(data["failing_checks"]) > 0 or len(data["warnings"]) > 0


@pytest.mark.anyio
async def test_deployment_gate_with_deployment_filter(client):
    """Should evaluate gate for a specific deployment."""
    resp = await client.get(
        f"{API_PREFIX}/gate",
        params={"deployment_id": "DEP-SEED-0002"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] in ["PASS", "FAIL", "WARN"]


@pytest.mark.anyio
async def test_deployment_gate_contract_pass_rate(client):
    """Contract pass rate should be between 0 and 100."""
    resp = await client.get(f"{API_PREFIX}/gate")
    data = resp.json()
    assert 0 <= data["contract_pass_rate"] <= 100


@pytest.mark.anyio
async def test_deployment_gate_error_budgets_not_healthy(client):
    """Error budgets should not all be healthy with seed data."""
    resp = await client.get(f"{API_PREFIX}/gate")
    data = resp.json()
    # EXHAUSTED budget exists in seed
    assert data["error_budgets_healthy"] is False


# ============================================================================
# Verification Trends
# ============================================================================


@pytest.mark.anyio
async def test_verification_trends(client):
    """Should return verification trends."""
    resp = await client.get(f"{API_PREFIX}/trends", params={"days": 365})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for trend in data:
        assert "date" in trend
        assert "total_verifications" in trend
        assert "passed" in trend
        assert "failed" in trend
        assert "pass_rate" in trend


@pytest.mark.anyio
async def test_verification_trends_default_30_days(client):
    """Should return trends for default 30 days."""
    resp = await client.get(f"{API_PREFIX}/trends")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_verification_trends_pass_rate_valid(client):
    """Trend pass rate should be between 0 and 100."""
    resp = await client.get(f"{API_PREFIX}/trends", params={"days": 365})
    data = resp.json()
    for trend in data:
        assert 0 <= trend["pass_rate"] <= 100


# ============================================================================
# Aggregate Metrics
# ============================================================================


@pytest.mark.anyio
async def test_metrics(client):
    """Should return aggregate metrics."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_verifications"] == 5
    assert "pass_rate" in data
    assert "avg_verification_time_ms" in data
    assert data["total_contracts"] == 15
    assert "contract_test_pass_rate" in data
    assert "breaking_changes_detected" in data
    assert "error_budgets_healthy" in data
    assert "error_budgets_total" in data


@pytest.mark.anyio
async def test_metrics_pass_rate(client):
    """Metrics pass rate should reflect seed data."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    data = resp.json()
    # 3 passed, 1 failed, 1 running = 60% pass rate
    assert data["pass_rate"] == 60.0


@pytest.mark.anyio
async def test_metrics_contract_pass_rate(client):
    """Contract test pass rate should reflect seed data."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    data = resp.json()
    # 8 passed out of 10 = 80%
    assert data["contract_test_pass_rate"] == 80.0


@pytest.mark.anyio
async def test_metrics_breaking_changes_count(client):
    """Should count breaking changes from seed data."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    data = resp.json()
    # CTX-SEED-0009 has 2 breaks, CTX-SEED-0010 has 1 = 3 total
    assert data["breaking_changes_detected"] == 3


@pytest.mark.anyio
async def test_metrics_error_budget_counts(client):
    """Should count error budget statuses correctly."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    data = resp.json()
    assert data["error_budgets_total"] == 6
    # HEALTHY: EB-SEED-0001, EB-SEED-0003, EB-SEED-0005 = 3
    assert data["error_budgets_healthy"] == 3


@pytest.mark.anyio
async def test_metrics_has_recent_trends(client):
    """Metrics should include recent trends."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    data = resp.json()
    assert "recent_trends" in data
    assert isinstance(data["recent_trends"], list)


@pytest.mark.anyio
async def test_metrics_avg_verification_time_positive(client):
    """Average verification time should be positive."""
    resp = await client.get(f"{API_PREFIX}/metrics")
    data = resp.json()
    assert data["avg_verification_time_ms"] > 0


# ============================================================================
# Service Direct Tests (unit tests)
# ============================================================================


@pytest.mark.anyio
async def test_service_singleton():
    """Service should be a singleton."""
    svc1 = get_deployment_verification_service()
    svc2 = get_deployment_verification_service()
    assert svc1 is svc2


@pytest.mark.anyio
async def test_service_reset():
    """Service should be resettable."""
    svc1 = get_deployment_verification_service()
    reset_deployment_verification_service()
    svc2 = get_deployment_verification_service()
    assert svc1 is not svc2


@pytest.mark.anyio
async def test_service_detect_breaking_changes_empty():
    """Detect breaking changes should handle empty schemas."""
    svc = get_deployment_verification_service()
    changes = svc.detect_breaking_changes("CTR-SEED-0001", {})
    # All fields removed
    assert len(changes) >= 1


@pytest.mark.anyio
async def test_service_detect_breaking_changes_no_contract():
    """Detect breaking changes should return empty for nonexistent contract."""
    svc = get_deployment_verification_service()
    changes = svc.detect_breaking_changes("NONEXISTENT", {"type": "object"})
    assert len(changes) == 0


@pytest.mark.anyio
async def test_service_create_and_list_verification():
    """Should create verification and find it in list."""
    svc = get_deployment_verification_service()
    v = svc.create_verification("DEP-TEST", EnvironmentName.QA, "4.0.0", "test")
    result = svc.list_verifications()
    ids = [vv.id for vv in result.verifications]
    assert v.id in ids


@pytest.mark.anyio
async def test_service_create_and_delete_contract():
    """Should create and then delete a contract."""
    svc = get_deployment_verification_service()
    from app.schemas.deployment_verification import APIContractCreate, EnvironmentName
    c = svc.create_contract(APIContractCreate(
        endpoint_path="/test/endpoint",
        method="GET",
    ))
    assert svc.get_contract(c.id) is not None
    assert svc.delete_contract(c.id) is True
    assert svc.get_contract(c.id) is None


@pytest.mark.anyio
async def test_service_run_contract_test_breaking_change():
    """Should run breaking change test."""
    svc = get_deployment_verification_service()
    result = svc.run_contract_test("CTR-SEED-0001", ContractTestType.BREAKING_CHANGE)
    assert result is not None
    assert result.test_type == ContractTestType.BREAKING_CHANGE


@pytest.mark.anyio
async def test_service_run_contract_test_nonexistent():
    """Contract test for nonexistent contract should return None."""
    svc = get_deployment_verification_service()
    result = svc.run_contract_test("NONEXISTENT", ContractTestType.RESPONSE_SCHEMA)
    assert result is None


@pytest.mark.anyio
async def test_service_create_and_delete_error_budget():
    """Should create and then delete an error budget."""
    svc = get_deployment_verification_service()
    from app.schemas.deployment_verification import ErrorBudgetCreate
    b = svc.create_error_budget(ErrorBudgetCreate(
        service_name="test-service",
        sli_name="test-sli",
        target_percent=99.9,
    ))
    assert svc.get_error_budget(b.id) is not None
    assert svc.delete_error_budget(b.id) is True
    assert svc.get_error_budget(b.id) is None


@pytest.mark.anyio
async def test_service_create_and_delete_sli():
    """Should create and then delete an SLI definition."""
    svc = get_deployment_verification_service()
    from app.schemas.deployment_verification import SLIDefinitionCreate
    s = svc.create_sli_definition(SLIDefinitionCreate(
        service_name="test-svc",
        sli_name="test-metric",
        target_percent=99.0,
    ))
    assert svc.get_sli_definition(s.id) is not None
    assert svc.delete_sli_definition(s.id) is True
    assert svc.get_sli_definition(s.id) is None


@pytest.mark.anyio
async def test_service_measure_sli_nonexistent():
    """Measuring nonexistent SLI should return None."""
    svc = get_deployment_verification_service()
    result = svc.measure_sli("NONEXISTENT")
    assert result is None


@pytest.mark.anyio
async def test_service_burn_rate_nonexistent():
    """Burn rate for nonexistent budget should return None."""
    svc = get_deployment_verification_service()
    result = svc.calculate_burn_rate("NONEXISTENT")
    assert result is None


@pytest.mark.anyio
async def test_service_gate_with_all_passed():
    """Gate should be favorable when all checks pass."""
    svc = get_deployment_verification_service()
    # Delete exhausted/critical budgets and failed verifications
    svc._error_budgets.pop("EB-SEED-0006", None)  # exhausted
    svc._error_budgets.pop("EB-SEED-0004", None)  # critical
    svc._verifications.pop("DV-SEED-0004", None)  # failed
    svc._verifications.pop("DV-SEED-0005", None)  # running
    # Remove failed contract test results
    svc._contract_results.pop("CTX-SEED-0009", None)
    svc._contract_results.pop("CTX-SEED-0010", None)

    gate = svc.evaluate_deployment_gate()
    assert gate.result == DeploymentGateResult.PASS
    assert gate.error_budgets_healthy is True
    assert gate.contract_pass_rate == 100.0


# Import enum for direct tests
from app.schemas.deployment_verification import (
    ContractTestType,
    DeploymentGateResult,
    EnvironmentName,
    ErrorBudgetStatus,
    VerificationStatus,
    VerificationType,
)


# ============================================================================
# Additional Enum / Edge Case Tests
# ============================================================================


@pytest.mark.anyio
async def test_verification_type_enum_values():
    """VerificationType enum should have expected values."""
    assert VerificationType.SMOKE_TEST == "SMOKE_TEST"
    assert VerificationType.HEALTH_CHECK == "HEALTH_CHECK"
    assert VerificationType.SCHEMA_VALIDATION == "SCHEMA_VALIDATION"
    assert VerificationType.PERFORMANCE_CHECK == "PERFORMANCE_CHECK"
    assert VerificationType.DATA_INTEGRITY == "DATA_INTEGRITY"
    assert VerificationType.ROLLBACK_READINESS == "ROLLBACK_READINESS"


@pytest.mark.anyio
async def test_verification_status_enum_values():
    """VerificationStatus enum should have expected values."""
    assert VerificationStatus.PENDING == "PENDING"
    assert VerificationStatus.RUNNING == "RUNNING"
    assert VerificationStatus.PASSED == "PASSED"
    assert VerificationStatus.FAILED == "FAILED"
    assert VerificationStatus.SKIPPED == "SKIPPED"
    assert VerificationStatus.TIMED_OUT == "TIMED_OUT"


@pytest.mark.anyio
async def test_contract_test_type_enum_values():
    """ContractTestType enum should have expected values."""
    assert ContractTestType.REQUEST_SCHEMA == "REQUEST_SCHEMA"
    assert ContractTestType.RESPONSE_SCHEMA == "RESPONSE_SCHEMA"
    assert ContractTestType.BACKWARD_COMPATIBILITY == "BACKWARD_COMPATIBILITY"
    assert ContractTestType.BREAKING_CHANGE == "BREAKING_CHANGE"
    assert ContractTestType.DEPRECATION == "DEPRECATION"


@pytest.mark.anyio
async def test_environment_name_enum_values():
    """EnvironmentName enum should have expected values."""
    assert EnvironmentName.DEVELOPMENT == "DEVELOPMENT"
    assert EnvironmentName.STAGING == "STAGING"
    assert EnvironmentName.QA == "QA"
    assert EnvironmentName.UAT == "UAT"
    assert EnvironmentName.PRODUCTION == "PRODUCTION"


@pytest.mark.anyio
async def test_error_budget_status_enum_values():
    """ErrorBudgetStatus enum should have expected values."""
    assert ErrorBudgetStatus.HEALTHY == "HEALTHY"
    assert ErrorBudgetStatus.WARNING == "WARNING"
    assert ErrorBudgetStatus.CRITICAL == "CRITICAL"
    assert ErrorBudgetStatus.EXHAUSTED == "EXHAUSTED"


@pytest.mark.anyio
async def test_deployment_gate_result_enum_values():
    """DeploymentGateResult enum should have expected values."""
    assert DeploymentGateResult.PASS == "PASS"
    assert DeploymentGateResult.FAIL == "FAIL"
    assert DeploymentGateResult.WARN == "WARN"


@pytest.mark.anyio
async def test_create_verification_default_triggered_by(client):
    """Should default triggered_by to 'system'."""
    payload = {
        "deployment_id": "DEP-DEFAULT",
        "environment": "DEVELOPMENT",
        "version": "1.0.0",
    }
    resp = await client.post(f"{API_PREFIX}/verifications", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["triggered_by"] == "system"


@pytest.mark.anyio
async def test_smoke_test_triggered_by(client):
    """Smoke test should record triggered_by."""
    payload = {
        "deployment_id": "DEP-TRIG",
        "environment": "STAGING",
        "version": "3.0.0",
        "triggered_by": "qa-engineer",
    }
    resp = await client.post(f"{API_PREFIX}/smoke-tests", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["triggered_by"] == "qa-engineer"


@pytest.mark.anyio
async def test_contract_method_normalized_to_uppercase(client):
    """Contract method should be normalized to uppercase."""
    payload = {
        "endpoint_path": "/api/v1/test",
        "method": "get",
    }
    resp = await client.post(f"{API_PREFIX}/contracts", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["method"] == "GET"


@pytest.mark.anyio
async def test_update_contract_deprecated_sets_date(client):
    """Setting deprecated should set deprecated_date."""
    payload = {"deprecated": True}
    resp = await client.put(f"{API_PREFIX}/contracts/CTR-SEED-0001", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["deprecated"] is True
    assert data["deprecated_date"] is not None


@pytest.mark.anyio
async def test_error_budget_violations_in_detail(client):
    """Error budget violations should contain full details."""
    resp = await client.get(f"{API_PREFIX}/error-budgets/EB-SEED-0004")
    data = resp.json()
    assert len(data["violations"]) == 2
    v = data["violations"][0]
    assert "timestamp" in v
    assert "duration_minutes" in v
    assert "error_rate_percent" in v
    assert "cause" in v


@pytest.mark.anyio
async def test_new_error_budget_starts_healthy(client):
    """Newly created budget should start HEALTHY with full budget."""
    payload = {
        "service_name": "fresh-service",
        "sli_name": "uptime",
        "target_percent": 99.99,
    }
    resp = await client.post(f"{API_PREFIX}/error-budgets", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert data["remaining_budget_percent"] == 100.0
    assert data["burn_rate_per_hour"] == 0.0
    assert len(data["violations"]) == 0


@pytest.mark.anyio
async def test_sli_definition_has_measurement_query(client):
    """SLI definitions should have measurement queries."""
    resp = await client.get(f"{API_PREFIX}/sli-definitions/SLI-SEED-0001")
    data = resp.json()
    assert data["measurement_query"] is not None
    assert len(data["measurement_query"]) > 0


@pytest.mark.anyio
async def test_sli_definition_window_hours(client):
    """SLI definition window hours should be present."""
    resp = await client.get(f"{API_PREFIX}/sli-definitions/SLI-SEED-0001")
    data = resp.json()
    assert data["window_hours"] == 720


@pytest.mark.anyio
async def test_run_smoke_tests_adds_to_list(client):
    """Running smoke tests should add the verification to the list."""
    initial = await client.get(f"{API_PREFIX}/verifications", params={"limit": 50})
    initial_count = initial.json()["total"]

    payload = {
        "deployment_id": "DEP-ADD",
        "environment": "QA",
        "version": "5.0.0",
    }
    await client.post(f"{API_PREFIX}/smoke-tests", json=payload)

    after = await client.get(f"{API_PREFIX}/verifications", params={"limit": 50})
    assert after.json()["total"] == initial_count + 1


@pytest.mark.anyio
async def test_run_contract_test_adds_to_results(client):
    """Running a contract test should add to results list."""
    initial = await client.get(f"{API_PREFIX}/contract-tests", params={"limit": 50})
    initial_count = initial.json()["total"]

    await client.post(
        f"{API_PREFIX}/contracts/CTR-SEED-0001/test",
        params={"test_type": "RESPONSE_SCHEMA"},
    )

    after = await client.get(f"{API_PREFIX}/contract-tests", params={"limit": 50})
    assert after.json()["total"] == initial_count + 1


@pytest.mark.anyio
async def test_filter_verifications_by_failed_status(client):
    """Should filter to only FAILED verifications."""
    resp = await client.get(
        f"{API_PREFIX}/verifications",
        params={"status": "FAILED"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["verifications"][0]["overall_status"] == "FAILED"


@pytest.mark.anyio
async def test_filter_verifications_by_staging(client):
    """Should filter to STAGING verifications."""
    resp = await client.get(
        f"{API_PREFIX}/verifications",
        params={"environment": "STAGING"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2  # DV-SEED-0002 and DV-SEED-0005


@pytest.mark.anyio
async def test_contracts_sorted_by_path(client):
    """Contracts should be sorted by endpoint path."""
    resp = await client.get(f"{API_PREFIX}/contracts", params={"limit": 50})
    data = resp.json()
    paths = [c["endpoint_path"] for c in data["contracts"]]
    assert paths == sorted(paths)


@pytest.mark.anyio
async def test_contract_test_results_sorted_by_created_at(client):
    """Contract test results should be sorted by created_at descending."""
    resp = await client.get(f"{API_PREFIX}/contract-tests", params={"limit": 50})
    data = resp.json()
    timestamps = [r["created_at"] for r in data["results"]]
    assert timestamps == sorted(timestamps, reverse=True)
