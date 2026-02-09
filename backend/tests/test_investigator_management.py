"""Tests for Investigator Performance Management (CMO-11).

Covers:
- Schema validation (enums, models, request/response)
- Investigator CRUD (create, read, update, delete, list, filter)
- Certification management and expiry alerts
- Scorecard generation and historical comparison
- Performance ranking across investigators
- Inspection record management
- Training compliance tracking and gap analysis
- Workload analysis and capacity planning
- Investigator matching for new trial assignments
- Aggregate metrics
- Service singleton and reset
- API endpoint integration (24 endpoints)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.investigator_management import (
    CertificationExpiryAlert,
    CertificationExpiryReport,
    CertificationType,
    InspectionCreateRequest,
    InspectionRecord,
    InspectionResult,
    Investigator,
    InvestigatorCertification,
    InvestigatorCreateRequest,
    InvestigatorListResponse,
    InvestigatorMatchResult,
    InvestigatorMetrics,
    InvestigatorRole,
    InvestigatorScorecard,
    InvestigatorWorkload,
    PerformanceRanking,
    PerformanceRankingResponse,
    PerformanceRating,
    ScorecardCreateRequest,
    ScorecardListResponse,
    TrainingCreateRequest,
    TrainingGapAnalysis,
    TrainingRecord,
    TrainingStatus,
    WorkloadReport,
)
from app.services.investigator_management_service import (
    InvestigatorManagementService,
    get_investigator_management_service,
    reset_investigator_management_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_service():
    """Ensure a fresh service for every test."""
    reset_investigator_management_service()
    svc = get_investigator_management_service()
    yield svc
    reset_investigator_management_service()


@pytest.fixture
def svc(clean_service) -> InvestigatorManagementService:
    """Shorthand for the clean service."""
    return clean_service


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------

class TestEnumValidation:
    """Test enum values are correct."""

    def test_investigator_role_values(self):
        assert InvestigatorRole.PRINCIPAL_INVESTIGATOR == "principal_investigator"
        assert InvestigatorRole.SUB_INVESTIGATOR == "sub_investigator"
        assert InvestigatorRole.CO_INVESTIGATOR == "co_investigator"
        assert InvestigatorRole.STUDY_COORDINATOR == "study_coordinator"

    def test_certification_type_values(self):
        assert CertificationType.GCP_TRAINING == "gcp_training"
        assert CertificationType.IATA_DANGEROUS_GOODS == "iata_dangerous_goods"
        assert CertificationType.HUMAN_SUBJECTS_PROTECTION == "human_subjects_protection"
        assert CertificationType.CV_UPDATED == "cv_updated"
        assert CertificationType.MEDICAL_LICENSE == "medical_license"
        assert CertificationType.DEA_LICENSE == "dea_license"
        assert CertificationType.PROTOCOL_TRAINING == "protocol_training"
        assert CertificationType.IRB_APPROVAL == "irb_approval"

    def test_performance_rating_values(self):
        assert PerformanceRating.EXCEPTIONAL == "exceptional"
        assert PerformanceRating.ABOVE_AVERAGE == "above_average"
        assert PerformanceRating.AVERAGE == "average"
        assert PerformanceRating.BELOW_AVERAGE == "below_average"
        assert PerformanceRating.UNACCEPTABLE == "unacceptable"

    def test_inspection_result_values(self):
        assert InspectionResult.NO_FINDINGS == "no_findings"
        assert InspectionResult.MINOR_FINDINGS == "minor_findings"
        assert InspectionResult.MAJOR_FINDINGS == "major_findings"
        assert InspectionResult.OFFICIAL_ACTION_INDICATED == "official_action_indicated"
        assert InspectionResult.CRITICAL == "critical"

    def test_training_status_values(self):
        assert TrainingStatus.COMPLETED == "completed"
        assert TrainingStatus.IN_PROGRESS == "in_progress"
        assert TrainingStatus.OVERDUE == "overdue"
        assert TrainingStatus.NOT_STARTED == "not_started"
        assert TrainingStatus.EXPIRED == "expired"

    def test_investigator_role_count(self):
        assert len(InvestigatorRole) == 4

    def test_certification_type_count(self):
        assert len(CertificationType) == 8

    def test_performance_rating_count(self):
        assert len(PerformanceRating) == 5

    def test_inspection_result_count(self):
        assert len(InspectionResult) == 5

    def test_training_status_count(self):
        assert len(TrainingStatus) == 5


class TestSchemaModels:
    """Test Pydantic model validation."""

    def test_investigator_model(self):
        inv = Investigator(
            id="test-001",
            name="Dr. Test",
            role=InvestigatorRole.PRINCIPAL_INVESTIGATOR,
            site_id="site-001",
            site_name="Test Site",
            email="test@test.com",
            specialty="Oncology",
            created_at="2025-01-01T00:00:00Z",
        )
        assert inv.id == "test-001"
        assert inv.role == InvestigatorRole.PRINCIPAL_INVESTIGATOR
        assert inv.years_experience == 0
        assert inv.certifications == []
        assert inv.performance_score is None

    def test_investigator_with_all_fields(self):
        inv = Investigator(
            id="test-002",
            name="Dr. Full",
            role=InvestigatorRole.SUB_INVESTIGATOR,
            site_id="site-002",
            site_name="Full Site",
            email="full@test.com",
            specialty="Dermatology",
            medical_license_number="ML-001",
            npi_number="1234567890",
            years_experience=15,
            trials_conducted=20,
            active_trials=3,
            certifications=["gcp_training"],
            performance_score=85.0,
            last_performance_review="2025-10-01",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-06-01T00:00:00Z",
        )
        assert inv.medical_license_number == "ML-001"
        assert inv.performance_score == 85.0

    def test_certification_model(self):
        cert = InvestigatorCertification(
            id="cert-test",
            investigator_id="inv-001",
            certification_type=CertificationType.GCP_TRAINING,
            issued_date="2024-01-01",
            expiry_date="2026-01-01",
            status=TrainingStatus.COMPLETED,
            issuing_authority="TransCelerate",
            certificate_number="GCP-001",
        )
        assert cert.certification_type == CertificationType.GCP_TRAINING
        assert cert.status == TrainingStatus.COMPLETED

    def test_scorecard_model(self):
        sc = InvestigatorScorecard(
            id="sc-test",
            investigator_id="inv-001",
            period_start="2025-07-01",
            period_end="2025-09-30",
            enrollment_target=20,
            enrollment_actual=22,
            enrollment_rate=1.1,
            screen_failure_rate=0.2,
            protocol_deviation_count=1,
            query_response_time_days=1.5,
            data_quality_score=90.0,
            patient_retention_rate=0.92,
            ae_reporting_timeliness=95.0,
            overall_rating=PerformanceRating.EXCEPTIONAL,
            strengths=["Good enrollment"],
            improvement_areas=[],
        )
        assert sc.enrollment_rate == 1.1
        assert sc.overall_rating == PerformanceRating.EXCEPTIONAL

    def test_inspection_record_model(self):
        insp = InspectionRecord(
            id="insp-test",
            investigator_id="inv-001",
            site_id="site-001",
            inspection_date="2025-06-15",
            inspector_name="Inspector Test",
            inspection_type="routine",
            result=InspectionResult.NO_FINDINGS,
        )
        assert insp.result == InspectionResult.NO_FINDINGS
        assert insp.findings == []

    def test_training_record_model(self):
        tr = TrainingRecord(
            id="tr-test",
            investigator_id="inv-001",
            training_name="GCP Refresher",
            training_type=CertificationType.GCP_TRAINING,
            required_by="2025-06-01",
            completed_date="2025-05-15",
            status=TrainingStatus.COMPLETED,
            valid_until="2027-05-15",
        )
        assert tr.status == TrainingStatus.COMPLETED

    def test_workload_model(self):
        wl = InvestigatorWorkload(
            investigator_id="inv-001",
            investigator_name="Dr. Test",
            active_trial_count=3,
            total_patients=36,
            enrollment_capacity=50,
            utilization_percent=72.0,
        )
        assert wl.utilization_percent == 72.0

    def test_create_request_model(self):
        req = InvestigatorCreateRequest(
            name="Dr. New",
            role=InvestigatorRole.PRINCIPAL_INVESTIGATOR,
            site_id="site-001",
            site_name="Test Site",
            email="new@test.com",
            specialty="Oncology",
        )
        assert req.years_experience == 0

    def test_scorecard_create_request(self):
        req = ScorecardCreateRequest(
            investigator_id="inv-001",
            period_start="2025-10-01",
            period_end="2025-12-31",
            enrollment_target=20,
            enrollment_actual=18,
        )
        assert req.screen_failure_rate == 0.0

    def test_inspection_create_request(self):
        req = InspectionCreateRequest(
            investigator_id="inv-001",
            site_id="site-001",
            inspection_date="2025-12-01",
            inspector_name="Inspector X",
            result=InspectionResult.MINOR_FINDINGS,
            findings=["Finding 1"],
        )
        assert req.inspection_type == "routine"

    def test_training_create_request(self):
        req = TrainingCreateRequest(
            investigator_id="inv-001",
            training_name="New Training",
            training_type=CertificationType.GCP_TRAINING,
            required_by="2026-06-01",
        )
        assert req.status == TrainingStatus.NOT_STARTED

    def test_investigator_list_response(self):
        resp = InvestigatorListResponse(investigators=[], total=0)
        assert resp.total == 0

    def test_scorecard_list_response(self):
        resp = ScorecardListResponse(scorecards=[], total=0)
        assert resp.total == 0

    def test_certification_expiry_report(self):
        report = CertificationExpiryReport(alerts=[], total_expired=2)
        assert report.total_expired == 2
        assert report.total_expiring_30_days == 0

    def test_workload_report(self):
        report = WorkloadReport(workloads=[], avg_utilization=50.0, overloaded_count=1, available_count=3)
        assert report.overloaded_count == 1

    def test_investigator_metrics(self):
        metrics = InvestigatorMetrics(
            total_investigators=12,
            by_role={"principal_investigator": 5},
            avg_performance_score=85.0,
        )
        assert metrics.total_investigators == 12

    def test_performance_ranking(self):
        ranking = PerformanceRanking(
            rank=1,
            investigator_id="inv-001",
            investigator_name="Dr. Test",
            role=InvestigatorRole.PRINCIPAL_INVESTIGATOR,
            site_name="Site A",
            performance_score=95.0,
        )
        assert ranking.rank == 1

    def test_investigator_match_result(self):
        match = InvestigatorMatchResult(
            investigator_id="inv-001",
            investigator_name="Dr. Test",
            role=InvestigatorRole.PRINCIPAL_INVESTIGATOR,
            site_name="Site A",
            available_capacity=20,
            performance_score=90.0,
            match_score=85.0,
        )
        assert match.certifications_valid is True


# ---------------------------------------------------------------------------
# Seed data verification
# ---------------------------------------------------------------------------

class TestSeedData:
    """Verify seed data is correctly populated."""

    def test_seed_investigators_count(self, svc):
        resp = svc.list_investigators()
        assert resp.total == 12

    def test_seed_investigators_have_ids(self, svc):
        for i in range(1, 13):
            inv = svc.get_investigator(f"inv-{i:03d}")
            assert inv is not None

    def test_seed_principal_investigators(self, svc):
        resp = svc.list_investigators(role="principal_investigator")
        assert resp.total == 5

    def test_seed_sub_investigators(self, svc):
        resp = svc.list_investigators(role="sub_investigator")
        assert resp.total == 3

    def test_seed_study_coordinators(self, svc):
        resp = svc.list_investigators(role="study_coordinator")
        assert resp.total == 2

    def test_seed_co_investigators(self, svc):
        resp = svc.list_investigators(role="co_investigator")
        assert resp.total == 2

    def test_seed_certifications_count(self, svc):
        stats = svc.get_stats()
        assert stats["total_certifications"] == 35

    def test_seed_scorecards_count(self, svc):
        stats = svc.get_stats()
        assert stats["total_scorecards"] == 8

    def test_seed_inspections_count(self, svc):
        stats = svc.get_stats()
        assert stats["total_inspections"] == 4

    def test_seed_training_records_count(self, svc):
        stats = svc.get_stats()
        assert stats["total_training_records"] == 27

    def test_seed_investigator_fields(self, svc):
        inv = svc.get_investigator("inv-001")
        assert inv is not None
        assert inv.name == "Dr. Sarah Chen"
        assert inv.role == InvestigatorRole.PRINCIPAL_INVESTIGATOR
        assert inv.site_id == "site-001"
        assert inv.email == "s.chen@jhmi.edu"
        assert inv.specialty == "Oncology"
        assert inv.years_experience == 15
        assert inv.performance_score == 92.5

    def test_seed_has_expired_certifications(self, svc):
        report = svc.get_certification_expiry_report(days_ahead=365)
        expired = [a for a in report.alerts if a.days_until_expiry < 0]
        assert len(expired) >= 2  # cert-006 and cert-017 are expired

    def test_seed_has_overdue_training(self, svc):
        all_training = svc.get_training_records()
        overdue = [t for t in all_training if t.status == TrainingStatus.OVERDUE]
        assert len(overdue) >= 3


# ---------------------------------------------------------------------------
# Investigator CRUD tests
# ---------------------------------------------------------------------------

class TestInvestigatorCRUD:
    """Test investigator CRUD operations."""

    def test_get_investigator(self, svc):
        inv = svc.get_investigator("inv-001")
        assert inv is not None
        assert inv.name == "Dr. Sarah Chen"

    def test_get_nonexistent_investigator(self, svc):
        assert svc.get_investigator("inv-999") is None

    def test_list_all_investigators(self, svc):
        resp = svc.list_investigators()
        assert resp.total == 12
        assert len(resp.investigators) == 12

    def test_filter_by_role(self, svc):
        resp = svc.list_investigators(role="principal_investigator")
        for inv in resp.investigators:
            assert inv.role == InvestigatorRole.PRINCIPAL_INVESTIGATOR

    def test_filter_by_site(self, svc):
        resp = svc.list_investigators(site_id="site-001")
        assert resp.total == 3  # inv-001, inv-004, inv-007
        for inv in resp.investigators:
            assert inv.site_id == "site-001"

    def test_filter_by_rating_exceptional(self, svc):
        resp = svc.list_investigators(rating="exceptional")
        for inv in resp.investigators:
            assert inv.performance_score is not None
            assert inv.performance_score >= 90.0

    def test_filter_by_rating_below_average(self, svc):
        resp = svc.list_investigators(rating="below_average")
        for inv in resp.investigators:
            assert inv.performance_score is not None
            assert 60.0 <= inv.performance_score < 70.0

    def test_filter_combined_role_and_site(self, svc):
        resp = svc.list_investigators(role="principal_investigator", site_id="site-001")
        assert resp.total == 1
        assert resp.investigators[0].id == "inv-001"

    def test_create_investigator(self, svc):
        req = InvestigatorCreateRequest(
            name="Dr. New Investigator",
            role=InvestigatorRole.PRINCIPAL_INVESTIGATOR,
            site_id="site-010",
            site_name="New Site",
            email="new@test.com",
            specialty="Cardiology",
            years_experience=10,
            trials_conducted=5,
        )
        inv = svc.create_investigator(req)
        assert inv.name == "Dr. New Investigator"
        assert inv.id.startswith("inv-")
        assert inv.created_at is not None
        # Verify it's retrievable
        assert svc.get_investigator(inv.id) is not None

    def test_update_investigator(self, svc):
        updated = svc.update_investigator("inv-001", {"years_experience": 16, "active_trials": 4})
        assert updated is not None
        assert updated.years_experience == 16
        assert updated.active_trials == 4
        assert updated.updated_at is not None

    def test_update_nonexistent_investigator(self, svc):
        assert svc.update_investigator("inv-999", {"name": "Ghost"}) is None

    def test_delete_investigator(self, svc):
        assert svc.delete_investigator("inv-001") is True
        assert svc.get_investigator("inv-001") is None

    def test_delete_nonexistent_investigator(self, svc):
        assert svc.delete_investigator("inv-999") is False

    def test_create_then_list_increases_count(self, svc):
        initial = svc.list_investigators().total
        req = InvestigatorCreateRequest(
            name="Dr. Extra",
            role=InvestigatorRole.SUB_INVESTIGATOR,
            site_id="site-010",
            site_name="Extra Site",
            email="extra@test.com",
            specialty="Neurology",
        )
        svc.create_investigator(req)
        assert svc.list_investigators().total == initial + 1

    def test_delete_then_list_decreases_count(self, svc):
        initial = svc.list_investigators().total
        svc.delete_investigator("inv-012")
        assert svc.list_investigators().total == initial - 1


# ---------------------------------------------------------------------------
# Certification tests
# ---------------------------------------------------------------------------

class TestCertifications:
    """Test certification management."""

    def test_get_certifications_for_investigator(self, svc):
        certs = svc.get_certifications("inv-001")
        assert len(certs) == 4

    def test_get_certifications_for_investigator_with_none(self, svc):
        # Create a new investigator with no certs
        req = InvestigatorCreateRequest(
            name="No Certs",
            role=InvestigatorRole.SUB_INVESTIGATOR,
            site_id="site-099",
            site_name="Empty Site",
            email="nocerts@test.com",
            specialty="General",
        )
        inv = svc.create_investigator(req)
        certs = svc.get_certifications(inv.id)
        assert len(certs) == 0

    def test_add_certification(self, svc):
        cert = InvestigatorCertification(
            id="cert-new-001",
            investigator_id="inv-001",
            certification_type=CertificationType.DEA_LICENSE,
            issued_date="2025-01-01",
            expiry_date="2027-01-01",
            status=TrainingStatus.COMPLETED,
            issuing_authority="DEA",
            certificate_number="DEA-NEW-001",
        )
        result = svc.add_certification(cert)
        assert result.id == "cert-new-001"
        # Verify it shows up
        certs = svc.get_certifications("inv-001")
        assert len(certs) == 5

    def test_certification_expiry_report(self, svc):
        report = svc.get_certification_expiry_report(days_ahead=365)
        assert isinstance(report, CertificationExpiryReport)
        assert len(report.alerts) > 0

    def test_certification_expiry_report_has_expired(self, svc):
        report = svc.get_certification_expiry_report(days_ahead=365)
        assert report.total_expired >= 2

    def test_certification_expiry_report_sorted_by_urgency(self, svc):
        report = svc.get_certification_expiry_report(days_ahead=365)
        for i in range(len(report.alerts) - 1):
            assert report.alerts[i].days_until_expiry <= report.alerts[i + 1].days_until_expiry

    def test_certification_expiry_alert_severity(self, svc):
        report = svc.get_certification_expiry_report(days_ahead=365)
        for alert in report.alerts:
            if alert.days_until_expiry < 0:
                assert alert.severity == "critical"
            elif alert.days_until_expiry <= 30:
                assert alert.severity == "critical"
            elif alert.days_until_expiry <= 60:
                assert alert.severity == "warning"
            else:
                assert alert.severity == "info"

    def test_certification_expiry_narrow_window(self, svc):
        report = svc.get_certification_expiry_report(days_ahead=1)
        # Only expired certs should show
        for alert in report.alerts:
            assert alert.days_until_expiry <= 1


# ---------------------------------------------------------------------------
# Scorecard tests
# ---------------------------------------------------------------------------

class TestScorecards:
    """Test scorecard management."""

    def test_get_scorecards(self, svc):
        resp = svc.get_scorecards("inv-001")
        assert resp.total == 2  # sc-001 and sc-002

    def test_get_scorecard_by_id(self, svc):
        sc = svc.get_scorecard("sc-001")
        assert sc is not None
        assert sc.investigator_id == "inv-001"
        assert sc.overall_rating == PerformanceRating.EXCEPTIONAL

    def test_get_nonexistent_scorecard(self, svc):
        assert svc.get_scorecard("sc-999") is None

    def test_create_scorecard_exceptional(self, svc):
        req = ScorecardCreateRequest(
            investigator_id="inv-003",
            period_start="2025-10-01",
            period_end="2025-12-31",
            enrollment_target=20,
            enrollment_actual=24,
            screen_failure_rate=0.15,
            protocol_deviation_count=0,
            query_response_time_days=1.0,
            data_quality_score=96.0,
            patient_retention_rate=0.95,
            ae_reporting_timeliness=98.0,
        )
        sc = svc.create_scorecard(req)
        assert sc.enrollment_rate == 1.2
        assert sc.overall_rating == PerformanceRating.EXCEPTIONAL
        assert "Met or exceeded enrollment target" in sc.strengths

    def test_create_scorecard_below_average(self, svc):
        req = ScorecardCreateRequest(
            investigator_id="inv-006",
            period_start="2025-10-01",
            period_end="2025-12-31",
            enrollment_target=20,
            enrollment_actual=8,
            screen_failure_rate=0.45,
            protocol_deviation_count=5,
            query_response_time_days=4.0,
            data_quality_score=60.0,
            patient_retention_rate=0.70,
            ae_reporting_timeliness=65.0,
        )
        sc = svc.create_scorecard(req)
        assert sc.enrollment_rate == 0.4
        assert "Below enrollment target" in sc.improvement_areas
        assert "Data quality needs improvement" in sc.improvement_areas

    def test_create_scorecard_auto_calculates_fields(self, svc):
        req = ScorecardCreateRequest(
            investigator_id="inv-001",
            period_start="2025-10-01",
            period_end="2025-12-31",
            enrollment_target=10,
            enrollment_actual=10,
            data_quality_score=85.0,
            patient_retention_rate=0.88,
            ae_reporting_timeliness=90.0,
        )
        sc = svc.create_scorecard(req)
        assert sc.enrollment_rate == 1.0
        assert sc.id.startswith("sc-")
        assert sc.overall_rating in list(PerformanceRating)

    def test_compare_scorecards_returns_sorted(self, svc):
        cards = svc.compare_scorecards("inv-001")
        assert len(cards) == 2
        assert cards[0].period_start <= cards[1].period_start

    def test_compare_scorecards_empty(self, svc):
        cards = svc.compare_scorecards("inv-012")
        assert len(cards) == 0

    def test_scorecard_strengths_populated(self, svc):
        sc = svc.get_scorecard("sc-004")
        assert sc is not None
        assert len(sc.strengths) > 0

    def test_scorecard_improvement_areas_populated(self, svc):
        sc = svc.get_scorecard("sc-008")
        assert sc is not None
        assert len(sc.improvement_areas) > 0


# ---------------------------------------------------------------------------
# Performance ranking tests
# ---------------------------------------------------------------------------

class TestPerformanceRankings:
    """Test performance ranking."""

    def test_get_rankings(self, svc):
        resp = svc.get_performance_rankings()
        assert resp.total > 0
        assert resp.rankings[0].rank == 1

    def test_rankings_sorted_by_score(self, svc):
        resp = svc.get_performance_rankings()
        for i in range(len(resp.rankings) - 1):
            assert resp.rankings[i].performance_score >= resp.rankings[i + 1].performance_score

    def test_rankings_limit(self, svc):
        resp = svc.get_performance_rankings(limit=3)
        assert resp.total == 3

    def test_rankings_top_is_highest_score(self, svc):
        resp = svc.get_performance_rankings()
        inv = svc.get_investigator(resp.rankings[0].investigator_id)
        assert inv is not None
        assert inv.performance_score == resp.rankings[0].performance_score

    def test_rankings_have_all_fields(self, svc):
        resp = svc.get_performance_rankings(limit=1)
        r = resp.rankings[0]
        assert r.investigator_id is not None
        assert r.investigator_name is not None
        assert r.role in list(InvestigatorRole)
        assert r.site_name is not None


# ---------------------------------------------------------------------------
# Inspection tests
# ---------------------------------------------------------------------------

class TestInspections:
    """Test inspection record management."""

    def test_get_all_inspections(self, svc):
        inspections = svc.get_inspections()
        assert len(inspections) == 4

    def test_get_inspections_by_investigator(self, svc):
        inspections = svc.get_inspections("inv-001")
        assert len(inspections) == 1
        assert inspections[0].result == InspectionResult.NO_FINDINGS

    def test_get_inspection_by_id(self, svc):
        insp = svc.get_inspection("insp-001")
        assert insp is not None
        assert insp.inspector_name == "FDA Inspector J. Martinez"

    def test_get_nonexistent_inspection(self, svc):
        assert svc.get_inspection("insp-999") is None

    def test_create_inspection(self, svc):
        req = InspectionCreateRequest(
            investigator_id="inv-002",
            site_id="site-002",
            inspection_date="2025-12-01",
            inspector_name="FDA Inspector Test",
            inspection_type="routine",
            result=InspectionResult.NO_FINDINGS,
        )
        insp = svc.create_inspection(req)
        assert insp.id.startswith("insp-")
        assert insp.result == InspectionResult.NO_FINDINGS
        # Total should now be 5
        assert len(svc.get_inspections()) == 5

    def test_inspection_with_findings(self, svc):
        insp = svc.get_inspection("insp-004")
        assert insp is not None
        assert insp.result == InspectionResult.MAJOR_FINDINGS
        assert len(insp.findings) == 3
        assert len(insp.corrective_actions) == 3

    def test_inspection_follow_up_date(self, svc):
        insp = svc.get_inspection("insp-003")
        assert insp is not None
        assert insp.follow_up_date == "2026-03-10"


# ---------------------------------------------------------------------------
# Training tests
# ---------------------------------------------------------------------------

class TestTraining:
    """Test training compliance tracking."""

    def test_get_all_training_records(self, svc):
        records = svc.get_training_records()
        assert len(records) == 27

    def test_get_training_by_investigator(self, svc):
        records = svc.get_training_records("inv-001")
        assert len(records) == 3
        for r in records:
            assert r.investigator_id == "inv-001"

    def test_create_training_record(self, svc):
        req = TrainingCreateRequest(
            investigator_id="inv-001",
            training_name="New Protocol Training",
            training_type=CertificationType.PROTOCOL_TRAINING,
            required_by="2026-06-01",
            status=TrainingStatus.NOT_STARTED,
        )
        tr = svc.create_training_record(req)
        assert tr.id.startswith("tr-")
        assert tr.status == TrainingStatus.NOT_STARTED

    def test_training_gap_analysis(self, svc):
        analysis = svc.get_training_gap_analysis("inv-002")
        assert analysis is not None
        assert analysis.investigator_name == "Dr. James Wilson"
        assert analysis.overdue_count >= 1
        assert analysis.compliance_rate < 100.0

    def test_training_gap_analysis_nonexistent(self, svc):
        assert svc.get_training_gap_analysis("inv-999") is None

    def test_training_gap_analysis_compliant(self, svc):
        analysis = svc.get_training_gap_analysis("inv-001")
        assert analysis is not None
        assert analysis.completed_count == 3
        assert analysis.overdue_count == 0
        assert analysis.compliance_rate == 100.0
        assert len(analysis.gaps) == 0

    def test_training_gap_analysis_has_gaps(self, svc):
        analysis = svc.get_training_gap_analysis("inv-005")
        assert analysis is not None
        assert len(analysis.gaps) > 0

    def test_training_gap_analysis_gap_descriptions(self, svc):
        analysis = svc.get_training_gap_analysis("inv-011")
        assert analysis is not None
        overdue_gaps = [g for g in analysis.gaps if g.startswith("Overdue:")]
        not_started_gaps = [g for g in analysis.gaps if g.startswith("Not started:")]
        assert len(overdue_gaps) >= 1
        assert len(not_started_gaps) >= 1


# ---------------------------------------------------------------------------
# Workload tests
# ---------------------------------------------------------------------------

class TestWorkload:
    """Test workload analysis."""

    def test_get_workload(self, svc):
        wl = svc.get_workload("inv-001")
        assert wl is not None
        assert wl.investigator_name == "Dr. Sarah Chen"
        assert wl.active_trial_count == 3

    def test_get_workload_nonexistent(self, svc):
        assert svc.get_workload("inv-999") is None

    def test_workload_capacity_by_role(self, svc):
        # PI gets 50 capacity
        wl_pi = svc.get_workload("inv-001")
        assert wl_pi is not None
        assert wl_pi.enrollment_capacity == 50

        # Sub-investigator gets 35
        wl_sub = svc.get_workload("inv-004")
        assert wl_sub is not None
        assert wl_sub.enrollment_capacity == 35

        # Coordinator gets 60
        wl_coord = svc.get_workload("inv-007")
        assert wl_coord is not None
        assert wl_coord.enrollment_capacity == 60

    def test_workload_utilization_calculation(self, svc):
        wl = svc.get_workload("inv-001")
        assert wl is not None
        expected = min(100.0, (wl.total_patients / max(wl.enrollment_capacity, 1)) * 100.0)
        assert abs(wl.utilization_percent - round(expected, 1)) < 0.2

    def test_workload_report(self, svc):
        report = svc.get_workload_report()
        assert isinstance(report, WorkloadReport)
        assert len(report.workloads) == 12
        assert report.avg_utilization > 0

    def test_workload_report_counts(self, svc):
        report = svc.get_workload_report()
        assert report.overloaded_count >= 0
        assert report.available_count >= 0


# ---------------------------------------------------------------------------
# Investigator matching tests
# ---------------------------------------------------------------------------

class TestInvestigatorMatching:
    """Test investigator matching for new trials."""

    def test_find_available_investigators(self, svc):
        results = svc.find_available_investigators()
        assert len(results) > 0
        for r in results:
            assert r.performance_score >= 70.0

    def test_find_available_with_high_min_performance(self, svc):
        results = svc.find_available_investigators(min_performance=90.0)
        for r in results:
            assert r.performance_score >= 90.0

    def test_find_available_by_specialty(self, svc):
        results = svc.find_available_investigators(specialty="Oncology")
        for r in results:
            inv = svc.get_investigator(r.investigator_id)
            assert inv is not None
            assert inv.specialty.lower() == "oncology"

    def test_find_available_limited_results(self, svc):
        results = svc.find_available_investigators(max_results=2)
        assert len(results) <= 2

    def test_find_available_sorted_by_match_score(self, svc):
        results = svc.find_available_investigators()
        for i in range(len(results) - 1):
            assert results[i].match_score >= results[i + 1].match_score

    def test_find_available_match_score_components(self, svc):
        results = svc.find_available_investigators()
        for r in results:
            assert 0.0 <= r.match_score <= 100.0
            assert r.available_capacity >= 0


# ---------------------------------------------------------------------------
# Metrics tests
# ---------------------------------------------------------------------------

class TestMetrics:
    """Test aggregate metrics."""

    def test_get_metrics(self, svc):
        metrics = svc.get_metrics()
        assert metrics.total_investigators == 12
        assert metrics.avg_performance_score > 0

    def test_metrics_by_role(self, svc):
        metrics = svc.get_metrics()
        assert "principal_investigator" in metrics.by_role
        assert "sub_investigator" in metrics.by_role
        total_by_role = sum(metrics.by_role.values())
        assert total_by_role == 12

    def test_metrics_certification_compliance(self, svc):
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.certification_compliance_rate <= 100.0

    def test_metrics_training_completion(self, svc):
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.training_completion_rate <= 100.0

    def test_metrics_inspection_readiness(self, svc):
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.inspection_readiness_score <= 100.0

    def test_metrics_active_trial_avg(self, svc):
        metrics = svc.get_metrics()
        assert metrics.active_trial_avg > 0


# ---------------------------------------------------------------------------
# Service lifecycle tests
# ---------------------------------------------------------------------------

class TestServiceLifecycle:
    """Test service singleton and reset."""

    def test_singleton(self):
        svc1 = get_investigator_management_service()
        svc2 = get_investigator_management_service()
        assert svc1 is svc2

    def test_reset(self):
        svc1 = get_investigator_management_service()
        reset_investigator_management_service()
        svc2 = get_investigator_management_service()
        assert svc1 is not svc2

    def test_clear_and_reseed(self, svc):
        svc.delete_investigator("inv-001")
        assert svc.list_investigators().total == 11
        svc.clear()
        assert svc.list_investigators().total == 12

    def test_get_stats(self, svc):
        stats = svc.get_stats()
        assert stats["total_investigators"] == 12
        assert stats["total_certifications"] == 35
        assert stats["total_scorecards"] == 8
        assert stats["total_inspections"] == 4
        assert stats["total_training_records"] == 27


# ---------------------------------------------------------------------------
# Scoring helpers tests
# ---------------------------------------------------------------------------

class TestScoringHelpers:
    """Test private scoring helper methods."""

    def test_score_to_rating_exceptional(self):
        assert InvestigatorManagementService._score_to_rating(95.0) == PerformanceRating.EXCEPTIONAL

    def test_score_to_rating_above_average(self):
        assert InvestigatorManagementService._score_to_rating(85.0) == PerformanceRating.ABOVE_AVERAGE

    def test_score_to_rating_average(self):
        assert InvestigatorManagementService._score_to_rating(75.0) == PerformanceRating.AVERAGE

    def test_score_to_rating_below_average(self):
        assert InvestigatorManagementService._score_to_rating(65.0) == PerformanceRating.BELOW_AVERAGE

    def test_score_to_rating_unacceptable(self):
        assert InvestigatorManagementService._score_to_rating(50.0) == PerformanceRating.UNACCEPTABLE

    def test_composite_score_perfect(self):
        score = InvestigatorManagementService._compute_composite_score(
            enrollment_rate=1.0,
            screen_failure_rate=0.0,
            protocol_deviation_count=0,
            query_response_time_days=1.0,
            data_quality_score=100.0,
            patient_retention_rate=1.0,
            ae_reporting_timeliness=100.0,
        )
        assert score >= 90.0

    def test_composite_score_poor(self):
        score = InvestigatorManagementService._compute_composite_score(
            enrollment_rate=0.3,
            screen_failure_rate=0.6,
            protocol_deviation_count=8,
            query_response_time_days=5.0,
            data_quality_score=40.0,
            patient_retention_rate=0.5,
            ae_reporting_timeliness=30.0,
        )
        assert score < 60.0

    def test_composite_score_range(self):
        score = InvestigatorManagementService._compute_composite_score(
            enrollment_rate=0.8,
            screen_failure_rate=0.25,
            protocol_deviation_count=2,
            query_response_time_days=2.0,
            data_quality_score=80.0,
            patient_retention_rate=0.85,
            ae_reporting_timeliness=85.0,
        )
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# API endpoint integration tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestAPIEndpoints:
    """Test API endpoints via HTTP client."""

    @pytest.fixture
    async def client(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_list_investigators(self, client):
        resp = await client.get("/api/v1/investigator-management/investigators")
        assert resp.status_code == 200
        data = resp.json()
        assert "investigators" in data
        assert "total" in data
        assert data["total"] == 12

    async def test_list_investigators_filter_role(self, client):
        resp = await client.get("/api/v1/investigator-management/investigators?role=principal_investigator")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    async def test_get_investigator(self, client):
        resp = await client.get("/api/v1/investigator-management/investigators/inv-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Dr. Sarah Chen"

    async def test_get_investigator_not_found(self, client):
        resp = await client.get("/api/v1/investigator-management/investigators/inv-999")
        assert resp.status_code == 404

    async def test_create_investigator(self, client):
        resp = await client.post(
            "/api/v1/investigator-management/investigators",
            json={
                "name": "Dr. API Test",
                "role": "principal_investigator",
                "site_id": "site-099",
                "site_name": "API Test Site",
                "email": "api@test.com",
                "specialty": "Cardiology",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Dr. API Test"

    async def test_update_investigator(self, client):
        resp = await client.put(
            "/api/v1/investigator-management/investigators/inv-001",
            json={"years_experience": 20},
        )
        assert resp.status_code == 200
        assert resp.json()["years_experience"] == 20

    async def test_delete_investigator(self, client):
        resp = await client.delete("/api/v1/investigator-management/investigators/inv-012")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_list_certifications(self, client):
        resp = await client.get("/api/v1/investigator-management/certifications/inv-001")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 4

    async def test_certification_expiry_report(self, client):
        resp = await client.get("/api/v1/investigator-management/certifications/expiry-report?days_ahead=365")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data
        assert "total_expired" in data

    async def test_list_scorecards(self, client):
        resp = await client.get("/api/v1/investigator-management/scorecards/inv-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_get_scorecard_detail(self, client):
        resp = await client.get("/api/v1/investigator-management/scorecards/detail/sc-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["investigator_id"] == "inv-001"

    async def test_create_scorecard(self, client):
        resp = await client.post(
            "/api/v1/investigator-management/scorecards",
            json={
                "investigator_id": "inv-002",
                "period_start": "2025-10-01",
                "period_end": "2025-12-31",
                "enrollment_target": 15,
                "enrollment_actual": 14,
                "data_quality_score": 88.0,
                "patient_retention_rate": 0.90,
                "ae_reporting_timeliness": 92.0,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["investigator_id"] == "inv-002"

    async def test_compare_scorecards(self, client):
        resp = await client.get("/api/v1/investigator-management/scorecards/compare/inv-001")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_get_rankings(self, client):
        resp = await client.get("/api/v1/investigator-management/rankings")
        assert resp.status_code == 200
        data = resp.json()
        assert "rankings" in data
        assert data["total"] > 0

    async def test_list_inspections(self, client):
        resp = await client.get("/api/v1/investigator-management/inspections")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4

    async def test_get_inspection(self, client):
        resp = await client.get("/api/v1/investigator-management/inspections/insp-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "no_findings"

    async def test_create_inspection(self, client):
        resp = await client.post(
            "/api/v1/investigator-management/inspections",
            json={
                "investigator_id": "inv-002",
                "site_id": "site-002",
                "inspection_date": "2025-12-15",
                "inspector_name": "Test Inspector",
                "result": "no_findings",
            },
        )
        assert resp.status_code == 201

    async def test_list_training_records(self, client):
        resp = await client.get("/api/v1/investigator-management/training/inv-001")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    async def test_create_training_record(self, client):
        resp = await client.post(
            "/api/v1/investigator-management/training",
            json={
                "investigator_id": "inv-001",
                "training_name": "API Test Training",
                "training_type": "gcp_training",
                "required_by": "2026-06-01",
            },
        )
        assert resp.status_code == 201

    async def test_training_gap_analysis(self, client):
        resp = await client.get("/api/v1/investigator-management/training/gap-analysis/inv-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["investigator_name"] == "Dr. James Wilson"
        assert data["overdue_count"] >= 1

    async def test_get_workload(self, client):
        resp = await client.get("/api/v1/investigator-management/workload/inv-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["investigator_name"] == "Dr. Sarah Chen"

    async def test_workload_report(self, client):
        resp = await client.get("/api/v1/investigator-management/workload-report")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["workloads"]) == 12

    async def test_find_available(self, client):
        resp = await client.get("/api/v1/investigator-management/match")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    async def test_get_metrics(self, client):
        resp = await client.get("/api/v1/investigator-management/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_investigators"] == 12

    async def test_get_stats(self, client):
        resp = await client.get("/api/v1/investigator-management/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_investigators" in data
