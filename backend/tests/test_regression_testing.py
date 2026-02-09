"""Comprehensive tests for Regression Test Orchestration (QA-4).

Tests cover:
- Seed data verification (test cases, suites, runs, flaky reports, coverage, trends)
- Test case CRUD and filtering
- Test suite CRUD, enable/disable
- Test run triggering and listing
- Run results retrieval
- Coverage tracking
- Flaky test detection and triaging
- Regression trend analysis
- Test health dashboard
- Impact analysis
- Estimated run time
- Test prioritization
- Error handling (404s, validation)
- Pagination and filtering
"""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

from app.main import app
from app.services.regression_testing_service import (
    get_regression_testing_service,
    reset_regression_testing_service,
)

API = "/api/v1/regression-testing"


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the service before each test."""
    reset_regression_testing_service()
    yield
    reset_regression_testing_service()


@pytest.fixture
async def client():
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================================
# Seed Data Verification - Test Cases
# ============================================================================


@pytest.mark.anyio
async def test_seed_test_cases_count(client):
    """Seed should contain 30 test cases."""
    resp = await client.get(f"{API}/test-cases", params={"limit": 100})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 30


@pytest.mark.anyio
async def test_seed_test_case_has_required_fields(client):
    """Each seeded test case has all required fields."""
    resp = await client.get(f"{API}/test-cases/tc-001")
    assert resp.status_code == 200
    tc = resp.json()
    assert tc["id"] == "tc-001"
    assert tc["name"]
    assert tc["module"]
    assert tc["suite_type"]
    assert tc["priority"]
    assert "tags" in tc
    assert "expected_duration_ms" in tc
    assert "automated" in tc
    assert "steps" in tc


@pytest.mark.anyio
async def test_seed_test_case_modules_distributed(client):
    """Test cases span multiple modules."""
    resp = await client.get(f"{API}/test-cases", params={"limit": 100})
    modules = {tc["module"] for tc in resp.json()["items"]}
    assert len(modules) >= 5


@pytest.mark.anyio
async def test_seed_test_case_priorities_distributed(client):
    """Test cases span multiple priorities."""
    resp = await client.get(f"{API}/test-cases", params={"limit": 100})
    priorities = {tc["priority"] for tc in resp.json()["items"]}
    assert len(priorities) >= 3


@pytest.mark.anyio
async def test_seed_test_case_suite_types_distributed(client):
    """Test cases span multiple suite types."""
    resp = await client.get(f"{API}/test-cases", params={"limit": 100})
    types = {tc["suite_type"] for tc in resp.json()["items"]}
    assert len(types) >= 4


# ============================================================================
# Seed Data Verification - Test Suites
# ============================================================================


@pytest.mark.anyio
async def test_seed_test_suites_count(client):
    """Seed should contain 6 test suites."""
    resp = await client.get(f"{API}/test-suites", params={"limit": 50})
    assert resp.status_code == 200
    assert resp.json()["total"] == 6


@pytest.mark.anyio
async def test_seed_smoke_suite(client):
    """Smoke suite should have correct properties."""
    resp = await client.get(f"{API}/test-suites/suite-smoke")
    assert resp.status_code == 200
    s = resp.json()
    assert s["suite_type"] == "SMOKE"
    assert s["estimated_duration_minutes"] == 5
    assert s["enabled"] is True
    assert len(s["test_case_ids"]) == 5


@pytest.mark.anyio
async def test_seed_regression_suite(client):
    """Full regression suite should contain all 30 test cases."""
    resp = await client.get(f"{API}/test-suites/suite-regression")
    assert resp.status_code == 200
    s = resp.json()
    assert s["suite_type"] == "REGRESSION"
    assert s["estimated_duration_minutes"] == 45
    assert len(s["test_case_ids"]) == 30


@pytest.mark.anyio
async def test_seed_e2e_suite_not_parallelizable(client):
    """E2E suite should not be parallelizable."""
    resp = await client.get(f"{API}/test-suites/suite-e2e")
    assert resp.status_code == 200
    assert resp.json()["parallelizable"] is False


@pytest.mark.anyio
async def test_seed_compliance_suite(client):
    """Compliance suite should exist with correct type."""
    resp = await client.get(f"{API}/test-suites/suite-compliance")
    assert resp.status_code == 200
    assert resp.json()["suite_type"] == "COMPLIANCE"


@pytest.mark.anyio
async def test_seed_all_suites_enabled(client):
    """All seeded suites should be enabled."""
    resp = await client.get(f"{API}/test-suites", params={"enabled": True, "limit": 50})
    assert resp.json()["total"] == 6


# ============================================================================
# Seed Data Verification - Test Runs
# ============================================================================


@pytest.mark.anyio
async def test_seed_test_runs_count(client):
    """Seed should contain 10 test runs."""
    resp = await client.get(f"{API}/runs", params={"limit": 50})
    assert resp.status_code == 200
    assert resp.json()["total"] == 10


@pytest.mark.anyio
async def test_seed_completed_runs(client):
    """8 runs should be completed."""
    resp = await client.get(f"{API}/runs", params={"status": "COMPLETED", "limit": 50})
    assert resp.json()["total"] == 8


@pytest.mark.anyio
async def test_seed_running_run(client):
    """1 run should be in RUNNING status."""
    resp = await client.get(f"{API}/runs", params={"status": "RUNNING", "limit": 50})
    assert resp.json()["total"] == 1


@pytest.mark.anyio
async def test_seed_queued_run(client):
    """1 run should be in QUEUED status."""
    resp = await client.get(f"{API}/runs", params={"status": "QUEUED", "limit": 50})
    assert resp.json()["total"] == 1


@pytest.mark.anyio
async def test_seed_run_has_results(client):
    """Completed runs should have per-test results."""
    resp = await client.get(f"{API}/runs/run-001")
    assert resp.status_code == 200
    run = resp.json()
    assert run["status"] == "COMPLETED"
    assert len(run["results"]) > 0


@pytest.mark.anyio
async def test_seed_run_pass_rate(client):
    """Completed run should have a valid pass rate."""
    resp = await client.get(f"{API}/runs/run-001")
    run = resp.json()
    assert 0 <= run["pass_rate"] <= 100


# ============================================================================
# Seed Data Verification - Flaky Tests
# ============================================================================


@pytest.mark.anyio
async def test_seed_flaky_reports_count(client):
    """Seed should contain 5 flaky test reports."""
    resp = await client.get(f"{API}/flaky-tests")
    assert resp.status_code == 200
    assert resp.json()["total"] == 5


@pytest.mark.anyio
async def test_seed_flaky_report_fields(client):
    """Flaky reports have all required fields."""
    resp = await client.get(f"{API}/flaky-tests")
    item = resp.json()["items"][0]
    assert "test_case_id" in item
    assert "flaky_rate" in item
    assert "total_runs_30d" in item
    assert "root_cause_category" in item
    assert "triaged" in item


@pytest.mark.anyio
async def test_seed_flaky_some_triaged(client):
    """Some flaky tests should be triaged."""
    resp = await client.get(f"{API}/flaky-tests", params={"triaged": True})
    assert resp.json()["total"] >= 1


@pytest.mark.anyio
async def test_seed_flaky_some_untriaged(client):
    """Some flaky tests should be untriaged."""
    resp = await client.get(f"{API}/flaky-tests", params={"triaged": False})
    assert resp.json()["total"] >= 1


# ============================================================================
# Seed Data Verification - Coverage
# ============================================================================


@pytest.mark.anyio
async def test_seed_coverage_count(client):
    """Seed should contain 8 coverage entries."""
    resp = await client.get(f"{API}/coverage")
    assert resp.status_code == 200
    assert resp.json()["total"] == 8


@pytest.mark.anyio
async def test_seed_coverage_overall(client):
    """Overall coverage should be a reasonable percentage."""
    resp = await client.get(f"{API}/coverage")
    overall = resp.json()["overall_coverage"]
    assert 50 <= overall <= 100


@pytest.mark.anyio
async def test_seed_coverage_module(client):
    """Individual module coverage should be available."""
    resp = await client.get(f"{API}/coverage/patient_screening")
    assert resp.status_code == 200
    cov = resp.json()
    assert cov["module"] == "patient_screening"
    assert cov["coverage_percent"] > 0
    assert cov["total_lines"] > 0


# ============================================================================
# Seed Data Verification - Trends
# ============================================================================


@pytest.mark.anyio
async def test_seed_trends(client):
    """Seed should contain 14 days of trend data."""
    resp = await client.get(f"{API}/trends")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_days"] == 14
    assert len(data["items"]) == 14


@pytest.mark.anyio
async def test_seed_trend_fields(client):
    """Each trend data point has required fields."""
    resp = await client.get(f"{API}/trends")
    item = resp.json()["items"][0]
    assert "date" in item
    assert "total_tests" in item
    assert "pass_rate" in item
    assert "avg_duration_seconds" in item
    assert "new_failures" in item
    assert "resolved_failures" in item


# ============================================================================
# Test Case CRUD
# ============================================================================


@pytest.mark.anyio
async def test_create_test_case(client):
    """Create a new test case."""
    payload = {
        "name": "New Screening Validation",
        "description": "Validates new screening logic",
        "suite_type": "REGRESSION",
        "priority": "P1_HIGH",
        "module": "patient_screening",
        "tags": ["screening", "regression"],
        "expected_duration_ms": 2500,
        "owner": "qa-team",
        "automated": True,
        "preconditions": ["Database seeded"],
        "steps": ["Setup", "Execute", "Assert"],
    }
    resp = await client.post(f"{API}/test-cases", json=payload)
    assert resp.status_code == 201
    tc = resp.json()
    assert tc["name"] == "New Screening Validation"
    assert tc["suite_type"] == "REGRESSION"
    assert tc["priority"] == "P1_HIGH"
    assert tc["module"] == "patient_screening"
    assert tc["automated"] is True


@pytest.mark.anyio
async def test_create_test_case_increases_total(client):
    """Creating a test case increases the total count."""
    resp = await client.get(f"{API}/test-cases", params={"limit": 1})
    before = resp.json()["total"]
    payload = {
        "name": "Extra Test",
        "suite_type": "SMOKE",
        "module": "auth_service",
    }
    await client.post(f"{API}/test-cases", json=payload)
    resp = await client.get(f"{API}/test-cases", params={"limit": 1})
    assert resp.json()["total"] == before + 1


@pytest.mark.anyio
async def test_update_test_case(client):
    """Update an existing test case."""
    payload = {"name": "Updated Name", "priority": "P0_CRITICAL"}
    resp = await client.patch(f"{API}/test-cases/tc-001", json=payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
    assert resp.json()["priority"] == "P0_CRITICAL"


@pytest.mark.anyio
async def test_update_test_case_partial(client):
    """Partial update preserves other fields."""
    resp_before = await client.get(f"{API}/test-cases/tc-002")
    original_module = resp_before.json()["module"]
    payload = {"name": "Only Name Changed"}
    resp = await client.patch(f"{API}/test-cases/tc-002", json=payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Only Name Changed"
    assert resp.json()["module"] == original_module


@pytest.mark.anyio
async def test_delete_test_case(client):
    """Delete a test case."""
    resp = await client.delete(f"{API}/test-cases/tc-030")
    assert resp.status_code == 204
    resp = await client.get(f"{API}/test-cases/tc-030")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_test_case_decreases_total(client):
    """Deleting a test case decreases the total count."""
    resp = await client.get(f"{API}/test-cases", params={"limit": 1})
    before = resp.json()["total"]
    await client.delete(f"{API}/test-cases/tc-029")
    resp = await client.get(f"{API}/test-cases", params={"limit": 1})
    assert resp.json()["total"] == before - 1


# ============================================================================
# Test Case Filtering
# ============================================================================


@pytest.mark.anyio
async def test_filter_by_suite_type(client):
    """Filter test cases by suite type."""
    resp = await client.get(f"{API}/test-cases", params={"suite_type": "SMOKE"})
    assert resp.status_code == 200
    for tc in resp.json()["items"]:
        assert tc["suite_type"] == "SMOKE"


@pytest.mark.anyio
async def test_filter_by_priority(client):
    """Filter test cases by priority."""
    resp = await client.get(f"{API}/test-cases", params={"priority": "P0_CRITICAL"})
    assert resp.status_code == 200
    for tc in resp.json()["items"]:
        assert tc["priority"] == "P0_CRITICAL"


@pytest.mark.anyio
async def test_filter_by_module(client):
    """Filter test cases by module."""
    resp = await client.get(f"{API}/test-cases", params={"module": "patient_screening"})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
    for tc in resp.json()["items"]:
        assert tc["module"] == "patient_screening"


@pytest.mark.anyio
async def test_filter_by_tag(client):
    """Filter test cases by tag."""
    resp = await client.get(f"{API}/test-cases", params={"tag": "smoke"})
    assert resp.status_code == 200
    for tc in resp.json()["items"]:
        assert "smoke" in tc["tags"]


@pytest.mark.anyio
async def test_filter_automated_only(client):
    """Filter to automated tests only."""
    resp = await client.get(f"{API}/test-cases", params={"automated": True})
    assert resp.status_code == 200
    for tc in resp.json()["items"]:
        assert tc["automated"] is True


@pytest.mark.anyio
async def test_filter_manual_only(client):
    """Filter to manual tests only."""
    resp = await client.get(f"{API}/test-cases", params={"automated": False})
    assert resp.status_code == 200
    for tc in resp.json()["items"]:
        assert tc["automated"] is False


@pytest.mark.anyio
async def test_pagination_test_cases(client):
    """Pagination works for test cases."""
    resp1 = await client.get(f"{API}/test-cases", params={"limit": 5, "offset": 0})
    resp2 = await client.get(f"{API}/test-cases", params={"limit": 5, "offset": 5})
    items1 = resp1.json()["items"]
    items2 = resp2.json()["items"]
    assert len(items1) == 5
    assert len(items2) == 5
    ids1 = {t["id"] for t in items1}
    ids2 = {t["id"] for t in items2}
    assert ids1.isdisjoint(ids2)


# ============================================================================
# Test Suite CRUD
# ============================================================================


@pytest.mark.anyio
async def test_create_test_suite(client):
    """Create a new test suite."""
    payload = {
        "name": "New Custom Suite",
        "suite_type": "SECURITY",
        "description": "Security validation suite",
        "test_case_ids": ["tc-001", "tc-002"],
        "trigger_types": ["MANUAL"],
        "estimated_duration_minutes": 25,
        "parallelizable": True,
        "max_parallel": 2,
        "enabled": True,
    }
    resp = await client.post(f"{API}/test-suites", json=payload)
    assert resp.status_code == 201
    s = resp.json()
    assert s["name"] == "New Custom Suite"
    assert s["suite_type"] == "SECURITY"
    assert len(s["test_case_ids"]) == 2


@pytest.mark.anyio
async def test_update_test_suite(client):
    """Update an existing test suite."""
    payload = {"name": "Updated Smoke Suite", "estimated_duration_minutes": 10}
    resp = await client.patch(f"{API}/test-suites/suite-smoke", json=payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Smoke Suite"
    assert resp.json()["estimated_duration_minutes"] == 10


@pytest.mark.anyio
async def test_delete_test_suite(client):
    """Delete a test suite."""
    resp = await client.delete(f"{API}/test-suites/suite-compliance")
    assert resp.status_code == 204
    resp = await client.get(f"{API}/test-suites/suite-compliance")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_enable_suite(client):
    """Enable a disabled suite."""
    await client.post(f"{API}/test-suites/suite-smoke/disable")
    resp = await client.post(f"{API}/test-suites/suite-smoke/enable")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


@pytest.mark.anyio
async def test_disable_suite(client):
    """Disable a suite."""
    resp = await client.post(f"{API}/test-suites/suite-smoke/disable")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


@pytest.mark.anyio
async def test_filter_suites_by_type(client):
    """Filter suites by suite type."""
    resp = await client.get(f"{API}/test-suites", params={"suite_type": "SMOKE"})
    assert resp.status_code == 200
    for s in resp.json()["items"]:
        assert s["suite_type"] == "SMOKE"


@pytest.mark.anyio
async def test_filter_suites_enabled(client):
    """Filter suites by enabled status."""
    await client.post(f"{API}/test-suites/suite-smoke/disable")
    resp = await client.get(f"{API}/test-suites", params={"enabled": False})
    assert resp.json()["total"] >= 1


@pytest.mark.anyio
async def test_suite_pagination(client):
    """Pagination works for suites."""
    resp = await client.get(f"{API}/test-suites", params={"limit": 2, "offset": 0})
    assert len(resp.json()["items"]) == 2
    resp2 = await client.get(f"{API}/test-suites", params={"limit": 2, "offset": 2})
    assert len(resp2.json()["items"]) == 2


# ============================================================================
# Test Runs
# ============================================================================


@pytest.mark.anyio
async def test_trigger_test_run(client):
    """Trigger a new test run."""
    payload = {
        "suite_id": "suite-smoke",
        "trigger_type": "MANUAL",
        "triggered_by": "test-user",
        "build_version": "v2.0.0",
        "environment": "staging",
    }
    resp = await client.post(f"{API}/runs/trigger", json=payload)
    assert resp.status_code == 201
    run = resp.json()
    assert run["suite_id"] == "suite-smoke"
    assert run["status"] == "COMPLETED"
    assert run["triggered_by"] == "test-user"
    assert run["total_tests"] == 5
    assert len(run["results"]) == 5


@pytest.mark.anyio
async def test_trigger_run_increases_total(client):
    """Triggering a run increases the total count."""
    resp = await client.get(f"{API}/runs", params={"limit": 1})
    before = resp.json()["total"]
    payload = {"suite_id": "suite-smoke"}
    await client.post(f"{API}/runs/trigger", json=payload)
    resp = await client.get(f"{API}/runs", params={"limit": 1})
    assert resp.json()["total"] == before + 1


@pytest.mark.anyio
async def test_trigger_run_invalid_suite(client):
    """Triggering a run for nonexistent suite returns 404."""
    payload = {"suite_id": "suite-nonexistent"}
    resp = await client.post(f"{API}/runs/trigger", json=payload)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_list_runs_filter_by_suite(client):
    """Filter runs by suite ID."""
    resp = await client.get(f"{API}/runs", params={"suite_id": "suite-smoke"})
    assert resp.status_code == 200
    for r in resp.json()["items"]:
        assert r["suite_id"] == "suite-smoke"


@pytest.mark.anyio
async def test_list_runs_filter_by_status(client):
    """Filter runs by status."""
    resp = await client.get(f"{API}/runs", params={"status": "COMPLETED"})
    assert resp.status_code == 200
    for r in resp.json()["items"]:
        assert r["status"] == "COMPLETED"


@pytest.mark.anyio
async def test_get_run_by_id(client):
    """Get a specific run by ID."""
    resp = await client.get(f"{API}/runs/run-001")
    assert resp.status_code == 200
    assert resp.json()["id"] == "run-001"


@pytest.mark.anyio
async def test_get_run_results(client):
    """Get results for a specific run."""
    resp = await client.get(f"{API}/runs/run-001/results")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) > 0
    assert "test_case_id" in results[0]
    assert "status" in results[0]
    assert "duration_ms" in results[0]


@pytest.mark.anyio
async def test_run_results_nonexistent(client):
    """Results for nonexistent run returns 404."""
    resp = await client.get(f"{API}/runs/run-nonexistent/results")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_run_pagination(client):
    """Pagination works for runs."""
    resp = await client.get(f"{API}/runs", params={"limit": 3, "offset": 0})
    assert len(resp.json()["items"]) == 3


# ============================================================================
# Coverage
# ============================================================================


@pytest.mark.anyio
async def test_list_coverage(client):
    """List all coverage entries."""
    resp = await client.get(f"{API}/coverage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 8
    assert data["overall_coverage"] > 0


@pytest.mark.anyio
async def test_get_module_coverage(client):
    """Get coverage for a specific module."""
    resp = await client.get(f"{API}/coverage/trial_matching")
    assert resp.status_code == 200
    cov = resp.json()
    assert cov["module"] == "trial_matching"
    assert cov["total_lines"] > 0
    assert cov["covered_lines"] > 0


@pytest.mark.anyio
async def test_coverage_module_not_found(client):
    """Coverage for nonexistent module returns 404."""
    resp = await client.get(f"{API}/coverage/nonexistent_module")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_coverage_has_uncovered_functions(client):
    """Coverage entries should list uncovered functions."""
    resp = await client.get(f"{API}/coverage/patient_screening")
    cov = resp.json()
    assert "uncovered_functions" in cov
    assert len(cov["uncovered_functions"]) >= 1


@pytest.mark.anyio
async def test_coverage_branch_coverage(client):
    """Branch coverage should be less than or equal to line coverage."""
    resp = await client.get(f"{API}/coverage/patient_screening")
    cov = resp.json()
    assert cov["branch_coverage_percent"] <= cov["coverage_percent"]


# ============================================================================
# Flaky Tests
# ============================================================================


@pytest.mark.anyio
async def test_list_flaky_tests(client):
    """List all flaky test reports."""
    resp = await client.get(f"{API}/flaky-tests")
    assert resp.status_code == 200
    assert resp.json()["total"] == 5


@pytest.mark.anyio
async def test_list_flaky_sorted_by_rate(client):
    """Flaky tests sorted by flaky rate descending."""
    resp = await client.get(f"{API}/flaky-tests")
    items = resp.json()["items"]
    rates = [i["flaky_rate"] for i in items]
    assert rates == sorted(rates, reverse=True)


@pytest.mark.anyio
async def test_filter_flaky_triaged(client):
    """Filter flaky tests by triaged status."""
    resp = await client.get(f"{API}/flaky-tests", params={"triaged": True})
    for item in resp.json()["items"]:
        assert item["triaged"] is True


@pytest.mark.anyio
async def test_filter_flaky_untriaged(client):
    """Filter flaky tests by untriaged status."""
    resp = await client.get(f"{API}/flaky-tests", params={"triaged": False})
    for item in resp.json()["items"]:
        assert item["triaged"] is False


@pytest.mark.anyio
async def test_get_flaky_report(client):
    """Get a specific flaky report."""
    resp = await client.get(f"{API}/flaky-tests")
    first_id = resp.json()["items"][0]["test_case_id"]
    resp = await client.get(f"{API}/flaky-tests/{first_id}")
    assert resp.status_code == 200
    assert resp.json()["test_case_id"] == first_id


@pytest.mark.anyio
async def test_flaky_report_not_found(client):
    """Nonexistent flaky report returns 404."""
    resp = await client.get(f"{API}/flaky-tests/tc-nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_triage_flaky_test(client):
    """Triage a flaky test."""
    resp = await client.get(f"{API}/flaky-tests", params={"triaged": False})
    untriaged = resp.json()["items"]
    assert len(untriaged) > 0
    tc_id = untriaged[0]["test_case_id"]
    payload = {"root_cause_category": "RACE_CONDITION", "triaged": True}
    resp = await client.post(f"{API}/flaky-tests/{tc_id}/triage", json=payload)
    assert resp.status_code == 200
    assert resp.json()["triaged"] is True
    assert resp.json()["root_cause_category"] == "RACE_CONDITION"


@pytest.mark.anyio
async def test_triage_nonexistent_flaky(client):
    """Triaging nonexistent flaky test returns 404."""
    payload = {"root_cause_category": "TIMING", "triaged": True}
    resp = await client.post(f"{API}/flaky-tests/tc-nonexistent/triage", json=payload)
    assert resp.status_code == 404


# ============================================================================
# Trends
# ============================================================================


@pytest.mark.anyio
async def test_get_trends_default(client):
    """Get trends with default 14-day window."""
    resp = await client.get(f"{API}/trends")
    assert resp.status_code == 200
    assert resp.json()["total_days"] == 14


@pytest.mark.anyio
async def test_get_trends_custom_window(client):
    """Get trends with custom window."""
    resp = await client.get(f"{API}/trends", params={"days": 7})
    assert resp.status_code == 200
    assert resp.json()["total_days"] == 7


@pytest.mark.anyio
async def test_trends_pass_rate_improving(client):
    """Pass rate should generally improve over time."""
    resp = await client.get(f"{API}/trends")
    items = resp.json()["items"]
    first_rate = items[0]["pass_rate"]
    last_rate = items[-1]["pass_rate"]
    assert last_rate >= first_rate


@pytest.mark.anyio
async def test_trends_have_dates(client):
    """Each trend entry has a date field."""
    resp = await client.get(f"{API}/trends")
    for item in resp.json()["items"]:
        assert len(item["date"]) == 10  # YYYY-MM-DD


# ============================================================================
# Dashboard
# ============================================================================


@pytest.mark.anyio
async def test_dashboard_returns_metrics(client):
    """Dashboard should return aggregate metrics."""
    resp = await client.get(f"{API}/dashboard")
    assert resp.status_code == 200
    d = resp.json()
    assert "metrics" in d
    m = d["metrics"]
    assert m["total_test_cases"] == 30
    assert m["total_automated"] >= 1
    assert m["automation_rate"] > 0


@pytest.mark.anyio
async def test_dashboard_recent_runs(client):
    """Dashboard should include recent runs."""
    resp = await client.get(f"{API}/dashboard")
    assert len(resp.json()["recent_runs"]) > 0


@pytest.mark.anyio
async def test_dashboard_flaky_reports(client):
    """Dashboard should include flaky reports."""
    resp = await client.get(f"{API}/dashboard")
    assert len(resp.json()["flaky_reports"]) == 5


@pytest.mark.anyio
async def test_dashboard_trends(client):
    """Dashboard should include trend data."""
    resp = await client.get(f"{API}/dashboard")
    assert len(resp.json()["trends"]) > 0


@pytest.mark.anyio
async def test_dashboard_suites_count(client):
    """Dashboard should report enabled/disabled suite counts."""
    resp = await client.get(f"{API}/dashboard")
    d = resp.json()
    assert d["suites_enabled"] == 6
    assert d["suites_disabled"] == 0


@pytest.mark.anyio
async def test_dashboard_health_score(client):
    """Dashboard should have a health score between 0-100."""
    resp = await client.get(f"{API}/dashboard")
    score = resp.json()["health_score"]
    assert 0 <= score <= 100


@pytest.mark.anyio
async def test_dashboard_coverage_by_module(client):
    """Dashboard metrics should include coverage by module."""
    resp = await client.get(f"{API}/dashboard")
    cov = resp.json()["metrics"]["coverage_by_module"]
    assert len(cov) == 8


@pytest.mark.anyio
async def test_dashboard_p0_pass_rate(client):
    """Dashboard should report P0 pass rate."""
    resp = await client.get(f"{API}/dashboard")
    m = resp.json()["metrics"]
    assert "p0_pass_rate" in m
    assert 0 <= m["p0_pass_rate"] <= 100


@pytest.mark.anyio
async def test_dashboard_next_scheduled_run(client):
    """Dashboard should include next scheduled run time."""
    resp = await client.get(f"{API}/dashboard")
    assert resp.json()["next_scheduled_run"] is not None


# ============================================================================
# Impact Analysis
# ============================================================================


@pytest.mark.anyio
async def test_impact_analysis_single_module(client):
    """Impact analysis for a single module."""
    payload = {"changed_modules": ["patient_screening"]}
    resp = await client.post(f"{API}/impact-analysis", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["affected_test_count"] >= 1
    assert len(data["affected_test_ids"]) >= 1


@pytest.mark.anyio
async def test_impact_analysis_multiple_modules(client):
    """Impact analysis for multiple modules."""
    payload = {"changed_modules": ["patient_screening", "trial_matching", "auth_service"]}
    resp = await client.post(f"{API}/impact-analysis", json=payload)
    assert resp.status_code == 200
    assert resp.json()["affected_test_count"] >= 3


@pytest.mark.anyio
async def test_impact_analysis_includes_dependent(client):
    """Impact analysis with dependent modules included."""
    payload = {"changed_modules": ["patient_screening"], "include_dependent": True}
    resp = await client.post(f"{API}/impact-analysis", json=payload)
    count_with = resp.json()["affected_test_count"]

    payload2 = {"changed_modules": ["patient_screening"], "include_dependent": False}
    resp2 = await client.post(f"{API}/impact-analysis", json=payload2)
    count_without = resp2.json()["affected_test_count"]

    assert count_with >= count_without


@pytest.mark.anyio
async def test_impact_analysis_estimated_duration(client):
    """Impact analysis should estimate duration."""
    payload = {"changed_modules": ["patient_screening"]}
    resp = await client.post(f"{API}/impact-analysis", json=payload)
    assert resp.json()["estimated_duration_minutes"] >= 0


@pytest.mark.anyio
async def test_impact_analysis_recommends_suite(client):
    """Impact analysis should recommend a suite type."""
    payload = {"changed_modules": ["patient_screening"]}
    resp = await client.post(f"{API}/impact-analysis", json=payload)
    assert resp.json()["recommended_suite_type"] in [
        "SMOKE", "REGRESSION", "INTEGRATION", "E2E",
        "PERFORMANCE", "SECURITY", "COMPLIANCE", "ACCESSIBILITY",
    ]


# ============================================================================
# Estimated Run Time
# ============================================================================


@pytest.mark.anyio
async def test_estimated_run_time_smoke(client):
    """Estimate run time for smoke suite."""
    resp = await client.get(f"{API}/suites/suite-smoke/estimated-time")
    assert resp.status_code == 200
    est = resp.json()
    assert est["suite_id"] == "suite-smoke"
    assert est["test_count"] == 5
    assert est["sequential_minutes"] > 0
    assert est["parallel_minutes"] > 0
    assert est["parallel_minutes"] <= est["sequential_minutes"]


@pytest.mark.anyio
async def test_estimated_run_time_e2e(client):
    """E2E suite should have same sequential and parallel time (not parallelizable)."""
    resp = await client.get(f"{API}/suites/suite-e2e/estimated-time")
    est = resp.json()
    assert est["sequential_minutes"] == est["parallel_minutes"]


@pytest.mark.anyio
async def test_estimated_run_time_not_found(client):
    """Nonexistent suite returns 404."""
    resp = await client.get(f"{API}/suites/suite-nonexistent/estimated-time")
    assert resp.status_code == 404


# ============================================================================
# Prioritization
# ============================================================================


@pytest.mark.anyio
async def test_prioritized_tests_p0_first(client):
    """P0 tests should come before P1/P2/P3."""
    resp = await client.get(f"{API}/prioritized-tests")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) > 0
    # Find first non-P0
    p0_done = False
    for tc in items:
        if tc["priority"] != "P0_CRITICAL":
            p0_done = True
        if p0_done:
            assert tc["priority"] != "P0_CRITICAL"


@pytest.mark.anyio
async def test_prioritized_tests_has_estimate(client):
    """Prioritized list should include estimated duration."""
    resp = await client.get(f"{API}/prioritized-tests")
    assert resp.json()["estimated_duration_minutes"] >= 0


@pytest.mark.anyio
async def test_prioritized_tests_filter_by_suite_type(client):
    """Filter prioritized tests by suite type."""
    resp = await client.get(f"{API}/prioritized-tests", params={"suite_type": "SMOKE"})
    for tc in resp.json()["items"]:
        assert tc["suite_type"] == "SMOKE"


@pytest.mark.anyio
async def test_prioritized_tests_limit(client):
    """Limit the number of prioritized tests."""
    resp = await client.get(f"{API}/prioritized-tests", params={"limit": 5})
    assert len(resp.json()["items"]) <= 5


# ============================================================================
# Error Handling - 404s
# ============================================================================


@pytest.mark.anyio
async def test_404_test_case(client):
    """Nonexistent test case returns 404."""
    resp = await client.get(f"{API}/test-cases/tc-nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_404_test_suite(client):
    """Nonexistent test suite returns 404."""
    resp = await client.get(f"{API}/test-suites/suite-nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_404_test_run(client):
    """Nonexistent test run returns 404."""
    resp = await client.get(f"{API}/runs/run-nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_404_update_test_case(client):
    """Update nonexistent test case returns 404."""
    resp = await client.patch(f"{API}/test-cases/tc-nonexistent", json={"name": "X"})
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_404_delete_test_case(client):
    """Delete nonexistent test case returns 404."""
    resp = await client.delete(f"{API}/test-cases/tc-nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_404_update_test_suite(client):
    """Update nonexistent test suite returns 404."""
    resp = await client.patch(f"{API}/test-suites/suite-nonexistent", json={"name": "X"})
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_404_delete_test_suite(client):
    """Delete nonexistent test suite returns 404."""
    resp = await client.delete(f"{API}/test-suites/suite-nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_404_enable_suite(client):
    """Enable nonexistent suite returns 404."""
    resp = await client.post(f"{API}/test-suites/suite-nonexistent/enable")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_404_disable_suite(client):
    """Disable nonexistent suite returns 404."""
    resp = await client.post(f"{API}/test-suites/suite-nonexistent/disable")
    assert resp.status_code == 404


# ============================================================================
# Validation Errors
# ============================================================================


@pytest.mark.anyio
async def test_validation_create_test_case_missing_name(client):
    """Creating test case without name fails validation."""
    payload = {"suite_type": "SMOKE", "module": "auth"}
    resp = await client.post(f"{API}/test-cases", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_validation_create_test_case_missing_module(client):
    """Creating test case without module fails validation."""
    payload = {"name": "Test", "suite_type": "SMOKE"}
    resp = await client.post(f"{API}/test-cases", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_validation_create_suite_missing_name(client):
    """Creating suite without name fails validation."""
    payload = {"suite_type": "SMOKE"}
    resp = await client.post(f"{API}/test-suites", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_validation_trigger_run_missing_suite_id(client):
    """Triggering run without suite_id fails validation."""
    payload = {}
    resp = await client.post(f"{API}/runs/trigger", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_validation_invalid_suite_type(client):
    """Invalid suite type fails validation."""
    payload = {"name": "Test", "suite_type": "INVALID", "module": "auth"}
    resp = await client.post(f"{API}/test-cases", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_validation_invalid_priority(client):
    """Invalid priority fails validation."""
    payload = {"name": "Test", "suite_type": "SMOKE", "module": "auth", "priority": "INVALID"}
    resp = await client.post(f"{API}/test-cases", json=payload)
    assert resp.status_code == 422


# ============================================================================
# Service direct tests
# ============================================================================


@pytest.mark.anyio
async def test_service_stats(client):
    """Service stats should report correct counts."""
    svc = get_regression_testing_service()
    stats = svc.get_stats()
    assert stats["test_cases"] == 30
    assert stats["test_suites"] == 6
    assert stats["test_runs"] == 10
    assert stats["coverage_entries"] == 8
    assert stats["flaky_reports"] == 5
    assert stats["trend_days"] == 14


@pytest.mark.anyio
async def test_service_reset():
    """Resetting service creates fresh instance."""
    svc1 = get_regression_testing_service()
    assert svc1.get_stats()["test_cases"] == 30
    reset_regression_testing_service()
    svc2 = get_regression_testing_service()
    assert svc2.get_stats()["test_cases"] == 30
    assert svc1 is not svc2


@pytest.mark.anyio
async def test_service_singleton():
    """Service should be a singleton."""
    svc1 = get_regression_testing_service()
    svc2 = get_regression_testing_service()
    assert svc1 is svc2


# ============================================================================
# Additional edge cases
# ============================================================================


@pytest.mark.anyio
async def test_create_and_get_test_case(client):
    """Create then immediately get a test case."""
    payload = {
        "name": "Roundtrip Test",
        "suite_type": "INTEGRATION",
        "module": "fhir_import",
    }
    resp = await client.post(f"{API}/test-cases", json=payload)
    tc_id = resp.json()["id"]
    resp2 = await client.get(f"{API}/test-cases/{tc_id}")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Roundtrip Test"


@pytest.mark.anyio
async def test_create_and_delete_test_suite(client):
    """Create then delete a test suite."""
    payload = {
        "name": "Temp Suite",
        "suite_type": "ACCESSIBILITY",
    }
    resp = await client.post(f"{API}/test-suites", json=payload)
    sid = resp.json()["id"]
    resp2 = await client.delete(f"{API}/test-suites/{sid}")
    assert resp2.status_code == 204
    resp3 = await client.get(f"{API}/test-suites/{sid}")
    assert resp3.status_code == 404


@pytest.mark.anyio
async def test_trigger_run_for_regression_suite(client):
    """Trigger a full regression run."""
    payload = {"suite_id": "suite-regression"}
    resp = await client.post(f"{API}/runs/trigger", json=payload)
    assert resp.status_code == 201
    run = resp.json()
    assert run["total_tests"] == 30
    assert run["pass_rate"] > 0


@pytest.mark.anyio
async def test_trigger_multiple_runs(client):
    """Triggering multiple runs should all succeed."""
    for _ in range(3):
        payload = {"suite_id": "suite-smoke"}
        resp = await client.post(f"{API}/runs/trigger", json=payload)
        assert resp.status_code == 201


@pytest.mark.anyio
async def test_estimated_time_regression(client):
    """Regression suite estimated time calculation."""
    resp = await client.get(f"{API}/suites/suite-regression/estimated-time")
    est = resp.json()
    assert est["test_count"] == 30
    assert est["parallel_minutes"] < est["sequential_minutes"]


@pytest.mark.anyio
async def test_impact_analysis_unknown_module(client):
    """Impact analysis for unknown module returns zero affected."""
    payload = {"changed_modules": ["totally_unknown_module"], "include_dependent": False}
    resp = await client.post(f"{API}/impact-analysis", json=payload)
    assert resp.status_code == 200
    assert resp.json()["affected_test_count"] == 0


@pytest.mark.anyio
async def test_dashboard_after_disable(client):
    """Dashboard reflects disabled suite count."""
    await client.post(f"{API}/test-suites/suite-smoke/disable")
    resp = await client.get(f"{API}/dashboard")
    d = resp.json()
    assert d["suites_disabled"] >= 1
    assert d["suites_enabled"] <= 5


@pytest.mark.anyio
async def test_coverage_overall_is_weighted(client):
    """Overall coverage is weighted by lines, not simple average."""
    resp = await client.get(f"{API}/coverage")
    data = resp.json()
    total_lines = sum(c["total_lines"] for c in data["items"])
    covered_lines = sum(c["covered_lines"] for c in data["items"])
    expected = round(covered_lines / total_lines * 100, 2)
    assert abs(data["overall_coverage"] - expected) < 0.1


@pytest.mark.anyio
async def test_trends_shorter_window(client):
    """Requesting fewer days returns fewer entries."""
    resp = await client.get(f"{API}/trends", params={"days": 3})
    assert resp.json()["total_days"] == 3


@pytest.mark.anyio
async def test_prioritized_order_stable(client):
    """Calling prioritization twice returns same order."""
    resp1 = await client.get(f"{API}/prioritized-tests", params={"limit": 10})
    resp2 = await client.get(f"{API}/prioritized-tests", params={"limit": 10})
    ids1 = [t["id"] for t in resp1.json()["items"]]
    ids2 = [t["id"] for t in resp2.json()["items"]]
    assert ids1 == ids2
