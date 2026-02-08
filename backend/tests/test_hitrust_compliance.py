"""Tests for HITRUST CSF v11 Roadmap (CISO-13).

Tests verify:
- Pre-populated controls correctness (50+ controls)
- All 14 HITRUST categories represented
- Control CRUD operations
- Maturity level transitions (NOT_STARTED -> POLICY -> ... -> MANAGED)
- Invalid maturity transitions rejected
- Evidence attachment and retrieval
- Readiness score calculation per category
- Overall readiness percentage and maturity score
- Maturity distribution tracking
- Roadmap generation with 4 phases
- Phase effort and duration estimation
- Category summaries with gap identification
- Filter controls by category and maturity level
- Update control maturity and remediation plan
- Estimated effort to certification
- API endpoint integration tests
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.hitrust_compliance import router as hitrust_compliance_router
from app.schemas.hitrust_compliance import (
    CategoryReadiness,
    CategorySummary,
    CertificationRoadmap,
    EvidenceAttachment,
    EvidenceCreate,
    EvidenceType,
    HITRUSTCategory,
    HITRUSTControl,
    HITRUSTControlUpdate,
    MaturityLevel,
    ReadinessScore,
    RoadmapItem,
    RoadmapPhase,
    RoadmapPhaseDetail,
)
from app.services.hitrust_service import (
    CATEGORY_NAMES,
    HITRUSTComplianceService,
    MATURITY_SCORES,
    VALID_MATURITY_TRANSITIONS,
    get_hitrust_service,
    reset_hitrust_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons between tests."""
    reset_hitrust_service()
    yield
    reset_hitrust_service()


@pytest.fixture
def service() -> HITRUSTComplianceService:
    """Get a fresh HITRUSTComplianceService instance."""
    return get_hitrust_service()


@pytest.fixture
def client() -> TestClient:
    """Create test client with HITRUST compliance router."""
    app = FastAPI()
    app.include_router(hitrust_compliance_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Pre-populated controls
# ---------------------------------------------------------------------------


class TestPrepopulatedControls:
    """Tests for pre-populated HITRUST controls."""

    def test_controls_loaded(self, service: HITRUSTComplianceService):
        """Service loads 50+ pre-populated controls."""
        controls = service.get_all_controls()
        assert len(controls) >= 50

    def test_all_14_categories_represented(self, service: HITRUSTComplianceService):
        """All 14 HITRUST categories (0-13) have at least one control."""
        controls = service.get_all_controls()
        categories_found = {c.category for c in controls}
        for cat in HITRUSTCategory:
            assert cat in categories_found, (
                f"Category {cat.value} ({CATEGORY_NAMES[cat]}) not represented"
            )

    def test_category_names_complete(self):
        """All 14 categories have human-readable names."""
        assert len(CATEGORY_NAMES) == 14
        for cat in HITRUSTCategory:
            assert cat in CATEGORY_NAMES
            assert len(CATEGORY_NAMES[cat]) > 0

    def test_controls_have_required_fields(self, service: HITRUSTComplianceService):
        """All controls have required fields populated."""
        for control in service.get_all_controls():
            assert control.id
            assert control.title
            assert control.description
            assert control.maturity_level in MaturityLevel
            assert control.category in HITRUSTCategory

    def test_implemented_controls_have_file_references(
        self, service: HITRUSTComplianceService
    ):
        """Controls at IMPLEMENTED or above have platform_control and file_reference."""
        for control in service.get_all_controls():
            if MATURITY_SCORES[control.maturity_level] >= MATURITY_SCORES[MaturityLevel.IMPLEMENTED]:
                assert control.platform_control, (
                    f"Control {control.id} is {control.maturity_level.value} "
                    f"but has no platform_control"
                )
                assert control.file_reference, (
                    f"Control {control.id} is {control.maturity_level.value} "
                    f"but has no file_reference"
                )

    def test_gap_controls_have_remediation(self, service: HITRUSTComplianceService):
        """Controls below target maturity have gap descriptions or remediation plans."""
        for control in service.get_all_controls():
            current = MATURITY_SCORES[control.maturity_level]
            target = MATURITY_SCORES[control.target_maturity]
            if current < target and current < MATURITY_SCORES[MaturityLevel.IMPLEMENTED]:
                has_gap_info = bool(control.gap_description) or bool(control.remediation_plan)
                assert has_gap_info, (
                    f"Control {control.id} has gap "
                    f"({control.maturity_level.value} < {control.target_maturity.value}) "
                    f"but no gap_description or remediation_plan"
                )

    def test_access_control_category_mapped(self, service: HITRUSTComplianceService):
        """Category 1 (Access Control) has RBAC and session management mapped."""
        controls = service.get_all_controls(
            category=HITRUSTCategory.ACCESS_CONTROL
        )
        assert len(controls) >= 4
        file_refs = [c.file_reference for c in controls if c.file_reference]
        # Should reference permissions or auth files
        has_permissions = any("permissions" in f or "auth" in f for f in file_refs)
        assert has_permissions

    def test_operations_category_mapped(self, service: HITRUSTComplianceService):
        """Category 9 (Communications and Operations) has observability and logging."""
        controls = service.get_all_controls(
            category=HITRUSTCategory.COMMUNICATIONS_AND_OPERATIONS_MANAGEMENT
        )
        assert len(controls) >= 3
        file_refs = [c.file_reference for c in controls if c.file_reference]
        has_observability = any(
            "observability" in f or "logging" in f for f in file_refs
        )
        assert has_observability

    def test_development_category_mapped(self, service: HITRUSTComplianceService):
        """Category 10 (Systems Development) has security CI and API contracts."""
        controls = service.get_all_controls(
            category=HITRUSTCategory.INFORMATION_SYSTEMS_ACQUISITION_DEVELOPMENT_MAINTENANCE
        )
        assert len(controls) >= 3
        file_refs = [c.file_reference for c in controls if c.file_reference]
        has_security = any("security" in f or "api_contract" in f for f in file_refs)
        assert has_security

    def test_incident_category_mapped(self, service: HITRUSTComplianceService):
        """Category 11 (Incident Management) has IR plan and runbooks."""
        controls = service.get_all_controls(
            category=HITRUSTCategory.INFORMATION_SECURITY_INCIDENT_MANAGEMENT
        )
        assert len(controls) >= 3
        file_refs = [c.file_reference for c in controls if c.file_reference]
        has_incident = any(
            "incident" in f or "runbook" in f for f in file_refs
        )
        assert has_incident

    def test_privacy_category_mapped(self, service: HITRUSTComplianceService):
        """Category 13 (Privacy Practices) has consent and deletion services."""
        controls = service.get_all_controls(
            category=HITRUSTCategory.PRIVACY_PRACTICES
        )
        assert len(controls) >= 3
        file_refs = [c.file_reference for c in controls if c.file_reference]
        has_consent = any("consent" in f for f in file_refs)
        has_deletion = any("deletion" in f for f in file_refs)
        assert has_consent
        assert has_deletion


# ---------------------------------------------------------------------------
# 2. Control CRUD
# ---------------------------------------------------------------------------


class TestControlCRUD:
    """Tests for control get/update operations."""

    def test_get_all_controls(self, service: HITRUSTComplianceService):
        """Returns all controls sorted by ID."""
        controls = service.get_all_controls()
        ids = [c.id for c in controls]
        assert ids == sorted(ids)

    def test_get_control_by_id(self, service: HITRUSTComplianceService):
        """Get a specific control by ID."""
        control = service.get_control("01.a")
        assert control is not None
        assert control.id == "01.a"
        assert control.category == HITRUSTCategory.ACCESS_CONTROL

    def test_get_nonexistent_control(self, service: HITRUSTComplianceService):
        """Getting a non-existent control returns None."""
        assert service.get_control("99.z") is None

    def test_filter_by_category(self, service: HITRUSTComplianceService):
        """Filter controls by category."""
        controls = service.get_all_controls(
            category=HITRUSTCategory.PRIVACY_PRACTICES
        )
        assert len(controls) >= 3
        for c in controls:
            assert c.category == HITRUSTCategory.PRIVACY_PRACTICES

    def test_filter_by_maturity_level(self, service: HITRUSTComplianceService):
        """Filter controls by maturity level."""
        controls = service.get_all_controls(
            maturity_level=MaturityLevel.IMPLEMENTED
        )
        assert len(controls) > 0
        for c in controls:
            assert c.maturity_level == MaturityLevel.IMPLEMENTED

    def test_filter_by_category_and_maturity(self, service: HITRUSTComplianceService):
        """Filter by both category and maturity."""
        controls = service.get_all_controls(
            category=HITRUSTCategory.ACCESS_CONTROL,
            maturity_level=MaturityLevel.NOT_STARTED,
        )
        for c in controls:
            assert c.category == HITRUSTCategory.ACCESS_CONTROL
            assert c.maturity_level == MaturityLevel.NOT_STARTED

    def test_update_control_remediation(self, service: HITRUSTComplianceService):
        """Update control remediation plan."""
        updated = service.update_control(
            "01.a",
            HITRUSTControlUpdate(
                remediation_plan="Updated remediation plan",
                notes="Test note",
                assessed_by="tester",
            ),
        )
        assert updated is not None
        assert updated.remediation_plan == "Updated remediation plan"
        assert updated.notes == "Test note"
        assert updated.assessed_by == "tester"
        assert updated.last_assessed is not None

    def test_update_nonexistent_control(self, service: HITRUSTComplianceService):
        """Updating a non-existent control returns None."""
        result = service.update_control(
            "99.z", HITRUSTControlUpdate(notes="test")
        )
        assert result is None


# ---------------------------------------------------------------------------
# 3. Maturity Level Transitions
# ---------------------------------------------------------------------------


class TestMaturityTransitions:
    """Tests for maturity level transition validation."""

    def test_valid_transition_not_started_to_policy(
        self, service: HITRUSTComplianceService
    ):
        """NOT_STARTED -> POLICY is valid."""
        # Find a NOT_STARTED control
        ns_controls = service.get_all_controls(
            maturity_level=MaturityLevel.NOT_STARTED
        )
        assert len(ns_controls) > 0
        control_id = ns_controls[0].id

        updated = service.update_control(
            control_id,
            HITRUSTControlUpdate(maturity_level=MaturityLevel.POLICY),
        )
        assert updated is not None
        assert updated.maturity_level == MaturityLevel.POLICY

    def test_valid_transition_policy_to_procedure(
        self, service: HITRUSTComplianceService
    ):
        """POLICY -> PROCEDURE is valid."""
        policy_controls = service.get_all_controls(
            maturity_level=MaturityLevel.POLICY
        )
        assert len(policy_controls) > 0
        control_id = policy_controls[0].id

        updated = service.update_control(
            control_id,
            HITRUSTControlUpdate(maturity_level=MaturityLevel.PROCEDURE),
        )
        assert updated is not None
        assert updated.maturity_level == MaturityLevel.PROCEDURE

    def test_valid_transition_implemented_to_measured(
        self, service: HITRUSTComplianceService
    ):
        """IMPLEMENTED -> MEASURED is valid."""
        impl_controls = service.get_all_controls(
            maturity_level=MaturityLevel.IMPLEMENTED
        )
        assert len(impl_controls) > 0
        control_id = impl_controls[0].id

        updated = service.update_control(
            control_id,
            HITRUSTControlUpdate(maturity_level=MaturityLevel.MEASURED),
        )
        assert updated is not None
        assert updated.maturity_level == MaturityLevel.MEASURED

    def test_valid_regression_policy_to_not_started(
        self, service: HITRUSTComplianceService
    ):
        """POLICY -> NOT_STARTED is valid (regression)."""
        policy_controls = service.get_all_controls(
            maturity_level=MaturityLevel.POLICY
        )
        assert len(policy_controls) > 0
        control_id = policy_controls[0].id

        updated = service.update_control(
            control_id,
            HITRUSTControlUpdate(maturity_level=MaturityLevel.NOT_STARTED),
        )
        assert updated is not None
        assert updated.maturity_level == MaturityLevel.NOT_STARTED

    def test_invalid_transition_not_started_to_implemented(
        self, service: HITRUSTComplianceService
    ):
        """NOT_STARTED -> IMPLEMENTED (skipping levels) is invalid."""
        ns_controls = service.get_all_controls(
            maturity_level=MaturityLevel.NOT_STARTED
        )
        assert len(ns_controls) > 0
        control_id = ns_controls[0].id

        with pytest.raises(ValueError, match="Invalid maturity transition"):
            service.update_control(
                control_id,
                HITRUSTControlUpdate(maturity_level=MaturityLevel.IMPLEMENTED),
            )

    def test_invalid_transition_policy_to_managed(
        self, service: HITRUSTComplianceService
    ):
        """POLICY -> MANAGED (skipping levels) is invalid."""
        policy_controls = service.get_all_controls(
            maturity_level=MaturityLevel.POLICY
        )
        assert len(policy_controls) > 0
        control_id = policy_controls[0].id

        with pytest.raises(ValueError, match="Invalid maturity transition"):
            service.update_control(
                control_id,
                HITRUSTControlUpdate(maturity_level=MaturityLevel.MANAGED),
            )

    def test_same_level_update_succeeds(self, service: HITRUSTComplianceService):
        """Updating to the same maturity level succeeds (no-op on level)."""
        control = service.get_all_controls()[0]
        updated = service.update_control(
            control.id,
            HITRUSTControlUpdate(
                maturity_level=control.maturity_level,
                notes="Same level update",
            ),
        )
        assert updated is not None
        assert updated.maturity_level == control.maturity_level
        assert updated.notes == "Same level update"

    def test_all_transitions_defined(self):
        """All maturity levels have defined valid transitions."""
        for level in MaturityLevel:
            if level == MaturityLevel.NOT_STARTED:
                # NOT_STARTED can only go to POLICY
                assert MaturityLevel.POLICY in VALID_MATURITY_TRANSITIONS[level]
            elif level == MaturityLevel.MANAGED:
                # MANAGED can only regress to MEASURED
                assert MaturityLevel.MEASURED in VALID_MATURITY_TRANSITIONS[level]
            else:
                # Middle levels can advance and regress
                assert len(VALID_MATURITY_TRANSITIONS[level]) == 2


# ---------------------------------------------------------------------------
# 4. Evidence
# ---------------------------------------------------------------------------


class TestEvidence:
    """Tests for evidence attachment and retrieval."""

    def test_attach_evidence(self, service: HITRUSTComplianceService):
        """Attach evidence to a control."""
        evidence = service.attach_evidence(
            EvidenceCreate(
                control_id="01.a",
                evidence_type=EvidenceType.DOCUMENT,
                title="Access Control Policy Document",
                description="Formal access control policy",
                file_reference="docs/security/access_control_policy.md",
            )
        )
        assert evidence.id.startswith("HEVD-")
        assert evidence.control_id == "01.a"
        assert evidence.evidence_type == EvidenceType.DOCUMENT
        assert evidence.collected_at is not None

    def test_attach_evidence_updates_control(
        self, service: HITRUSTComplianceService
    ):
        """Attaching evidence updates the control's evidence list."""
        service.attach_evidence(
            EvidenceCreate(
                control_id="01.a",
                evidence_type=EvidenceType.TEST,
                title="RBAC Test Suite",
                file_reference="backend/tests/test_auth.py",
            )
        )
        control = service.get_control("01.a")
        assert control is not None
        assert len(control.evidence) == 1
        assert control.evidence[0].title == "RBAC Test Suite"

    def test_attach_evidence_nonexistent_control(
        self, service: HITRUSTComplianceService
    ):
        """Attaching evidence to non-existent control raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.attach_evidence(
                EvidenceCreate(
                    control_id="99.z",
                    evidence_type=EvidenceType.DOCUMENT,
                    title="Test",
                    file_reference="test.md",
                )
            )

    def test_get_evidence(self, service: HITRUSTComplianceService):
        """Get evidence for a specific control."""
        service.attach_evidence(
            EvidenceCreate(
                control_id="01.a",
                evidence_type=EvidenceType.CODE,
                title="Permission Module",
                file_reference="app/core/permissions.py",
            )
        )
        evidence = service.get_evidence("01.a")
        assert len(evidence) == 1
        assert evidence[0].evidence_type == EvidenceType.CODE

    def test_multiple_evidence_attachments(
        self, service: HITRUSTComplianceService
    ):
        """Multiple evidence items can be attached to the same control."""
        for i in range(3):
            service.attach_evidence(
                EvidenceCreate(
                    control_id="01.a",
                    evidence_type=EvidenceType.DOCUMENT,
                    title=f"Evidence {i}",
                    file_reference=f"docs/evidence_{i}.md",
                )
            )
        evidence = service.get_evidence("01.a")
        assert len(evidence) == 3


# ---------------------------------------------------------------------------
# 5. Readiness Scoring
# ---------------------------------------------------------------------------


class TestReadinessScoring:
    """Tests for readiness score calculations."""

    def test_readiness_scores_structure(self, service: HITRUSTComplianceService):
        """Readiness scores have correct structure."""
        scores = service.get_readiness_scores()
        assert 0.0 <= scores.overall_percentage <= 100.0
        assert 0.0 <= scores.overall_maturity_score <= 5.0
        assert scores.total_controls >= 50
        assert scores.assessed_at is not None

    def test_readiness_per_category(self, service: HITRUSTComplianceService):
        """Readiness includes scores for all categories with controls."""
        scores = service.get_readiness_scores()
        # Should have entries for all 14 categories
        assert len(scores.categories) == 14
        for cat_score in scores.categories:
            assert 0.0 <= cat_score.readiness_percentage <= 100.0
            assert 0.0 <= cat_score.average_maturity_score <= 5.0
            assert cat_score.total_controls > 0

    def test_maturity_distribution_totals(self, service: HITRUSTComplianceService):
        """Overall maturity distribution sums to total controls."""
        scores = service.get_readiness_scores()
        total_from_dist = sum(scores.maturity_distribution.values())
        assert total_from_dist == scores.total_controls

    def test_category_maturity_distribution(
        self, service: HITRUSTComplianceService
    ):
        """Category maturity distributions sum to category total controls."""
        scores = service.get_readiness_scores()
        for cat_score in scores.categories:
            total_from_dist = sum(cat_score.maturity_distribution.values())
            assert total_from_dist == cat_score.total_controls

    def test_maturity_score_calculation(self, service: HITRUSTComplianceService):
        """Maturity score correctly averages numeric scores."""
        scores = service.get_readiness_scores()
        # Verify overall maturity score
        all_controls = service.get_all_controls()
        expected_scores = [
            MATURITY_SCORES[c.maturity_level] for c in all_controls
        ]
        expected_avg = sum(expected_scores) / len(expected_scores)
        assert abs(scores.overall_maturity_score - round(expected_avg, 2)) < 0.01

    def test_estimated_effort_to_certification(
        self, service: HITRUSTComplianceService
    ):
        """Estimated effort to certification is calculated."""
        scores = service.get_readiness_scores()
        assert scores.estimated_effort_to_certification >= 0
        # Should include effort from controls not yet at MANAGED
        non_managed = [
            c for c in service.get_all_controls()
            if c.maturity_level != MaturityLevel.MANAGED
        ]
        expected_effort = sum(c.effort_hours for c in non_managed)
        assert scores.estimated_effort_to_certification == expected_effort

    def test_improving_maturity_increases_readiness(
        self, service: HITRUSTComplianceService
    ):
        """Improving a control's maturity level increases readiness percentage."""
        scores_before = service.get_readiness_scores()
        # Find a NOT_STARTED control and advance it
        ns_controls = service.get_all_controls(
            maturity_level=MaturityLevel.NOT_STARTED
        )
        if ns_controls:
            service.update_control(
                ns_controls[0].id,
                HITRUSTControlUpdate(maturity_level=MaturityLevel.POLICY),
            )
            scores_after = service.get_readiness_scores()
            assert scores_after.overall_percentage >= scores_before.overall_percentage


# ---------------------------------------------------------------------------
# 6. Category Summaries
# ---------------------------------------------------------------------------


class TestCategorySummaries:
    """Tests for category-level summaries."""

    def test_all_categories_summarized(self, service: HITRUSTComplianceService):
        """Summaries cover all 14 categories."""
        summaries = service.get_category_summaries()
        assert len(summaries) == 14

    def test_summary_fields(self, service: HITRUSTComplianceService):
        """Category summaries have correct fields."""
        summaries = service.get_category_summaries()
        for summary in summaries:
            assert summary.category in HITRUSTCategory
            assert summary.category_name == CATEGORY_NAMES[summary.category]
            assert summary.total_controls > 0
            assert 0.0 <= summary.average_maturity_score <= 5.0
            assert 0.0 <= summary.readiness_percentage <= 100.0

    def test_gaps_identified(self, service: HITRUSTComplianceService):
        """Categories with gaps identify the top gap controls."""
        summaries = service.get_category_summaries()
        # At least some categories should have gaps
        categories_with_gaps = [s for s in summaries if len(s.top_gaps) > 0]
        assert len(categories_with_gaps) > 0


# ---------------------------------------------------------------------------
# 7. Roadmap Generation
# ---------------------------------------------------------------------------


class TestRoadmapGeneration:
    """Tests for certification roadmap generation."""

    def test_roadmap_has_four_phases(self, service: HITRUSTComplianceService):
        """Roadmap contains exactly 4 phases."""
        roadmap = service.generate_roadmap()
        assert len(roadmap.phases) == 4

    def test_phase_order(self, service: HITRUSTComplianceService):
        """Phases are in correct order (1-4)."""
        roadmap = service.generate_roadmap()
        phases = [p.phase for p in roadmap.phases]
        assert phases == [
            RoadmapPhase.PHASE_1,
            RoadmapPhase.PHASE_2,
            RoadmapPhase.PHASE_3,
            RoadmapPhase.PHASE_4,
        ]

    def test_phase_names(self, service: HITRUSTComplianceService):
        """Phases have human-readable names."""
        roadmap = service.generate_roadmap()
        names = [p.phase_name for p in roadmap.phases]
        assert names == [
            "Quick Wins",
            "Foundational Controls",
            "Advanced Controls",
            "Certification Readiness",
        ]

    def test_phase_items_have_gaps(self, service: HITRUSTComplianceService):
        """Roadmap items are controls that need maturity improvement."""
        roadmap = service.generate_roadmap()
        for phase in roadmap.phases:
            for item in phase.items:
                current_score = MATURITY_SCORES[item.current_maturity]
                target_score = MATURITY_SCORES[item.target_maturity]
                assert current_score < target_score, (
                    f"Roadmap item {item.control_id} has current_maturity "
                    f"{item.current_maturity.value} >= target {item.target_maturity.value}"
                )

    def test_total_effort_sums_correctly(self, service: HITRUSTComplianceService):
        """Total roadmap effort equals sum of phase efforts."""
        roadmap = service.generate_roadmap()
        phase_total = sum(p.total_effort_hours for p in roadmap.phases)
        assert roadmap.total_effort_hours == phase_total

    def test_phase_effort_sums_correctly(self, service: HITRUSTComplianceService):
        """Phase effort equals sum of item efforts."""
        roadmap = service.generate_roadmap()
        for phase in roadmap.phases:
            item_total = sum(i.effort_hours for i in phase.items)
            assert phase.total_effort_hours == item_total

    def test_roadmap_includes_readiness(self, service: HITRUSTComplianceService):
        """Roadmap includes current readiness assessment."""
        roadmap = service.generate_roadmap()
        assert roadmap.overall_readiness is not None
        assert 0.0 <= roadmap.overall_readiness.overall_percentage <= 100.0

    def test_estimated_total_weeks(self, service: HITRUSTComplianceService):
        """Roadmap has total estimated weeks."""
        roadmap = service.generate_roadmap()
        assert roadmap.estimated_total_weeks > 0
        # Should equal sum of phase durations
        phase_weeks = sum(p.estimated_duration_weeks for p in roadmap.phases)
        assert roadmap.estimated_total_weeks == phase_weeks

    def test_roadmap_items_sorted(self, service: HITRUSTComplianceService):
        """Roadmap items within a phase are sorted by category then ID."""
        roadmap = service.generate_roadmap()
        for phase in roadmap.phases:
            if len(phase.items) > 1:
                for i in range(len(phase.items) - 1):
                    curr = phase.items[i]
                    next_ = phase.items[i + 1]
                    assert (
                        curr.category.value,
                        curr.control_id,
                    ) <= (
                        next_.category.value,
                        next_.control_id,
                    )


# ---------------------------------------------------------------------------
# 8. API Endpoints
# ---------------------------------------------------------------------------


class TestAPIEndpoints:
    """Tests for HITRUST compliance API endpoints."""

    def test_list_controls_endpoint(self, client: TestClient):
        """GET /compliance/hitrust/controls returns all controls."""
        resp = client.get("/compliance/hitrust/controls")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 50

    def test_list_controls_filter_category(self, client: TestClient):
        """GET /compliance/hitrust/controls?category=1 filters by category."""
        resp = client.get("/compliance/hitrust/controls", params={"category": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for control in data:
            assert control["category"] == 1

    def test_list_controls_filter_maturity(self, client: TestClient):
        """GET /compliance/hitrust/controls?maturity_level=IMPLEMENTED filters by maturity."""
        resp = client.get(
            "/compliance/hitrust/controls",
            params={"maturity_level": "IMPLEMENTED"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for control in data:
            assert control["maturity_level"] == "IMPLEMENTED"

    def test_get_control_endpoint(self, client: TestClient):
        """GET /compliance/hitrust/controls/{id} returns control detail."""
        resp = client.get("/compliance/hitrust/controls/01.a")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "01.a"
        assert data["category"] == 1

    def test_get_control_not_found(self, client: TestClient):
        """GET /compliance/hitrust/controls/{id} returns 404 for missing control."""
        resp = client.get("/compliance/hitrust/controls/99.z")
        assert resp.status_code == 404

    def test_update_control_endpoint(self, client: TestClient):
        """PUT /compliance/hitrust/controls/{id} updates control."""
        resp = client.put(
            "/compliance/hitrust/controls/01.a",
            json={"notes": "Updated via API", "assessed_by": "api_test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated via API"
        assert data["assessed_by"] == "api_test"

    def test_update_control_invalid_transition(self, client: TestClient):
        """PUT /compliance/hitrust/controls/{id} rejects invalid transition."""
        # 01.a is IMPLEMENTED, can't jump to MANAGED
        resp = client.put(
            "/compliance/hitrust/controls/01.a",
            json={"maturity_level": "MANAGED"},
        )
        assert resp.status_code == 400

    def test_update_control_not_found(self, client: TestClient):
        """PUT /compliance/hitrust/controls/{id} returns 404 for missing control."""
        resp = client.put(
            "/compliance/hitrust/controls/99.z",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    def test_readiness_endpoint(self, client: TestClient):
        """GET /compliance/hitrust/readiness returns readiness scores."""
        resp = client.get("/compliance/hitrust/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_percentage" in data
        assert "categories" in data
        assert len(data["categories"]) == 14

    def test_roadmap_endpoint(self, client: TestClient):
        """GET /compliance/hitrust/roadmap returns certification roadmap."""
        resp = client.get("/compliance/hitrust/roadmap")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["phases"]) == 4
        assert "total_effort_hours" in data
        assert "estimated_total_weeks" in data

    def test_categories_endpoint(self, client: TestClient):
        """GET /compliance/hitrust/categories returns category summaries."""
        resp = client.get("/compliance/hitrust/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 14

    def test_evidence_endpoint(self, client: TestClient):
        """POST /compliance/hitrust/evidence attaches evidence."""
        resp = client.post(
            "/compliance/hitrust/evidence",
            json={
                "control_id": "01.a",
                "evidence_type": "DOCUMENT",
                "title": "Test Evidence",
                "description": "Evidence for testing",
                "file_reference": "docs/test.md",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("HEVD-")
        assert data["control_id"] == "01.a"

    def test_evidence_endpoint_not_found(self, client: TestClient):
        """POST /compliance/hitrust/evidence returns 404 for missing control."""
        resp = client.post(
            "/compliance/hitrust/evidence",
            json={
                "control_id": "99.z",
                "evidence_type": "DOCUMENT",
                "title": "Test",
                "file_reference": "test.md",
            },
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 9. Singleton Management
# ---------------------------------------------------------------------------


class TestSingletonManagement:
    """Tests for service singleton behavior."""

    def test_singleton_returns_same_instance(self):
        """get_hitrust_service returns the same instance."""
        svc1 = get_hitrust_service()
        svc2 = get_hitrust_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        """reset_hitrust_service creates a fresh instance."""
        svc1 = get_hitrust_service()
        reset_hitrust_service()
        svc2 = get_hitrust_service()
        assert svc1 is not svc2
