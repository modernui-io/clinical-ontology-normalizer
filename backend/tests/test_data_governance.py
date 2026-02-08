"""Tests for Data Governance (DUA + Right-to-Deletion).

CLO-2: Data Use Agreements and Right-to-Deletion

Tests verify:
- DUA CRUD and lifecycle transitions
- DUA compliance checking (allowed/denied scenarios)
- DUA expiration monitoring
- DUA amendment tracking
- Pre-populated DUA templates
- Deletion request workflow (full lifecycle)
- Legal hold blocking deletion
- Retention override (clinical trial data < 6 years)
- Partial deletion (audit logs retained, PHI redacted)
- Deletion certificate generation
- Scope-specific deletion (ALL vs PHI_ONLY vs SPECIFIC_RECORDS)
- Requester identity validation
- Data access logging
- Suspicious access detection (access without DUA coverage)
- API endpoints (via TestClient)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.data_governance import router as data_governance_router
from app.schemas.data_governance import (
    AccessLogCreate,
    ComplianceDecision,
    DataCategory,
    DeletionRequestCreate,
    DeletionScope,
    DeletionStatus,
    DUAComplianceCheck,
    DUACreate,
    DUAStatus,
    DUAType,
    DUAUpdate,
)
from app.services.data_use_agreement_service import (
    DataUseAgreementService,
    get_dua_service,
    reset_dua_service,
)
from app.services.deletion_service import (
    DeletionService,
    get_deletion_service,
    reset_deletion_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset():
    """Reset singletons between tests."""
    reset_dua_service()
    reset_deletion_service()
    yield
    reset_dua_service()
    reset_deletion_service()


@pytest.fixture
def dua_service() -> DataUseAgreementService:
    """Fresh DataUseAgreementService instance."""
    return DataUseAgreementService()


@pytest.fixture
def deletion_service() -> DeletionService:
    """Fresh DeletionService instance."""
    return DeletionService()


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient with data governance router mounted."""
    app = FastAPI()
    app.include_router(data_governance_router, prefix="/api/v1")
    return TestClient(app)


# ===========================================================================
# 1. DUA CRUD Tests
# ===========================================================================


class TestDUACRUD:
    """Test DUA creation, retrieval, listing, and updates."""

    def test_create_dua_basic(self, dua_service: DataUseAgreementService):
        """Create a basic DUA and verify fields."""
        dua = dua_service.create_dua(
            DUACreate(
                title="Test Site DUA",
                dua_type=DUAType.SITE_DUA,
                parties=["Platform", "Test Hospital"],
                data_categories=[DataCategory.PHI, DataCategory.LIMITED_DATASET],
            )
        )
        assert dua.title == "Test Site DUA"
        assert dua.dua_type == DUAType.SITE_DUA
        assert dua.status == DUAStatus.DRAFT
        assert dua.parties == ["Platform", "Test Hospital"]
        assert DataCategory.PHI in dua.data_categories
        assert dua.id is not None
        assert dua.created_at is not None

    def test_create_dua_with_all_fields(self, dua_service: DataUseAgreementService):
        """Create a DUA with all optional fields populated."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=365)
        dua = dua_service.create_dua(
            DUACreate(
                title="Full DUA",
                dua_type=DUAType.SPONSOR_DUA,
                parties=["Platform", "Sponsor Corp"],
                data_categories=[DataCategory.DE_IDENTIFIED, DataCategory.AGGREGATE],
                permitted_uses=["Feasibility analysis", "Cohort reporting"],
                prohibited_uses=["Re-identification", "Marketing"],
                retention_period_days=3650,
                start_date=start,
                end_date=end,
            )
        )
        assert dua.permitted_uses == ["Feasibility analysis", "Cohort reporting"]
        assert dua.prohibited_uses == ["Re-identification", "Marketing"]
        assert dua.retention_period_days == 3650
        assert dua.start_date == start
        assert dua.end_date == end

    def test_get_dua_by_id(self, dua_service: DataUseAgreementService):
        """Retrieve a DUA by its ID."""
        created = dua_service.create_dua(
            DUACreate(
                title="Retrieve Test",
                dua_type=DUAType.RESEARCH_DUA,
                parties=["Platform", "University"],
                data_categories=[DataCategory.DE_IDENTIFIED],
            )
        )
        retrieved = dua_service.get_dua(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == "Retrieve Test"

    def test_get_dua_not_found(self, dua_service: DataUseAgreementService):
        """Return None for non-existent DUA."""
        assert dua_service.get_dua("nonexistent-id") is None

    def test_list_duas_all(self, dua_service: DataUseAgreementService):
        """List all DUAs."""
        dua_service.create_dua(
            DUACreate(title="DUA 1", dua_type=DUAType.SITE_DUA, parties=["A"], data_categories=[DataCategory.PHI])
        )
        dua_service.create_dua(
            DUACreate(title="DUA 2", dua_type=DUAType.VENDOR_DUA, parties=["B"], data_categories=[DataCategory.PHI])
        )
        all_duas = dua_service.list_duas()
        assert len(all_duas) == 2

    def test_list_duas_with_status_filter(self, dua_service: DataUseAgreementService):
        """List DUAs filtered by status."""
        dua_service.create_dua(
            DUACreate(title="Draft DUA", dua_type=DUAType.SITE_DUA, parties=["A"], data_categories=[DataCategory.PHI])
        )
        drafts = dua_service.list_duas(status_filter=DUAStatus.DRAFT)
        assert len(drafts) == 1
        active = dua_service.list_duas(status_filter=DUAStatus.ACTIVE)
        assert len(active) == 0


# ===========================================================================
# 2. DUA Lifecycle Transition Tests
# ===========================================================================


class TestDUALifecycle:
    """Test DUA state transitions."""

    def test_draft_to_pending_review(self, dua_service: DataUseAgreementService):
        """Transition from DRAFT to PENDING_REVIEW."""
        dua = dua_service.create_dua(
            DUACreate(title="Lifecycle Test", dua_type=DUAType.SITE_DUA, parties=["A", "B"], data_categories=[DataCategory.PHI])
        )
        updated = dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.PENDING_REVIEW))
        assert updated.status == DUAStatus.PENDING_REVIEW

    def test_pending_review_to_active(self, dua_service: DataUseAgreementService):
        """Transition from PENDING_REVIEW to ACTIVE with signing."""
        dua = dua_service.create_dua(
            DUACreate(title="Activation Test", dua_type=DUAType.SITE_DUA, parties=["A"], data_categories=[DataCategory.PHI])
        )
        dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.PENDING_REVIEW))
        updated = dua_service.update_dua(
            dua.id,
            DUAUpdate(status=DUAStatus.ACTIVE, signed_by="John Smith"),
        )
        assert updated.status == DUAStatus.ACTIVE
        assert updated.signed_by == "John Smith"
        assert updated.signed_date is not None

    def test_activation_requires_signature(self, dua_service: DataUseAgreementService):
        """Cannot activate without signed_by."""
        dua = dua_service.create_dua(
            DUACreate(title="No Sig Test", dua_type=DUAType.SITE_DUA, parties=["A"], data_categories=[DataCategory.PHI])
        )
        dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.PENDING_REVIEW))
        with pytest.raises(ValueError, match="signed"):
            dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.ACTIVE))

    def test_active_to_terminated(self, dua_service: DataUseAgreementService):
        """Transition from ACTIVE to TERMINATED."""
        dua = dua_service.create_dua(
            DUACreate(title="Termination Test", dua_type=DUAType.SITE_DUA, parties=["A"], data_categories=[DataCategory.PHI])
        )
        dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.PENDING_REVIEW))
        dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.ACTIVE, signed_by="Admin"))
        updated = dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.TERMINATED))
        assert updated.status == DUAStatus.TERMINATED

    def test_invalid_transition_rejected(self, dua_service: DataUseAgreementService):
        """Invalid state transitions are rejected."""
        dua = dua_service.create_dua(
            DUACreate(title="Invalid Trans", dua_type=DUAType.SITE_DUA, parties=["A"], data_categories=[DataCategory.PHI])
        )
        with pytest.raises(ValueError, match="Invalid state transition"):
            dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.ACTIVE))

    def test_terminated_is_final(self, dua_service: DataUseAgreementService):
        """Cannot transition out of TERMINATED."""
        dua = dua_service.create_dua(
            DUACreate(title="Final Test", dua_type=DUAType.SITE_DUA, parties=["A"], data_categories=[DataCategory.PHI])
        )
        dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.TERMINATED))
        with pytest.raises(ValueError, match="Invalid state transition"):
            dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.DRAFT))

    def test_expired_is_final(self, dua_service: DataUseAgreementService):
        """Cannot transition out of EXPIRED."""
        dua = dua_service.create_dua(
            DUACreate(title="Expired Final", dua_type=DUAType.SITE_DUA, parties=["A"], data_categories=[DataCategory.PHI])
        )
        dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.PENDING_REVIEW))
        dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.ACTIVE, signed_by="Admin"))
        dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.EXPIRED))
        with pytest.raises(ValueError, match="Invalid state transition"):
            dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.ACTIVE))


# ===========================================================================
# 3. DUA Amendment Tracking Tests
# ===========================================================================


class TestDUAAmendments:
    """Test amendment tracking for active DUAs."""

    def _create_active_dua(self, svc: DataUseAgreementService) -> str:
        """Helper to create and activate a DUA."""
        dua = svc.create_dua(
            DUACreate(
                title="Amendment Test",
                dua_type=DUAType.SITE_DUA,
                parties=["Platform", "Hospital"],
                data_categories=[DataCategory.PHI],
                permitted_uses=["Screening"],
            )
        )
        svc.update_dua(dua.id, DUAUpdate(status=DUAStatus.PENDING_REVIEW))
        svc.update_dua(dua.id, DUAUpdate(status=DUAStatus.ACTIVE, signed_by="Admin"))
        return dua.id

    def test_amendment_tracked_on_active_dua(self, dua_service: DataUseAgreementService):
        """Changes to active DUA are tracked as amendments."""
        dua_id = self._create_active_dua(dua_service)
        updated = dua_service.update_dua(
            dua_id,
            DUAUpdate(
                title="Amended Title",
                amendment_reason="Title correction",
                amendment_approved_by="Legal Team",
            ),
        )
        assert updated.title == "Amended Title"
        assert len(updated.amendment_history) == 1
        amendment = updated.amendment_history[0]
        assert amendment.field_changed == "title"
        assert amendment.reason == "Title correction"
        assert amendment.approved_by == "Legal Team"

    def test_amendment_requires_reason_for_active_dua(self, dua_service: DataUseAgreementService):
        """Amendments to active DUA require a reason."""
        dua_id = self._create_active_dua(dua_service)
        with pytest.raises(ValueError, match="Amendment reason required"):
            dua_service.update_dua(
                dua_id,
                DUAUpdate(title="No Reason Change"),
            )

    def test_no_amendment_tracking_for_draft(self, dua_service: DataUseAgreementService):
        """Changes to DRAFT DUAs are not tracked as amendments."""
        dua = dua_service.create_dua(
            DUACreate(title="Draft DUA", dua_type=DUAType.SITE_DUA, parties=["A"], data_categories=[DataCategory.PHI])
        )
        updated = dua_service.update_dua(dua.id, DUAUpdate(title="Updated Draft"))
        assert updated.title == "Updated Draft"
        assert len(updated.amendment_history) == 0

    def test_multiple_amendments(self, dua_service: DataUseAgreementService):
        """Multiple amendments are tracked independently."""
        dua_id = self._create_active_dua(dua_service)
        dua_service.update_dua(
            dua_id,
            DUAUpdate(
                title="First Amendment",
                amendment_reason="Initial correction",
                amendment_approved_by="Admin",
            ),
        )
        updated = dua_service.update_dua(
            dua_id,
            DUAUpdate(
                permitted_uses=["Screening", "Research"],
                amendment_reason="Expanded scope",
                amendment_approved_by="Legal",
            ),
        )
        assert len(updated.amendment_history) == 2


# ===========================================================================
# 4. DUA Compliance Checking Tests
# ===========================================================================


class TestDUACompliance:
    """Test DUA compliance checking (allowed/denied scenarios)."""

    def _create_active_dua_with_categories(
        self,
        svc: DataUseAgreementService,
        categories: list[DataCategory],
        permitted_uses: list[str] | None = None,
        prohibited_uses: list[str] | None = None,
        end_date: datetime | None = None,
    ) -> str:
        dua = svc.create_dua(
            DUACreate(
                title="Compliance Test DUA",
                dua_type=DUAType.SITE_DUA,
                parties=["Platform", "Hospital"],
                data_categories=categories,
                permitted_uses=permitted_uses or ["patient screening"],
                prohibited_uses=prohibited_uses or [],
                end_date=end_date,
            )
        )
        svc.update_dua(dua.id, DUAUpdate(status=DUAStatus.PENDING_REVIEW))
        svc.update_dua(dua.id, DUAUpdate(status=DUAStatus.ACTIVE, signed_by="Admin"))
        return dua.id

    def test_access_allowed_matching_dua(self, dua_service: DataUseAgreementService):
        """Access allowed when covered by an active DUA."""
        self._create_active_dua_with_categories(dua_service, [DataCategory.PHI])
        result = dua_service.check_compliance(
            DUAComplianceCheck(
                user_id="user-1",
                data_category=DataCategory.PHI,
                purpose="patient screening",
            )
        )
        assert result.decision == ComplianceDecision.ALLOWED
        assert result.dua_id is not None

    def test_access_denied_no_matching_category(self, dua_service: DataUseAgreementService):
        """Access denied when no DUA covers the data category."""
        self._create_active_dua_with_categories(dua_service, [DataCategory.AGGREGATE])
        result = dua_service.check_compliance(
            DUAComplianceCheck(
                user_id="user-1",
                data_category=DataCategory.PHI,
                purpose="patient screening",
            )
        )
        assert result.decision == ComplianceDecision.DENIED

    def test_access_denied_no_active_duas(self, dua_service: DataUseAgreementService):
        """Access denied when no active DUAs exist."""
        result = dua_service.check_compliance(
            DUAComplianceCheck(
                user_id="user-1",
                data_category=DataCategory.PHI,
                purpose="screening",
            )
        )
        assert result.decision == ComplianceDecision.DENIED

    def test_access_denied_prohibited_use(self, dua_service: DataUseAgreementService):
        """Access denied when purpose matches a prohibited use."""
        self._create_active_dua_with_categories(
            dua_service,
            [DataCategory.PHI],
            permitted_uses=["patient screening", "marketing"],
            prohibited_uses=["marketing to patients"],
        )
        result = dua_service.check_compliance(
            DUAComplianceCheck(
                user_id="user-1",
                data_category=DataCategory.PHI,
                purpose="marketing to patients",
            )
        )
        assert result.decision == ComplianceDecision.DENIED

    def test_access_denied_expired_dua(self, dua_service: DataUseAgreementService):
        """Access denied when DUA has expired end_date."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        self._create_active_dua_with_categories(
            dua_service,
            [DataCategory.PHI],
            end_date=past,
        )
        result = dua_service.check_compliance(
            DUAComplianceCheck(
                user_id="user-1",
                data_category=DataCategory.PHI,
                purpose="patient screening",
            )
        )
        assert result.decision == ComplianceDecision.DENIED


# ===========================================================================
# 5. DUA Expiration Monitoring Tests
# ===========================================================================


class TestDUAExpiration:
    """Test DUA expiration monitoring."""

    def test_find_expiring_duas(self, dua_service: DataUseAgreementService):
        """Find DUAs expiring within a window."""
        end_soon = datetime.now(timezone.utc) + timedelta(days=15)
        end_later = datetime.now(timezone.utc) + timedelta(days=90)

        for title, end in [("Expiring Soon", end_soon), ("Expiring Later", end_later)]:
            dua = dua_service.create_dua(
                DUACreate(
                    title=title,
                    dua_type=DUAType.SITE_DUA,
                    parties=["A"],
                    data_categories=[DataCategory.PHI],
                    end_date=end,
                )
            )
            dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.PENDING_REVIEW))
            dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.ACTIVE, signed_by="Admin"))

        expiring = dua_service.get_expiring_duas(within_days=30)
        assert len(expiring) == 1
        assert expiring[0].title == "Expiring Soon"

    def test_no_expiring_duas(self, dua_service: DataUseAgreementService):
        """No DUAs expiring when none are close to end date."""
        future = datetime.now(timezone.utc) + timedelta(days=365)
        dua = dua_service.create_dua(
            DUACreate(
                title="Far Future",
                dua_type=DUAType.SITE_DUA,
                parties=["A"],
                data_categories=[DataCategory.PHI],
                end_date=future,
            )
        )
        dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.PENDING_REVIEW))
        dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.ACTIVE, signed_by="Admin"))

        expiring = dua_service.get_expiring_duas(within_days=30)
        assert len(expiring) == 0


# ===========================================================================
# 6. DUA Templates Tests
# ===========================================================================


class TestDUATemplates:
    """Test pre-populated DUA templates."""

    def test_site_dua_template(self, dua_service: DataUseAgreementService):
        """Get Site DUA template."""
        template = dua_service.get_template(DUAType.SITE_DUA)
        assert template.dua_type == DUAType.SITE_DUA
        assert len(template.permitted_uses) > 0
        assert len(template.prohibited_uses) > 0
        assert template.retention_period_days == 2190

    def test_sponsor_dua_template(self, dua_service: DataUseAgreementService):
        """Get Sponsor DUA template."""
        template = dua_service.get_template(DUAType.SPONSOR_DUA)
        assert template.dua_type == DUAType.SPONSOR_DUA
        assert DataCategory.DE_IDENTIFIED in template.data_categories

    def test_research_dua_template(self, dua_service: DataUseAgreementService):
        """Get Research DUA template."""
        template = dua_service.get_template(DUAType.RESEARCH_DUA)
        assert template.dua_type == DUAType.RESEARCH_DUA
        assert template.retention_period_days == 3650

    def test_vendor_dua_template(self, dua_service: DataUseAgreementService):
        """Get Vendor DUA template."""
        template = dua_service.get_template(DUAType.VENDOR_DUA)
        assert template.dua_type == DUAType.VENDOR_DUA
        assert DataCategory.PHI in template.data_categories

    def test_all_templates_available(self, dua_service: DataUseAgreementService):
        """All DUA types have templates."""
        for dua_type in DUAType:
            template = dua_service.get_template(dua_type)
            assert template.dua_type == dua_type


# ===========================================================================
# 7. Deletion Request Lifecycle Tests
# ===========================================================================


class TestDeletionLifecycle:
    """Test deletion request full lifecycle."""

    def test_create_deletion_request(self, deletion_service: DeletionService):
        """Create a deletion request in RECEIVED status."""
        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-1",
                requester="patient-1",
                reason="Right to be forgotten",
                scope=DeletionScope.ALL,
            )
        )
        assert req.status == DeletionStatus.RECEIVED
        assert req.patient_id == "patient-1"
        assert req.requester == "patient-1"
        assert req.id is not None
        assert len(req.audit_entries) == 1

    def test_full_deletion_lifecycle(self, deletion_service: DeletionService):
        """Request -> Validate -> Execute -> Certificate."""
        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-2",
                requester="patient-2",
                reason="GDPR request",
            )
        )
        assert req.status == DeletionStatus.RECEIVED

        # Validate
        validated = deletion_service.validate_request(req.id, validator="admin")
        assert validated.status == DeletionStatus.VALIDATING

        # Execute
        executed = deletion_service.execute_deletion(req.id, executor="admin")
        assert executed.status == DeletionStatus.COMPLETED
        assert len(executed.deleted_items) > 0
        assert executed.completed_at is not None

        # Certificate
        cert = deletion_service.get_deletion_certificate(req.id)
        assert cert.deletion_request_id == req.id
        assert cert.patient_id == "patient-2"
        assert len(cert.deleted_items) > 0

    def test_execute_without_validation(self, deletion_service: DeletionService):
        """Can execute directly from RECEIVED status."""
        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-3",
                requester="admin",
                reason="Admin deletion",
            )
        )
        executed = deletion_service.execute_deletion(req.id, executor="admin")
        assert executed.status == DeletionStatus.COMPLETED

    def test_list_deletion_requests(self, deletion_service: DeletionService):
        """List deletion requests with filters."""
        deletion_service.create_request(
            DeletionRequestCreate(patient_id="p1", requester="r1", reason="r")
        )
        deletion_service.create_request(
            DeletionRequestCreate(patient_id="p2", requester="r2", reason="r")
        )
        all_requests = deletion_service.list_requests()
        assert len(all_requests) == 2

        p1_requests = deletion_service.list_requests(patient_id="p1")
        assert len(p1_requests) == 1

    def test_get_deletion_request_not_found(self, deletion_service: DeletionService):
        """Return None for non-existent request."""
        assert deletion_service.get_request("nonexistent") is None


# ===========================================================================
# 8. Legal Hold Tests
# ===========================================================================


class TestLegalHold:
    """Test legal hold blocking deletion."""

    def test_legal_hold_blocks_deletion(self, deletion_service: DeletionService):
        """Deletion denied when patient has active legal hold."""
        deletion_service.add_legal_hold("patient-hold", "Active litigation - Case #123")
        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-hold",
                requester="patient-hold",
                reason="Deletion request",
            )
        )
        validated = deletion_service.validate_request(req.id)
        assert validated.status == DeletionStatus.DENIED
        assert "Legal hold" in validated.denial_reason

    def test_legal_hold_removed_allows_deletion(self, deletion_service: DeletionService):
        """Deletion proceeds after legal hold is removed."""
        deletion_service.add_legal_hold("patient-cleared", "Investigation")
        deletion_service.remove_legal_hold("patient-cleared", "Investigation")

        assert not deletion_service.has_legal_hold("patient-cleared")

        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-cleared",
                requester="patient-cleared",
                reason="Post-hold deletion",
            )
        )
        validated = deletion_service.validate_request(req.id)
        assert validated.status == DeletionStatus.VALIDATING

    def test_has_legal_hold(self, deletion_service: DeletionService):
        """Check legal hold status."""
        assert not deletion_service.has_legal_hold("patient-x")
        deletion_service.add_legal_hold("patient-x", "Reason 1")
        assert deletion_service.has_legal_hold("patient-x")


# ===========================================================================
# 9. Retention Override Tests
# ===========================================================================


class TestRetentionOverride:
    """Test clinical trial data retention requirements."""

    def test_retention_blocks_deletion_within_6_years(self, deletion_service: DeletionService):
        """Deletion denied when clinical trial data is within 6-year retention."""
        recent_enrollment = datetime.now(timezone.utc) - timedelta(days=365)  # 1 year ago
        deletion_service.record_trial_enrollment("patient-trial", recent_enrollment)

        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-trial",
                requester="patient-trial",
                reason="Deletion request",
            )
        )
        validated = deletion_service.validate_request(req.id)
        assert validated.status == DeletionStatus.DENIED
        assert "21 CFR Part 11" in validated.denial_reason

    def test_retention_allows_deletion_after_6_years(self, deletion_service: DeletionService):
        """Deletion allowed when clinical trial data is past 6-year retention."""
        old_enrollment = datetime.now(timezone.utc) - timedelta(days=2555)  # ~7 years ago
        deletion_service.record_trial_enrollment("patient-old-trial", old_enrollment)

        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-old-trial",
                requester="patient-old-trial",
                reason="Deletion request",
            )
        )
        validated = deletion_service.validate_request(req.id)
        assert validated.status == DeletionStatus.VALIDATING

    def test_no_enrollment_allows_deletion(self, deletion_service: DeletionService):
        """Deletion allowed when patient has no trial enrollment record."""
        is_blocked, reason = deletion_service.check_retention_override("patient-no-trial")
        assert not is_blocked
        assert reason == ""


# ===========================================================================
# 10. Partial Deletion Tests
# ===========================================================================


class TestPartialDeletion:
    """Test scope-specific deletion (ALL vs PHI_ONLY vs SPECIFIC_RECORDS)."""

    def test_all_scope_deletion(self, deletion_service: DeletionService):
        """ALL scope deletes all deletable stores."""
        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-all",
                requester="patient-all",
                scope=DeletionScope.ALL,
            )
        )
        result = deletion_service.execute_deletion(req.id)
        assert result.status == DeletionStatus.COMPLETED
        assert "clinical_facts" in result.deleted_items
        assert "documents" in result.deleted_items
        assert "screening_results" in result.deleted_items

    def test_phi_only_scope_deletion(self, deletion_service: DeletionService):
        """PHI_ONLY scope produces PARTIALLY_COMPLETED."""
        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-phi",
                requester="patient-phi",
                scope=DeletionScope.PHI_ONLY,
            )
        )
        result = deletion_service.execute_deletion(req.id)
        assert result.status == DeletionStatus.PARTIALLY_COMPLETED
        assert "clinical_facts" in result.deleted_items
        assert "documents" in result.deleted_items

    def test_specific_records_deletion(self, deletion_service: DeletionService):
        """SPECIFIC_RECORDS scope only deletes specified stores."""
        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-specific",
                requester="patient-specific",
                scope=DeletionScope.SPECIFIC_RECORDS,
                specific_records=["documents"],
            )
        )
        result = deletion_service.execute_deletion(req.id)
        assert "documents" in result.deleted_items
        assert len(result.deleted_items) == 1

    def test_audit_logs_always_retained(self, deletion_service: DeletionService):
        """Audit logs are retained regardless of scope."""
        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-audit",
                requester="patient-audit",
                scope=DeletionScope.ALL,
            )
        )
        result = deletion_service.execute_deletion(req.id)
        retained_text = " ".join(result.retained_items)
        assert "audit_logs" in retained_text

    def test_data_deletion_tracking(self, deletion_service: DeletionService):
        """Verify data is tracked as deleted after execution."""
        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-tracked",
                requester="admin",
                scope=DeletionScope.ALL,
            )
        )
        deletion_service.execute_deletion(req.id)
        assert deletion_service.is_data_deleted("patient-tracked", "clinical_facts")
        assert deletion_service.is_data_deleted("patient-tracked", "documents")
        assert not deletion_service.is_data_deleted("patient-other", "clinical_facts")


# ===========================================================================
# 11. Deletion Certificate Tests
# ===========================================================================


class TestDeletionCertificate:
    """Test deletion certificate generation."""

    def test_certificate_for_completed_deletion(self, deletion_service: DeletionService):
        """Generate certificate for completed deletion."""
        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-cert",
                requester="patient-cert",
            )
        )
        deletion_service.execute_deletion(req.id)
        cert = deletion_service.get_deletion_certificate(req.id)
        assert cert.certificate_id is not None
        assert cert.patient_id == "patient-cert"
        assert len(cert.deleted_items) > 0
        assert "compliance" in cert.compliance_statement.lower()
        assert "backup" in cert.backup_note.lower()

    def test_certificate_not_available_for_pending(self, deletion_service: DeletionService):
        """Certificate not available for non-completed requests."""
        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-pending",
                requester="patient-pending",
            )
        )
        with pytest.raises(ValueError, match="completed"):
            deletion_service.get_deletion_certificate(req.id)

    def test_certificate_for_partially_completed(self, deletion_service: DeletionService):
        """Certificate available for partially completed deletions."""
        req = deletion_service.create_request(
            DeletionRequestCreate(
                patient_id="patient-partial",
                requester="patient-partial",
                scope=DeletionScope.PHI_ONLY,
            )
        )
        deletion_service.execute_deletion(req.id)
        cert = deletion_service.get_deletion_certificate(req.id)
        assert len(cert.exceptions) > 0

    def test_certificate_not_found(self, deletion_service: DeletionService):
        """Certificate request for non-existent deletion raises error."""
        with pytest.raises(ValueError, match="not found"):
            deletion_service.get_deletion_certificate("nonexistent")


# ===========================================================================
# 12. Data Access Logging Tests
# ===========================================================================


class TestAccessLogging:
    """Test data access logging."""

    def test_record_access(self, dua_service: DataUseAgreementService):
        """Record a data access event."""
        entry = dua_service.record_access(
            AccessLogCreate(
                user_id="user-1",
                patient_id="patient-1",
                data_category=DataCategory.PHI,
                purpose="screening",
                dua_id="dua-123",
            )
        )
        assert entry.user_id == "user-1"
        assert entry.patient_id == "patient-1"
        assert entry.dua_id == "dua-123"

    def test_query_access_log_by_user(self, dua_service: DataUseAgreementService):
        """Query access logs filtered by user."""
        dua_service.record_access(
            AccessLogCreate(user_id="user-a", data_category=DataCategory.PHI, purpose="screening")
        )
        dua_service.record_access(
            AccessLogCreate(user_id="user-b", data_category=DataCategory.PHI, purpose="screening")
        )
        from app.schemas.data_governance import AccessLogQuery
        results = dua_service.query_access_log(AccessLogQuery(user_id="user-a"))
        assert len(results) == 1
        assert results[0].user_id == "user-a"

    def test_query_access_log_by_category(self, dua_service: DataUseAgreementService):
        """Query access logs filtered by data category."""
        dua_service.record_access(
            AccessLogCreate(user_id="user-1", data_category=DataCategory.PHI, purpose="screening")
        )
        dua_service.record_access(
            AccessLogCreate(user_id="user-1", data_category=DataCategory.AGGREGATE, purpose="reporting")
        )
        from app.schemas.data_governance import AccessLogQuery
        results = dua_service.query_access_log(AccessLogQuery(data_category=DataCategory.PHI))
        assert len(results) == 1

    def test_query_access_log_by_dua(self, dua_service: DataUseAgreementService):
        """Query access logs filtered by DUA."""
        dua_service.record_access(
            AccessLogCreate(user_id="user-1", data_category=DataCategory.PHI, purpose="s", dua_id="dua-1")
        )
        dua_service.record_access(
            AccessLogCreate(user_id="user-1", data_category=DataCategory.PHI, purpose="s", dua_id="dua-2")
        )
        from app.schemas.data_governance import AccessLogQuery
        results = dua_service.query_access_log(AccessLogQuery(dua_id="dua-1"))
        assert len(results) == 1

    def test_get_dua_accesses(self, dua_service: DataUseAgreementService):
        """Get all accesses for a specific DUA."""
        dua_service.record_access(
            AccessLogCreate(user_id="u1", data_category=DataCategory.PHI, purpose="s", dua_id="dua-x")
        )
        dua_service.record_access(
            AccessLogCreate(user_id="u2", data_category=DataCategory.PHI, purpose="s", dua_id="dua-x")
        )
        dua_service.record_access(
            AccessLogCreate(user_id="u3", data_category=DataCategory.PHI, purpose="s", dua_id="dua-y")
        )
        accesses = dua_service.get_dua_accesses("dua-x")
        assert len(accesses) == 2


# ===========================================================================
# 13. Suspicious Access Detection Tests
# ===========================================================================


class TestSuspiciousAccess:
    """Test detection of accesses not covered by active DUAs."""

    def test_detect_uncovered_access(self, dua_service: DataUseAgreementService):
        """Detect access without DUA coverage."""
        dua_service.record_access(
            AccessLogCreate(user_id="user-1", data_category=DataCategory.PHI, purpose="screening", dua_id=None)
        )
        report = dua_service.get_suspicious_accesses()
        assert report.total_uncovered == 1
        assert len(report.entries) == 1

    def test_covered_access_not_flagged(self, dua_service: DataUseAgreementService):
        """Access covered by active DUA is not flagged."""
        dua = dua_service.create_dua(
            DUACreate(
                title="Active DUA",
                dua_type=DUAType.SITE_DUA,
                parties=["A"],
                data_categories=[DataCategory.PHI],
            )
        )
        dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.PENDING_REVIEW))
        dua_service.update_dua(dua.id, DUAUpdate(status=DUAStatus.ACTIVE, signed_by="Admin"))

        dua_service.record_access(
            AccessLogCreate(user_id="user-1", data_category=DataCategory.PHI, purpose="screening", dua_id=dua.id)
        )
        report = dua_service.get_suspicious_accesses()
        assert report.total_uncovered == 0

    def test_access_with_inactive_dua_flagged(self, dua_service: DataUseAgreementService):
        """Access linked to non-active DUA is flagged as suspicious."""
        dua = dua_service.create_dua(
            DUACreate(
                title="Draft DUA",
                dua_type=DUAType.SITE_DUA,
                parties=["A"],
                data_categories=[DataCategory.PHI],
            )
        )
        # DUA stays in DRAFT - not active
        dua_service.record_access(
            AccessLogCreate(user_id="user-1", data_category=DataCategory.PHI, purpose="screening", dua_id=dua.id)
        )
        report = dua_service.get_suspicious_accesses()
        assert report.total_uncovered == 1


# ===========================================================================
# 14. Service Stats Tests
# ===========================================================================


class TestServiceStats:
    """Test service statistics."""

    def test_dua_service_stats(self, dua_service: DataUseAgreementService):
        """DUA service returns useful stats."""
        dua_service.create_dua(
            DUACreate(title="DUA 1", dua_type=DUAType.SITE_DUA, parties=["A"], data_categories=[DataCategory.PHI])
        )
        dua_service.record_access(
            AccessLogCreate(user_id="u1", data_category=DataCategory.PHI, purpose="s")
        )
        stats = dua_service.get_stats()
        assert stats["total_duas"] == 1
        assert stats["total_access_log_entries"] == 1

    def test_deletion_service_stats(self, deletion_service: DeletionService):
        """Deletion service returns useful stats."""
        deletion_service.create_request(
            DeletionRequestCreate(patient_id="p1", requester="r1")
        )
        deletion_service.add_legal_hold("p2", "Litigation")
        stats = deletion_service.get_stats()
        assert stats["total_requests"] == 1
        assert stats["total_legal_holds"] == 1


# ===========================================================================
# 15. API Endpoint Tests
# ===========================================================================


class TestAPIEndpoints:
    """Test API endpoints via TestClient."""

    def test_create_dua_api(self, client: TestClient):
        """POST /governance/dua creates a DUA."""
        response = client.post(
            "/api/v1/governance/dua",
            json={
                "title": "API Test DUA",
                "dua_type": "SITE_DUA",
                "parties": ["Platform", "Site"],
                "data_categories": ["PHI"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "API Test DUA"
        assert data["status"] == "DRAFT"

    def test_list_duas_api(self, client: TestClient):
        """GET /governance/dua lists all DUAs."""
        client.post(
            "/api/v1/governance/dua",
            json={
                "title": "List Test",
                "dua_type": "SITE_DUA",
                "parties": ["A"],
                "data_categories": ["PHI"],
            },
        )
        response = client.get("/api/v1/governance/dua")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_get_dua_api(self, client: TestClient):
        """GET /governance/dua/{id} returns DUA detail."""
        create_resp = client.post(
            "/api/v1/governance/dua",
            json={
                "title": "Detail Test",
                "dua_type": "VENDOR_DUA",
                "parties": ["A"],
                "data_categories": ["DE_IDENTIFIED"],
            },
        )
        dua_id = create_resp.json()["id"]
        response = client.get(f"/api/v1/governance/dua/{dua_id}")
        assert response.status_code == 200
        assert response.json()["id"] == dua_id

    def test_get_dua_not_found_api(self, client: TestClient):
        """GET /governance/dua/{id} returns 404 for missing DUA."""
        response = client.get("/api/v1/governance/dua/nonexistent")
        assert response.status_code == 404

    def test_update_dua_api(self, client: TestClient):
        """PUT /governance/dua/{id} updates DUA."""
        create_resp = client.post(
            "/api/v1/governance/dua",
            json={
                "title": "Update Test",
                "dua_type": "SITE_DUA",
                "parties": ["A"],
                "data_categories": ["PHI"],
            },
        )
        dua_id = create_resp.json()["id"]
        response = client.put(
            f"/api/v1/governance/dua/{dua_id}",
            json={"status": "PENDING_REVIEW"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "PENDING_REVIEW"

    def test_check_compliance_api(self, client: TestClient):
        """POST /governance/dua/check-access checks compliance."""
        response = client.post(
            "/api/v1/governance/dua/check-access",
            json={
                "user_id": "user-1",
                "data_category": "PHI",
                "purpose": "screening",
            },
        )
        assert response.status_code == 200
        assert response.json()["decision"] == "DENIED"  # No active DUAs

    def test_create_deletion_request_api(self, client: TestClient):
        """POST /governance/deletion-requests creates a request."""
        response = client.post(
            "/api/v1/governance/deletion-requests",
            json={
                "patient_id": "patient-api",
                "requester": "patient-api",
                "reason": "Right to deletion",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "RECEIVED"
        assert data["patient_id"] == "patient-api"

    def test_list_deletion_requests_api(self, client: TestClient):
        """GET /governance/deletion-requests lists requests."""
        client.post(
            "/api/v1/governance/deletion-requests",
            json={"patient_id": "p1", "requester": "r1"},
        )
        response = client.get("/api/v1/governance/deletion-requests")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_get_deletion_request_api(self, client: TestClient):
        """GET /governance/deletion-requests/{id} returns detail."""
        create_resp = client.post(
            "/api/v1/governance/deletion-requests",
            json={"patient_id": "p-detail", "requester": "r-detail"},
        )
        req_id = create_resp.json()["id"]
        response = client.get(f"/api/v1/governance/deletion-requests/{req_id}")
        assert response.status_code == 200
        assert response.json()["id"] == req_id

    def test_execute_deletion_api(self, client: TestClient):
        """POST /governance/deletion-requests/{id}/execute triggers deletion."""
        create_resp = client.post(
            "/api/v1/governance/deletion-requests",
            json={"patient_id": "p-exec", "requester": "r-exec"},
        )
        req_id = create_resp.json()["id"]
        response = client.post(f"/api/v1/governance/deletion-requests/{req_id}/execute?executor=admin")
        assert response.status_code == 200
        assert response.json()["status"] in ("COMPLETED", "PARTIALLY_COMPLETED")

    def test_get_deletion_certificate_api(self, client: TestClient):
        """GET /governance/deletion-requests/{id}/certificate returns cert."""
        create_resp = client.post(
            "/api/v1/governance/deletion-requests",
            json={"patient_id": "p-cert", "requester": "r-cert"},
        )
        req_id = create_resp.json()["id"]
        client.post(f"/api/v1/governance/deletion-requests/{req_id}/execute?executor=admin")
        response = client.get(f"/api/v1/governance/deletion-requests/{req_id}/certificate")
        assert response.status_code == 200
        assert "certificate_id" in response.json()

    def test_record_access_api(self, client: TestClient):
        """POST /governance/access-log records access."""
        response = client.post(
            "/api/v1/governance/access-log",
            json={
                "user_id": "user-api",
                "data_category": "PHI",
                "purpose": "screening",
            },
        )
        assert response.status_code == 201
        assert response.json()["user_id"] == "user-api"

    def test_query_access_log_api(self, client: TestClient):
        """GET /governance/access-log queries logs."""
        client.post(
            "/api/v1/governance/access-log",
            json={"user_id": "api-user", "data_category": "PHI", "purpose": "test"},
        )
        response = client.get("/api/v1/governance/access-log?user_id=api-user")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_suspicious_access_api(self, client: TestClient):
        """GET /governance/access-log/suspicious returns report."""
        client.post(
            "/api/v1/governance/access-log",
            json={"user_id": "sus-user", "data_category": "PHI", "purpose": "unknown"},
        )
        response = client.get("/api/v1/governance/access-log/suspicious")
        assert response.status_code == 200
        data = response.json()
        assert data["total_uncovered"] >= 1

    def test_dua_template_api(self, client: TestClient):
        """GET /governance/dua/templates/{type} returns template."""
        response = client.get("/api/v1/governance/dua/templates/SITE_DUA")
        assert response.status_code == 200
        data = response.json()
        assert data["dua_type"] == "SITE_DUA"

    def test_expiring_duas_api(self, client: TestClient):
        """GET /governance/dua/expiring returns expiring DUAs."""
        response = client.get("/api/v1/governance/dua/expiring?within_days=30")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ===========================================================================
# 16. Edge Cases and Error Handling
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_update_nonexistent_dua(self, dua_service: DataUseAgreementService):
        """Updating a non-existent DUA raises error."""
        with pytest.raises(ValueError, match="not found"):
            dua_service.update_dua("nonexistent", DUAUpdate(title="Nope"))

    def test_validate_already_validated(self, deletion_service: DeletionService):
        """Cannot validate a request that is not in RECEIVED status."""
        req = deletion_service.create_request(
            DeletionRequestCreate(patient_id="p1", requester="r1")
        )
        deletion_service.validate_request(req.id)
        with pytest.raises(ValueError, match="expected RECEIVED"):
            deletion_service.validate_request(req.id)

    def test_execute_completed_request(self, deletion_service: DeletionService):
        """Cannot execute an already completed request."""
        req = deletion_service.create_request(
            DeletionRequestCreate(patient_id="p1", requester="r1")
        )
        deletion_service.execute_deletion(req.id)
        with pytest.raises(ValueError, match="expected VALIDATING or RECEIVED"):
            deletion_service.execute_deletion(req.id)

    def test_execute_denied_request(self, deletion_service: DeletionService):
        """Cannot execute a denied request."""
        deletion_service.add_legal_hold("p-denied", "Hold")
        req = deletion_service.create_request(
            DeletionRequestCreate(patient_id="p-denied", requester="r")
        )
        deletion_service.validate_request(req.id)  # Will be denied
        with pytest.raises(ValueError, match="expected VALIDATING or RECEIVED"):
            deletion_service.execute_deletion(req.id)

    def test_singleton_pattern(self):
        """Singleton services return same instance."""
        svc1 = get_dua_service()
        svc2 = get_dua_service()
        assert svc1 is svc2

        del_svc1 = get_deletion_service()
        del_svc2 = get_deletion_service()
        assert del_svc1 is del_svc2

    def test_deletion_audit_trail(self, deletion_service: DeletionService):
        """Verify deletion request maintains complete audit trail."""
        req = deletion_service.create_request(
            DeletionRequestCreate(patient_id="p-audit", requester="r-audit", reason="Test")
        )
        assert len(req.audit_entries) == 1  # REQUEST_RECEIVED

        deletion_service.validate_request(req.id)
        validated = deletion_service.get_request(req.id)
        assert len(validated.audit_entries) >= 3  # + VALIDATION_STARTED + VALIDATION_PASSED

        deletion_service.execute_deletion(req.id)
        executed = deletion_service.get_request(req.id)
        assert len(executed.audit_entries) >= 6  # + DELETION_STARTED + per-store + COMPLETED
