"""Tests for Vendor Risk Management (COO-3).

Tests verify:
- Pre-populated vendor records (12 seed vendors)
- All vendor categories represented
- Vendor CRUD (create, read, update, list with filters)
- Risk assessment scoring (weighted average calculation)
- Auto risk-level assignment from scores
- Certification expiry tracking
- Vendor lifecycle (suspend, reactivate, status transitions)
- Contract renewal detection
- PHI access vendor listing
- Portfolio metrics calculation
- API endpoint integration tests
- Edge cases (assessment on terminated vendor, duplicate suspend, etc.)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.vendor_management import router as vendor_management_router
from app.schemas.vendor_management import (
    AssessmentListResponse,
    AssessmentRequest,
    CertificationAlert,
    CertificationName,
    CertificationStatus,
    ComplianceCertification,
    ContractRenewal,
    DataAccessLevel,
    RiskLevel,
    VendorCategory,
    VendorCreate,
    VendorListResponse,
    VendorMetrics,
    VendorRecord,
    VendorRiskAssessment,
    VendorStatus,
    VendorUpdate,
)
from app.services.vendor_management_service import (
    ASSESSMENT_WEIGHTS,
    VendorManagementService,
    _risk_level_from_score,
    get_vendor_management_service,
    reset_vendor_management_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons between tests."""
    reset_vendor_management_service()
    yield
    reset_vendor_management_service()


@pytest.fixture
def service() -> VendorManagementService:
    """Get a fresh VendorManagementService instance."""
    return get_vendor_management_service()


@pytest.fixture
def client() -> TestClient:
    """Create test client with vendor management router."""
    app = FastAPI()
    app.include_router(vendor_management_router)
    return TestClient(app)


# ===========================================================================
# 1. Pre-populated Vendor Tests
# ===========================================================================


class TestSeedVendors:
    """Tests for pre-populated vendor records."""

    def test_vendors_loaded(self, service: VendorManagementService):
        """Seed vendors are loaded on initialization."""
        vendors, total = service.list_vendors()
        assert total == 12, f"Expected 12 seed vendors, got {total}"

    def test_all_categories_represented(self, service: VendorManagementService):
        """Multiple vendor categories are represented."""
        vendors, _ = service.list_vendors()
        categories = {v.category for v in vendors}
        assert VendorCategory.CLOUD_INFRASTRUCTURE in categories
        assert VendorCategory.DATA_PROCESSING in categories
        assert VendorCategory.CLINICAL_OPERATIONS in categories
        assert VendorCategory.SECURITY in categories
        assert VendorCategory.INTEGRATION in categories
        assert VendorCategory.ANALYTICS in categories
        assert VendorCategory.COMPLIANCE in categories

    def test_vendors_have_unique_ids(self, service: VendorManagementService):
        """All vendor IDs are unique."""
        vendors, _ = service.list_vendors()
        ids = [v.id for v in vendors]
        assert len(ids) == len(set(ids)), "Duplicate vendor IDs found"

    def test_vendors_have_required_fields(self, service: VendorManagementService):
        """All vendors have required fields populated."""
        vendors, _ = service.list_vendors()
        for v in vendors:
            assert v.id, "Vendor missing ID"
            assert v.name, f"Vendor {v.id} missing name"
            assert v.category in VendorCategory
            assert v.status in VendorStatus
            assert v.risk_level in RiskLevel
            assert v.data_access_level in DataAccessLevel
            assert v.created_at is not None
            assert v.updated_at is not None

    def test_aws_vendor_details(self, service: VendorManagementService):
        """AWS vendor has correct details."""
        vendor = service.get_vendor("vendor-001")
        assert vendor is not None
        assert vendor.name == "Amazon Web Services (AWS)"
        assert vendor.category == VendorCategory.CLOUD_INFRASTRUCTURE
        assert vendor.risk_level == RiskLevel.CRITICAL
        assert vendor.data_access_level == DataAccessLevel.PHI
        assert len(vendor.certifications) >= 3

    def test_metriport_vendor_details(self, service: VendorManagementService):
        """Metriport vendor has correct details."""
        vendor = service.get_vendor("vendor-002")
        assert vendor is not None
        assert vendor.name == "Metriport"
        assert vendor.category == VendorCategory.INTEGRATION
        assert vendor.risk_level == RiskLevel.HIGH

    def test_anthropic_vendor_details(self, service: VendorManagementService):
        """Anthropic vendor has correct details."""
        vendor = service.get_vendor("vendor-005")
        assert vendor is not None
        assert vendor.name == "Anthropic"
        assert vendor.category == VendorCategory.ANALYTICS
        assert vendor.data_access_level == DataAccessLevel.METADATA

    def test_phi_vendors_exist(self, service: VendorManagementService):
        """There are vendors with PHI access."""
        phi_vendors = service.get_vendors_by_data_access(DataAccessLevel.PHI)
        assert len(phi_vendors) >= 4

    def test_critical_vendors_exist(self, service: VendorManagementService):
        """There are CRITICAL risk vendors."""
        vendors, _ = service.list_vendors(risk_level=RiskLevel.CRITICAL)
        assert len(vendors) >= 1

    def test_vendors_sorted_by_name(self, service: VendorManagementService):
        """Vendors are returned sorted by name."""
        vendors, _ = service.list_vendors()
        names = [v.name for v in vendors]
        assert names == sorted(names)


# ===========================================================================
# 2. Vendor CRUD Tests
# ===========================================================================


class TestVendorCRUD:
    """Tests for vendor create, read, update, list operations."""

    def test_create_vendor(self, service: VendorManagementService):
        """Create a new vendor."""
        request = VendorCreate(
            name="TestVendor Corp",
            category=VendorCategory.ANALYTICS,
            description="Test vendor for analytics",
            contact_email="test@testvendor.com",
            annual_cost=50000.0,
            data_access_level=DataAccessLevel.METADATA,
        )
        vendor = service.create_vendor(request)
        assert vendor.name == "TestVendor Corp"
        assert vendor.category == VendorCategory.ANALYTICS
        assert vendor.id.startswith("vendor-")
        assert vendor.risk_score == 0.0
        assert vendor.status == VendorStatus.ACTIVE

    def test_create_vendor_generates_unique_id(self, service: VendorManagementService):
        """Each created vendor gets a unique ID."""
        r1 = VendorCreate(name="V1", category=VendorCategory.SECURITY)
        r2 = VendorCreate(name="V2", category=VendorCategory.SECURITY)
        v1 = service.create_vendor(r1)
        v2 = service.create_vendor(r2)
        assert v1.id != v2.id

    def test_get_vendor_by_id(self, service: VendorManagementService):
        """Get a specific vendor by ID."""
        vendor = service.get_vendor("vendor-001")
        assert vendor is not None
        assert vendor.id == "vendor-001"

    def test_get_nonexistent_vendor(self, service: VendorManagementService):
        """Getting nonexistent vendor returns None."""
        vendor = service.get_vendor("nonexistent")
        assert vendor is None

    def test_update_vendor_name(self, service: VendorManagementService):
        """Update a vendor's name."""
        update = VendorUpdate(name="AWS Updated")
        result = service.update_vendor("vendor-001", update)
        assert result is not None
        assert result.name == "AWS Updated"

    def test_update_vendor_risk_level(self, service: VendorManagementService):
        """Update a vendor's risk level."""
        update = VendorUpdate(risk_level=RiskLevel.LOW)
        result = service.update_vendor("vendor-001", update)
        assert result is not None
        assert result.risk_level == RiskLevel.LOW

    def test_update_vendor_preserves_unchanged_fields(
        self, service: VendorManagementService
    ):
        """Updating specific fields preserves other fields."""
        original = service.get_vendor("vendor-001")
        assert original is not None
        update = VendorUpdate(notes="Updated note")
        result = service.update_vendor("vendor-001", update)
        assert result is not None
        assert result.notes == "Updated note"
        assert result.name == original.name
        assert result.category == original.category

    def test_update_nonexistent_vendor(self, service: VendorManagementService):
        """Updating nonexistent vendor returns None."""
        update = VendorUpdate(name="X")
        result = service.update_vendor("nonexistent", update)
        assert result is None

    def test_update_vendor_updates_timestamp(self, service: VendorManagementService):
        """Updating a vendor changes updated_at timestamp."""
        original = service.get_vendor("vendor-007")
        assert original is not None
        update = VendorUpdate(notes="timestamp test")
        result = service.update_vendor("vendor-007", update)
        assert result is not None
        assert result.updated_at >= original.updated_at

    def test_list_vendors_default(self, service: VendorManagementService):
        """List all vendors without filters."""
        vendors, total = service.list_vendors()
        assert total == 12
        assert len(vendors) == 12

    def test_list_vendors_filter_by_category(self, service: VendorManagementService):
        """Filter vendors by category."""
        vendors, total = service.list_vendors(
            category=VendorCategory.CLOUD_INFRASTRUCTURE
        )
        assert total >= 1
        for v in vendors:
            assert v.category == VendorCategory.CLOUD_INFRASTRUCTURE

    def test_list_vendors_filter_by_risk_level(self, service: VendorManagementService):
        """Filter vendors by risk level."""
        vendors, total = service.list_vendors(risk_level=RiskLevel.HIGH)
        assert total >= 1
        for v in vendors:
            assert v.risk_level == RiskLevel.HIGH

    def test_list_vendors_filter_by_status(self, service: VendorManagementService):
        """Filter vendors by status."""
        vendors, total = service.list_vendors(status=VendorStatus.ACTIVE)
        assert total >= 1
        for v in vendors:
            assert v.status == VendorStatus.ACTIVE

    def test_list_vendors_pagination(self, service: VendorManagementService):
        """List vendors with pagination."""
        page1, total = service.list_vendors(limit=5, offset=0)
        page2, _ = service.list_vendors(limit=5, offset=5)
        assert total == 12
        assert len(page1) == 5
        assert len(page2) == 5
        # No overlap
        ids1 = {v.id for v in page1}
        ids2 = {v.id for v in page2}
        assert ids1.isdisjoint(ids2)

    def test_list_vendors_combined_filters(self, service: VendorManagementService):
        """Apply multiple filters simultaneously."""
        vendors, total = service.list_vendors(
            category=VendorCategory.CLOUD_INFRASTRUCTURE,
            status=VendorStatus.ACTIVE,
        )
        assert total >= 1
        for v in vendors:
            assert v.category == VendorCategory.CLOUD_INFRASTRUCTURE
            assert v.status == VendorStatus.ACTIVE

    def test_list_vendors_no_matches(self, service: VendorManagementService):
        """Empty result for non-matching filter."""
        vendors, total = service.list_vendors(status=VendorStatus.TERMINATED)
        assert total == 0
        assert len(vendors) == 0


# ===========================================================================
# 3. Risk Assessment Tests
# ===========================================================================


class TestRiskAssessment:
    """Tests for risk assessment scoring and risk level assignment."""

    def test_conduct_assessment(self, service: VendorManagementService):
        """Conduct a basic assessment."""
        request = AssessmentRequest(
            assessed_by="test-assessor",
            data_handling_score=7.0,
            security_posture_score=6.0,
            compliance_score=8.0,
            business_continuity_score=5.0,
        )
        assessment = service.conduct_assessment("vendor-001", request)
        assert assessment is not None
        assert assessment.vendor_id == "vendor-001"
        assert assessment.assessed_by == "test-assessor"
        assert assessment.id.startswith("assess-")

    def test_weighted_average_calculation(self, service: VendorManagementService):
        """Overall score is weighted average of dimension scores."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=5.0,
            security_posture_score=5.0,
            compliance_score=5.0,
            business_continuity_score=5.0,
        )
        assessment = service.conduct_assessment("vendor-001", request)
        assert assessment is not None
        # All 5/10 -> all contribute 50% -> weighted average = 50
        expected = (
            5.0 * 10 * ASSESSMENT_WEIGHTS["data_handling"]
            + 5.0 * 10 * ASSESSMENT_WEIGHTS["security_posture"]
            + 5.0 * 10 * ASSESSMENT_WEIGHTS["compliance"]
            + 5.0 * 10 * ASSESSMENT_WEIGHTS["business_continuity"]
        )
        assert assessment.overall_risk_score == round(expected, 2)

    def test_max_score_assessment(self, service: VendorManagementService):
        """Perfect 10s across the board yield score of 100."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=10.0,
            security_posture_score=10.0,
            compliance_score=10.0,
            business_continuity_score=10.0,
        )
        assessment = service.conduct_assessment("vendor-001", request)
        assert assessment is not None
        assert assessment.overall_risk_score == 100.0

    def test_min_score_assessment(self, service: VendorManagementService):
        """All zeros yield score of 0."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=0.0,
            security_posture_score=0.0,
            compliance_score=0.0,
            business_continuity_score=0.0,
        )
        assessment = service.conduct_assessment("vendor-001", request)
        assert assessment is not None
        assert assessment.overall_risk_score == 0.0

    def test_risk_level_critical(self, service: VendorManagementService):
        """Score >= 76 maps to CRITICAL."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=8.0,
            security_posture_score=8.0,
            compliance_score=8.0,
            business_continuity_score=8.0,
        )
        assessment = service.conduct_assessment("vendor-007", request)
        assert assessment is not None
        assert assessment.risk_level == RiskLevel.CRITICAL

    def test_risk_level_high(self, service: VendorManagementService):
        """Score 51-75 maps to HIGH."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=6.0,
            security_posture_score=6.0,
            compliance_score=6.0,
            business_continuity_score=6.0,
        )
        assessment = service.conduct_assessment("vendor-007", request)
        assert assessment is not None
        assert assessment.risk_level == RiskLevel.HIGH

    def test_risk_level_medium(self, service: VendorManagementService):
        """Score 26-50 maps to MEDIUM."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=3.0,
            security_posture_score=3.0,
            compliance_score=3.0,
            business_continuity_score=3.0,
        )
        assessment = service.conduct_assessment("vendor-007", request)
        assert assessment is not None
        assert assessment.risk_level == RiskLevel.MEDIUM

    def test_risk_level_low(self, service: VendorManagementService):
        """Score 1-25 maps to LOW."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=2.0,
            security_posture_score=2.0,
            compliance_score=2.0,
            business_continuity_score=2.0,
        )
        assessment = service.conduct_assessment("vendor-007", request)
        assert assessment is not None
        assert assessment.risk_level == RiskLevel.LOW

    def test_risk_level_minimal(self, service: VendorManagementService):
        """Score 0 maps to MINIMAL."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=0.0,
            security_posture_score=0.0,
            compliance_score=0.0,
            business_continuity_score=0.0,
        )
        assessment = service.conduct_assessment("vendor-007", request)
        assert assessment is not None
        assert assessment.risk_level == RiskLevel.MINIMAL

    def test_assessment_updates_vendor_risk_level(
        self, service: VendorManagementService
    ):
        """Assessment auto-updates vendor's risk level."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=2.0,
            security_posture_score=2.0,
            compliance_score=2.0,
            business_continuity_score=2.0,
        )
        service.conduct_assessment("vendor-007", request)
        vendor = service.get_vendor("vendor-007")
        assert vendor is not None
        assert vendor.risk_level == RiskLevel.LOW

    def test_assessment_updates_vendor_score(
        self, service: VendorManagementService
    ):
        """Assessment auto-updates vendor's risk score."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=5.0,
            security_posture_score=5.0,
            compliance_score=5.0,
            business_continuity_score=5.0,
        )
        assessment = service.conduct_assessment("vendor-007", request)
        assert assessment is not None
        vendor = service.get_vendor("vendor-007")
        assert vendor is not None
        assert vendor.risk_score == assessment.overall_risk_score

    def test_assessment_updates_dates(self, service: VendorManagementService):
        """Assessment updates last_assessment_date and next_assessment_due."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=5.0,
            security_posture_score=5.0,
            compliance_score=5.0,
            business_continuity_score=5.0,
        )
        before = datetime.now(timezone.utc)
        service.conduct_assessment("vendor-007", request)
        vendor = service.get_vendor("vendor-007")
        assert vendor is not None
        assert vendor.last_assessment_date is not None
        assert vendor.last_assessment_date >= before
        assert vendor.next_assessment_due is not None
        assert vendor.next_assessment_due > vendor.last_assessment_date

    def test_assessment_on_nonexistent_vendor(
        self, service: VendorManagementService
    ):
        """Assessment on nonexistent vendor returns None."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=5.0,
            security_posture_score=5.0,
            compliance_score=5.0,
            business_continuity_score=5.0,
        )
        result = service.conduct_assessment("nonexistent", request)
        assert result is None

    def test_assessment_on_terminated_vendor_raises(
        self, service: VendorManagementService
    ):
        """Assessment on terminated vendor raises ValueError."""
        # Manually set vendor to TERMINATED
        update = VendorUpdate(status=VendorStatus.TERMINATED)
        service.update_vendor("vendor-007", update)

        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=5.0,
            security_posture_score=5.0,
            compliance_score=5.0,
            business_continuity_score=5.0,
        )
        with pytest.raises(ValueError, match="terminated"):
            service.conduct_assessment("vendor-007", request)

    def test_assessment_with_findings(self, service: VendorManagementService):
        """Assessment includes findings and recommendations."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=5.0,
            security_posture_score=5.0,
            compliance_score=5.0,
            business_continuity_score=5.0,
            findings=["Finding 1", "Finding 2"],
            recommendations=["Rec 1"],
        )
        assessment = service.conduct_assessment("vendor-001", request)
        assert assessment is not None
        assert len(assessment.findings) == 2
        assert len(assessment.recommendations) == 1

    def test_get_assessments(self, service: VendorManagementService):
        """Get assessment history for a vendor."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=5.0,
            security_posture_score=5.0,
            compliance_score=5.0,
            business_continuity_score=5.0,
        )
        service.conduct_assessment("vendor-001", request)
        service.conduct_assessment("vendor-001", request)
        assessments = service.get_assessments("vendor-001")
        assert assessments is not None
        assert len(assessments) == 2

    def test_get_assessments_empty(self, service: VendorManagementService):
        """New vendor has empty assessment history."""
        assessments = service.get_assessments("vendor-001")
        assert assessments is not None
        assert len(assessments) == 0

    def test_get_assessments_nonexistent_vendor(
        self, service: VendorManagementService
    ):
        """Get assessments for nonexistent vendor returns None."""
        result = service.get_assessments("nonexistent")
        assert result is None

    def test_get_single_assessment(self, service: VendorManagementService):
        """Get a single assessment by ID."""
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=5.0,
            security_posture_score=5.0,
            compliance_score=5.0,
            business_continuity_score=5.0,
        )
        created = service.conduct_assessment("vendor-001", request)
        assert created is not None
        found = service.get_assessment(created.id)
        assert found is not None
        assert found.id == created.id

    def test_get_nonexistent_assessment(self, service: VendorManagementService):
        """Get nonexistent assessment returns None."""
        result = service.get_assessment("nonexistent-id")
        assert result is None


# ===========================================================================
# 4. Risk Level Helper Tests
# ===========================================================================


class TestRiskLevelFromScore:
    """Tests for the _risk_level_from_score helper."""

    def test_critical_threshold(self):
        assert _risk_level_from_score(100.0) == RiskLevel.CRITICAL
        assert _risk_level_from_score(76.0) == RiskLevel.CRITICAL

    def test_high_threshold(self):
        assert _risk_level_from_score(75.0) == RiskLevel.HIGH
        assert _risk_level_from_score(51.0) == RiskLevel.HIGH

    def test_medium_threshold(self):
        assert _risk_level_from_score(50.0) == RiskLevel.MEDIUM
        assert _risk_level_from_score(26.0) == RiskLevel.MEDIUM

    def test_low_threshold(self):
        assert _risk_level_from_score(25.0) == RiskLevel.LOW
        assert _risk_level_from_score(1.0) == RiskLevel.LOW

    def test_minimal_threshold(self):
        assert _risk_level_from_score(0.0) == RiskLevel.MINIMAL


# ===========================================================================
# 5. Certification Tracking Tests
# ===========================================================================


class TestCertificationTracking:
    """Tests for certification expiry tracking."""

    def test_check_certifications_returns_alerts(
        self, service: VendorManagementService
    ):
        """Certification check returns alerts for expiring/expired certs."""
        alerts = service.check_certifications()
        assert isinstance(alerts, list)
        # At least the Clinical Data Solutions expired SOC2 should show
        assert len(alerts) >= 1

    def test_expired_certification_detected(
        self, service: VendorManagementService
    ):
        """Expired certification is detected."""
        alerts = service.check_certifications()
        expired = [a for a in alerts if a.days_until_expiry is not None and a.days_until_expiry < 0]
        assert len(expired) >= 1

    def test_alerts_sorted_by_urgency(self, service: VendorManagementService):
        """Alerts are sorted by days until expiry (most urgent first)."""
        alerts = service.check_certifications()
        if len(alerts) >= 2:
            days = [a.days_until_expiry for a in alerts if a.days_until_expiry is not None]
            assert days == sorted(days)

    def test_not_required_certs_excluded(self, service: VendorManagementService):
        """NOT_REQUIRED certifications are excluded from alerts."""
        alerts = service.check_certifications()
        for alert in alerts:
            assert alert.certification.status != CertificationStatus.NOT_REQUIRED

    def test_alert_has_vendor_info(self, service: VendorManagementService):
        """Each alert includes vendor identifying information."""
        alerts = service.check_certifications()
        for alert in alerts:
            assert alert.vendor_id
            assert alert.vendor_name


# ===========================================================================
# 6. Vendor Lifecycle Tests
# ===========================================================================


class TestVendorLifecycle:
    """Tests for vendor suspension and reactivation."""

    def test_suspend_vendor(self, service: VendorManagementService):
        """Suspend an active vendor."""
        result = service.suspend_vendor("vendor-007", "Security concern")
        assert result is not None
        assert result.status == VendorStatus.SUSPENDED
        assert "Security concern" in result.notes

    def test_suspend_already_suspended_raises(
        self, service: VendorManagementService
    ):
        """Cannot suspend already-suspended vendor."""
        service.suspend_vendor("vendor-007", "First suspension")
        with pytest.raises(ValueError, match="already suspended"):
            service.suspend_vendor("vendor-007", "Second suspension")

    def test_suspend_terminated_raises(self, service: VendorManagementService):
        """Cannot suspend terminated vendor."""
        update = VendorUpdate(status=VendorStatus.TERMINATED)
        service.update_vendor("vendor-007", update)
        with pytest.raises(ValueError, match="terminated"):
            service.suspend_vendor("vendor-007", "Reason")

    def test_suspend_nonexistent_returns_none(
        self, service: VendorManagementService
    ):
        """Suspend nonexistent vendor returns None."""
        result = service.suspend_vendor("nonexistent", "Reason")
        assert result is None

    def test_reactivate_vendor(self, service: VendorManagementService):
        """Reactivate a suspended vendor."""
        service.suspend_vendor("vendor-007", "Temp suspension")
        result = service.reactivate_vendor("vendor-007")
        assert result is not None
        assert result.status == VendorStatus.ACTIVE
        assert "REACTIVATED" in result.notes

    def test_reactivate_not_suspended_raises(
        self, service: VendorManagementService
    ):
        """Cannot reactivate vendor that is not suspended."""
        with pytest.raises(ValueError, match="not suspended"):
            service.reactivate_vendor("vendor-007")

    def test_reactivate_nonexistent_returns_none(
        self, service: VendorManagementService
    ):
        """Reactivate nonexistent vendor returns None."""
        result = service.reactivate_vendor("nonexistent")
        assert result is None

    def test_suspend_reactivate_cycle(self, service: VendorManagementService):
        """Full suspend-reactivate cycle works."""
        # Suspend
        suspended = service.suspend_vendor("vendor-007", "Planned review")
        assert suspended is not None
        assert suspended.status == VendorStatus.SUSPENDED

        # Reactivate
        reactivated = service.reactivate_vendor("vendor-007")
        assert reactivated is not None
        assert reactivated.status == VendorStatus.ACTIVE

        # Verify we can suspend again
        re_suspended = service.suspend_vendor("vendor-007", "Another review")
        assert re_suspended is not None
        assert re_suspended.status == VendorStatus.SUSPENDED


# ===========================================================================
# 7. Contract Renewal Tests
# ===========================================================================


class TestContractRenewals:
    """Tests for contract renewal detection."""

    def test_get_contract_renewals(self, service: VendorManagementService):
        """Get vendors with contracts expiring within default 90 days."""
        renewals = service.get_contract_renewals(days_ahead=90)
        assert isinstance(renewals, list)
        for r in renewals:
            assert r.days_until_expiry <= 90

    def test_renewals_sorted_by_urgency(self, service: VendorManagementService):
        """Renewals are sorted by days until expiry."""
        renewals = service.get_contract_renewals(days_ahead=365)
        if len(renewals) >= 2:
            days = [r.days_until_expiry for r in renewals]
            assert days == sorted(days)

    def test_renewals_365_days_includes_more(
        self, service: VendorManagementService
    ):
        """Wider window includes more renewals."""
        short = service.get_contract_renewals(days_ahead=30)
        long = service.get_contract_renewals(days_ahead=365)
        assert len(long) >= len(short)

    def test_renewal_has_cost_info(self, service: VendorManagementService):
        """Renewal records include cost information."""
        renewals = service.get_contract_renewals(days_ahead=365)
        for r in renewals:
            assert r.annual_cost >= 0
            assert r.risk_level in RiskLevel


# ===========================================================================
# 8. PHI Access Tests
# ===========================================================================


class TestPHIAccess:
    """Tests for PHI data access vendor tracking."""

    def test_get_phi_vendors(self, service: VendorManagementService):
        """Get all vendors with PHI access."""
        phi_vendors = service.get_vendors_by_data_access(DataAccessLevel.PHI)
        assert len(phi_vendors) >= 4
        for v in phi_vendors:
            assert v.data_access_level == DataAccessLevel.PHI

    def test_phi_vendors_include_aws(self, service: VendorManagementService):
        """AWS is a PHI vendor."""
        phi_vendors = service.get_vendors_by_data_access(DataAccessLevel.PHI)
        phi_ids = {v.id for v in phi_vendors}
        assert "vendor-001" in phi_ids  # AWS

    def test_metadata_vendors(self, service: VendorManagementService):
        """Can also filter by METADATA access."""
        metadata_vendors = service.get_vendors_by_data_access(
            DataAccessLevel.METADATA
        )
        assert len(metadata_vendors) >= 1
        for v in metadata_vendors:
            assert v.data_access_level == DataAccessLevel.METADATA

    def test_none_access_vendors(self, service: VendorManagementService):
        """Can filter by NONE access."""
        none_vendors = service.get_vendors_by_data_access(DataAccessLevel.NONE)
        for v in none_vendors:
            assert v.data_access_level == DataAccessLevel.NONE


# ===========================================================================
# 9. Portfolio Metrics Tests
# ===========================================================================


class TestVendorMetrics:
    """Tests for aggregated portfolio metrics."""

    def test_metrics_total_vendors(self, service: VendorManagementService):
        """Total vendors count is correct."""
        metrics = service.get_metrics()
        assert metrics.total_vendors == 12

    def test_metrics_by_category(self, service: VendorManagementService):
        """Category breakdown sums to total."""
        metrics = service.get_metrics()
        category_sum = sum(metrics.by_category.values())
        assert category_sum == metrics.total_vendors

    def test_metrics_by_risk_level(self, service: VendorManagementService):
        """Risk level breakdown sums to total."""
        metrics = service.get_metrics()
        risk_sum = sum(metrics.by_risk_level.values())
        assert risk_sum == metrics.total_vendors

    def test_metrics_by_status(self, service: VendorManagementService):
        """Status breakdown sums to total."""
        metrics = service.get_metrics()
        status_sum = sum(metrics.by_status.values())
        assert status_sum == metrics.total_vendors

    def test_metrics_total_spend(self, service: VendorManagementService):
        """Total annual spend is reasonable."""
        metrics = service.get_metrics()
        assert metrics.total_annual_spend > 0

    def test_metrics_average_risk_score(self, service: VendorManagementService):
        """Average risk score is between 0 and 100."""
        metrics = service.get_metrics()
        assert 0 <= metrics.average_risk_score <= 100

    def test_metrics_expired_certifications(
        self, service: VendorManagementService
    ):
        """Expired certifications are counted."""
        metrics = service.get_metrics()
        assert metrics.expired_certifications >= 1  # Clinical Data Solutions has one

    def test_metrics_after_vendor_addition(
        self, service: VendorManagementService
    ):
        """Metrics update after adding a vendor."""
        before = service.get_metrics()
        request = VendorCreate(
            name="New Vendor",
            category=VendorCategory.ANALYTICS,
            annual_cost=10000.0,
        )
        service.create_vendor(request)
        after = service.get_metrics()
        assert after.total_vendors == before.total_vendors + 1
        assert after.total_annual_spend == before.total_annual_spend + 10000.0


# ===========================================================================
# 10. Singleton Tests
# ===========================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """get_vendor_management_service returns same instance."""
        s1 = get_vendor_management_service()
        s2 = get_vendor_management_service()
        assert s1 is s2

    def test_reset_creates_new_instance(self):
        """reset creates a new instance."""
        s1 = get_vendor_management_service()
        reset_vendor_management_service()
        s2 = get_vendor_management_service()
        assert s1 is not s2


# ===========================================================================
# 11. API Endpoint Tests
# ===========================================================================


class TestAPIEndpoints:
    """Integration tests for API endpoints."""

    def test_list_vendors_endpoint(self, client: TestClient):
        """GET /vendor-management/vendors returns list."""
        response = client.get("/vendor-management/vendors")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 12
        assert len(data["items"]) == 12

    def test_list_vendors_with_category_filter(self, client: TestClient):
        """GET /vendor-management/vendors?category=SECURITY filters correctly."""
        response = client.get(
            "/vendor-management/vendors",
            params={"category": "SECURITY"},
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["category"] == "SECURITY"

    def test_list_vendors_with_status_filter(self, client: TestClient):
        """GET /vendor-management/vendors?status=ACTIVE filters correctly."""
        response = client.get(
            "/vendor-management/vendors",
            params={"status": "ACTIVE"},
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["status"] == "ACTIVE"

    def test_list_vendors_pagination(self, client: TestClient):
        """GET /vendor-management/vendors with limit/offset paginates."""
        response = client.get(
            "/vendor-management/vendors",
            params={"limit": 3, "offset": 0},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 12

    def test_get_vendor_endpoint(self, client: TestClient):
        """GET /vendor-management/vendors/{id} returns vendor."""
        response = client.get("/vendor-management/vendors/vendor-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "vendor-001"
        assert data["name"] == "Amazon Web Services (AWS)"

    def test_get_vendor_not_found(self, client: TestClient):
        """GET /vendor-management/vendors/{id} returns 404 for missing vendor."""
        response = client.get("/vendor-management/vendors/nonexistent")
        assert response.status_code == 404

    def test_create_vendor_endpoint(self, client: TestClient):
        """POST /vendor-management/vendors creates vendor."""
        response = client.post(
            "/vendor-management/vendors",
            json={
                "name": "API Test Vendor",
                "category": "ANALYTICS",
                "description": "Created via API test",
                "annual_cost": 25000.0,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "API Test Vendor"
        assert data["category"] == "ANALYTICS"

    def test_update_vendor_endpoint(self, client: TestClient):
        """PUT /vendor-management/vendors/{id} updates vendor."""
        response = client.put(
            "/vendor-management/vendors/vendor-007",
            json={"notes": "Updated via API"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Updated via API"

    def test_update_vendor_not_found(self, client: TestClient):
        """PUT /vendor-management/vendors/{id} returns 404 for missing vendor."""
        response = client.put(
            "/vendor-management/vendors/nonexistent",
            json={"notes": "test"},
        )
        assert response.status_code == 404

    def test_suspend_vendor_endpoint(self, client: TestClient):
        """POST /vendor-management/vendors/{id}/suspend suspends vendor."""
        response = client.post(
            "/vendor-management/vendors/vendor-007/suspend",
            params={"reason": "API test suspension"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUSPENDED"

    def test_suspend_vendor_not_found(self, client: TestClient):
        """POST /vendor-management/vendors/{id}/suspend returns 404 for missing vendor."""
        response = client.post(
            "/vendor-management/vendors/nonexistent/suspend",
            params={"reason": "test"},
        )
        assert response.status_code == 404

    def test_reactivate_vendor_endpoint(self, client: TestClient):
        """POST /vendor-management/vendors/{id}/reactivate reactivates vendor."""
        # First suspend
        client.post(
            "/vendor-management/vendors/vendor-007/suspend",
            params={"reason": "temp"},
        )
        # Then reactivate
        response = client.post(
            "/vendor-management/vendors/vendor-007/reactivate"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ACTIVE"

    def test_reactivate_not_suspended(self, client: TestClient):
        """POST /vendor-management/vendors/{id}/reactivate returns 400 if not suspended."""
        response = client.post(
            "/vendor-management/vendors/vendor-007/reactivate"
        )
        assert response.status_code == 400

    def test_conduct_assessment_endpoint(self, client: TestClient):
        """POST /vendor-management/vendors/{id}/assess conducts assessment."""
        response = client.post(
            "/vendor-management/vendors/vendor-001/assess",
            json={
                "assessed_by": "api-tester",
                "data_handling_score": 7.0,
                "security_posture_score": 6.0,
                "compliance_score": 8.0,
                "business_continuity_score": 5.0,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["vendor_id"] == "vendor-001"
        assert data["assessed_by"] == "api-tester"
        assert "overall_risk_score" in data

    def test_conduct_assessment_not_found(self, client: TestClient):
        """POST /vendor-management/vendors/{id}/assess returns 404."""
        response = client.post(
            "/vendor-management/vendors/nonexistent/assess",
            json={
                "assessed_by": "test",
                "data_handling_score": 5.0,
                "security_posture_score": 5.0,
                "compliance_score": 5.0,
                "business_continuity_score": 5.0,
            },
        )
        assert response.status_code == 404

    def test_get_assessments_endpoint(self, client: TestClient):
        """GET /vendor-management/vendors/{id}/assessments returns history."""
        # Create an assessment first
        client.post(
            "/vendor-management/vendors/vendor-001/assess",
            json={
                "assessed_by": "test",
                "data_handling_score": 5.0,
                "security_posture_score": 5.0,
                "compliance_score": 5.0,
                "business_continuity_score": 5.0,
            },
        )
        response = client.get(
            "/vendor-management/vendors/vendor-001/assessments"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["vendor_id"] == "vendor-001"
        assert len(data["items"]) == 1

    def test_get_assessments_not_found(self, client: TestClient):
        """GET /vendor-management/vendors/{id}/assessments returns 404."""
        response = client.get(
            "/vendor-management/vendors/nonexistent/assessments"
        )
        assert response.status_code == 404

    def test_get_metrics_endpoint(self, client: TestClient):
        """GET /vendor-management/vendors/metrics returns metrics."""
        response = client.get("/vendor-management/vendors/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_vendors"] == 12
        assert "by_category" in data
        assert "by_risk_level" in data
        assert "total_annual_spend" in data

    def test_get_expiring_certifications_endpoint(self, client: TestClient):
        """GET /vendor-management/certifications/expiring returns alerts."""
        response = client.get("/vendor-management/certifications/expiring")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_contract_renewals_endpoint(self, client: TestClient):
        """GET /vendor-management/contracts/renewals returns renewals."""
        response = client.get(
            "/vendor-management/contracts/renewals",
            params={"days": 365},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_phi_vendors_endpoint(self, client: TestClient):
        """GET /vendor-management/data-access/phi returns PHI vendors."""
        response = client.get("/vendor-management/data-access/phi")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 4
        for v in data:
            assert v["data_access_level"] == "PHI"


# ===========================================================================
# 12. Edge Case Tests
# ===========================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_create_vendor_with_certifications(
        self, service: VendorManagementService
    ):
        """Create vendor with initial certifications."""
        request = VendorCreate(
            name="Certified Vendor",
            category=VendorCategory.SECURITY,
            certifications=[
                ComplianceCertification(
                    name=CertificationName.SOC2,
                    status=CertificationStatus.VERIFIED,
                    verified_date=datetime.now(timezone.utc),
                    expiry_date=datetime.now(timezone.utc) + timedelta(days=365),
                ),
            ],
        )
        vendor = service.create_vendor(request)
        assert len(vendor.certifications) == 1
        assert vendor.certifications[0].name == CertificationName.SOC2

    def test_assessment_score_capping(self, service: VendorManagementService):
        """Assessment score is capped at 100."""
        # Even if somehow scores exceed 10, overall is capped
        request = AssessmentRequest(
            assessed_by="test",
            data_handling_score=10.0,
            security_posture_score=10.0,
            compliance_score=10.0,
            business_continuity_score=10.0,
        )
        assessment = service.conduct_assessment("vendor-001", request)
        assert assessment is not None
        assert assessment.overall_risk_score <= 100.0

    def test_multiple_assessments_keep_history(
        self, service: VendorManagementService
    ):
        """Multiple assessments maintain full history."""
        for i in range(5):
            request = AssessmentRequest(
                assessed_by=f"assessor-{i}",
                data_handling_score=float(i + 1),
                security_posture_score=float(i + 1),
                compliance_score=float(i + 1),
                business_continuity_score=float(i + 1),
            )
            service.conduct_assessment("vendor-001", request)

        assessments = service.get_assessments("vendor-001")
        assert assessments is not None
        assert len(assessments) == 5

    def test_update_vendor_certifications(self, service: VendorManagementService):
        """Can update vendor certifications via update."""
        new_certs = [
            ComplianceCertification(
                name=CertificationName.HITRUST,
                status=CertificationStatus.VERIFIED,
                verified_date=datetime.now(timezone.utc),
                expiry_date=datetime.now(timezone.utc) + timedelta(days=365),
            ),
        ]
        update = VendorUpdate(certifications=new_certs)
        result = service.update_vendor("vendor-007", update)
        assert result is not None
        assert len(result.certifications) == 1
        assert result.certifications[0].name == CertificationName.HITRUST

    def test_contract_renewals_with_no_end_date(
        self, service: VendorManagementService
    ):
        """Vendors without contract_end are excluded from renewals."""
        request = VendorCreate(
            name="No End Date",
            category=VendorCategory.COMPLIANCE,
            contract_start=datetime.now(timezone.utc),
            contract_end=None,
        )
        service.create_vendor(request)
        renewals = service.get_contract_renewals(days_ahead=365)
        no_end_vendors = [r for r in renewals if r.vendor_name == "No End Date"]
        assert len(no_end_vendors) == 0

    def test_suspend_with_notes_appended(self, service: VendorManagementService):
        """Suspension reason is appended to existing notes."""
        original = service.get_vendor("vendor-007")
        assert original is not None
        original_notes = original.notes

        result = service.suspend_vendor("vendor-007", "New concern")
        assert result is not None
        assert original_notes in result.notes
        assert "New concern" in result.notes

    def test_assessment_weights_sum_to_one(self):
        """Assessment weights sum to 1.0."""
        total = sum(ASSESSMENT_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9
