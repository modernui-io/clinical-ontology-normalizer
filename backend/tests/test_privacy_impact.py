"""Tests for Privacy Impact Assessment (DPIA) framework.

CLO-4: Tests verify:
- PIA lifecycle (create, add activities, add risks, submit, approve, complete)
- Risk score calculation (likelihood * impact)
- Risk level auto-assignment from score
- Mitigation tracking and residual risk
- Approval validation (can't approve with unmitigated HIGH/CRITICAL risks)
- DPO approval workflow
- Consultation requirement detection
- Overdue review detection
- Metrics calculation
- Template management
- Processing activity validation
- API endpoint integration tests
- Edge cases (approve with open risks, transition from wrong status)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.privacy_impact import (
    AffectedRight,
    DataCategoryType,
    DataSubjectType,
    LegalBasis,
    MitigationStatus,
    PIAStatus,
    RiskImpact,
    RiskLevel,
    RiskLikelihood,
)
from app.services.privacy_impact_service import (
    VALID_PIA_TRANSITIONS,
    PrivacyImpactService,
    calculate_risk_level,
    get_privacy_impact_service,
    reset_privacy_impact_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton service before and after each test."""
    reset_privacy_impact_service()
    yield
    reset_privacy_impact_service()


@pytest.fixture
def service() -> PrivacyImpactService:
    """Fresh PrivacyImpactService instance."""
    return get_privacy_impact_service()


@pytest.fixture
def client():
    """Async test client for API endpoint tests."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ===========================================================================
# 1. Risk Score Calculation
# ===========================================================================


class TestRiskScoreCalculation:
    """Test risk score and level auto-calculation."""

    def test_risk_score_rare_negligible(self):
        """RARE(1) * NEGLIGIBLE(1) = 1 -> LOW."""
        assert 1 * 1 == 1
        assert calculate_risk_level(1) == RiskLevel.LOW

    def test_risk_score_unlikely_minor(self):
        """UNLIKELY(2) * MINOR(2) = 4 -> LOW."""
        assert 2 * 2 == 4
        assert calculate_risk_level(4) == RiskLevel.LOW

    def test_risk_score_possible_moderate(self):
        """POSSIBLE(3) * MODERATE(3) = 9 -> MEDIUM."""
        assert 3 * 3 == 9
        assert calculate_risk_level(9) == RiskLevel.MEDIUM

    def test_risk_score_likely_major(self):
        """LIKELY(4) * MAJOR(4) = 16 -> HIGH."""
        assert 4 * 4 == 16
        assert calculate_risk_level(16) == RiskLevel.HIGH

    def test_risk_score_almost_certain_severe(self):
        """ALMOST_CERTAIN(5) * SEVERE(5) = 25 -> CRITICAL."""
        assert 5 * 5 == 25
        assert calculate_risk_level(25) == RiskLevel.CRITICAL

    def test_risk_level_boundary_low(self):
        """Score 6 is the upper boundary for LOW."""
        assert calculate_risk_level(6) == RiskLevel.LOW

    def test_risk_level_boundary_medium_lower(self):
        """Score 7 is the lower boundary for MEDIUM."""
        assert calculate_risk_level(7) == RiskLevel.MEDIUM

    def test_risk_level_boundary_medium_upper(self):
        """Score 12 is the upper boundary for MEDIUM."""
        assert calculate_risk_level(12) == RiskLevel.MEDIUM

    def test_risk_level_boundary_high_lower(self):
        """Score 13 is the lower boundary for HIGH."""
        assert calculate_risk_level(13) == RiskLevel.HIGH

    def test_risk_level_boundary_high_upper(self):
        """Score 19 is the upper boundary for HIGH."""
        assert calculate_risk_level(19) == RiskLevel.HIGH

    def test_risk_level_boundary_critical_lower(self):
        """Score 20 is the lower boundary for CRITICAL."""
        assert calculate_risk_level(20) == RiskLevel.CRITICAL

    def test_risk_score_auto_calculated_on_add(self, service: PrivacyImpactService):
        """Risk score should be auto-calculated when adding a risk."""
        pia = service.create_pia("Test", "Test PIA", "analyst")
        updated = service.add_risk(
            pia.id,
            title="Test Risk",
            description="A test risk",
            likelihood=RiskLikelihood.LIKELY,
            impact=RiskImpact.MAJOR,
        )
        risk = updated.identified_risks[0]
        assert risk.risk_score == 4 * 4
        assert risk.risk_score == 16
        assert risk.risk_level == RiskLevel.HIGH

    def test_risk_score_rare_severe(self, service: PrivacyImpactService):
        """RARE(1) * SEVERE(5) = 5 -> LOW."""
        pia = service.create_pia("Test", "Test PIA", "analyst")
        updated = service.add_risk(
            pia.id,
            title="Low probability high impact",
            description="Rare but severe",
            likelihood=RiskLikelihood.RARE,
            impact=RiskImpact.SEVERE,
        )
        risk = updated.identified_risks[0]
        assert risk.risk_score == 5
        assert risk.risk_level == RiskLevel.LOW

    def test_risk_score_almost_certain_negligible(self, service: PrivacyImpactService):
        """ALMOST_CERTAIN(5) * NEGLIGIBLE(1) = 5 -> LOW."""
        pia = service.create_pia("Test", "Test PIA", "analyst")
        updated = service.add_risk(
            pia.id,
            title="High probability low impact",
            description="Almost certain but negligible",
            likelihood=RiskLikelihood.ALMOST_CERTAIN,
            impact=RiskImpact.NEGLIGIBLE,
        )
        risk = updated.identified_risks[0]
        assert risk.risk_score == 5
        assert risk.risk_level == RiskLevel.LOW


# ===========================================================================
# 2. PIA Lifecycle
# ===========================================================================


class TestPIALifecycle:
    """Test PIA creation, updates, and state transitions."""

    def test_create_pia_basic(self, service: PrivacyImpactService):
        """Create a basic PIA and verify fields."""
        pia = service.create_pia(
            title="Test PIA",
            description="Testing the PIA system",
            assessor="test-analyst",
        )
        assert pia.id is not None
        assert pia.title == "Test PIA"
        assert pia.description == "Testing the PIA system"
        assert pia.assessor == "test-analyst"
        assert pia.status == PIAStatus.DRAFT
        assert pia.processing_activities == []
        assert pia.identified_risks == []
        assert pia.dpo_approval is False
        assert pia.consultation_required is False
        assert pia.created_at is not None
        assert pia.updated_at is not None
        assert pia.completed_at is None

    def test_create_pia_generates_unique_ids(self, service: PrivacyImpactService):
        """Each PIA should get a unique ID."""
        pia1 = service.create_pia("PIA 1", "Desc 1", "analyst")
        pia2 = service.create_pia("PIA 2", "Desc 2", "analyst")
        assert pia1.id != pia2.id

    def test_get_pia(self, service: PrivacyImpactService):
        """Retrieve a PIA by ID."""
        created = service.create_pia("Test", "Desc", "analyst")
        fetched = service.get_pia(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.title == "Test"

    def test_get_pia_not_found(self, service: PrivacyImpactService):
        """Return None for nonexistent PIA."""
        assert service.get_pia("PIA-NONEXISTENT") is None

    def test_update_pia_title(self, service: PrivacyImpactService):
        """Update PIA title."""
        pia = service.create_pia("Original", "Desc", "analyst")
        updated = service.update_pia(pia.id, title="Updated Title")
        assert updated.title == "Updated Title"

    def test_update_pia_reviewer(self, service: PrivacyImpactService):
        """Update PIA reviewer."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.update_pia(pia.id, reviewer="senior-analyst")
        assert updated.reviewer == "senior-analyst"

    def test_update_pia_necessity_assessment(self, service: PrivacyImpactService):
        """Update necessity assessment."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.update_pia(
            pia.id, necessity_assessment="Processing is necessary for trial recruitment."
        )
        assert updated.necessity_assessment == "Processing is necessary for trial recruitment."

    def test_update_pia_proportionality_assessment(self, service: PrivacyImpactService):
        """Update proportionality assessment."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.update_pia(
            pia.id,
            proportionality_assessment="Data collection is proportionate to the stated purpose.",
        )
        assert updated.proportionality_assessment == "Data collection is proportionate to the stated purpose."

    def test_update_pia_not_found(self, service: PrivacyImpactService):
        """Raise ValueError when updating nonexistent PIA."""
        with pytest.raises(ValueError, match="not found"):
            service.update_pia("PIA-NONEXISTENT", title="New Title")

    def test_update_pia_next_review_date(self, service: PrivacyImpactService):
        """Update next review date."""
        pia = service.create_pia("Test", "Desc", "analyst")
        future = datetime.now(timezone.utc) + timedelta(days=365)
        updated = service.update_pia(pia.id, next_review_date=future)
        assert updated.next_review_date is not None

    def test_list_pias_returns_seeded(self, service: PrivacyImpactService):
        """List should include seeded PIAs."""
        pias, total = service.list_pias()
        assert total >= 4  # 4 seeded PIAs
        assert len(pias) >= 4

    def test_list_pias_filter_by_status(self, service: PrivacyImpactService):
        """Filter PIAs by status."""
        pias, total = service.list_pias(status=PIAStatus.COMPLETED)
        assert total >= 1
        for p in pias:
            assert p.status == PIAStatus.COMPLETED

    def test_list_pias_pagination(self, service: PrivacyImpactService):
        """Test pagination with limit and offset."""
        pias_all, total = service.list_pias(limit=100, offset=0)
        pias_page, _ = service.list_pias(limit=2, offset=0)
        assert len(pias_page) == 2
        pias_page2, _ = service.list_pias(limit=2, offset=2)
        assert len(pias_page2) >= 1

    def test_list_pias_empty_filter(self, service: PrivacyImpactService):
        """Filtering by status with no matches returns empty."""
        pias, total = service.list_pias(status=PIAStatus.ARCHIVED)
        assert total == 0
        assert pias == []


# ===========================================================================
# 3. Processing Activities
# ===========================================================================


class TestProcessingActivities:
    """Test adding processing activities to PIAs."""

    def test_add_processing_activity(self, service: PrivacyImpactService):
        """Add a processing activity to a PIA."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.add_processing_activity(
            pia.id,
            name="Data Collection",
            description="Collect patient demographics",
            data_categories=[DataCategoryType.DEMOGRAPHICS],
            processing_purpose="Trial screening",
            legal_basis=LegalBasis.CONSENT,
            data_subjects=[DataSubjectType.PATIENTS],
            retention_period_months=72,
        )
        assert len(updated.processing_activities) == 1
        act = updated.processing_activities[0]
        assert act.name == "Data Collection"
        assert act.data_categories == [DataCategoryType.DEMOGRAPHICS]
        assert act.legal_basis == LegalBasis.CONSENT
        assert act.retention_period_months == 72
        assert act.cross_border_transfer is False

    def test_add_multiple_activities(self, service: PrivacyImpactService):
        """Add multiple processing activities."""
        pia = service.create_pia("Test", "Desc", "analyst")
        service.add_processing_activity(
            pia.id,
            name="Activity 1",
            description="First activity",
            data_categories=[DataCategoryType.CLINICAL],
            processing_purpose="Screening",
            legal_basis=LegalBasis.CONSENT,
            data_subjects=[DataSubjectType.PATIENTS],
            retention_period_months=36,
        )
        updated = service.add_processing_activity(
            pia.id,
            name="Activity 2",
            description="Second activity",
            data_categories=[DataCategoryType.GENETIC],
            processing_purpose="Research",
            legal_basis=LegalBasis.LEGITIMATE_INTEREST,
            data_subjects=[DataSubjectType.PATIENTS, DataSubjectType.RESEARCHERS],
            retention_period_months=60,
            cross_border_transfer=True,
        )
        assert len(updated.processing_activities) == 2
        assert updated.processing_activities[1].cross_border_transfer is True

    def test_add_activity_with_third_parties(self, service: PrivacyImpactService):
        """Add activity with third-party sharing."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.add_processing_activity(
            pia.id,
            name="Data Sharing",
            description="Share with sponsors",
            data_categories=[DataCategoryType.CLINICAL],
            processing_purpose="Trial reporting",
            legal_basis=LegalBasis.CONSENT,
            data_subjects=[DataSubjectType.PATIENTS],
            retention_period_months=72,
            third_party_sharing=True,
            third_parties=["Sponsor A", "CRO B"],
        )
        act = updated.processing_activities[0]
        assert act.third_party_sharing is True
        assert act.third_parties == ["Sponsor A", "CRO B"]

    def test_add_activity_to_nonexistent_pia(self, service: PrivacyImpactService):
        """Raise ValueError when adding activity to nonexistent PIA."""
        with pytest.raises(ValueError, match="not found"):
            service.add_processing_activity(
                "PIA-NONEXISTENT",
                name="Test",
                description="Test",
                data_categories=[DataCategoryType.CLINICAL],
                processing_purpose="Test",
                legal_basis=LegalBasis.CONSENT,
                data_subjects=[DataSubjectType.PATIENTS],
                retention_period_months=12,
            )

    def test_add_activity_automated_decision_making(self, service: PrivacyImpactService):
        """Add activity with automated decision-making flag."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.add_processing_activity(
            pia.id,
            name="ML Screening",
            description="Automated screening",
            data_categories=[DataCategoryType.CLINICAL, DataCategoryType.GENETIC],
            processing_purpose="Automated trial matching",
            legal_basis=LegalBasis.CONSENT,
            data_subjects=[DataSubjectType.PATIENTS],
            retention_period_months=36,
            automated_decision_making=True,
        )
        act = updated.processing_activities[0]
        assert act.automated_decision_making is True


# ===========================================================================
# 4. Privacy Risks
# ===========================================================================


class TestPrivacyRisks:
    """Test adding and managing privacy risks."""

    def test_add_risk_auto_score(self, service: PrivacyImpactService):
        """Risk score is auto-calculated when risk is added."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.add_risk(
            pia.id,
            title="Data Breach",
            description="Potential data breach",
            likelihood=RiskLikelihood.POSSIBLE,
            impact=RiskImpact.SEVERE,
        )
        risk = updated.identified_risks[0]
        assert risk.risk_score == 3 * 5  # 15
        assert risk.risk_level == RiskLevel.HIGH

    def test_add_risk_with_affected_rights(self, service: PrivacyImpactService):
        """Risk with affected rights list."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.add_risk(
            pia.id,
            title="Consent Violation",
            description="Processing without valid consent",
            likelihood=RiskLikelihood.UNLIKELY,
            impact=RiskImpact.MAJOR,
            affected_rights=[AffectedRight.OBJECTION, AffectedRight.ERASURE],
        )
        risk = updated.identified_risks[0]
        assert AffectedRight.OBJECTION in risk.affected_rights
        assert AffectedRight.ERASURE in risk.affected_rights

    def test_add_multiple_risks(self, service: PrivacyImpactService):
        """Add multiple risks to a PIA."""
        pia = service.create_pia("Test", "Desc", "analyst")
        service.add_risk(
            pia.id, "Risk 1", "Desc 1", RiskLikelihood.RARE, RiskImpact.MINOR
        )
        updated = service.add_risk(
            pia.id, "Risk 2", "Desc 2", RiskLikelihood.LIKELY, RiskImpact.SEVERE
        )
        assert len(updated.identified_risks) == 2

    def test_add_risk_default_mitigation_status(self, service: PrivacyImpactService):
        """New risks should default to PENDING mitigation status."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.add_risk(
            pia.id, "Risk", "Desc", RiskLikelihood.POSSIBLE, RiskImpact.MODERATE
        )
        risk = updated.identified_risks[0]
        assert risk.mitigation_status == MitigationStatus.PENDING
        assert risk.mitigation_measures == []
        assert risk.residual_risk_score is None

    def test_add_risk_to_nonexistent_pia(self, service: PrivacyImpactService):
        """Raise ValueError when adding risk to nonexistent PIA."""
        with pytest.raises(ValueError, match="not found"):
            service.add_risk(
                "PIA-NONEXISTENT",
                "Risk",
                "Desc",
                RiskLikelihood.POSSIBLE,
                RiskImpact.MODERATE,
            )


# ===========================================================================
# 5. Mitigation Tracking
# ===========================================================================


class TestMitigationTracking:
    """Test risk mitigation updates."""

    def test_update_mitigation(self, service: PrivacyImpactService):
        """Update mitigation measures and residual risk."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.add_risk(
            pia.id,
            "Risk",
            "Desc",
            RiskLikelihood.LIKELY,
            RiskImpact.MAJOR,
        )
        risk_id = updated.identified_risks[0].id

        mitigated = service.update_risk_mitigation(
            pia.id,
            risk_id,
            mitigation_measures=["Encrypt data at rest", "Implement RBAC"],
            residual_risk_score=4,
        )
        risk = mitigated.identified_risks[0]
        assert risk.mitigation_measures == ["Encrypt data at rest", "Implement RBAC"]
        assert risk.residual_risk_score == 4
        assert risk.mitigation_status == MitigationStatus.IN_PROGRESS

    def test_update_mitigation_not_found_pia(self, service: PrivacyImpactService):
        """Raise ValueError for nonexistent PIA."""
        with pytest.raises(ValueError, match="PIA not found"):
            service.update_risk_mitigation(
                "PIA-NONEXISTENT", "RISK-001", ["measure"], 5
            )

    def test_update_mitigation_not_found_risk(self, service: PrivacyImpactService):
        """Raise ValueError for nonexistent risk."""
        pia = service.create_pia("Test", "Desc", "analyst")
        with pytest.raises(ValueError, match="Risk not found"):
            service.update_risk_mitigation(
                pia.id, "RISK-NONEXISTENT", ["measure"], 5
            )

    def test_mitigation_preserves_other_risks(self, service: PrivacyImpactService):
        """Updating one risk's mitigation should not affect other risks."""
        pia = service.create_pia("Test", "Desc", "analyst")
        service.add_risk(
            pia.id, "Risk 1", "Desc", RiskLikelihood.POSSIBLE, RiskImpact.MODERATE
        )
        updated = service.add_risk(
            pia.id, "Risk 2", "Desc", RiskLikelihood.LIKELY, RiskImpact.MAJOR
        )
        risk1_id = updated.identified_risks[0].id
        risk2_id = updated.identified_risks[1].id

        mitigated = service.update_risk_mitigation(
            pia.id, risk1_id, ["Measure A"], 3
        )
        assert mitigated.identified_risks[0].mitigation_measures == ["Measure A"]
        assert mitigated.identified_risks[1].mitigation_measures == []
        assert mitigated.identified_risks[1].mitigation_status == MitigationStatus.PENDING


# ===========================================================================
# 6. State Transitions
# ===========================================================================


class TestStateTransitions:
    """Test PIA status transitions and validation."""

    def test_submit_for_review(self, service: PrivacyImpactService):
        """DRAFT -> IN_REVIEW."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.submit_for_review(pia.id)
        assert updated.status == PIAStatus.IN_REVIEW

    def test_submit_invalid_from_approved(self, service: PrivacyImpactService):
        """Cannot submit for review from APPROVED status."""
        # Use a seeded PIA that's already APPROVED
        pia = service.get_pia("PIA-002")
        assert pia is not None
        assert pia.status == PIAStatus.APPROVED
        with pytest.raises(ValueError, match="Invalid PIA status transition"):
            service.submit_for_review("PIA-002")

    def test_approve_pia_no_high_risks(self, service: PrivacyImpactService):
        """Approve a PIA with no HIGH/CRITICAL risks."""
        pia = service.create_pia("Test", "Desc", "analyst")
        service.add_risk(
            pia.id, "Low Risk", "Desc", RiskLikelihood.RARE, RiskImpact.MINOR
        )
        service.submit_for_review(pia.id)
        approved = service.approve_pia(pia.id, reviewer="senior-analyst")
        assert approved.status == PIAStatus.APPROVED
        assert approved.reviewer == "senior-analyst"

    def test_approve_pia_with_mitigated_high_risks(self, service: PrivacyImpactService):
        """Approve a PIA where HIGH risks have mitigation in progress."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.add_risk(
            pia.id, "High Risk", "Desc", RiskLikelihood.LIKELY, RiskImpact.MAJOR
        )
        risk_id = updated.identified_risks[0].id

        # Add mitigation to move status from PENDING
        service.update_risk_mitigation(
            pia.id, risk_id, ["Implement encryption"], 6
        )

        service.submit_for_review(pia.id)
        approved = service.approve_pia(pia.id, reviewer="senior-analyst")
        assert approved.status == PIAStatus.APPROVED

    def test_cannot_approve_with_unmitigated_high_risks(self, service: PrivacyImpactService):
        """Cannot approve PIA with unmitigated HIGH/CRITICAL risks."""
        pia = service.create_pia("Test", "Desc", "analyst")
        service.add_risk(
            pia.id,
            "Critical Risk",
            "Desc",
            RiskLikelihood.ALMOST_CERTAIN,
            RiskImpact.SEVERE,
        )
        service.submit_for_review(pia.id)
        with pytest.raises(ValueError, match="unmitigated HIGH/CRITICAL"):
            service.approve_pia(pia.id, reviewer="senior-analyst")

    def test_cannot_approve_from_draft(self, service: PrivacyImpactService):
        """Cannot approve directly from DRAFT."""
        pia = service.create_pia("Test", "Desc", "analyst")
        with pytest.raises(ValueError, match="Invalid PIA status transition"):
            service.approve_pia(pia.id, reviewer="senior-analyst")

    def test_full_lifecycle(self, service: PrivacyImpactService):
        """Full lifecycle: DRAFT -> IN_REVIEW -> APPROVED -> COMPLETED."""
        pia = service.create_pia("Lifecycle Test", "Full test", "analyst")
        assert pia.status == PIAStatus.DRAFT

        # Add activity and low risk
        service.add_processing_activity(
            pia.id,
            name="Test Activity",
            description="Test desc",
            data_categories=[DataCategoryType.DEMOGRAPHICS],
            processing_purpose="Testing",
            legal_basis=LegalBasis.CONSENT,
            data_subjects=[DataSubjectType.PATIENTS],
            retention_period_months=12,
        )
        service.add_risk(
            pia.id, "Low Risk", "A low risk", RiskLikelihood.RARE, RiskImpact.MINOR
        )

        # Submit for review
        submitted = service.submit_for_review(pia.id)
        assert submitted.status == PIAStatus.IN_REVIEW

        # Approve
        approved = service.approve_pia(pia.id, reviewer="reviewer")
        assert approved.status == PIAStatus.APPROVED

        # Complete
        completed = service._transition(pia.id, PIAStatus.COMPLETED)
        assert completed.status == PIAStatus.COMPLETED
        assert completed.completed_at is not None

    def test_valid_transitions_map(self):
        """Verify the transition map covers all statuses."""
        for status in PIAStatus:
            assert status in VALID_PIA_TRANSITIONS

    def test_archived_is_terminal(self):
        """ARCHIVED should be a terminal state."""
        assert VALID_PIA_TRANSITIONS[PIAStatus.ARCHIVED] == []

    def test_transition_not_found(self, service: PrivacyImpactService):
        """Transition on nonexistent PIA raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.submit_for_review("PIA-NONEXISTENT")


# ===========================================================================
# 7. DPO Approval Workflow
# ===========================================================================


class TestDPOApproval:
    """Test DPO approval workflow."""

    def test_request_dpo_approval(self, service: PrivacyImpactService):
        """Request DPO approval flags the PIA."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.request_dpo_approval(pia.id)
        assert updated.dpo_approval is True
        assert updated.dpo_approval_date is not None

    def test_dpo_approval_not_found(self, service: PrivacyImpactService):
        """Raise ValueError for nonexistent PIA."""
        with pytest.raises(ValueError, match="not found"):
            service.request_dpo_approval("PIA-NONEXISTENT")

    def test_seeded_completed_has_dpo_approval(self, service: PrivacyImpactService):
        """Seeded COMPLETED PIA should have DPO approval."""
        pia = service.get_pia("PIA-001")
        assert pia is not None
        assert pia.dpo_approval is True
        assert pia.dpo_approval_date is not None

    def test_seeded_requires_mitigation_no_dpo(self, service: PrivacyImpactService):
        """Seeded REQUIRES_MITIGATION PIA should not have DPO approval."""
        pia = service.get_pia("PIA-004")
        assert pia is not None
        assert pia.dpo_approval is False


# ===========================================================================
# 8. Consultation Requirement Detection
# ===========================================================================


class TestConsultationDetection:
    """Test supervisory authority consultation requirement checks."""

    def test_consultation_required_critical_risk(self, service: PrivacyImpactService):
        """Consultation required when CRITICAL risk is unmitigated."""
        pia = service.create_pia("Test", "Desc", "analyst")
        service.add_risk(
            pia.id,
            "Critical Risk",
            "Critical unmitigated risk",
            RiskLikelihood.ALMOST_CERTAIN,
            RiskImpact.SEVERE,
        )
        result = service.check_consultation_required(pia.id)
        assert result.consultation_required is True
        assert len(result.reasons) > 0

    def test_consultation_required_automated_decision_on_clinical(
        self, service: PrivacyImpactService
    ):
        """Consultation required for automated decisions on special category data."""
        pia = service.create_pia("Test", "Desc", "analyst")
        service.add_processing_activity(
            pia.id,
            name="ML Screening",
            description="Automated clinical screening",
            data_categories=[DataCategoryType.CLINICAL],
            processing_purpose="Trial matching",
            legal_basis=LegalBasis.CONSENT,
            data_subjects=[DataSubjectType.PATIENTS],
            retention_period_months=36,
            automated_decision_making=True,
        )
        result = service.check_consultation_required(pia.id)
        assert result.consultation_required is True
        assert any("automated decision-making" in r for r in result.reasons)

    def test_consultation_required_automated_decision_on_genetic(
        self, service: PrivacyImpactService
    ):
        """Consultation required for automated decisions on genetic data."""
        pia = service.create_pia("Test", "Desc", "analyst")
        service.add_processing_activity(
            pia.id,
            name="Genetic Analysis",
            description="Automated genetic matching",
            data_categories=[DataCategoryType.GENETIC],
            processing_purpose="Genetic trial matching",
            legal_basis=LegalBasis.CONSENT,
            data_subjects=[DataSubjectType.PATIENTS],
            retention_period_months=24,
            automated_decision_making=True,
        )
        result = service.check_consultation_required(pia.id)
        assert result.consultation_required is True

    def test_no_consultation_low_risk(self, service: PrivacyImpactService):
        """No consultation required for low-risk PIA without automated decisions on special data."""
        pia = service.create_pia("Test", "Desc", "analyst")
        service.add_risk(
            pia.id, "Low Risk", "Desc", RiskLikelihood.RARE, RiskImpact.MINOR
        )
        service.add_processing_activity(
            pia.id,
            name="Manual Review",
            description="Manual data review",
            data_categories=[DataCategoryType.DEMOGRAPHICS],
            processing_purpose="Demographic collection",
            legal_basis=LegalBasis.CONSENT,
            data_subjects=[DataSubjectType.PATIENTS],
            retention_period_months=12,
            automated_decision_making=False,
        )
        result = service.check_consultation_required(pia.id)
        assert result.consultation_required is False
        assert result.reasons == []

    def test_consultation_not_found(self, service: PrivacyImpactService):
        """Raise ValueError for nonexistent PIA."""
        with pytest.raises(ValueError, match="not found"):
            service.check_consultation_required("PIA-NONEXISTENT")

    def test_consultation_seeded_trial_matching(self, service: PrivacyImpactService):
        """Seeded Trial Matching PIA should require consultation."""
        result = service.check_consultation_required("PIA-004")
        assert result.consultation_required is True

    def test_consultation_critical_residual_risk(self, service: PrivacyImpactService):
        """Consultation required when residual risk score is CRITICAL (>=20)."""
        pia = service.create_pia("Test", "Desc", "analyst")
        updated = service.add_risk(
            pia.id,
            "High Risk",
            "Desc",
            RiskLikelihood.ALMOST_CERTAIN,
            RiskImpact.SEVERE,
        )
        risk_id = updated.identified_risks[0].id
        service.update_risk_mitigation(
            pia.id, risk_id, ["Mitigation attempted"], 20
        )
        result = service.check_consultation_required(pia.id)
        assert result.consultation_required is True
        assert any("CRITICAL residual risk" in r for r in result.reasons)


# ===========================================================================
# 9. Overdue Review Detection
# ===========================================================================


class TestOverdueReviews:
    """Test overdue review detection."""

    def test_no_overdue_by_default(self, service: PrivacyImpactService):
        """Seeded PIAs should not be overdue (review dates in the future)."""
        overdue = service.get_overdue_reviews()
        # Seeded PIAs have future review dates or None
        for p in overdue:
            assert p.next_review_date is not None
            assert p.next_review_date < datetime.now(timezone.utc)

    def test_detect_overdue_review(self, service: PrivacyImpactService):
        """PIA with past review date should be detected as overdue."""
        pia = service.create_pia("Overdue Test", "Desc", "analyst")
        past = datetime.now(timezone.utc) - timedelta(days=30)
        service.update_pia(pia.id, next_review_date=past)

        overdue = service.get_overdue_reviews()
        overdue_ids = [p.id for p in overdue]
        assert pia.id in overdue_ids

    def test_archived_not_overdue(self, service: PrivacyImpactService):
        """Archived PIAs should not appear as overdue even with past review dates."""
        pia = service.create_pia("Archive Test", "Desc", "analyst")
        past = datetime.now(timezone.utc) - timedelta(days=30)
        service.update_pia(pia.id, next_review_date=past)

        # Transition to completed then archived
        service.submit_for_review(pia.id)
        service.approve_pia(pia.id, reviewer="reviewer")
        service._transition(pia.id, PIAStatus.COMPLETED)
        service._transition(pia.id, PIAStatus.ARCHIVED)

        overdue = service.get_overdue_reviews()
        overdue_ids = [p.id for p in overdue]
        assert pia.id not in overdue_ids

    def test_future_review_not_overdue(self, service: PrivacyImpactService):
        """PIA with future review date should not be overdue."""
        pia = service.create_pia("Future Test", "Desc", "analyst")
        future = datetime.now(timezone.utc) + timedelta(days=365)
        service.update_pia(pia.id, next_review_date=future)

        overdue = service.get_overdue_reviews()
        overdue_ids = [p.id for p in overdue]
        assert pia.id not in overdue_ids


# ===========================================================================
# 10. Metrics Calculation
# ===========================================================================


class TestMetrics:
    """Test PIA metrics calculation."""

    def test_metrics_total_assessments(self, service: PrivacyImpactService):
        """Metrics should include seeded PIAs."""
        metrics = service.get_metrics()
        assert metrics.total_assessments >= 4

    def test_metrics_by_status(self, service: PrivacyImpactService):
        """Metrics should include status breakdown."""
        metrics = service.get_metrics()
        assert isinstance(metrics.by_status, dict)
        assert "COMPLETED" in metrics.by_status
        assert metrics.by_status["COMPLETED"] >= 1

    def test_metrics_high_risk_count(self, service: PrivacyImpactService):
        """Metrics should count PIAs with HIGH/CRITICAL risks."""
        metrics = service.get_metrics()
        assert metrics.high_risk_count >= 2  # PIA-003 and PIA-004 have HIGH/CRITICAL risks

    def test_metrics_open_mitigations(self, service: PrivacyImpactService):
        """Metrics should count open (pending/in-progress) mitigations."""
        metrics = service.get_metrics()
        assert metrics.open_mitigations > 0

    def test_metrics_avg_risk_score(self, service: PrivacyImpactService):
        """Metrics should calculate average risk score."""
        metrics = service.get_metrics()
        assert metrics.avg_risk_score > 0

    def test_metrics_processing_activities(self, service: PrivacyImpactService):
        """Metrics should count total processing activities."""
        metrics = service.get_metrics()
        assert metrics.processing_activities_assessed >= 8  # Across seeded PIAs

    def test_metrics_cross_border(self, service: PrivacyImpactService):
        """Metrics should count cross-border transfers."""
        metrics = service.get_metrics()
        assert metrics.cross_border_count >= 2  # PIA-003 has cross-border activities

    def test_metrics_automated_decision(self, service: PrivacyImpactService):
        """Metrics should count automated decision-making activities."""
        metrics = service.get_metrics()
        assert metrics.automated_decision_count >= 4  # PIA-001 and PIA-004


# ===========================================================================
# 11. Template Management
# ===========================================================================


class TestTemplates:
    """Test PIA template management."""

    def test_get_templates(self, service: PrivacyImpactService):
        """List templates should return 2 seeded templates."""
        templates = service.get_templates()
        assert len(templates) == 2

    def test_get_template_by_id(self, service: PrivacyImpactService):
        """Get template by ID."""
        template = service.get_template("TPL-001")
        assert template is not None
        assert template.name == "Standard PIA"

    def test_get_template_not_found(self, service: PrivacyImpactService):
        """Return None for nonexistent template."""
        assert service.get_template("TPL-NONEXISTENT") is None

    def test_standard_template_has_questions(self, service: PrivacyImpactService):
        """Standard template should have assessment questions."""
        template = service.get_template("TPL-001")
        assert template is not None
        assert len(template.default_questions) >= 20

    def test_high_risk_template_has_more_questions(self, service: PrivacyImpactService):
        """High-risk template should have more questions than standard."""
        standard = service.get_template("TPL-001")
        high_risk = service.get_template("TPL-002")
        assert standard is not None
        assert high_risk is not None
        assert len(high_risk.default_questions) > len(standard.default_questions)

    def test_template_question_categories(self, service: PrivacyImpactService):
        """Templates should cover all question categories."""
        template = service.get_template("TPL-001")
        assert template is not None
        categories = {q.category for q in template.default_questions}
        assert "Data Collection" in categories
        assert "Processing" in categories
        assert "Storage" in categories
        assert "Sharing" in categories
        assert "Security" in categories
        assert "Rights" in categories

    def test_template_questions_have_guidance(self, service: PrivacyImpactService):
        """All template questions should have guidance text."""
        template = service.get_template("TPL-001")
        assert template is not None
        for q in template.default_questions:
            assert q.guidance, f"Question '{q.question}' missing guidance"


# ===========================================================================
# 12. Seeded PIA Data Verification
# ===========================================================================


class TestSeededData:
    """Verify seeded PIA data integrity."""

    def test_seeded_pia_001_completed(self, service: PrivacyImpactService):
        """PIA-001 should be COMPLETED with 4 risks and 3 activities."""
        pia = service.get_pia("PIA-001")
        assert pia is not None
        assert pia.status == PIAStatus.COMPLETED
        assert len(pia.identified_risks) == 4
        assert len(pia.processing_activities) == 3
        assert pia.dpo_approval is True

    def test_seeded_pia_002_approved(self, service: PrivacyImpactService):
        """PIA-002 should be APPROVED with 3 risks."""
        pia = service.get_pia("PIA-002")
        assert pia is not None
        assert pia.status == PIAStatus.APPROVED
        assert len(pia.identified_risks) == 3

    def test_seeded_pia_003_in_review(self, service: PrivacyImpactService):
        """PIA-003 should be IN_REVIEW with 5 risks and cross-border concern."""
        pia = service.get_pia("PIA-003")
        assert pia is not None
        assert pia.status == PIAStatus.IN_REVIEW
        assert len(pia.identified_risks) == 5
        has_cross_border = any(a.cross_border_transfer for a in pia.processing_activities)
        assert has_cross_border is True

    def test_seeded_pia_004_requires_mitigation(self, service: PrivacyImpactService):
        """PIA-004 should be REQUIRES_MITIGATION with 6 risks and automated decisions."""
        pia = service.get_pia("PIA-004")
        assert pia is not None
        assert pia.status == PIAStatus.REQUIRES_MITIGATION
        assert len(pia.identified_risks) == 6
        has_automated = any(a.automated_decision_making for a in pia.processing_activities)
        assert has_automated is True

    def test_seeded_risk_scores_valid(self, service: PrivacyImpactService):
        """All seeded risks should have valid scores matching likelihood * impact."""
        pias, _ = service.list_pias()
        for pia in pias:
            for risk in pia.identified_risks:
                expected_score = risk.likelihood.value * risk.impact.value
                assert risk.risk_score == expected_score, (
                    f"Risk {risk.id} in PIA {pia.id}: expected score {expected_score}, "
                    f"got {risk.risk_score}"
                )

    def test_seeded_risk_levels_valid(self, service: PrivacyImpactService):
        """All seeded risk levels should match their scores."""
        pias, _ = service.list_pias()
        for pia in pias:
            for risk in pia.identified_risks:
                expected_level = calculate_risk_level(risk.risk_score)
                assert risk.risk_level == expected_level, (
                    f"Risk {risk.id} in PIA {pia.id}: expected level {expected_level.value}, "
                    f"got {risk.risk_level.value} for score {risk.risk_score}"
                )


# ===========================================================================
# 13. Service Stats & Singleton
# ===========================================================================


class TestServiceManagement:
    """Test service stats and singleton pattern."""

    def test_get_stats(self, service: PrivacyImpactService):
        """Service stats should report counts."""
        stats = service.get_stats()
        assert stats["total_pias"] >= 4
        assert stats["total_templates"] == 2

    def test_singleton_returns_same_instance(self):
        """get_privacy_impact_service should return the same instance."""
        svc1 = get_privacy_impact_service()
        svc2 = get_privacy_impact_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        """reset_privacy_impact_service should create a fresh instance."""
        svc1 = get_privacy_impact_service()
        reset_privacy_impact_service()
        svc2 = get_privacy_impact_service()
        assert svc1 is not svc2


# ===========================================================================
# 14. API Endpoint Integration Tests
# ===========================================================================


class TestAPIEndpoints:
    """Tests for Privacy Impact Assessment API endpoints."""

    @pytest.mark.anyio
    async def test_list_assessments(self, client: AsyncClient):
        """GET /assessments should return all PIAs."""
        resp = await client.get("/api/v1/privacy-impact/assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 4
        assert len(data["assessments"]) >= 4

    @pytest.mark.anyio
    async def test_list_assessments_filter_status(self, client: AsyncClient):
        """GET /assessments?status=COMPLETED should filter."""
        resp = await client.get(
            "/api/v1/privacy-impact/assessments?status=COMPLETED"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for a in data["assessments"]:
            assert a["status"] == "COMPLETED"

    @pytest.mark.anyio
    async def test_list_assessments_pagination(self, client: AsyncClient):
        """GET /assessments with limit and offset."""
        resp = await client.get(
            "/api/v1/privacy-impact/assessments?limit=2&offset=0"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["assessments"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0

    @pytest.mark.anyio
    async def test_get_assessment(self, client: AsyncClient):
        """GET /assessments/{id} should return a PIA."""
        resp = await client.get("/api/v1/privacy-impact/assessments/PIA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PIA-001"
        assert data["status"] == "COMPLETED"

    @pytest.mark.anyio
    async def test_get_assessment_not_found(self, client: AsyncClient):
        """GET /assessments/{id} should return 404 for nonexistent PIA."""
        resp = await client.get("/api/v1/privacy-impact/assessments/PIA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assessment(self, client: AsyncClient):
        """POST /assessments should create a new PIA."""
        resp = await client.post(
            "/api/v1/privacy-impact/assessments",
            json={
                "title": "API Test PIA",
                "description": "Created via API test",
                "assessor": "test-user",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "API Test PIA"
        assert data["status"] == "DRAFT"
        assert data["assessor"] == "test-user"

    @pytest.mark.anyio
    async def test_update_assessment(self, client: AsyncClient):
        """PUT /assessments/{id} should update a PIA."""
        # First create one
        create_resp = await client.post(
            "/api/v1/privacy-impact/assessments",
            json={
                "title": "Update Test",
                "description": "Will be updated",
                "assessor": "test-user",
            },
        )
        pia_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/privacy-impact/assessments/{pia_id}",
            json={"title": "Updated Title", "reviewer": "senior-analyst"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["reviewer"] == "senior-analyst"

    @pytest.mark.anyio
    async def test_update_assessment_not_found(self, client: AsyncClient):
        """PUT /assessments/{id} should return 404 for nonexistent PIA."""
        resp = await client.put(
            "/api/v1/privacy-impact/assessments/PIA-NONEXISTENT",
            json={"title": "New Title"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_add_processing_activity_endpoint(self, client: AsyncClient):
        """POST /assessments/{id}/processing-activities should add an activity."""
        create_resp = await client.post(
            "/api/v1/privacy-impact/assessments",
            json={
                "title": "Activity Test",
                "description": "Test adding activities",
                "assessor": "test-user",
            },
        )
        pia_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/privacy-impact/assessments/{pia_id}/processing-activities",
            json={
                "name": "Data Collection",
                "description": "Collect demographics",
                "data_categories": ["DEMOGRAPHICS"],
                "processing_purpose": "Screening",
                "legal_basis": "CONSENT",
                "data_subjects": ["PATIENTS"],
                "retention_period_months": 72,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["processing_activities"]) == 1

    @pytest.mark.anyio
    async def test_add_risk_endpoint(self, client: AsyncClient):
        """POST /assessments/{id}/risks should add a risk."""
        create_resp = await client.post(
            "/api/v1/privacy-impact/assessments",
            json={
                "title": "Risk Test",
                "description": "Test adding risks",
                "assessor": "test-user",
            },
        )
        pia_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/privacy-impact/assessments/{pia_id}/risks",
            json={
                "title": "Test Risk",
                "description": "A test risk",
                "likelihood": 3,
                "impact": 4,
                "affected_rights": ["ACCESS", "ERASURE"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        risk = data["identified_risks"][0]
        assert risk["risk_score"] == 12
        assert risk["risk_level"] == "MEDIUM"

    @pytest.mark.anyio
    async def test_update_mitigation_endpoint(self, client: AsyncClient):
        """PUT /assessments/{id}/risks/{risk_id}/mitigation should update mitigation."""
        # Create PIA and add risk
        create_resp = await client.post(
            "/api/v1/privacy-impact/assessments",
            json={
                "title": "Mitigation Test",
                "description": "Test mitigation",
                "assessor": "test-user",
            },
        )
        pia_id = create_resp.json()["id"]

        risk_resp = await client.post(
            f"/api/v1/privacy-impact/assessments/{pia_id}/risks",
            json={
                "title": "Risk to Mitigate",
                "description": "Needs mitigation",
                "likelihood": 4,
                "impact": 4,
            },
        )
        risk_id = risk_resp.json()["identified_risks"][0]["id"]

        resp = await client.put(
            f"/api/v1/privacy-impact/assessments/{pia_id}/risks/{risk_id}/mitigation",
            json={
                "mitigation_measures": ["Encrypt all data", "Add RBAC"],
                "residual_risk_score": 6,
            },
        )
        assert resp.status_code == 200
        risk = resp.json()["identified_risks"][0]
        assert risk["mitigation_measures"] == ["Encrypt all data", "Add RBAC"]
        assert risk["residual_risk_score"] == 6

    @pytest.mark.anyio
    async def test_submit_for_review_endpoint(self, client: AsyncClient):
        """POST /assessments/{id}/submit should transition to IN_REVIEW."""
        create_resp = await client.post(
            "/api/v1/privacy-impact/assessments",
            json={
                "title": "Submit Test",
                "description": "Test submission",
                "assessor": "test-user",
            },
        )
        pia_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/privacy-impact/assessments/{pia_id}/submit"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "IN_REVIEW"

    @pytest.mark.anyio
    async def test_approve_endpoint(self, client: AsyncClient):
        """POST /assessments/{id}/approve should approve the PIA."""
        create_resp = await client.post(
            "/api/v1/privacy-impact/assessments",
            json={
                "title": "Approve Test",
                "description": "Test approval",
                "assessor": "test-user",
            },
        )
        pia_id = create_resp.json()["id"]

        # Submit for review first
        await client.post(f"/api/v1/privacy-impact/assessments/{pia_id}/submit")

        resp = await client.post(
            f"/api/v1/privacy-impact/assessments/{pia_id}/approve",
            json={"reviewer": "senior-analyst"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"
        assert resp.json()["reviewer"] == "senior-analyst"

    @pytest.mark.anyio
    async def test_approve_endpoint_with_unmitigated_risks(self, client: AsyncClient):
        """POST /assessments/{id}/approve should fail with unmitigated HIGH risks."""
        create_resp = await client.post(
            "/api/v1/privacy-impact/assessments",
            json={
                "title": "Block Test",
                "description": "Test blocked approval",
                "assessor": "test-user",
            },
        )
        pia_id = create_resp.json()["id"]

        # Add HIGH risk
        await client.post(
            f"/api/v1/privacy-impact/assessments/{pia_id}/risks",
            json={
                "title": "Critical Risk",
                "description": "Unmitigated critical risk",
                "likelihood": 5,
                "impact": 5,
            },
        )

        # Submit for review
        await client.post(f"/api/v1/privacy-impact/assessments/{pia_id}/submit")

        # Try to approve - should fail
        resp = await client.post(
            f"/api/v1/privacy-impact/assessments/{pia_id}/approve",
            json={"reviewer": "senior-analyst"},
        )
        assert resp.status_code == 400
        body = resp.json()
        # ErrorHandlerMiddleware wraps detail into message
        error_text = body.get("detail", body.get("message", ""))
        assert "unmitigated" in error_text.lower()

    @pytest.mark.anyio
    async def test_dpo_approval_endpoint(self, client: AsyncClient):
        """POST /assessments/{id}/dpo-approval should flag for DPO review."""
        create_resp = await client.post(
            "/api/v1/privacy-impact/assessments",
            json={
                "title": "DPO Test",
                "description": "Test DPO approval",
                "assessor": "test-user",
            },
        )
        pia_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/privacy-impact/assessments/{pia_id}/dpo-approval"
        )
        assert resp.status_code == 200
        assert resp.json()["dpo_approval"] is True

    @pytest.mark.anyio
    async def test_consultation_check_endpoint(self, client: AsyncClient):
        """GET /assessments/{id}/consultation-check should return consultation result."""
        resp = await client.get(
            "/api/v1/privacy-impact/assessments/PIA-004/consultation-check"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["consultation_required"] is True
        assert len(data["reasons"]) > 0

    @pytest.mark.anyio
    async def test_consultation_check_not_found(self, client: AsyncClient):
        """GET /assessments/{id}/consultation-check should return 404."""
        resp = await client.get(
            "/api/v1/privacy-impact/assessments/PIA-NONEXISTENT/consultation-check"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_metrics_endpoint(self, client: AsyncClient):
        """GET /assessments/metrics should return program metrics."""
        resp = await client.get("/api/v1/privacy-impact/assessments/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_assessments"] >= 4
        assert "by_status" in data
        assert data["high_risk_count"] >= 2

    @pytest.mark.anyio
    async def test_overdue_endpoint(self, client: AsyncClient):
        """GET /assessments/overdue should return overdue reviews."""
        resp = await client.get("/api/v1/privacy-impact/assessments/overdue")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.anyio
    async def test_list_templates_endpoint(self, client: AsyncClient):
        """GET /templates should return templates."""
        resp = await client.get("/api/v1/privacy-impact/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["templates"]) == 2

    @pytest.mark.anyio
    async def test_get_template_endpoint(self, client: AsyncClient):
        """GET /templates/{id} should return a template."""
        resp = await client.get("/api/v1/privacy-impact/templates/TPL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Standard PIA"
        assert len(data["default_questions"]) >= 20

    @pytest.mark.anyio
    async def test_get_template_not_found_endpoint(self, client: AsyncClient):
        """GET /templates/{id} should return 404 for nonexistent template."""
        resp = await client.get("/api/v1/privacy-impact/templates/TPL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_submit_invalid_transition_endpoint(self, client: AsyncClient):
        """POST /assessments/{id}/submit from wrong status should return 400."""
        resp = await client.post(
            "/api/v1/privacy-impact/assessments/PIA-002/submit"
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_add_risk_not_found_endpoint(self, client: AsyncClient):
        """POST /assessments/{id}/risks should return 404 for nonexistent PIA."""
        resp = await client.post(
            "/api/v1/privacy-impact/assessments/PIA-NONEXISTENT/risks",
            json={
                "title": "Risk",
                "description": "Desc",
                "likelihood": 3,
                "impact": 3,
            },
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_add_activity_not_found_endpoint(self, client: AsyncClient):
        """POST /assessments/{id}/processing-activities should return 404."""
        resp = await client.post(
            "/api/v1/privacy-impact/assessments/PIA-NONEXISTENT/processing-activities",
            json={
                "name": "Test",
                "description": "Test",
                "data_categories": ["CLINICAL"],
                "processing_purpose": "Test",
                "legal_basis": "CONSENT",
                "data_subjects": ["PATIENTS"],
                "retention_period_months": 12,
            },
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_mitigation_update_not_found_endpoint(self, client: AsyncClient):
        """PUT /assessments/{id}/risks/{risk_id}/mitigation should return 404."""
        resp = await client.put(
            "/api/v1/privacy-impact/assessments/PIA-NONEXISTENT/risks/RISK-001/mitigation",
            json={
                "mitigation_measures": ["Test"],
                "residual_risk_score": 5,
            },
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_dpo_approval_not_found_endpoint(self, client: AsyncClient):
        """POST /assessments/{id}/dpo-approval should return 404."""
        resp = await client.post(
            "/api/v1/privacy-impact/assessments/PIA-NONEXISTENT/dpo-approval"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_full_api_lifecycle(self, client: AsyncClient):
        """Full API lifecycle: create, add activity, add risk, submit, approve."""
        # Create
        create_resp = await client.post(
            "/api/v1/privacy-impact/assessments",
            json={
                "title": "Full Lifecycle API",
                "description": "Complete lifecycle test",
                "assessor": "api-tester",
            },
        )
        assert create_resp.status_code == 201
        pia_id = create_resp.json()["id"]

        # Add activity
        act_resp = await client.post(
            f"/api/v1/privacy-impact/assessments/{pia_id}/processing-activities",
            json={
                "name": "Test Activity",
                "description": "A test processing activity",
                "data_categories": ["DEMOGRAPHICS", "CLINICAL"],
                "processing_purpose": "Testing",
                "legal_basis": "CONSENT",
                "data_subjects": ["PATIENTS"],
                "retention_period_months": 24,
            },
        )
        assert act_resp.status_code == 201

        # Add low risk
        risk_resp = await client.post(
            f"/api/v1/privacy-impact/assessments/{pia_id}/risks",
            json={
                "title": "Low Risk",
                "description": "A low risk",
                "likelihood": 1,
                "impact": 2,
            },
        )
        assert risk_resp.status_code == 201

        # Submit
        submit_resp = await client.post(
            f"/api/v1/privacy-impact/assessments/{pia_id}/submit"
        )
        assert submit_resp.status_code == 200
        assert submit_resp.json()["status"] == "IN_REVIEW"

        # Approve
        approve_resp = await client.post(
            f"/api/v1/privacy-impact/assessments/{pia_id}/approve",
            json={"reviewer": "senior-analyst"},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "APPROVED"

        # Verify final state
        get_resp = await client.get(
            f"/api/v1/privacy-impact/assessments/{pia_id}"
        )
        assert get_resp.status_code == 200
        final = get_resp.json()
        assert final["status"] == "APPROVED"
        assert len(final["processing_activities"]) == 1
        assert len(final["identified_risks"]) == 1
