"""Tests for OHDSI DQD API endpoints.

Tests verify:
- POST /data-quality/dqd/run triggers checks and returns results
- GET /data-quality/dqd/results returns summary
- GET /data-quality/dqd/history returns run history
- GET /data-quality/dqd/issues returns filtered issues
"""

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.data_quality import router


def create_test_app():
    """Create a minimal FastAPI app with just the data_quality router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client():
    app = create_test_app()
    return TestClient(app, raise_server_exceptions=False)


def _mock_enum(value):
    """Create a mock enum with .value attribute."""
    m = MagicMock()
    m.value = value
    return m


def _mock_check_result(check_id="chk-001", name="completeness_person_gender", status="passed"):
    """Create a mock DQD check result."""
    result = MagicMock()
    result.check_id = check_id
    result.check_name = name
    result.category = _mock_enum("completeness")
    result.subcategory = _mock_enum("required_fields")
    result.table = _mock_enum("person")
    result.field = "gender_concept_id"
    result.status = _mock_enum(status)
    result.score = 95.0
    result.records_total = 1000
    result.records_passed = 950
    result.records_failed = 50
    result.percent_passed = 95.0
    result.message = "95% of records have valid gender"
    return result


def _mock_category_summary(category="completeness"):
    """Create a mock category summary."""
    cat = MagicMock()
    cat.category = _mock_enum(category)
    cat.score = 92.5
    cat.checks_total = 10
    cat.checks_passed = 9
    cat.checks_failed = 1
    return cat


def _mock_table_summary(table="person"):
    """Create a mock table summary."""
    tbl = MagicMock()
    tbl.table = _mock_enum(table)
    tbl.record_count = 5000
    tbl.score = 88.0
    tbl.completeness_score = 95.0
    tbl.conformance_score = 85.0
    tbl.plausibility_score = 84.0
    tbl.issues_count = 3
    return tbl


def _mock_summary():
    """Create a mock DQD summary."""
    summary = MagicMock()
    summary.overall_score = 90.5
    summary.executed_at = "2026-01-24T10:00:00"
    summary.total_checks = 30
    summary.checks_passed = 27
    summary.checks_failed = 3
    summary.completeness_score = 92.5
    summary.conformance_score = 88.0
    summary.plausibility_score = 91.0
    summary.total_issues = 5
    summary.category_summaries = [
        _mock_category_summary("completeness"),
        _mock_category_summary("conformance"),
        _mock_category_summary("plausibility"),
    ]
    summary.table_summaries = [
        _mock_table_summary("person"),
        _mock_table_summary("visit_occurrence"),
    ]
    return summary


def _mock_run_result():
    """Create a mock DQD run result."""
    result = MagicMock()
    result.run_id = "run-abc123"
    result.started_at = "2026-01-24T10:00:00"
    result.completed_at = "2026-01-24T10:00:05"
    result.duration_ms = 5000.0
    result.summary = _mock_summary()
    result.check_results = [
        _mock_check_result("chk-001", "completeness_person_gender", "passed"),
        _mock_check_result("chk-002", "conformance_gender_valid", "failed"),
    ]
    result.issues = [_mock_issue()]
    return result


def _mock_issue(severity="high"):
    """Create a mock DQD issue."""
    issue = MagicMock()
    issue.issue_id = "iss-001"
    issue.check_id = "chk-002"
    issue.category = _mock_enum("conformance")
    issue.severity = _mock_enum(severity)
    issue.table = _mock_enum("person")
    issue.field = "gender_concept_id"
    issue.description = "Invalid gender concept found"
    issue.current_value = "99999"
    issue.expected_value = "8507, 8532"
    issue.recommendation = "Map to valid OMOP gender concepts"
    return issue


def _mock_history_entry(run_id="run-001"):
    """Create a mock history entry."""
    entry = MagicMock()
    entry.run_id = run_id
    entry.timestamp = "2026-01-24T09:00:00"
    entry.overall_score = 89.0
    entry.completeness_score = 91.0
    entry.conformance_score = 87.0
    entry.plausibility_score = 89.0
    entry.total_checks = 30
    entry.checks_passed = 26
    entry.total_issues = 4
    return entry


class TestRunDQDChecks:
    """Test POST /data-quality/dqd/run endpoint."""

    @patch("app.api.data_quality.get_data_quality_service")
    def test_run_returns_200(self, mock_svc, client):
        svc = MagicMock()
        svc.run_checks.return_value = _mock_run_result()
        mock_svc.return_value = svc

        response = client.post("/data-quality/dqd/run")
        assert response.status_code == 200

    @patch("app.api.data_quality.get_data_quality_service")
    def test_run_returns_run_id(self, mock_svc, client):
        svc = MagicMock()
        svc.run_checks.return_value = _mock_run_result()
        mock_svc.return_value = svc

        data = client.post("/data-quality/dqd/run").json()
        assert data["run_id"] == "run-abc123"

    @patch("app.api.data_quality.get_data_quality_service")
    def test_run_returns_timing(self, mock_svc, client):
        svc = MagicMock()
        svc.run_checks.return_value = _mock_run_result()
        mock_svc.return_value = svc

        data = client.post("/data-quality/dqd/run").json()
        assert data["started_at"] == "2026-01-24T10:00:00"
        assert data["duration_ms"] == 5000.0

    @patch("app.api.data_quality.get_data_quality_service")
    def test_run_returns_check_counts(self, mock_svc, client):
        svc = MagicMock()
        svc.run_checks.return_value = _mock_run_result()
        mock_svc.return_value = svc

        data = client.post("/data-quality/dqd/run").json()
        assert data["total_checks"] == 30
        assert data["checks_passed"] == 27
        assert data["checks_failed"] == 3
        assert data["pass_rate"] == 90.0

    @patch("app.api.data_quality.get_data_quality_service")
    def test_run_returns_check_results(self, mock_svc, client):
        svc = MagicMock()
        svc.run_checks.return_value = _mock_run_result()
        mock_svc.return_value = svc

        data = client.post("/data-quality/dqd/run").json()
        assert len(data["results"]) == 2
        first = data["results"][0]
        assert first["check_id"] == "chk-001"
        assert first["category"] == "completeness"
        assert first["table"] == "person"
        assert first["status"] == "passed"
        assert first["records_total"] == 1000


class TestGetDQDResults:
    """Test GET /data-quality/dqd/results endpoint."""

    @patch("app.api.data_quality.get_data_quality_service")
    def test_results_returns_200(self, mock_svc, client):
        svc = MagicMock()
        svc.get_summary.return_value = _mock_summary()
        mock_svc.return_value = svc

        response = client.get("/data-quality/dqd/results")
        assert response.status_code == 200

    @patch("app.api.data_quality.get_data_quality_service")
    def test_results_overall_score(self, mock_svc, client):
        svc = MagicMock()
        svc.get_summary.return_value = _mock_summary()
        mock_svc.return_value = svc

        data = client.get("/data-quality/dqd/results").json()
        assert data["overall_score"] == 90.5
        assert data["total_checks"] == 30
        assert data["checks_passed"] == 27

    @patch("app.api.data_quality.get_data_quality_service")
    def test_results_category_breakdown(self, mock_svc, client):
        svc = MagicMock()
        svc.get_summary.return_value = _mock_summary()
        mock_svc.return_value = svc

        data = client.get("/data-quality/dqd/results").json()
        assert len(data["categories"]) == 3

    @patch("app.api.data_quality.get_data_quality_service")
    def test_results_table_breakdown(self, mock_svc, client):
        svc = MagicMock()
        svc.get_summary.return_value = _mock_summary()
        mock_svc.return_value = svc

        data = client.get("/data-quality/dqd/results").json()
        assert len(data["tables"]) == 2
        person_table = data["tables"][0]
        assert person_table["table"] == "person"
        assert person_table["record_count"] == 5000


class TestGetDQDHistory:
    """Test GET /data-quality/dqd/history endpoint."""

    @patch("app.api.data_quality.get_data_quality_service")
    def test_history_returns_200(self, mock_svc, client):
        svc = MagicMock()
        svc.get_history.return_value = [_mock_history_entry("run-001")]
        mock_svc.return_value = svc

        response = client.get("/data-quality/dqd/history")
        assert response.status_code == 200

    @patch("app.api.data_quality.get_data_quality_service")
    def test_history_entries(self, mock_svc, client):
        svc = MagicMock()
        svc.get_history.return_value = [
            _mock_history_entry("run-001"),
            _mock_history_entry("run-002"),
        ]
        mock_svc.return_value = svc

        data = client.get("/data-quality/dqd/history").json()
        assert data["total"] == 2
        assert data["entries"][0]["run_id"] == "run-001"

    @patch("app.api.data_quality.get_data_quality_service")
    def test_history_limit_param(self, mock_svc, client):
        svc = MagicMock()
        svc.get_history.return_value = []
        mock_svc.return_value = svc

        client.get("/data-quality/dqd/history", params={"limit": 5})
        svc.get_history.assert_called_once_with(limit=5)


class TestGetDQDIssues:
    """Test GET /data-quality/dqd/issues endpoint."""

    @patch("app.api.data_quality.get_data_quality_service")
    def test_issues_returns_200(self, mock_svc, client):
        svc = MagicMock()
        svc.get_issues.return_value = [_mock_issue()]
        mock_svc.return_value = svc

        response = client.get("/data-quality/dqd/issues")
        assert response.status_code == 200

    @patch("app.api.data_quality.get_data_quality_service")
    def test_issues_content(self, mock_svc, client):
        svc = MagicMock()
        svc.get_issues.return_value = [_mock_issue("critical")]
        mock_svc.return_value = svc

        data = client.get("/data-quality/dqd/issues").json()
        assert data["total"] == 1
        issue = data["issues"][0]
        assert issue["issue_id"] == "iss-001"
        assert issue["severity"] == "critical"
        assert issue["table"] == "person"
        assert issue["description"] == "Invalid gender concept found"

    @patch("app.api.data_quality.get_data_quality_service")
    def test_issues_empty_when_no_run(self, mock_svc, client):
        svc = MagicMock()
        svc.get_issues.return_value = []
        mock_svc.return_value = svc

        data = client.get("/data-quality/dqd/issues").json()
        assert data["total"] == 0
        assert data["issues"] == []

    @patch("app.api.data_quality.get_data_quality_service")
    def test_issues_severity_filter(self, mock_svc, client):
        svc = MagicMock()
        svc.get_issues.return_value = []
        mock_svc.return_value = svc

        client.get("/data-quality/dqd/issues", params={"severity": "critical"})
        call_args = svc.get_issues.call_args
        # severity should be converted to DQDSeverity enum
        assert call_args.kwargs["limit"] == 50
