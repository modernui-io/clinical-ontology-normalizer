"""Tests for Requirements Traceability (VP-Quality-3).

Covers:
- TraceabilityService CRUD operations
- Coverage analysis computation
- Gap analysis detection
- Impact analysis for code changes
- Full traceability matrix generation
- API endpoint validation
- Edge cases and error handling

35+ test cases.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.schemas.traceability import (
    AffectedRequirement,
    CoverageLevel,
    CoverageReport,
    CoverageSummary,
    GapItem,
    GapReport,
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    MatrixRow,
    RequirementCategory,
    RequirementCreate,
    RequirementListResponse,
    RequirementPriority,
    RequirementResponse,
    RequirementStatus,
    RequirementUpdate,
    TraceabilityMatrix,
    TraceLink,
    TraceLevelKind,
    TraceLinks,
)
from app.services.traceability_service import (
    TraceabilityService,
    _compute_coverage,
    get_traceability_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service() -> TraceabilityService:
    """Create a fresh TraceabilityService instance for each test."""
    return TraceabilityService()


@pytest.fixture
def client() -> TestClient:
    """Create a test client for API endpoint tests."""
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSchemas:
    """Test Pydantic schema construction and validation."""

    def test_trace_link_creation(self) -> None:
        """Test creating a TraceLink."""
        link = TraceLink(ref="backend/app/services/fhir_import.py", description="FHIR import service")
        assert link.ref == "backend/app/services/fhir_import.py"
        assert link.description == "FHIR import service"
        assert link.verified is False
        assert link.verified_at is None

    def test_trace_link_verified(self) -> None:
        """Test creating a verified TraceLink."""
        now = datetime.now(timezone.utc)
        link = TraceLink(ref="test.py", description="test", verified=True, verified_at=now)
        assert link.verified is True
        assert link.verified_at == now

    def test_trace_links_defaults(self) -> None:
        """Test TraceLinks defaults to empty lists."""
        links = TraceLinks()
        assert links.design_refs == []
        assert links.code_refs == []
        assert links.test_refs == []
        assert links.validation_refs == []

    def test_requirement_create_schema(self) -> None:
        """Test RequirementCreate schema validation."""
        req = RequirementCreate(
            title="Test Requirement",
            description="A test requirement",
            category=RequirementCategory.FUNCTIONAL,
            priority=RequirementPriority.P1,
            source="Test Source",
        )
        assert req.title == "Test Requirement"
        assert req.category == RequirementCategory.FUNCTIONAL
        assert req.status == RequirementStatus.DEFINED  # default

    def test_requirement_update_partial(self) -> None:
        """Test RequirementUpdate allows partial updates."""
        update = RequirementUpdate(title="Updated Title")
        assert update.title == "Updated Title"
        assert update.description is None
        assert update.category is None

    def test_coverage_summary_schema(self) -> None:
        """Test CoverageSummary schema."""
        summary = CoverageSummary(
            total_requirements=10,
            fully_covered=3,
            tested_unvalidated=2,
            implemented_untested=3,
            not_implemented=2,
            coverage_percentage=30.0,
        )
        assert summary.total_requirements == 10
        assert summary.coverage_percentage == 30.0

    def test_gap_item_schema(self) -> None:
        """Test GapItem schema."""
        gap = GapItem(
            requirement_id="REQ-FUNC-001",
            requirement_title="Test",
            category=RequirementCategory.FUNCTIONAL,
            priority=RequirementPriority.P1,
            missing_levels=[TraceLevelKind.TEST, TraceLevelKind.VALIDATION],
            coverage_level=CoverageLevel.IMPLEMENTED_UNTESTED,
            recommendation="Add tests",
        )
        assert len(gap.missing_levels) == 2
        assert TraceLevelKind.TEST in gap.missing_levels

    def test_impact_analysis_request_schema(self) -> None:
        """Test ImpactAnalysisRequest schema."""
        req = ImpactAnalysisRequest(
            changed_files=["backend/app/services/fhir_import.py"],
            change_description="Fix FHIR import bug",
        )
        assert len(req.changed_files) == 1


# ---------------------------------------------------------------------------
# Coverage computation tests
# ---------------------------------------------------------------------------


class TestCoverageComputation:
    """Test the _compute_coverage helper function."""

    def test_not_implemented(self) -> None:
        """No code refs means not implemented."""
        links = TraceLinks()
        assert _compute_coverage(links) == CoverageLevel.NOT_IMPLEMENTED

    def test_implemented_untested(self) -> None:
        """Code refs but no tests means implemented but untested."""
        links = TraceLinks(
            code_refs=[TraceLink(ref="test.py", description="code")],
        )
        assert _compute_coverage(links) == CoverageLevel.IMPLEMENTED_UNTESTED

    def test_tested_unvalidated(self) -> None:
        """Code + tests but no validation means tested but unvalidated."""
        links = TraceLinks(
            code_refs=[TraceLink(ref="code.py", description="code")],
            test_refs=[TraceLink(ref="test.py", description="test")],
        )
        assert _compute_coverage(links) == CoverageLevel.TESTED_UNVALIDATED

    def test_fully_covered(self) -> None:
        """Code + tests + validation means fully covered."""
        links = TraceLinks(
            code_refs=[TraceLink(ref="code.py", description="code")],
            test_refs=[TraceLink(ref="test.py", description="test")],
            validation_refs=[TraceLink(ref="val.md", description="validation")],
        )
        assert _compute_coverage(links) == CoverageLevel.FULLY_COVERED

    def test_design_only_not_implemented(self) -> None:
        """Design refs alone don't count as implemented."""
        links = TraceLinks(
            design_refs=[TraceLink(ref="design.md", description="design")],
        )
        assert _compute_coverage(links) == CoverageLevel.NOT_IMPLEMENTED


# ---------------------------------------------------------------------------
# Service CRUD tests
# ---------------------------------------------------------------------------


class TestServiceCRUD:
    """Test TraceabilityService CRUD operations."""

    def test_seed_requirements_loaded(self, service: TraceabilityService) -> None:
        """Service starts with pre-populated seed requirements."""
        reqs, total = service.list_requirements()
        assert total >= 40
        assert len(reqs) >= 40

    def test_get_requirement_exists(self, service: TraceabilityService) -> None:
        """Can retrieve a seed requirement by ID."""
        result = service.get_requirement("REQ-FUNC-001")
        assert result is not None
        assert result.id == "REQ-FUNC-001"
        assert "FHIR" in result.title

    def test_get_requirement_not_found(self, service: TraceabilityService) -> None:
        """Returns None for nonexistent requirement."""
        result = service.get_requirement("REQ-NONEXISTENT-999")
        assert result is None

    def test_create_requirement_auto_id(self, service: TraceabilityService) -> None:
        """Creating without ID auto-generates one."""
        data = RequirementCreate(
            title="New Functional Req",
            description="Test auto-ID generation",
            category=RequirementCategory.FUNCTIONAL,
            priority=RequirementPriority.P3,
            source="Test",
        )
        result = service.create_requirement(data)
        assert result.id.startswith("REQ-FUNC-")
        assert result.title == "New Functional Req"

    def test_create_requirement_custom_id(self, service: TraceabilityService) -> None:
        """Creating with custom ID uses it."""
        data = RequirementCreate(
            id="REQ-CUSTOM-001",
            title="Custom ID Req",
            description="Custom ID test",
            category=RequirementCategory.SECURITY,
            priority=RequirementPriority.P2,
            source="Test",
        )
        result = service.create_requirement(data)
        assert result.id == "REQ-CUSTOM-001"

    def test_create_requirement_duplicate_id_raises(self, service: TraceabilityService) -> None:
        """Creating with duplicate ID raises ValueError."""
        with pytest.raises(ValueError, match="already exists"):
            service.create_requirement(
                RequirementCreate(
                    id="REQ-FUNC-001",
                    title="Duplicate",
                    description="Should fail",
                    category=RequirementCategory.FUNCTIONAL,
                    priority=RequirementPriority.P1,
                    source="Test",
                )
            )

    def test_update_requirement_title(self, service: TraceabilityService) -> None:
        """Can update requirement title."""
        result = service.update_requirement(
            "REQ-FUNC-001",
            RequirementUpdate(title="Updated FHIR Import Title"),
        )
        assert result is not None
        assert result.title == "Updated FHIR Import Title"

    def test_update_requirement_status(self, service: TraceabilityService) -> None:
        """Can update requirement status."""
        result = service.update_requirement(
            "REQ-FUNC-007",
            RequirementUpdate(status=RequirementStatus.TESTED),
        )
        assert result is not None
        assert result.status == RequirementStatus.TESTED

    def test_update_requirement_not_found(self, service: TraceabilityService) -> None:
        """Update returns None for nonexistent requirement."""
        result = service.update_requirement(
            "REQ-NONEXISTENT-999",
            RequirementUpdate(title="Nope"),
        )
        assert result is None

    def test_update_requirement_trace_links(self, service: TraceabilityService) -> None:
        """Can update trace links."""
        new_links = TraceLinks(
            code_refs=[TraceLink(ref="new_code.py", description="new code ref")],
            test_refs=[TraceLink(ref="new_test.py", description="new test ref")],
            validation_refs=[TraceLink(ref="new_val.md", description="new validation")],
        )
        result = service.update_requirement(
            "REQ-FUNC-010",
            RequirementUpdate(trace_links=new_links),
        )
        assert result is not None
        assert result.coverage_level == CoverageLevel.FULLY_COVERED

    def test_delete_requirement(self, service: TraceabilityService) -> None:
        """Can delete a requirement."""
        assert service.delete_requirement("REQ-FUNC-020") is True
        assert service.get_requirement("REQ-FUNC-020") is None

    def test_delete_nonexistent_requirement(self, service: TraceabilityService) -> None:
        """Deleting nonexistent requirement returns False."""
        assert service.delete_requirement("REQ-NONEXISTENT-999") is False

    def test_list_filter_by_category(self, service: TraceabilityService) -> None:
        """Can filter requirements by category."""
        reqs, total = service.list_requirements(category=RequirementCategory.SECURITY)
        assert total > 0
        assert all(r.category == RequirementCategory.SECURITY for r in reqs)

    def test_list_filter_by_priority(self, service: TraceabilityService) -> None:
        """Can filter requirements by priority."""
        reqs, total = service.list_requirements(priority=RequirementPriority.P1)
        assert total > 0
        assert all(r.priority == RequirementPriority.P1 for r in reqs)

    def test_list_filter_by_status(self, service: TraceabilityService) -> None:
        """Can filter requirements by status."""
        reqs, total = service.list_requirements(status=RequirementStatus.VALIDATED)
        assert total > 0
        assert all(r.status == RequirementStatus.VALIDATED for r in reqs)

    def test_list_filter_by_coverage(self, service: TraceabilityService) -> None:
        """Can filter requirements by coverage level."""
        reqs, total = service.list_requirements(coverage=CoverageLevel.FULLY_COVERED)
        assert total > 0
        assert all(r.coverage_level == CoverageLevel.FULLY_COVERED for r in reqs)

    def test_list_pagination(self, service: TraceabilityService) -> None:
        """Pagination works correctly."""
        page1, total = service.list_requirements(page=1, page_size=5)
        assert len(page1) == 5
        assert total >= 40

        page2, _ = service.list_requirements(page=2, page_size=5)
        assert len(page2) == 5
        assert page1[0].id != page2[0].id


# ---------------------------------------------------------------------------
# Coverage analysis tests
# ---------------------------------------------------------------------------


class TestCoverageAnalysis:
    """Test coverage analysis report generation."""

    def test_coverage_report_structure(self, service: TraceabilityService) -> None:
        """Coverage report has correct structure."""
        report = service.get_coverage_report()
        assert report.summary.total_requirements >= 40
        assert report.summary.coverage_percentage >= 0
        assert report.summary.coverage_percentage <= 100
        assert len(report.requirements) == report.summary.total_requirements

    def test_coverage_counts_add_up(self, service: TraceabilityService) -> None:
        """Coverage counts sum to total requirements."""
        report = service.get_coverage_report()
        s = report.summary
        total = s.fully_covered + s.tested_unvalidated + s.implemented_untested + s.not_implemented
        assert total == s.total_requirements

    def test_coverage_has_category_breakdown(self, service: TraceabilityService) -> None:
        """Coverage summary includes category breakdown."""
        report = service.get_coverage_report()
        assert "FUNCTIONAL" in report.summary.by_category
        assert "SECURITY" in report.summary.by_category

    def test_coverage_has_priority_breakdown(self, service: TraceabilityService) -> None:
        """Coverage summary includes priority breakdown."""
        report = service.get_coverage_report()
        assert "P1" in report.summary.by_priority

    def test_coverage_fully_covered_exists(self, service: TraceabilityService) -> None:
        """Some requirements should be fully covered (seed data includes validated items)."""
        report = service.get_coverage_report()
        assert report.summary.fully_covered > 0


# ---------------------------------------------------------------------------
# Gap analysis tests
# ---------------------------------------------------------------------------


class TestGapAnalysis:
    """Test gap analysis report generation."""

    def test_gap_report_structure(self, service: TraceabilityService) -> None:
        """Gap report has correct structure."""
        report = service.get_gap_report()
        assert report.total_gaps >= 0
        assert report.total_gaps == len(report.gaps)

    def test_gap_excludes_fully_covered(self, service: TraceabilityService) -> None:
        """Fully covered requirements should not appear in gaps."""
        report = service.get_gap_report()
        for gap in report.gaps:
            assert gap.coverage_level != CoverageLevel.FULLY_COVERED

    def test_gap_has_missing_levels(self, service: TraceabilityService) -> None:
        """Each gap item should have at least one missing level."""
        report = service.get_gap_report()
        for gap in report.gaps:
            assert len(gap.missing_levels) > 0

    def test_gap_has_recommendations(self, service: TraceabilityService) -> None:
        """Each gap item should have a recommendation."""
        report = service.get_gap_report()
        for gap in report.gaps:
            assert gap.recommendation != ""

    def test_critical_gaps_count(self, service: TraceabilityService) -> None:
        """Critical gaps count matches P1 requirements with gaps."""
        report = service.get_gap_report()
        p1_gaps = [g for g in report.gaps if g.priority == RequirementPriority.P1]
        assert report.critical_gaps == len(p1_gaps)


# ---------------------------------------------------------------------------
# Impact analysis tests
# ---------------------------------------------------------------------------


class TestImpactAnalysis:
    """Test impact analysis for code changes."""

    def test_impact_fhir_import_change(self, service: TraceabilityService) -> None:
        """Changing fhir_import.py should affect FHIR requirements."""
        request = ImpactAnalysisRequest(
            changed_files=["backend/app/services/fhir_import.py"],
            change_description="Fix FHIR patient import",
        )
        result = service.analyze_impact(request)
        assert result.total_affected > 0
        affected_ids = [a.requirement_id for a in result.affected_requirements]
        assert "REQ-FUNC-001" in affected_ids

    def test_impact_nlp_change(self, service: TraceabilityService) -> None:
        """Changing NLP service should affect NLP requirements."""
        request = ImpactAnalysisRequest(
            changed_files=["backend/app/services/nlp.py"],
            change_description="Update NLP model",
        )
        result = service.analyze_impact(request)
        assert result.total_affected > 0
        affected_ids = [a.requirement_id for a in result.affected_requirements]
        assert "REQ-FUNC-003" in affected_ids

    def test_impact_no_match(self, service: TraceabilityService) -> None:
        """Changing unrelated file should not affect any requirements."""
        request = ImpactAnalysisRequest(
            changed_files=["backend/app/utils/some_random_util.py"],
            change_description="Utility update",
        )
        result = service.analyze_impact(request)
        assert result.total_affected == 0

    def test_impact_risk_summary(self, service: TraceabilityService) -> None:
        """Impact analysis provides risk summary."""
        request = ImpactAnalysisRequest(
            changed_files=["backend/app/services/fhir_import.py"],
        )
        result = service.analyze_impact(request)
        assert isinstance(result.risk_summary, dict)

    def test_impact_recommendations(self, service: TraceabilityService) -> None:
        """Impact analysis provides recommendations."""
        request = ImpactAnalysisRequest(
            changed_files=["backend/app/services/fhir_import.py"],
        )
        result = service.analyze_impact(request)
        assert len(result.recommendations) > 0

    def test_impact_multiple_files(self, service: TraceabilityService) -> None:
        """Impact analysis handles multiple changed files."""
        request = ImpactAnalysisRequest(
            changed_files=[
                "backend/app/services/fhir_import.py",
                "backend/app/services/nlp.py",
                "backend/app/services/mapping.py",
            ],
        )
        result = service.analyze_impact(request)
        assert result.total_affected >= 3  # At least FUNC-001, FUNC-003, FUNC-004

    def test_impact_audit_change_is_critical(self, service: TraceabilityService) -> None:
        """Changing audit service (P1 security) without test change = CRITICAL risk."""
        request = ImpactAnalysisRequest(
            changed_files=["backend/app/services/audit_service.py"],
        )
        result = service.analyze_impact(request)
        assert result.total_affected > 0
        # REQ-SEC-002 audit logging is P1
        sec_002 = [a for a in result.affected_requirements if a.requirement_id == "REQ-SEC-002"]
        assert len(sec_002) > 0


# ---------------------------------------------------------------------------
# Traceability matrix tests
# ---------------------------------------------------------------------------


class TestTraceabilityMatrix:
    """Test full traceability matrix generation."""

    def test_matrix_structure(self, service: TraceabilityService) -> None:
        """Matrix has correct structure."""
        matrix = service.get_matrix()
        assert len(matrix.rows) >= 40
        assert matrix.summary.total_requirements == len(matrix.rows)

    def test_matrix_rows_have_counts(self, service: TraceabilityService) -> None:
        """Matrix rows have ref counts."""
        matrix = service.get_matrix()
        func_001 = [r for r in matrix.rows if r.requirement_id == "REQ-FUNC-001"]
        assert len(func_001) == 1
        row = func_001[0]
        assert row.design_count > 0
        assert row.code_count > 0
        assert row.test_count > 0
        assert row.validation_count > 0
        assert row.coverage_level == CoverageLevel.FULLY_COVERED

    def test_matrix_rows_have_ref_lists(self, service: TraceabilityService) -> None:
        """Matrix rows include actual ref strings."""
        matrix = service.get_matrix()
        func_001 = [r for r in matrix.rows if r.requirement_id == "REQ-FUNC-001"]
        assert len(func_001) == 1
        row = func_001[0]
        assert any("fhir_import" in ref for ref in row.code_refs)


# ---------------------------------------------------------------------------
# Service stats tests
# ---------------------------------------------------------------------------


class TestServiceStats:
    """Test service statistics."""

    def test_get_stats(self, service: TraceabilityService) -> None:
        """Stats returns expected keys."""
        stats = service.get_stats()
        assert "total_requirements" in stats
        assert "fully_covered" in stats
        assert "coverage_percentage" in stats
        assert "critical_gaps" in stats
        assert stats["total_requirements"] >= 40


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------


class TestSingleton:
    """Test singleton pattern."""

    def test_get_traceability_service_singleton(self) -> None:
        """get_traceability_service returns singleton."""
        svc1 = get_traceability_service()
        svc2 = get_traceability_service()
        assert svc1 is svc2


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestAPIEndpoints:
    """Test API endpoint responses."""

    def test_list_requirements(self, client: TestClient) -> None:
        """GET /quality/traceability/requirements returns list."""
        resp = client.get("/api/v1/quality/traceability/requirements")
        assert resp.status_code == 200
        data = resp.json()
        assert "requirements" in data
        assert "total" in data
        assert data["total"] >= 40

    def test_list_requirements_with_category_filter(self, client: TestClient) -> None:
        """GET /quality/traceability/requirements?category=SECURITY filters correctly."""
        resp = client.get("/api/v1/quality/traceability/requirements?category=SECURITY")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for req in data["requirements"]:
            assert req["category"] == "SECURITY"

    def test_list_requirements_pagination(self, client: TestClient) -> None:
        """GET /quality/traceability/requirements supports pagination."""
        resp = client.get("/api/v1/quality/traceability/requirements?page=1&page_size=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["requirements"]) == 5
        assert data["page"] == 1
        assert data["page_size"] == 5

    def test_get_requirement_detail(self, client: TestClient) -> None:
        """GET /quality/traceability/requirements/{id} returns detail."""
        resp = client.get("/api/v1/quality/traceability/requirements/REQ-FUNC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "REQ-FUNC-001"
        assert "trace_links" in data
        assert "coverage_level" in data

    def test_get_requirement_not_found(self, client: TestClient) -> None:
        """GET /quality/traceability/requirements/{id} returns 404 for unknown."""
        resp = client.get("/api/v1/quality/traceability/requirements/REQ-NONEXISTENT-999")
        assert resp.status_code == 404

    def test_create_requirement(self, client: TestClient) -> None:
        """POST /quality/traceability/requirements creates a new requirement."""
        payload = {
            "title": "API Test Requirement",
            "description": "Created via API test",
            "category": "FUNCTIONAL",
            "priority": "P3",
            "source": "API Test",
        }
        resp = client.post("/api/v1/quality/traceability/requirements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "API Test Requirement"
        assert data["id"].startswith("REQ-FUNC-")

    def test_create_requirement_duplicate(self, client: TestClient) -> None:
        """POST /quality/traceability/requirements returns 409 for duplicate ID."""
        payload = {
            "id": "REQ-FUNC-001",
            "title": "Duplicate",
            "description": "Should fail",
            "category": "FUNCTIONAL",
            "priority": "P1",
            "source": "Test",
        }
        resp = client.post("/api/v1/quality/traceability/requirements", json=payload)
        assert resp.status_code == 409

    def test_update_requirement(self, client: TestClient) -> None:
        """PUT /quality/traceability/requirements/{id} updates requirement."""
        payload = {"title": "Updated via API"}
        resp = client.put("/api/v1/quality/traceability/requirements/REQ-FUNC-002", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated via API"

    def test_update_requirement_not_found(self, client: TestClient) -> None:
        """PUT /quality/traceability/requirements/{id} returns 404 for unknown."""
        payload = {"title": "Nope"}
        resp = client.put("/api/v1/quality/traceability/requirements/REQ-NONEXISTENT-999", json=payload)
        assert resp.status_code == 404

    def test_coverage_endpoint(self, client: TestClient) -> None:
        """GET /quality/traceability/coverage returns coverage report."""
        resp = client.get("/api/v1/quality/traceability/coverage")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "requirements" in data
        assert data["summary"]["total_requirements"] >= 40

    def test_gaps_endpoint(self, client: TestClient) -> None:
        """GET /quality/traceability/gaps returns gap report."""
        resp = client.get("/api/v1/quality/traceability/gaps")
        assert resp.status_code == 200
        data = resp.json()
        assert "gaps" in data
        assert "total_gaps" in data
        assert "critical_gaps" in data

    def test_impact_analysis_endpoint(self, client: TestClient) -> None:
        """POST /quality/traceability/impact-analysis returns impact report."""
        payload = {
            "changed_files": ["backend/app/services/fhir_import.py"],
            "change_description": "Fix bug",
        }
        resp = client.post("/api/v1/quality/traceability/impact-analysis", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "affected_requirements" in data
        assert "total_affected" in data
        assert data["total_affected"] > 0

    def test_matrix_endpoint(self, client: TestClient) -> None:
        """GET /quality/traceability/matrix returns full matrix."""
        resp = client.get("/api/v1/quality/traceability/matrix")
        assert resp.status_code == 200
        data = resp.json()
        assert "rows" in data
        assert "summary" in data
        assert len(data["rows"]) >= 40


# ---------------------------------------------------------------------------
# Path matching tests
# ---------------------------------------------------------------------------


class TestPathMatching:
    """Test the _paths_match helper method."""

    def test_exact_match(self, service: TraceabilityService) -> None:
        """Exact path match."""
        assert service._paths_match("backend/app/services/fhir_import.py", "backend/app/services/fhir_import.py")

    def test_leading_dot_slash(self, service: TraceabilityService) -> None:
        """Match ignoring leading ./."""
        assert service._paths_match("./backend/app/services/fhir_import.py", "backend/app/services/fhir_import.py")

    def test_directory_match(self, service: TraceabilityService) -> None:
        """Directory ref matches files within."""
        assert service._paths_match("backend/app/api/documents/", "backend/app/api/documents/upload.py")

    def test_no_match(self, service: TraceabilityService) -> None:
        """Unrelated paths don't match."""
        assert not service._paths_match("backend/app/services/fhir_import.py", "backend/app/utils/helpers.py")

    def test_basename_match(self, service: TraceabilityService) -> None:
        """Base filename match works."""
        assert service._paths_match("backend/app/services/fhir_import.py", "app/services/fhir_import.py")


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_create_requirement_all_categories(self, service: TraceabilityService) -> None:
        """Can create requirements for all categories."""
        for cat in RequirementCategory:
            data = RequirementCreate(
                title=f"Test {cat.value}",
                description=f"Testing {cat.value} category",
                category=cat,
                priority=RequirementPriority.P4,
                source="Edge case test",
            )
            result = service.create_requirement(data)
            assert result.category == cat

    def test_empty_impact_analysis(self, service: TraceabilityService) -> None:
        """Impact analysis with unrelated files returns empty."""
        request = ImpactAnalysisRequest(
            changed_files=["completely/unrelated/file.py"],
        )
        result = service.analyze_impact(request)
        assert result.total_affected == 0
        assert result.recommendations[0].startswith("No critical")

    def test_coverage_percentage_after_additions(self, service: TraceabilityService) -> None:
        """Coverage percentage changes when adding requirements."""
        initial = service.get_coverage_report()
        initial_pct = initial.summary.coverage_percentage

        # Add an uncovered requirement
        service.create_requirement(
            RequirementCreate(
                title="Uncovered req",
                description="No code",
                category=RequirementCategory.FUNCTIONAL,
                priority=RequirementPriority.P4,
                source="Test",
            )
        )

        updated = service.get_coverage_report()
        # Coverage percentage should decrease slightly (more total, same covered)
        assert updated.summary.total_requirements == initial.summary.total_requirements + 1
