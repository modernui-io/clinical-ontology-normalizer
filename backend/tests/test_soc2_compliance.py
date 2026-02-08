"""Tests for SOC 2 Gap Analysis (CISO-12).

Tests verify:
- Pre-populated controls correctness (40+ controls)
- All 5 Trust Service Categories represented
- Control CRUD operations
- Status transitions (NOT_IMPLEMENTED -> PARTIAL -> IMPLEMENTED)
- Invalid status transitions rejected
- Evidence attachment and retrieval
- Gap report generation with executive summary
- Readiness score calculation per category
- Remediation plan prioritization (P1 > P2 > P3)
- Filter controls by status and category
- Update control evidence and remediation plan
- Overall readiness percentage calculation
- Category-level gap summaries
- Evidence collection metadata
- API endpoint integration tests
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.soc2_compliance import router as soc2_compliance_router
from app.schemas.soc2_compliance import (
    CategoryGapSummary,
    CategoryReadiness,
    ControlStatus,
    EvidenceAttachment,
    EvidenceCreate,
    EvidenceType,
    GapReport,
    ReadinessScore,
    RemediationItem,
    RemediationPlan,
    RemediationPriority,
    SOC2Control,
    SOC2ControlUpdate,
    TrustServiceCategory,
)
from app.services.soc2_service import (
    CATEGORY_NAMES,
    SOC2ComplianceService,
    VALID_STATUS_TRANSITIONS,
    get_soc2_service,
    reset_soc2_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons between tests."""
    reset_soc2_service()
    yield
    reset_soc2_service()


@pytest.fixture
def service() -> SOC2ComplianceService:
    """Get a fresh SOC2ComplianceService instance."""
    return get_soc2_service()


@pytest.fixture
def client() -> TestClient:
    """Create test client with SOC 2 compliance router."""
    app = FastAPI()
    app.include_router(soc2_compliance_router)
    return TestClient(app)


# ===========================================================================
# 1. Pre-populated Controls Tests
# ===========================================================================


class TestPrepopulatedControls:
    """Tests for pre-populated SOC 2 controls."""

    def test_controls_loaded(self, service: SOC2ComplianceService):
        """Controls are loaded on initialization."""
        controls = service.get_all_controls()
        assert len(controls) >= 40, f"Expected 40+ controls, got {len(controls)}"

    def test_all_five_categories_represented(self, service: SOC2ComplianceService):
        """All 5 Trust Service Categories have at least one control."""
        controls = service.get_all_controls()
        categories = {c.category for c in controls}
        assert TrustServiceCategory.CC in categories
        assert TrustServiceCategory.A in categories
        assert TrustServiceCategory.PI in categories
        assert TrustServiceCategory.C in categories
        assert TrustServiceCategory.P in categories

    def test_cc_category_has_most_controls(self, service: SOC2ComplianceService):
        """CC (Security) category has the most controls."""
        cc_controls = service.get_all_controls(category=TrustServiceCategory.CC)
        a_controls = service.get_all_controls(category=TrustServiceCategory.A)
        assert len(cc_controls) > len(a_controls)

    def test_controls_have_required_fields(self, service: SOC2ComplianceService):
        """All controls have required fields populated."""
        for control in service.get_all_controls():
            assert control.id, f"Control missing ID"
            assert control.category, f"Control {control.id} missing category"
            assert control.criterion, f"Control {control.id} missing criterion"
            assert control.title, f"Control {control.id} missing title"
            assert control.description, f"Control {control.id} missing description"
            assert control.status in ControlStatus

    def test_controls_sorted_by_id(self, service: SOC2ComplianceService):
        """Controls are returned sorted by ID."""
        controls = service.get_all_controls()
        ids = [c.id for c in controls]
        assert ids == sorted(ids)

    def test_implemented_controls_have_file_reference(
        self, service: SOC2ComplianceService
    ):
        """Implemented controls reference a platform feature or file."""
        for control in service.get_all_controls():
            if control.status == ControlStatus.IMPLEMENTED:
                assert control.file_reference or control.platform_control, (
                    f"Implemented control {control.id} missing file/platform reference"
                )

    def test_gap_controls_have_remediation_plan(
        self, service: SOC2ComplianceService
    ):
        """NOT_IMPLEMENTED and PARTIAL controls have remediation plans."""
        for control in service.get_all_controls():
            if control.status in (
                ControlStatus.NOT_IMPLEMENTED,
                ControlStatus.PARTIAL,
            ):
                assert control.remediation_plan, (
                    f"Gap control {control.id} ({control.status.value}) "
                    f"missing remediation plan"
                )

    def test_unique_control_ids(self, service: SOC2ComplianceService):
        """All control IDs are unique."""
        controls = service.get_all_controls()
        ids = [c.id for c in controls]
        assert len(ids) == len(set(ids)), "Duplicate control IDs found"


# ===========================================================================
# 2. Control CRUD Tests
# ===========================================================================


class TestControlCRUD:
    """Tests for control get/update operations."""

    def test_get_control_by_id(self, service: SOC2ComplianceService):
        """Get a specific control by ID."""
        control = service.get_control("CC1.1")
        assert control is not None
        assert control.id == "CC1.1"
        assert control.category == TrustServiceCategory.CC

    def test_get_nonexistent_control(self, service: SOC2ComplianceService):
        """Getting nonexistent control returns None."""
        control = service.get_control("NONEXISTENT")
        assert control is None

    def test_update_control_status(self, service: SOC2ComplianceService):
        """Update a control's status."""
        # C1.2 is NOT_IMPLEMENTED -> can go to PARTIAL
        update = SOC2ControlUpdate(status=ControlStatus.PARTIAL)
        updated = service.update_control("C1.2", update)
        assert updated is not None
        assert updated.status == ControlStatus.PARTIAL

    def test_update_control_remediation(self, service: SOC2ComplianceService):
        """Update a control's remediation plan."""
        update = SOC2ControlUpdate(
            remediation_plan="New remediation plan",
            effort_hours=100,
        )
        updated = service.update_control("CC1.1", update)
        assert updated is not None
        assert updated.remediation_plan == "New remediation plan"
        assert updated.effort_hours == 100

    def test_update_control_sets_assessed_timestamp(
        self, service: SOC2ComplianceService
    ):
        """Updating a control sets last_assessed timestamp."""
        update = SOC2ControlUpdate(notes="Updated during test")
        updated = service.update_control("CC1.1", update)
        assert updated is not None
        assert updated.last_assessed is not None

    def test_update_nonexistent_control(self, service: SOC2ComplianceService):
        """Updating nonexistent control returns None."""
        update = SOC2ControlUpdate(status=ControlStatus.IMPLEMENTED)
        result = service.update_control("NONEXISTENT", update)
        assert result is None


# ===========================================================================
# 3. Status Transition Tests
# ===========================================================================


class TestStatusTransitions:
    """Tests for valid and invalid status transitions."""

    def test_not_implemented_to_partial(self, service: SOC2ComplianceService):
        """NOT_IMPLEMENTED -> PARTIAL is valid."""
        update = SOC2ControlUpdate(status=ControlStatus.PARTIAL)
        updated = service.update_control("C1.2", update)
        assert updated is not None
        assert updated.status == ControlStatus.PARTIAL

    def test_not_implemented_to_implemented(self, service: SOC2ComplianceService):
        """NOT_IMPLEMENTED -> IMPLEMENTED is valid."""
        update = SOC2ControlUpdate(status=ControlStatus.IMPLEMENTED)
        updated = service.update_control("C1.2", update)
        assert updated is not None
        assert updated.status == ControlStatus.IMPLEMENTED

    def test_not_implemented_to_not_applicable(
        self, service: SOC2ComplianceService
    ):
        """NOT_IMPLEMENTED -> NOT_APPLICABLE is valid."""
        update = SOC2ControlUpdate(status=ControlStatus.NOT_APPLICABLE)
        updated = service.update_control("C1.2", update)
        assert updated is not None
        assert updated.status == ControlStatus.NOT_APPLICABLE

    def test_partial_to_implemented(self, service: SOC2ComplianceService):
        """PARTIAL -> IMPLEMENTED is valid."""
        # CC1.2 is PARTIAL
        update = SOC2ControlUpdate(status=ControlStatus.IMPLEMENTED)
        updated = service.update_control("CC1.2", update)
        assert updated is not None
        assert updated.status == ControlStatus.IMPLEMENTED

    def test_partial_to_not_implemented(self, service: SOC2ComplianceService):
        """PARTIAL -> NOT_IMPLEMENTED is valid (regression)."""
        update = SOC2ControlUpdate(status=ControlStatus.NOT_IMPLEMENTED)
        updated = service.update_control("CC1.2", update)
        assert updated is not None
        assert updated.status == ControlStatus.NOT_IMPLEMENTED

    def test_implemented_to_partial(self, service: SOC2ComplianceService):
        """IMPLEMENTED -> PARTIAL is valid (regression)."""
        update = SOC2ControlUpdate(status=ControlStatus.PARTIAL)
        updated = service.update_control("CC1.1", update)
        assert updated is not None
        assert updated.status == ControlStatus.PARTIAL

    def test_invalid_implemented_to_not_implemented(
        self, service: SOC2ComplianceService
    ):
        """IMPLEMENTED -> NOT_IMPLEMENTED is invalid."""
        update = SOC2ControlUpdate(status=ControlStatus.NOT_IMPLEMENTED)
        with pytest.raises(ValueError, match="Invalid status transition"):
            service.update_control("CC1.1", update)

    def test_invalid_implemented_to_not_applicable(
        self, service: SOC2ComplianceService
    ):
        """IMPLEMENTED -> NOT_APPLICABLE is invalid."""
        update = SOC2ControlUpdate(status=ControlStatus.NOT_APPLICABLE)
        with pytest.raises(ValueError, match="Invalid status transition"):
            service.update_control("CC1.1", update)

    def test_same_status_is_noop(self, service: SOC2ComplianceService):
        """Updating to the same status is allowed (no-op)."""
        update = SOC2ControlUpdate(status=ControlStatus.IMPLEMENTED)
        updated = service.update_control("CC1.1", update)
        assert updated is not None
        assert updated.status == ControlStatus.IMPLEMENTED

    def test_valid_transitions_cover_all_statuses(self):
        """All ControlStatus values have entries in valid transitions."""
        for status in ControlStatus:
            assert status in VALID_STATUS_TRANSITIONS


# ===========================================================================
# 4. Evidence Tests
# ===========================================================================


class TestEvidence:
    """Tests for evidence attachment and retrieval."""

    def test_attach_evidence(self, service: SOC2ComplianceService):
        """Attach evidence to a control."""
        evidence = EvidenceCreate(
            control_id="CC1.1",
            evidence_type=EvidenceType.DOCUMENT,
            title="Security Policy Document",
            description="Annual security policy review",
            file_reference="docs/security/policy.pdf",
        )
        attachment = service.attach_evidence(evidence)
        assert attachment.id.startswith("EVD-")
        assert attachment.control_id == "CC1.1"
        assert attachment.evidence_type == EvidenceType.DOCUMENT
        assert attachment.title == "Security Policy Document"

    def test_get_evidence_for_control(self, service: SOC2ComplianceService):
        """Retrieve evidence attached to a control."""
        evidence = EvidenceCreate(
            control_id="CC1.1",
            evidence_type=EvidenceType.TEST,
            title="Unit test results",
            file_reference="test_results.xml",
        )
        service.attach_evidence(evidence)
        attachments = service.get_evidence("CC1.1")
        assert len(attachments) >= 1
        assert any(a.title == "Unit test results" for a in attachments)

    def test_attach_multiple_evidence(self, service: SOC2ComplianceService):
        """Attach multiple pieces of evidence to one control."""
        for i in range(3):
            service.attach_evidence(
                EvidenceCreate(
                    control_id="CC5.1",
                    evidence_type=EvidenceType.CODE,
                    title=f"RBAC test {i}",
                    file_reference=f"tests/test_rbac_{i}.py",
                )
            )
        attachments = service.get_evidence("CC5.1")
        assert len(attachments) == 3

    def test_evidence_reflected_in_control(self, service: SOC2ComplianceService):
        """Attached evidence appears in control's evidence list."""
        service.attach_evidence(
            EvidenceCreate(
                control_id="A1.1",
                evidence_type=EvidenceType.DOCUMENT,
                title="DR Plan Review",
                file_reference="docs/dr_plan.pdf",
            )
        )
        control = service.get_control("A1.1")
        assert control is not None
        assert len(control.evidence) >= 1
        assert any(e.title == "DR Plan Review" for e in control.evidence)

    def test_attach_evidence_nonexistent_control(
        self, service: SOC2ComplianceService
    ):
        """Attaching evidence to nonexistent control raises ValueError."""
        evidence = EvidenceCreate(
            control_id="NONEXISTENT",
            evidence_type=EvidenceType.DOCUMENT,
            title="Test",
            file_reference="test.pdf",
        )
        with pytest.raises(ValueError, match="not found"):
            service.attach_evidence(evidence)

    def test_get_evidence_empty(self, service: SOC2ComplianceService):
        """Get evidence for control with no attachments."""
        attachments = service.get_evidence("CC1.1")
        assert isinstance(attachments, list)
        # Initially no evidence (pre-populated controls start with empty evidence)
        assert len(attachments) == 0

    def test_evidence_has_collected_at(self, service: SOC2ComplianceService):
        """Evidence has collected_at timestamp."""
        attachment = service.attach_evidence(
            EvidenceCreate(
                control_id="CC1.1",
                evidence_type=EvidenceType.LOG,
                title="Audit log",
                file_reference="logs/audit.log",
            )
        )
        assert attachment.collected_at is not None
        assert isinstance(attachment.collected_at, datetime)


# ===========================================================================
# 5. Readiness Score Tests
# ===========================================================================


class TestReadinessScores:
    """Tests for readiness score calculation."""

    def test_readiness_scores_structure(self, service: SOC2ComplianceService):
        """Readiness scores have correct structure."""
        scores = service.get_readiness_scores()
        assert isinstance(scores, ReadinessScore)
        assert scores.overall_percentage >= 0
        assert scores.overall_percentage <= 100
        assert len(scores.categories) == 5  # All 5 TSC

    def test_readiness_per_category(self, service: SOC2ComplianceService):
        """Each category has a readiness score."""
        scores = service.get_readiness_scores()
        categories_found = {cs.category for cs in scores.categories}
        for cat in TrustServiceCategory:
            assert cat in categories_found

    def test_pi_category_fully_implemented(self, service: SOC2ComplianceService):
        """Processing Integrity should be 100% (all controls implemented)."""
        scores = service.get_readiness_scores()
        pi_score = next(
            cs for cs in scores.categories if cs.category == TrustServiceCategory.PI
        )
        assert pi_score.readiness_percentage == 100.0
        assert pi_score.not_implemented == 0
        assert pi_score.partial == 0

    def test_readiness_totals_match(self, service: SOC2ComplianceService):
        """Total counts should match sum of category counts."""
        scores = service.get_readiness_scores()
        cat_impl = sum(cs.implemented for cs in scores.categories)
        cat_partial = sum(cs.partial for cs in scores.categories)
        cat_not_impl = sum(cs.not_implemented for cs in scores.categories)
        cat_na = sum(cs.not_applicable for cs in scores.categories)
        assert scores.total_implemented == cat_impl
        assert scores.total_partial == cat_partial
        assert scores.total_not_implemented == cat_not_impl
        assert scores.total_not_applicable == cat_na

    def test_readiness_total_controls_consistent(
        self, service: SOC2ComplianceService
    ):
        """Total controls equals sum of all statuses."""
        scores = service.get_readiness_scores()
        computed_total = (
            scores.total_implemented
            + scores.total_partial
            + scores.total_not_implemented
            + scores.total_not_applicable
        )
        assert scores.total_controls == computed_total

    def test_readiness_changes_after_update(self, service: SOC2ComplianceService):
        """Readiness changes when a control status is updated."""
        before = service.get_readiness_scores()
        # Move C1.2 from NOT_IMPLEMENTED to IMPLEMENTED
        service.update_control(
            "C1.2", SOC2ControlUpdate(status=ControlStatus.IMPLEMENTED)
        )
        after = service.get_readiness_scores()
        assert after.overall_percentage > before.overall_percentage
        assert after.total_implemented == before.total_implemented + 1
        assert after.total_not_implemented == before.total_not_implemented - 1

    def test_category_readiness_has_name(self, service: SOC2ComplianceService):
        """Category readiness includes human-readable name."""
        scores = service.get_readiness_scores()
        for cs in scores.categories:
            assert cs.category_name == CATEGORY_NAMES[cs.category]


# ===========================================================================
# 6. Remediation Plan Tests
# ===========================================================================


class TestRemediationPlan:
    """Tests for remediation plan generation."""

    def test_remediation_plan_structure(self, service: SOC2ComplianceService):
        """Remediation plan has correct structure."""
        plan = service.get_remediation_plan()
        assert isinstance(plan, RemediationPlan)
        assert plan.total_items > 0
        assert plan.total_effort_hours > 0

    def test_remediation_sorted_by_priority(self, service: SOC2ComplianceService):
        """Remediation items are sorted by priority (P1 first)."""
        plan = service.get_remediation_plan()
        priority_order = {
            RemediationPriority.P1: 0,
            RemediationPriority.P2: 1,
            RemediationPriority.P3: 2,
        }
        for i in range(len(plan.items) - 1):
            assert priority_order[plan.items[i].priority] <= priority_order[
                plan.items[i + 1].priority
            ]

    def test_remediation_only_gaps(self, service: SOC2ComplianceService):
        """Remediation plan only includes non-implemented controls."""
        plan = service.get_remediation_plan()
        for item in plan.items:
            assert item.current_status in (
                ControlStatus.NOT_IMPLEMENTED,
                ControlStatus.PARTIAL,
            )

    def test_remediation_counts_match(self, service: SOC2ComplianceService):
        """P1 + P2 + P3 counts match total items."""
        plan = service.get_remediation_plan()
        assert plan.p1_items + plan.p2_items + plan.p3_items == plan.total_items

    def test_remediation_has_p1_items(self, service: SOC2ComplianceService):
        """At least some P1 (audit blocker) items exist."""
        plan = service.get_remediation_plan()
        assert plan.p1_items > 0

    def test_remediation_effort_consistent(self, service: SOC2ComplianceService):
        """Total effort matches sum of individual item efforts."""
        plan = service.get_remediation_plan()
        computed = sum(item.effort_hours for item in plan.items)
        assert plan.total_effort_hours == computed

    def test_remediation_shrinks_after_fix(self, service: SOC2ComplianceService):
        """Remediation plan shrinks when a gap is fixed."""
        before = service.get_remediation_plan()
        # Fix C1.2 (NOT_IMPLEMENTED -> IMPLEMENTED)
        service.update_control(
            "C1.2", SOC2ControlUpdate(status=ControlStatus.IMPLEMENTED)
        )
        after = service.get_remediation_plan()
        assert after.total_items < before.total_items


# ===========================================================================
# 7. Gap Report Tests
# ===========================================================================


class TestGapReport:
    """Tests for gap report generation."""

    def test_gap_report_structure(self, service: SOC2ComplianceService):
        """Gap report has correct structure."""
        report = service.generate_gap_report()
        assert isinstance(report, GapReport)
        assert report.report_id.startswith("SOC2-GAP-")
        assert report.executive_summary
        assert len(report.category_analysis) == 5
        assert report.overall_readiness is not None
        assert report.remediation_plan is not None

    def test_gap_report_executive_summary(self, service: SOC2ComplianceService):
        """Executive summary contains key metrics."""
        report = service.generate_gap_report()
        summary = report.executive_summary
        assert "readiness" in summary.lower()
        assert "%" in summary

    def test_gap_report_all_categories(self, service: SOC2ComplianceService):
        """Gap report covers all 5 categories."""
        report = service.generate_gap_report()
        categories = {ca.category for ca in report.category_analysis}
        for cat in TrustServiceCategory:
            assert cat in categories

    def test_gap_report_category_gaps(self, service: SOC2ComplianceService):
        """Category gap summary separates implemented from gaps."""
        report = service.generate_gap_report()
        for ca in report.category_analysis:
            for gap in ca.gaps:
                assert gap.status in (
                    ControlStatus.NOT_IMPLEMENTED,
                    ControlStatus.PARTIAL,
                )
            for impl in ca.implemented_controls:
                assert impl.status == ControlStatus.IMPLEMENTED


# ===========================================================================
# 8. Filter Tests
# ===========================================================================


class TestFiltering:
    """Tests for filtering controls."""

    def test_filter_by_category(self, service: SOC2ComplianceService):
        """Filter controls by Trust Service Category."""
        cc_controls = service.get_all_controls(category=TrustServiceCategory.CC)
        assert all(c.category == TrustServiceCategory.CC for c in cc_controls)
        assert len(cc_controls) >= 10  # CC should have many controls

    def test_filter_by_status(self, service: SOC2ComplianceService):
        """Filter controls by implementation status."""
        implemented = service.get_all_controls(status=ControlStatus.IMPLEMENTED)
        assert all(c.status == ControlStatus.IMPLEMENTED for c in implemented)
        assert len(implemented) > 0

    def test_filter_by_category_and_status(self, service: SOC2ComplianceService):
        """Filter by both category and status."""
        cc_gaps = service.get_all_controls(
            category=TrustServiceCategory.CC,
            status=ControlStatus.PARTIAL,
        )
        for c in cc_gaps:
            assert c.category == TrustServiceCategory.CC
            assert c.status == ControlStatus.PARTIAL

    def test_filter_no_results(self, service: SOC2ComplianceService):
        """Filter with no matching results returns empty list."""
        # PI is fully implemented, so NOT_IMPLEMENTED should return empty
        results = service.get_all_controls(
            category=TrustServiceCategory.PI,
            status=ControlStatus.NOT_IMPLEMENTED,
        )
        assert results == []


# ===========================================================================
# 9. API Integration Tests
# ===========================================================================


class TestSOC2API:
    """Integration tests for SOC 2 compliance API endpoints."""

    def test_list_controls(self, client: TestClient):
        """GET /compliance/soc2/controls returns all controls."""
        resp = client.get("/compliance/soc2/controls")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 40

    def test_list_controls_filter_category(self, client: TestClient):
        """GET /compliance/soc2/controls?category=CC filters by category."""
        resp = client.get("/compliance/soc2/controls", params={"category": "CC"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(c["category"] == "CC" for c in data)

    def test_list_controls_filter_status(self, client: TestClient):
        """GET /compliance/soc2/controls?status=IMPLEMENTED filters by status."""
        resp = client.get(
            "/compliance/soc2/controls", params={"status": "IMPLEMENTED"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(c["status"] == "IMPLEMENTED" for c in data)

    def test_get_control_detail(self, client: TestClient):
        """GET /compliance/soc2/controls/CC1.1 returns control detail."""
        resp = client.get("/compliance/soc2/controls/CC1.1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CC1.1"
        assert data["category"] == "CC"

    def test_get_control_not_found(self, client: TestClient):
        """GET /compliance/soc2/controls/NONEXISTENT returns 404."""
        resp = client.get("/compliance/soc2/controls/NONEXISTENT")
        assert resp.status_code == 404

    def test_update_control(self, client: TestClient):
        """PUT /compliance/soc2/controls/C1.2 updates control."""
        resp = client.put(
            "/compliance/soc2/controls/C1.2",
            json={"status": "PARTIAL"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PARTIAL"

    def test_update_control_invalid_transition(self, client: TestClient):
        """PUT with invalid status transition returns 400."""
        resp = client.put(
            "/compliance/soc2/controls/CC1.1",
            json={"status": "NOT_IMPLEMENTED"},
        )
        assert resp.status_code == 400

    def test_update_control_not_found(self, client: TestClient):
        """PUT on nonexistent control returns 404."""
        resp = client.put(
            "/compliance/soc2/controls/NONEXISTENT",
            json={"status": "PARTIAL"},
        )
        assert resp.status_code == 404

    def test_get_readiness(self, client: TestClient):
        """GET /compliance/soc2/readiness returns readiness scores."""
        resp = client.get("/compliance/soc2/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_percentage" in data
        assert "categories" in data
        assert len(data["categories"]) == 5

    def test_get_remediation(self, client: TestClient):
        """GET /compliance/soc2/remediation returns remediation plan."""
        resp = client.get("/compliance/soc2/remediation")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_items" in data
        assert "items" in data
        assert data["total_items"] > 0

    def test_get_gap_report(self, client: TestClient):
        """GET /compliance/soc2/gap-report returns full report."""
        resp = client.get("/compliance/soc2/gap-report")
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_id"].startswith("SOC2-GAP-")
        assert "executive_summary" in data
        assert "category_analysis" in data
        assert "remediation_plan" in data
        assert "overall_readiness" in data

    def test_attach_evidence(self, client: TestClient):
        """POST /compliance/soc2/evidence attaches evidence."""
        resp = client.post(
            "/compliance/soc2/evidence",
            json={
                "control_id": "CC1.1",
                "evidence_type": "DOCUMENT",
                "title": "Security Policy",
                "description": "Annual review",
                "file_reference": "docs/security_policy.pdf",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("EVD-")
        assert data["control_id"] == "CC1.1"

    def test_attach_evidence_nonexistent_control(self, client: TestClient):
        """POST /compliance/soc2/evidence with bad control returns 404."""
        resp = client.post(
            "/compliance/soc2/evidence",
            json={
                "control_id": "NONEXISTENT",
                "evidence_type": "DOCUMENT",
                "title": "Test",
                "file_reference": "test.pdf",
            },
        )
        assert resp.status_code == 404
