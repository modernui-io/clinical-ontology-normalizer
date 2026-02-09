"""Investigator Performance Management Service (CMO-11).

Provides investigator tracking, certification management, performance
scorecards, inspection records, training compliance, and workload
capacity planning for multi-site clinical trial operations.

Usage:
    from app.services.investigator_management_service import (
        get_investigator_management_service,
    )

    svc = get_investigator_management_service()
    investigators = svc.list_investigators()
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

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

logger = logging.getLogger(__name__)


class InvestigatorManagementService:
    """In-memory investigator performance management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._investigators: dict[str, Investigator] = {}
        self._certifications: dict[str, InvestigatorCertification] = {}
        self._scorecards: dict[str, InvestigatorScorecard] = {}
        self._inspections: dict[str, InspectionRecord] = {}
        self._training_records: dict[str, TrainingRecord] = {}
        self._lock = threading.Lock()
        self._seed_data()

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    def _seed_data(self) -> None:
        """Pre-populate investigators, certifications, scorecards, inspections, and training."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # --- 12 investigators across sites ---
        investigators_raw: list[dict[str, Any]] = [
            {
                "id": "inv-001", "name": "Dr. Sarah Chen", "role": InvestigatorRole.PRINCIPAL_INVESTIGATOR,
                "site_id": "site-001", "site_name": "Johns Hopkins Oncology Center",
                "email": "s.chen@jhmi.edu", "specialty": "Oncology",
                "medical_license_number": "MD-2019-44821", "npi_number": "1234567890",
                "years_experience": 15, "trials_conducted": 28, "active_trials": 3,
                "certifications": ["gcp_training", "human_subjects_protection", "medical_license", "protocol_training"],
                "performance_score": 92.5, "last_performance_review": "2025-10-01",
            },
            {
                "id": "inv-002", "name": "Dr. James Wilson", "role": InvestigatorRole.PRINCIPAL_INVESTIGATOR,
                "site_id": "site-002", "site_name": "Mayo Clinic Rochester",
                "email": "j.wilson@mayo.edu", "specialty": "Dermatology",
                "medical_license_number": "MD-2015-33912", "npi_number": "2345678901",
                "years_experience": 20, "trials_conducted": 45, "active_trials": 4,
                "certifications": ["gcp_training", "human_subjects_protection", "medical_license", "dea_license"],
                "performance_score": 88.0, "last_performance_review": "2025-09-15",
            },
            {
                "id": "inv-003", "name": "Prof. Klaus Mueller", "role": InvestigatorRole.PRINCIPAL_INVESTIGATOR,
                "site_id": "site-003", "site_name": "Charite Universitaetsmedizin Berlin",
                "email": "k.mueller@charite.de", "specialty": "Ophthalmology",
                "medical_license_number": "DE-MED-2010-7834", "npi_number": None,
                "years_experience": 22, "trials_conducted": 52, "active_trials": 3,
                "certifications": ["gcp_training", "human_subjects_protection", "medical_license", "protocol_training", "irb_approval"],
                "performance_score": 95.0, "last_performance_review": "2025-11-01",
            },
            {
                "id": "inv-004", "name": "Dr. Maria Santos", "role": InvestigatorRole.SUB_INVESTIGATOR,
                "site_id": "site-001", "site_name": "Johns Hopkins Oncology Center",
                "email": "m.santos@jhmi.edu", "specialty": "Oncology",
                "medical_license_number": "MD-2020-55193", "npi_number": "3456789012",
                "years_experience": 8, "trials_conducted": 12, "active_trials": 2,
                "certifications": ["gcp_training", "human_subjects_protection", "protocol_training"],
                "performance_score": 78.5, "last_performance_review": "2025-10-01",
            },
            {
                "id": "inv-005", "name": "Dr. Akira Tanaka", "role": InvestigatorRole.PRINCIPAL_INVESTIGATOR,
                "site_id": "site-006", "site_name": "University of Tokyo Hospital",
                "email": "a.tanaka@todai.ac.jp", "specialty": "Immunology",
                "medical_license_number": "JP-MD-2012-9921", "npi_number": None,
                "years_experience": 18, "trials_conducted": 35, "active_trials": 3,
                "certifications": ["gcp_training", "human_subjects_protection", "medical_license"],
                "performance_score": 85.0, "last_performance_review": "2025-08-15",
            },
            {
                "id": "inv-006", "name": "Dr. Emily Brooks", "role": InvestigatorRole.SUB_INVESTIGATOR,
                "site_id": "site-004", "site_name": "Cleveland Clinic",
                "email": "e.brooks@ccf.org", "specialty": "Ophthalmology",
                "medical_license_number": "MD-2018-66782", "npi_number": "4567890123",
                "years_experience": 10, "trials_conducted": 15, "active_trials": 2,
                "certifications": ["gcp_training", "human_subjects_protection"],
                "performance_score": 72.0, "last_performance_review": "2025-09-01",
            },
            {
                "id": "inv-007", "name": "Rachel Kim", "role": InvestigatorRole.STUDY_COORDINATOR,
                "site_id": "site-001", "site_name": "Johns Hopkins Oncology Center",
                "email": "r.kim@jhmi.edu", "specialty": "Clinical Coordination",
                "medical_license_number": None, "npi_number": None,
                "years_experience": 6, "trials_conducted": 10, "active_trials": 3,
                "certifications": ["gcp_training", "human_subjects_protection", "protocol_training", "iata_dangerous_goods"],
                "performance_score": 82.0, "last_performance_review": "2025-10-01",
            },
            {
                "id": "inv-008", "name": "Dr. Robert Chang", "role": InvestigatorRole.CO_INVESTIGATOR,
                "site_id": "site-005", "site_name": "Stanford Medical Center",
                "email": "r.chang@stanford.edu", "specialty": "Dermatology",
                "medical_license_number": "MD-2016-44290", "npi_number": "5678901234",
                "years_experience": 12, "trials_conducted": 20, "active_trials": 2,
                "certifications": ["gcp_training", "medical_license", "protocol_training"],
                "performance_score": 80.0, "last_performance_review": "2025-07-15",
            },
            {
                "id": "inv-009", "name": "Dr. Priya Patel", "role": InvestigatorRole.PRINCIPAL_INVESTIGATOR,
                "site_id": "site-007", "site_name": "Apollo Hospitals Mumbai",
                "email": "p.patel@apollohospitals.com", "specialty": "Immunology",
                "medical_license_number": "IN-MD-2011-38821", "npi_number": None,
                "years_experience": 16, "trials_conducted": 30, "active_trials": 2,
                "certifications": ["gcp_training", "human_subjects_protection", "medical_license", "protocol_training"],
                "performance_score": 90.0, "last_performance_review": "2025-10-15",
            },
            {
                "id": "inv-010", "name": "Mark Johnson", "role": InvestigatorRole.STUDY_COORDINATOR,
                "site_id": "site-002", "site_name": "Mayo Clinic Rochester",
                "email": "m.johnson@mayo.edu", "specialty": "Clinical Coordination",
                "medical_license_number": None, "npi_number": None,
                "years_experience": 4, "trials_conducted": 8, "active_trials": 4,
                "certifications": ["gcp_training", "human_subjects_protection", "iata_dangerous_goods"],
                "performance_score": 76.0, "last_performance_review": "2025-09-15",
            },
            {
                "id": "inv-011", "name": "Dr. Lisa Park", "role": InvestigatorRole.SUB_INVESTIGATOR,
                "site_id": "site-005", "site_name": "Stanford Medical Center",
                "email": "l.park@stanford.edu", "specialty": "Oncology",
                "medical_license_number": "MD-2019-77312", "npi_number": "6789012345",
                "years_experience": 7, "trials_conducted": 9, "active_trials": 1,
                "certifications": ["gcp_training", "protocol_training"],
                "performance_score": 68.0, "last_performance_review": "2025-08-01",
            },
            {
                "id": "inv-012", "name": "Dr. Hans Weber", "role": InvestigatorRole.CO_INVESTIGATOR,
                "site_id": "site-003", "site_name": "Charite Universitaetsmedizin Berlin",
                "email": "h.weber@charite.de", "specialty": "Ophthalmology",
                "medical_license_number": "DE-MED-2014-5521", "npi_number": None,
                "years_experience": 14, "trials_conducted": 22, "active_trials": 2,
                "certifications": ["gcp_training", "human_subjects_protection", "medical_license", "irb_approval"],
                "performance_score": 86.0, "last_performance_review": "2025-11-01",
            },
        ]

        for raw in investigators_raw:
            raw["created_at"] = now_iso
            raw["updated_at"] = now_iso
            inv = Investigator(**raw)
            self._investigators[inv.id] = inv

        # --- 30+ certifications (some expired, some expiring within 90 days) ---
        certs_raw: list[dict[str, Any]] = [
            # inv-001
            {"id": "cert-001", "investigator_id": "inv-001", "certification_type": CertificationType.GCP_TRAINING, "issued_date": "2024-01-15", "expiry_date": "2026-01-15", "status": TrainingStatus.COMPLETED, "issuing_authority": "TransCelerate", "certificate_number": "GCP-2024-001"},
            {"id": "cert-002", "investigator_id": "inv-001", "certification_type": CertificationType.HUMAN_SUBJECTS_PROTECTION, "issued_date": "2023-06-01", "expiry_date": "2026-06-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "CITI Program", "certificate_number": "HSP-2023-001"},
            {"id": "cert-003", "investigator_id": "inv-001", "certification_type": CertificationType.MEDICAL_LICENSE, "issued_date": "2019-03-01", "expiry_date": "2026-03-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "Maryland Board of Medicine", "certificate_number": "ML-MD-44821"},
            {"id": "cert-004", "investigator_id": "inv-001", "certification_type": CertificationType.PROTOCOL_TRAINING, "issued_date": "2025-01-10", "expiry_date": "2026-01-10", "status": TrainingStatus.COMPLETED, "issuing_authority": "Regeneron", "certificate_number": "PT-2025-001"},
            # inv-002
            {"id": "cert-005", "investigator_id": "inv-002", "certification_type": CertificationType.GCP_TRAINING, "issued_date": "2024-03-01", "expiry_date": "2026-03-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "TransCelerate", "certificate_number": "GCP-2024-005"},
            {"id": "cert-006", "investigator_id": "inv-002", "certification_type": CertificationType.HUMAN_SUBJECTS_PROTECTION, "issued_date": "2023-09-15", "expiry_date": "2025-09-15", "status": TrainingStatus.EXPIRED, "issuing_authority": "CITI Program", "certificate_number": "HSP-2023-006"},
            {"id": "cert-007", "investigator_id": "inv-002", "certification_type": CertificationType.MEDICAL_LICENSE, "issued_date": "2015-05-01", "expiry_date": "2026-05-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "Minnesota Board of Medicine", "certificate_number": "ML-MN-33912"},
            {"id": "cert-008", "investigator_id": "inv-002", "certification_type": CertificationType.DEA_LICENSE, "issued_date": "2020-01-01", "expiry_date": "2026-01-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "DEA", "certificate_number": "DEA-2020-008"},
            # inv-003
            {"id": "cert-009", "investigator_id": "inv-003", "certification_type": CertificationType.GCP_TRAINING, "issued_date": "2024-06-01", "expiry_date": "2026-06-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "TransCelerate", "certificate_number": "GCP-2024-009"},
            {"id": "cert-010", "investigator_id": "inv-003", "certification_type": CertificationType.HUMAN_SUBJECTS_PROTECTION, "issued_date": "2024-01-15", "expiry_date": "2026-01-15", "status": TrainingStatus.COMPLETED, "issuing_authority": "CITI Program", "certificate_number": "HSP-2024-010"},
            {"id": "cert-011", "investigator_id": "inv-003", "certification_type": CertificationType.MEDICAL_LICENSE, "issued_date": "2010-09-01", "expiry_date": "2026-09-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "German Medical Association", "certificate_number": "ML-DE-7834"},
            {"id": "cert-012", "investigator_id": "inv-003", "certification_type": CertificationType.IRB_APPROVAL, "issued_date": "2025-01-01", "expiry_date": "2026-01-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "Charite Ethics Committee", "certificate_number": "IRB-2025-012"},
            {"id": "cert-013", "investigator_id": "inv-003", "certification_type": CertificationType.PROTOCOL_TRAINING, "issued_date": "2025-02-01", "expiry_date": "2026-02-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "Regeneron", "certificate_number": "PT-2025-013"},
            # inv-004
            {"id": "cert-014", "investigator_id": "inv-004", "certification_type": CertificationType.GCP_TRAINING, "issued_date": "2024-04-01", "expiry_date": "2026-04-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "TransCelerate", "certificate_number": "GCP-2024-014"},
            {"id": "cert-015", "investigator_id": "inv-004", "certification_type": CertificationType.HUMAN_SUBJECTS_PROTECTION, "issued_date": "2024-02-01", "expiry_date": "2026-02-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "CITI Program", "certificate_number": "HSP-2024-015"},
            {"id": "cert-016", "investigator_id": "inv-004", "certification_type": CertificationType.PROTOCOL_TRAINING, "issued_date": "2025-03-01", "expiry_date": "2026-03-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "Regeneron", "certificate_number": "PT-2025-016"},
            # inv-005
            {"id": "cert-017", "investigator_id": "inv-005", "certification_type": CertificationType.GCP_TRAINING, "issued_date": "2023-11-01", "expiry_date": "2025-11-01", "status": TrainingStatus.EXPIRED, "issuing_authority": "TransCelerate", "certificate_number": "GCP-2023-017"},
            {"id": "cert-018", "investigator_id": "inv-005", "certification_type": CertificationType.HUMAN_SUBJECTS_PROTECTION, "issued_date": "2024-05-01", "expiry_date": "2026-05-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "CITI Program", "certificate_number": "HSP-2024-018"},
            {"id": "cert-019", "investigator_id": "inv-005", "certification_type": CertificationType.MEDICAL_LICENSE, "issued_date": "2012-07-01", "expiry_date": "2026-07-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "Japan Medical Association", "certificate_number": "ML-JP-9921"},
            # inv-006
            {"id": "cert-020", "investigator_id": "inv-006", "certification_type": CertificationType.GCP_TRAINING, "issued_date": "2024-08-01", "expiry_date": "2026-08-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "TransCelerate", "certificate_number": "GCP-2024-020"},
            {"id": "cert-021", "investigator_id": "inv-006", "certification_type": CertificationType.HUMAN_SUBJECTS_PROTECTION, "issued_date": "2024-03-01", "expiry_date": "2026-03-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "CITI Program", "certificate_number": "HSP-2024-021"},
            # inv-007
            {"id": "cert-022", "investigator_id": "inv-007", "certification_type": CertificationType.GCP_TRAINING, "issued_date": "2025-01-01", "expiry_date": "2027-01-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "TransCelerate", "certificate_number": "GCP-2025-022"},
            {"id": "cert-023", "investigator_id": "inv-007", "certification_type": CertificationType.IATA_DANGEROUS_GOODS, "issued_date": "2024-06-01", "expiry_date": "2026-06-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "IATA", "certificate_number": "IATA-2024-023"},
            {"id": "cert-024", "investigator_id": "inv-007", "certification_type": CertificationType.HUMAN_SUBJECTS_PROTECTION, "issued_date": "2024-09-01", "expiry_date": "2026-09-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "CITI Program", "certificate_number": "HSP-2024-024"},
            {"id": "cert-025", "investigator_id": "inv-007", "certification_type": CertificationType.PROTOCOL_TRAINING, "issued_date": "2025-03-15", "expiry_date": "2026-03-15", "status": TrainingStatus.COMPLETED, "issuing_authority": "Regeneron", "certificate_number": "PT-2025-025"},
            # inv-008
            {"id": "cert-026", "investigator_id": "inv-008", "certification_type": CertificationType.GCP_TRAINING, "issued_date": "2024-07-01", "expiry_date": "2026-07-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "TransCelerate", "certificate_number": "GCP-2024-026"},
            {"id": "cert-027", "investigator_id": "inv-008", "certification_type": CertificationType.MEDICAL_LICENSE, "issued_date": "2016-02-01", "expiry_date": "2026-02-15", "status": TrainingStatus.COMPLETED, "issuing_authority": "California Medical Board", "certificate_number": "ML-CA-44290"},
            {"id": "cert-028", "investigator_id": "inv-008", "certification_type": CertificationType.PROTOCOL_TRAINING, "issued_date": "2025-04-01", "expiry_date": "2026-04-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "Regeneron", "certificate_number": "PT-2025-028"},
            # inv-009
            {"id": "cert-029", "investigator_id": "inv-009", "certification_type": CertificationType.GCP_TRAINING, "issued_date": "2024-02-15", "expiry_date": "2026-02-15", "status": TrainingStatus.COMPLETED, "issuing_authority": "TransCelerate", "certificate_number": "GCP-2024-029"},
            {"id": "cert-030", "investigator_id": "inv-009", "certification_type": CertificationType.HUMAN_SUBJECTS_PROTECTION, "issued_date": "2024-04-01", "expiry_date": "2026-04-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "CITI Program", "certificate_number": "HSP-2024-030"},
            {"id": "cert-031", "investigator_id": "inv-009", "certification_type": CertificationType.MEDICAL_LICENSE, "issued_date": "2011-08-01", "expiry_date": "2026-08-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "Medical Council of India", "certificate_number": "ML-IN-38821"},
            {"id": "cert-032", "investigator_id": "inv-009", "certification_type": CertificationType.PROTOCOL_TRAINING, "issued_date": "2025-05-01", "expiry_date": "2026-05-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "Regeneron", "certificate_number": "PT-2025-032"},
            # inv-010 coordinator
            {"id": "cert-033", "investigator_id": "inv-010", "certification_type": CertificationType.GCP_TRAINING, "issued_date": "2024-10-01", "expiry_date": "2026-10-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "TransCelerate", "certificate_number": "GCP-2024-033"},
            {"id": "cert-034", "investigator_id": "inv-010", "certification_type": CertificationType.IATA_DANGEROUS_GOODS, "issued_date": "2024-11-01", "expiry_date": "2026-11-01", "status": TrainingStatus.COMPLETED, "issuing_authority": "IATA", "certificate_number": "IATA-2024-034"},
            {"id": "cert-035", "investigator_id": "inv-010", "certification_type": CertificationType.HUMAN_SUBJECTS_PROTECTION, "issued_date": "2024-07-15", "expiry_date": "2026-07-15", "status": TrainingStatus.COMPLETED, "issuing_authority": "CITI Program", "certificate_number": "HSP-2024-035"},
        ]

        for raw in certs_raw:
            cert = InvestigatorCertification(**raw)
            self._certifications[cert.id] = cert

        # --- 8 scorecards across top investigators ---
        scorecards_raw: list[dict[str, Any]] = [
            {"id": "sc-001", "investigator_id": "inv-001", "period_start": "2025-07-01", "period_end": "2025-09-30", "enrollment_target": 25, "enrollment_actual": 28, "enrollment_rate": 1.12, "screen_failure_rate": 0.22, "protocol_deviation_count": 1, "query_response_time_days": 1.2, "data_quality_score": 95.0, "patient_retention_rate": 0.94, "ae_reporting_timeliness": 98.0, "overall_rating": PerformanceRating.EXCEPTIONAL, "strengths": ["Excellent enrollment rate", "Strong data quality", "Timely AE reporting"], "improvement_areas": ["Minor protocol deviation documented"]},
            {"id": "sc-002", "investigator_id": "inv-001", "period_start": "2025-04-01", "period_end": "2025-06-30", "enrollment_target": 20, "enrollment_actual": 22, "enrollment_rate": 1.10, "screen_failure_rate": 0.25, "protocol_deviation_count": 0, "query_response_time_days": 1.5, "data_quality_score": 93.0, "patient_retention_rate": 0.92, "ae_reporting_timeliness": 96.0, "overall_rating": PerformanceRating.EXCEPTIONAL, "strengths": ["Zero protocol deviations", "Above-target enrollment"], "improvement_areas": []},
            {"id": "sc-003", "investigator_id": "inv-002", "period_start": "2025-07-01", "period_end": "2025-09-30", "enrollment_target": 20, "enrollment_actual": 18, "enrollment_rate": 0.90, "screen_failure_rate": 0.20, "protocol_deviation_count": 1, "query_response_time_days": 1.8, "data_quality_score": 88.0, "patient_retention_rate": 0.90, "ae_reporting_timeliness": 92.0, "overall_rating": PerformanceRating.ABOVE_AVERAGE, "strengths": ["Low screen failure rate", "Good patient retention"], "improvement_areas": ["Slightly below enrollment target"]},
            {"id": "sc-004", "investigator_id": "inv-003", "period_start": "2025-07-01", "period_end": "2025-09-30", "enrollment_target": 22, "enrollment_actual": 26, "enrollment_rate": 1.18, "screen_failure_rate": 0.18, "protocol_deviation_count": 0, "query_response_time_days": 1.0, "data_quality_score": 97.0, "patient_retention_rate": 0.96, "ae_reporting_timeliness": 99.0, "overall_rating": PerformanceRating.EXCEPTIONAL, "strengths": ["Outstanding data quality", "Fastest query response time", "Best retention rate"], "improvement_areas": []},
            {"id": "sc-005", "investigator_id": "inv-005", "period_start": "2025-07-01", "period_end": "2025-09-30", "enrollment_target": 18, "enrollment_actual": 16, "enrollment_rate": 0.89, "screen_failure_rate": 0.28, "protocol_deviation_count": 2, "query_response_time_days": 2.5, "data_quality_score": 82.0, "patient_retention_rate": 0.88, "ae_reporting_timeliness": 85.0, "overall_rating": PerformanceRating.AVERAGE, "strengths": ["Consistent enrollment numbers"], "improvement_areas": ["Reduce screen failure rate", "Improve query response time", "Address protocol deviations"]},
            {"id": "sc-006", "investigator_id": "inv-006", "period_start": "2025-07-01", "period_end": "2025-09-30", "enrollment_target": 15, "enrollment_actual": 10, "enrollment_rate": 0.67, "screen_failure_rate": 0.35, "protocol_deviation_count": 3, "query_response_time_days": 3.5, "data_quality_score": 72.0, "patient_retention_rate": 0.80, "ae_reporting_timeliness": 78.0, "overall_rating": PerformanceRating.BELOW_AVERAGE, "strengths": [], "improvement_areas": ["Increase enrollment rate", "Reduce screen failure rate", "Improve data quality", "Address protocol deviations"]},
            {"id": "sc-007", "investigator_id": "inv-009", "period_start": "2025-07-01", "period_end": "2025-09-30", "enrollment_target": 20, "enrollment_actual": 21, "enrollment_rate": 1.05, "screen_failure_rate": 0.20, "protocol_deviation_count": 0, "query_response_time_days": 1.3, "data_quality_score": 94.0, "patient_retention_rate": 0.95, "ae_reporting_timeliness": 97.0, "overall_rating": PerformanceRating.EXCEPTIONAL, "strengths": ["Zero deviations", "Excellent data quality", "Strong patient retention"], "improvement_areas": []},
            {"id": "sc-008", "investigator_id": "inv-011", "period_start": "2025-07-01", "period_end": "2025-09-30", "enrollment_target": 12, "enrollment_actual": 7, "enrollment_rate": 0.58, "screen_failure_rate": 0.42, "protocol_deviation_count": 4, "query_response_time_days": 4.2, "data_quality_score": 65.0, "patient_retention_rate": 0.72, "ae_reporting_timeliness": 70.0, "overall_rating": PerformanceRating.BELOW_AVERAGE, "strengths": [], "improvement_areas": ["Significantly increase enrollment", "Reduce screen failures", "Improve data quality urgently", "Mandatory retraining on protocol"]},
        ]

        for raw in scorecards_raw:
            sc = InvestigatorScorecard(**raw)
            self._scorecards[sc.id] = sc

        # --- 4 inspection records ---
        inspections_raw: list[dict[str, Any]] = [
            {"id": "insp-001", "investigator_id": "inv-001", "site_id": "site-001", "inspection_date": "2025-06-15", "inspector_name": "FDA Inspector J. Martinez", "inspection_type": "routine", "result": InspectionResult.NO_FINDINGS, "findings": [], "corrective_actions": [], "follow_up_date": None},
            {"id": "insp-002", "investigator_id": "inv-003", "site_id": "site-003", "inspection_date": "2025-08-20", "inspector_name": "EMA Inspector K. Schneider", "inspection_type": "routine", "result": InspectionResult.NO_FINDINGS, "findings": [], "corrective_actions": [], "follow_up_date": None},
            {"id": "insp-003", "investigator_id": "inv-006", "site_id": "site-004", "inspection_date": "2025-09-10", "inspector_name": "FDA Inspector L. Thompson", "inspection_type": "for-cause", "result": InspectionResult.MINOR_FINDINGS, "findings": ["Incomplete source document verification", "Minor consent form dating errors"], "corrective_actions": ["Implement double-check procedure for source documents", "Retrain coordinators on consent form completion"], "follow_up_date": "2026-03-10"},
            {"id": "insp-004", "investigator_id": "inv-011", "site_id": "site-005", "inspection_date": "2025-10-05", "inspector_name": "FDA Inspector M. Rodriguez", "inspection_type": "for-cause", "result": InspectionResult.MAJOR_FINDINGS, "findings": ["Protocol deviations not reported timely", "Inadequate drug accountability records", "Missing informed consent signatures"], "corrective_actions": ["Submit CAPA within 30 days", "Implement electronic drug accountability system", "Audit all consent forms within 60 days"], "follow_up_date": "2026-01-05"},
        ]

        for raw in inspections_raw:
            insp = InspectionRecord(**raw)
            self._inspections[insp.id] = insp

        # --- 20+ training records ---
        training_raw: list[dict[str, Any]] = [
            # inv-001
            {"id": "tr-001", "investigator_id": "inv-001", "training_name": "GCP Refresher 2025", "training_type": CertificationType.GCP_TRAINING, "required_by": "2025-06-01", "completed_date": "2025-05-15", "status": TrainingStatus.COMPLETED, "valid_until": "2027-05-15"},
            {"id": "tr-002", "investigator_id": "inv-001", "training_name": "Protocol EYLEA-HD Amendment 3", "training_type": CertificationType.PROTOCOL_TRAINING, "required_by": "2025-03-01", "completed_date": "2025-02-20", "status": TrainingStatus.COMPLETED, "valid_until": "2026-02-20"},
            {"id": "tr-003", "investigator_id": "inv-001", "training_name": "AE Reporting Update", "training_type": CertificationType.HUMAN_SUBJECTS_PROTECTION, "required_by": "2025-09-01", "completed_date": "2025-08-28", "status": TrainingStatus.COMPLETED, "valid_until": "2026-08-28"},
            # inv-002
            {"id": "tr-004", "investigator_id": "inv-002", "training_name": "GCP Refresher 2025", "training_type": CertificationType.GCP_TRAINING, "required_by": "2025-07-01", "completed_date": "2025-06-25", "status": TrainingStatus.COMPLETED, "valid_until": "2027-06-25"},
            {"id": "tr-005", "investigator_id": "inv-002", "training_name": "Human Subjects Protection Renewal", "training_type": CertificationType.HUMAN_SUBJECTS_PROTECTION, "required_by": "2025-09-15", "completed_date": None, "status": TrainingStatus.OVERDUE, "valid_until": None},
            {"id": "tr-006", "investigator_id": "inv-002", "training_name": "Protocol DUPIXENT Amendment 2", "training_type": CertificationType.PROTOCOL_TRAINING, "required_by": "2025-11-01", "completed_date": None, "status": TrainingStatus.IN_PROGRESS, "valid_until": None},
            # inv-003
            {"id": "tr-007", "investigator_id": "inv-003", "training_name": "GCP Advanced Training", "training_type": CertificationType.GCP_TRAINING, "required_by": "2025-08-01", "completed_date": "2025-07-20", "status": TrainingStatus.COMPLETED, "valid_until": "2027-07-20"},
            {"id": "tr-008", "investigator_id": "inv-003", "training_name": "IRB Annual Review Training", "training_type": CertificationType.IRB_APPROVAL, "required_by": "2025-12-01", "completed_date": "2025-11-15", "status": TrainingStatus.COMPLETED, "valid_until": "2026-11-15"},
            # inv-004
            {"id": "tr-009", "investigator_id": "inv-004", "training_name": "GCP Refresher 2025", "training_type": CertificationType.GCP_TRAINING, "required_by": "2025-05-01", "completed_date": "2025-04-28", "status": TrainingStatus.COMPLETED, "valid_until": "2027-04-28"},
            {"id": "tr-010", "investigator_id": "inv-004", "training_name": "Protocol LIBTAYO Training", "training_type": CertificationType.PROTOCOL_TRAINING, "required_by": "2025-10-01", "completed_date": None, "status": TrainingStatus.IN_PROGRESS, "valid_until": None},
            # inv-005
            {"id": "tr-011", "investigator_id": "inv-005", "training_name": "GCP Refresher 2025", "training_type": CertificationType.GCP_TRAINING, "required_by": "2025-10-01", "completed_date": None, "status": TrainingStatus.OVERDUE, "valid_until": None},
            {"id": "tr-012", "investigator_id": "inv-005", "training_name": "Protocol Amendment Training", "training_type": CertificationType.PROTOCOL_TRAINING, "required_by": "2025-12-15", "completed_date": None, "status": TrainingStatus.NOT_STARTED, "valid_until": None},
            # inv-006
            {"id": "tr-013", "investigator_id": "inv-006", "training_name": "GCP Refresher 2025", "training_type": CertificationType.GCP_TRAINING, "required_by": "2025-09-01", "completed_date": "2025-08-30", "status": TrainingStatus.COMPLETED, "valid_until": "2027-08-30"},
            {"id": "tr-014", "investigator_id": "inv-006", "training_name": "Source Document Verification", "training_type": CertificationType.PROTOCOL_TRAINING, "required_by": "2025-12-01", "completed_date": None, "status": TrainingStatus.NOT_STARTED, "valid_until": None},
            # inv-007
            {"id": "tr-015", "investigator_id": "inv-007", "training_name": "GCP Initial Training", "training_type": CertificationType.GCP_TRAINING, "required_by": "2025-02-01", "completed_date": "2025-01-25", "status": TrainingStatus.COMPLETED, "valid_until": "2027-01-25"},
            {"id": "tr-016", "investigator_id": "inv-007", "training_name": "IATA Dangerous Goods Recertification", "training_type": CertificationType.IATA_DANGEROUS_GOODS, "required_by": "2025-07-01", "completed_date": "2025-06-15", "status": TrainingStatus.COMPLETED, "valid_until": "2027-06-15"},
            {"id": "tr-017", "investigator_id": "inv-007", "training_name": "Coordinator Essentials", "training_type": CertificationType.PROTOCOL_TRAINING, "required_by": "2025-04-01", "completed_date": "2025-03-28", "status": TrainingStatus.COMPLETED, "valid_until": "2026-03-28"},
            # inv-008
            {"id": "tr-018", "investigator_id": "inv-008", "training_name": "GCP Refresher 2025", "training_type": CertificationType.GCP_TRAINING, "required_by": "2025-08-01", "completed_date": "2025-07-28", "status": TrainingStatus.COMPLETED, "valid_until": "2027-07-28"},
            {"id": "tr-019", "investigator_id": "inv-008", "training_name": "Medical License Renewal Training", "training_type": CertificationType.MEDICAL_LICENSE, "required_by": "2026-02-01", "completed_date": None, "status": TrainingStatus.IN_PROGRESS, "valid_until": None},
            # inv-009
            {"id": "tr-020", "investigator_id": "inv-009", "training_name": "GCP Refresher 2025", "training_type": CertificationType.GCP_TRAINING, "required_by": "2025-04-01", "completed_date": "2025-03-20", "status": TrainingStatus.COMPLETED, "valid_until": "2027-03-20"},
            {"id": "tr-021", "investigator_id": "inv-009", "training_name": "Protocol Training DUPIXENT", "training_type": CertificationType.PROTOCOL_TRAINING, "required_by": "2025-06-01", "completed_date": "2025-05-28", "status": TrainingStatus.COMPLETED, "valid_until": "2026-05-28"},
            # inv-010
            {"id": "tr-022", "investigator_id": "inv-010", "training_name": "IATA Dangerous Goods Initial", "training_type": CertificationType.IATA_DANGEROUS_GOODS, "required_by": "2025-01-01", "completed_date": "2024-12-20", "status": TrainingStatus.COMPLETED, "valid_until": "2026-12-20"},
            {"id": "tr-023", "investigator_id": "inv-010", "training_name": "GCP Coordinator Training", "training_type": CertificationType.GCP_TRAINING, "required_by": "2025-11-01", "completed_date": "2025-10-20", "status": TrainingStatus.COMPLETED, "valid_until": "2027-10-20"},
            # inv-011
            {"id": "tr-024", "investigator_id": "inv-011", "training_name": "GCP Refresher 2025", "training_type": CertificationType.GCP_TRAINING, "required_by": "2025-06-01", "completed_date": None, "status": TrainingStatus.OVERDUE, "valid_until": None},
            {"id": "tr-025", "investigator_id": "inv-011", "training_name": "Protocol Deviation Reporting", "training_type": CertificationType.PROTOCOL_TRAINING, "required_by": "2025-11-01", "completed_date": None, "status": TrainingStatus.NOT_STARTED, "valid_until": None},
            # inv-012
            {"id": "tr-026", "investigator_id": "inv-012", "training_name": "GCP Refresher 2025", "training_type": CertificationType.GCP_TRAINING, "required_by": "2025-09-01", "completed_date": "2025-08-25", "status": TrainingStatus.COMPLETED, "valid_until": "2027-08-25"},
            {"id": "tr-027", "investigator_id": "inv-012", "training_name": "IRB Ethics Training", "training_type": CertificationType.IRB_APPROVAL, "required_by": "2025-12-01", "completed_date": "2025-11-20", "status": TrainingStatus.COMPLETED, "valid_until": "2026-11-20"},
        ]

        for raw in training_raw:
            tr = TrainingRecord(**raw)
            self._training_records[tr.id] = tr

    # ------------------------------------------------------------------
    # Investigator CRUD
    # ------------------------------------------------------------------

    def get_investigator(self, investigator_id: str) -> Investigator | None:
        """Return an investigator by ID, or ``None`` if not found."""
        return self._investigators.get(investigator_id)

    def list_investigators(
        self,
        *,
        role: str | None = None,
        site_id: str | None = None,
        rating: str | None = None,
    ) -> InvestigatorListResponse:
        """Return investigators with optional filters."""
        result = list(self._investigators.values())

        if role:
            result = [inv for inv in result if inv.role.value == role]
        if site_id:
            result = [inv for inv in result if inv.site_id == site_id]
        if rating:
            # Map rating to score ranges
            rating_ranges = {
                "exceptional": (90.0, 100.0),
                "above_average": (80.0, 89.99),
                "average": (70.0, 79.99),
                "below_average": (60.0, 69.99),
                "unacceptable": (0.0, 59.99),
            }
            bounds = rating_ranges.get(rating)
            if bounds:
                lo, hi = bounds
                result = [
                    inv for inv in result
                    if inv.performance_score is not None and lo <= inv.performance_score <= hi
                ]

        return InvestigatorListResponse(investigators=result, total=len(result))

    def create_investigator(self, req: InvestigatorCreateRequest) -> Investigator:
        """Create a new investigator."""
        now_iso = datetime.now(timezone.utc).isoformat()
        inv = Investigator(
            id=f"inv-{uuid.uuid4().hex[:8]}",
            name=req.name,
            role=req.role,
            site_id=req.site_id,
            site_name=req.site_name,
            email=req.email,
            specialty=req.specialty,
            medical_license_number=req.medical_license_number,
            npi_number=req.npi_number,
            years_experience=req.years_experience,
            trials_conducted=req.trials_conducted,
            active_trials=req.active_trials,
            certifications=[],
            performance_score=None,
            last_performance_review=None,
            created_at=now_iso,
            updated_at=now_iso,
        )
        with self._lock:
            self._investigators[inv.id] = inv
        return inv

    def update_investigator(self, investigator_id: str, updates: dict[str, Any]) -> Investigator | None:
        """Update fields of an existing investigator."""
        inv = self._investigators.get(investigator_id)
        if inv is None:
            return None
        data = inv.model_dump()
        data.update(updates)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated = Investigator(**data)
        with self._lock:
            self._investigators[investigator_id] = updated
        return updated

    def delete_investigator(self, investigator_id: str) -> bool:
        """Delete an investigator. Returns True if found and deleted."""
        with self._lock:
            return self._investigators.pop(investigator_id, None) is not None

    # ------------------------------------------------------------------
    # Certification management
    # ------------------------------------------------------------------

    def get_certifications(self, investigator_id: str) -> list[InvestigatorCertification]:
        """Return all certifications for an investigator."""
        return [c for c in self._certifications.values() if c.investigator_id == investigator_id]

    def add_certification(self, cert: InvestigatorCertification) -> InvestigatorCertification:
        """Add a new certification record."""
        with self._lock:
            self._certifications[cert.id] = cert
        return cert

    def get_certification_expiry_report(self, days_ahead: int = 90) -> CertificationExpiryReport:
        """Generate a report of certifications expiring within ``days_ahead`` days."""
        now = datetime.now(timezone.utc).date()
        alerts: list[CertificationExpiryAlert] = []
        expired = 0
        exp_30 = 0
        exp_60 = 0
        exp_90 = 0

        for cert in self._certifications.values():
            if cert.expiry_date is None:
                continue
            try:
                expiry = datetime.fromisoformat(cert.expiry_date).date()
            except (ValueError, TypeError):
                continue

            days_until = (expiry - now).days
            if days_until > days_ahead:
                continue

            inv = self._investigators.get(cert.investigator_id)
            inv_name = inv.name if inv else "Unknown"

            if days_until < 0:
                severity = "critical"
                expired += 1
            elif days_until <= 30:
                severity = "critical"
                exp_30 += 1
            elif days_until <= 60:
                severity = "warning"
                exp_60 += 1
            else:
                severity = "info"
                exp_90 += 1

            alerts.append(CertificationExpiryAlert(
                investigator_id=cert.investigator_id,
                investigator_name=inv_name,
                certification_type=cert.certification_type,
                expiry_date=cert.expiry_date,
                days_until_expiry=days_until,
                severity=severity,
            ))

        # Sort by days_until_expiry ascending (most urgent first)
        alerts.sort(key=lambda a: a.days_until_expiry)

        return CertificationExpiryReport(
            alerts=alerts,
            total_expiring_30_days=exp_30,
            total_expiring_60_days=exp_60,
            total_expiring_90_days=exp_90,
            total_expired=expired,
        )

    # ------------------------------------------------------------------
    # Scorecard management
    # ------------------------------------------------------------------

    def get_scorecards(self, investigator_id: str) -> ScorecardListResponse:
        """Return all scorecards for an investigator."""
        cards = [sc for sc in self._scorecards.values() if sc.investigator_id == investigator_id]
        return ScorecardListResponse(scorecards=cards, total=len(cards))

    def get_scorecard(self, scorecard_id: str) -> InvestigatorScorecard | None:
        """Return a scorecard by ID."""
        return self._scorecards.get(scorecard_id)

    def create_scorecard(self, req: ScorecardCreateRequest) -> InvestigatorScorecard:
        """Create a new scorecard. Auto-calculates enrollment_rate and overall_rating."""
        enrollment_rate = req.enrollment_actual / max(req.enrollment_target, 1)

        # Calculate overall rating from composite metrics
        composite = self._compute_composite_score(
            enrollment_rate=enrollment_rate,
            screen_failure_rate=req.screen_failure_rate,
            protocol_deviation_count=req.protocol_deviation_count,
            query_response_time_days=req.query_response_time_days,
            data_quality_score=req.data_quality_score,
            patient_retention_rate=req.patient_retention_rate,
            ae_reporting_timeliness=req.ae_reporting_timeliness,
        )
        overall_rating = self._score_to_rating(composite)

        strengths: list[str] = []
        improvement_areas: list[str] = []
        if enrollment_rate >= 1.0:
            strengths.append("Met or exceeded enrollment target")
        else:
            improvement_areas.append("Below enrollment target")
        if req.data_quality_score >= 90.0:
            strengths.append("High data quality score")
        elif req.data_quality_score < 75.0:
            improvement_areas.append("Data quality needs improvement")
        if req.protocol_deviation_count == 0:
            strengths.append("Zero protocol deviations")
        elif req.protocol_deviation_count >= 3:
            improvement_areas.append("Address protocol deviations")
        if req.query_response_time_days <= 2.0:
            strengths.append("Timely query responses")
        elif req.query_response_time_days > 3.0:
            improvement_areas.append("Improve query response time")

        sc = InvestigatorScorecard(
            id=f"sc-{uuid.uuid4().hex[:8]}",
            investigator_id=req.investigator_id,
            period_start=req.period_start,
            period_end=req.period_end,
            enrollment_target=req.enrollment_target,
            enrollment_actual=req.enrollment_actual,
            enrollment_rate=round(enrollment_rate, 2),
            screen_failure_rate=req.screen_failure_rate,
            protocol_deviation_count=req.protocol_deviation_count,
            query_response_time_days=req.query_response_time_days,
            data_quality_score=req.data_quality_score,
            patient_retention_rate=req.patient_retention_rate,
            ae_reporting_timeliness=req.ae_reporting_timeliness,
            overall_rating=overall_rating,
            strengths=strengths,
            improvement_areas=improvement_areas,
        )
        with self._lock:
            self._scorecards[sc.id] = sc
        return sc

    def compare_scorecards(self, investigator_id: str) -> list[InvestigatorScorecard]:
        """Return scorecards for an investigator sorted by period_start for historical comparison."""
        cards = [sc for sc in self._scorecards.values() if sc.investigator_id == investigator_id]
        cards.sort(key=lambda x: x.period_start)
        return cards

    # ------------------------------------------------------------------
    # Performance ranking
    # ------------------------------------------------------------------

    def get_performance_rankings(self, limit: int = 20) -> PerformanceRankingResponse:
        """Rank investigators by performance score descending."""
        scored = [
            inv for inv in self._investigators.values()
            if inv.performance_score is not None
        ]
        scored.sort(key=lambda x: x.performance_score or 0.0, reverse=True)
        scored = scored[:limit]

        rankings: list[PerformanceRanking] = []
        for idx, inv in enumerate(scored, 1):
            # Find most recent scorecard for additional context
            cards = [sc for sc in self._scorecards.values() if sc.investigator_id == inv.id]
            latest_card = max(cards, key=lambda x: x.period_end) if cards else None

            rankings.append(PerformanceRanking(
                rank=idx,
                investigator_id=inv.id,
                investigator_name=inv.name,
                role=inv.role,
                site_name=inv.site_name,
                performance_score=inv.performance_score or 0.0,
                enrollment_rate=latest_card.enrollment_rate if latest_card else 0.0,
                data_quality_score=latest_card.data_quality_score if latest_card else 0.0,
            ))

        return PerformanceRankingResponse(rankings=rankings, total=len(rankings))

    # ------------------------------------------------------------------
    # Inspection records
    # ------------------------------------------------------------------

    def get_inspections(self, investigator_id: str | None = None) -> list[InspectionRecord]:
        """Return inspection records, optionally filtered by investigator."""
        if investigator_id:
            return [i for i in self._inspections.values() if i.investigator_id == investigator_id]
        return list(self._inspections.values())

    def get_inspection(self, inspection_id: str) -> InspectionRecord | None:
        """Return a single inspection by ID."""
        return self._inspections.get(inspection_id)

    def create_inspection(self, req: InspectionCreateRequest) -> InspectionRecord:
        """Create a new inspection record."""
        insp = InspectionRecord(
            id=f"insp-{uuid.uuid4().hex[:8]}",
            investigator_id=req.investigator_id,
            site_id=req.site_id,
            inspection_date=req.inspection_date,
            inspector_name=req.inspector_name,
            inspection_type=req.inspection_type,
            result=req.result,
            findings=req.findings,
            corrective_actions=req.corrective_actions,
            follow_up_date=req.follow_up_date,
        )
        with self._lock:
            self._inspections[insp.id] = insp
        return insp

    # ------------------------------------------------------------------
    # Training compliance
    # ------------------------------------------------------------------

    def get_training_records(self, investigator_id: str | None = None) -> list[TrainingRecord]:
        """Return training records, optionally filtered by investigator."""
        if investigator_id:
            return [t for t in self._training_records.values() if t.investigator_id == investigator_id]
        return list(self._training_records.values())

    def create_training_record(self, req: TrainingCreateRequest) -> TrainingRecord:
        """Create a new training record."""
        tr = TrainingRecord(
            id=f"tr-{uuid.uuid4().hex[:8]}",
            investigator_id=req.investigator_id,
            training_name=req.training_name,
            training_type=req.training_type,
            required_by=req.required_by,
            completed_date=req.completed_date,
            status=req.status,
            valid_until=req.valid_until,
        )
        with self._lock:
            self._training_records[tr.id] = tr
        return tr

    def get_training_gap_analysis(self, investigator_id: str) -> TrainingGapAnalysis | None:
        """Analyze training gaps for an investigator."""
        inv = self._investigators.get(investigator_id)
        if inv is None:
            return None

        records = self.get_training_records(investigator_id)
        completed = sum(1 for r in records if r.status == TrainingStatus.COMPLETED)
        overdue = sum(1 for r in records if r.status == TrainingStatus.OVERDUE)
        in_progress = sum(1 for r in records if r.status == TrainingStatus.IN_PROGRESS)
        not_started = sum(1 for r in records if r.status == TrainingStatus.NOT_STARTED)
        expired = sum(1 for r in records if r.status == TrainingStatus.EXPIRED)

        total = len(records)
        compliance_rate = (completed / total * 100.0) if total > 0 else 100.0

        gaps: list[str] = []
        if overdue > 0:
            overdue_names = [r.training_name for r in records if r.status == TrainingStatus.OVERDUE]
            gaps.extend([f"Overdue: {name}" for name in overdue_names])
        if expired > 0:
            expired_names = [r.training_name for r in records if r.status == TrainingStatus.EXPIRED]
            gaps.extend([f"Expired: {name}" for name in expired_names])
        if not_started > 0:
            ns_names = [r.training_name for r in records if r.status == TrainingStatus.NOT_STARTED]
            gaps.extend([f"Not started: {name}" for name in ns_names])

        return TrainingGapAnalysis(
            investigator_id=investigator_id,
            investigator_name=inv.name,
            completed_count=completed,
            overdue_count=overdue,
            in_progress_count=in_progress,
            not_started_count=not_started,
            expired_count=expired,
            compliance_rate=round(compliance_rate, 1),
            gaps=gaps,
        )

    # ------------------------------------------------------------------
    # Workload analysis
    # ------------------------------------------------------------------

    def get_workload(self, investigator_id: str) -> InvestigatorWorkload | None:
        """Return workload metrics for an investigator."""
        inv = self._investigators.get(investigator_id)
        if inv is None:
            return None

        # Capacity heuristic based on role
        capacity_map = {
            InvestigatorRole.PRINCIPAL_INVESTIGATOR: 50,
            InvestigatorRole.SUB_INVESTIGATOR: 35,
            InvestigatorRole.CO_INVESTIGATOR: 40,
            InvestigatorRole.STUDY_COORDINATOR: 60,
        }
        capacity = capacity_map.get(inv.role, 40)
        # Estimate total patients based on active_trials * avg patients per trial
        total_patients = inv.active_trials * 12  # rough estimate
        utilization = min(100.0, (total_patients / max(capacity, 1)) * 100.0)

        return InvestigatorWorkload(
            investigator_id=inv.id,
            investigator_name=inv.name,
            active_trial_count=inv.active_trials,
            total_patients=total_patients,
            enrollment_capacity=capacity,
            utilization_percent=round(utilization, 1),
        )

    def get_workload_report(self) -> WorkloadReport:
        """Return workload analysis for all investigators."""
        workloads: list[InvestigatorWorkload] = []
        for inv_id in self._investigators:
            wl = self.get_workload(inv_id)
            if wl:
                workloads.append(wl)

        if not workloads:
            return WorkloadReport(workloads=[], avg_utilization=0.0, overloaded_count=0, available_count=0)

        avg_util = sum(w.utilization_percent for w in workloads) / len(workloads)
        overloaded = sum(1 for w in workloads if w.utilization_percent > 90.0)
        available = sum(1 for w in workloads if w.utilization_percent < 50.0)

        return WorkloadReport(
            workloads=workloads,
            avg_utilization=round(avg_util, 1),
            overloaded_count=overloaded,
            available_count=available,
        )

    # ------------------------------------------------------------------
    # Investigator matching (capacity planning)
    # ------------------------------------------------------------------

    def find_available_investigators(
        self,
        *,
        min_performance: float = 70.0,
        required_certs: list[str] | None = None,
        specialty: str | None = None,
        max_results: int = 10,
    ) -> list[InvestigatorMatchResult]:
        """Find investigators with capacity for new trial assignments."""
        candidates: list[InvestigatorMatchResult] = []

        for inv in self._investigators.values():
            if inv.performance_score is not None and inv.performance_score < min_performance:
                continue
            if specialty and inv.specialty.lower() != specialty.lower():
                continue

            wl = self.get_workload(inv.id)
            if wl is None or wl.utilization_percent >= 95.0:
                continue

            # Check certifications
            certs_valid = True
            if required_certs:
                inv_cert_types = {c.certification_type.value for c in self.get_certifications(inv.id) if c.status == TrainingStatus.COMPLETED}
                for rc in required_certs:
                    if rc not in inv_cert_types:
                        certs_valid = False
                        break

            available_capacity = max(0, wl.enrollment_capacity - wl.total_patients)
            perf = inv.performance_score or 0.0

            # Match score: weighted combination of performance, capacity, and cert validity
            match_score = (perf * 0.5) + ((100.0 - wl.utilization_percent) * 0.3) + (20.0 if certs_valid else 0.0)
            match_score = min(100.0, round(match_score, 1))

            candidates.append(InvestigatorMatchResult(
                investigator_id=inv.id,
                investigator_name=inv.name,
                role=inv.role,
                site_name=inv.site_name,
                available_capacity=available_capacity,
                performance_score=perf,
                match_score=match_score,
                certifications_valid=certs_valid,
            ))

        candidates.sort(key=lambda x: x.match_score, reverse=True)
        return candidates[:max_results]

    # ------------------------------------------------------------------
    # Aggregate metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> InvestigatorMetrics:
        """Return aggregate investigator metrics."""
        all_inv = list(self._investigators.values())
        by_role: dict[str, int] = {}
        perf_scores: list[float] = []
        exp_values: list[int] = []

        for inv in all_inv:
            role_val = inv.role.value
            by_role[role_val] = by_role.get(role_val, 0) + 1
            if inv.performance_score is not None:
                perf_scores.append(inv.performance_score)
            exp_values.append(inv.years_experience)

        avg_perf = sum(perf_scores) / len(perf_scores) if perf_scores else 0.0
        avg_exp = sum(exp_values) / len(exp_values) if exp_values else 0.0

        # Certification compliance: % of investigators with no expired certs
        compliant = 0
        for inv in all_inv:
            certs = self.get_certifications(inv.id)
            has_expired = any(c.status == TrainingStatus.EXPIRED for c in certs)
            if not has_expired:
                compliant += 1
        cert_compliance = (compliant / len(all_inv) * 100.0) if all_inv else 0.0

        # Training completion
        all_training = list(self._training_records.values())
        completed_training = sum(1 for t in all_training if t.status == TrainingStatus.COMPLETED)
        training_rate = (completed_training / len(all_training) * 100.0) if all_training else 0.0

        # Inspection readiness: % with no major/critical findings
        all_inspections = list(self._inspections.values())
        bad_results = {InspectionResult.MAJOR_FINDINGS, InspectionResult.OFFICIAL_ACTION_INDICATED, InspectionResult.CRITICAL}
        clean_inspections = sum(1 for i in all_inspections if i.result not in bad_results)
        inspection_readiness = (clean_inspections / len(all_inspections) * 100.0) if all_inspections else 100.0

        active_trials = [inv.active_trials for inv in all_inv]
        active_avg = sum(active_trials) / len(active_trials) if active_trials else 0.0

        return InvestigatorMetrics(
            total_investigators=len(all_inv),
            by_role=by_role,
            avg_performance_score=round(avg_perf, 1),
            avg_years_experience=round(avg_exp, 1),
            certification_compliance_rate=round(cert_compliance, 1),
            training_completion_rate=round(training_rate, 1),
            inspection_readiness_score=round(inspection_readiness, 1),
            active_trial_avg=round(active_avg, 1),
        )

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data and re-seed."""
        with self._lock:
            self._investigators.clear()
            self._certifications.clear()
            self._scorecards.clear()
            self._inspections.clear()
            self._training_records.clear()
        self._seed_data()

    def get_stats(self) -> dict[str, Any]:
        """Return service stats for health check."""
        return {
            "total_investigators": len(self._investigators),
            "total_certifications": len(self._certifications),
            "total_scorecards": len(self._scorecards),
            "total_inspections": len(self._inspections),
            "total_training_records": len(self._training_records),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_composite_score(
        *,
        enrollment_rate: float,
        screen_failure_rate: float,
        protocol_deviation_count: int,
        query_response_time_days: float,
        data_quality_score: float,
        patient_retention_rate: float,
        ae_reporting_timeliness: float,
    ) -> float:
        """Compute a composite performance score (0-100) from individual metrics."""
        # Enrollment: rate >= 1.0 is 100, 0 is 0
        enroll_s = min(100.0, enrollment_rate * 100.0)
        # Screen failure: lower is better
        sfr_s = max(0.0, (1.0 - screen_failure_rate) * 100.0)
        # Deviations: 0 = 100, 10+ = 0
        dev_s = max(0.0, min(100.0, (1.0 - protocol_deviation_count / 10.0) * 100.0))
        # Query response: <= 1 day = 100, >= 5 days = 0
        qrt_s = max(0.0, min(100.0, (1.0 - (query_response_time_days - 1.0) / 4.0) * 100.0))
        # Data quality and AE timeliness are already 0-100
        # Patient retention: 0-1 scale -> 0-100
        ret_s = patient_retention_rate * 100.0

        # Weighted average
        composite = (
            enroll_s * 0.20
            + sfr_s * 0.10
            + dev_s * 0.15
            + qrt_s * 0.10
            + data_quality_score * 0.20
            + ret_s * 0.10
            + ae_reporting_timeliness * 0.15
        )
        return round(min(100.0, max(0.0, composite)), 1)

    @staticmethod
    def _score_to_rating(score: float) -> PerformanceRating:
        """Convert a composite score to a performance rating."""
        if score >= 90.0:
            return PerformanceRating.EXCEPTIONAL
        if score >= 80.0:
            return PerformanceRating.ABOVE_AVERAGE
        if score >= 70.0:
            return PerformanceRating.AVERAGE
        if score >= 60.0:
            return PerformanceRating.BELOW_AVERAGE
        return PerformanceRating.UNACCEPTABLE


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: InvestigatorManagementService | None = None
_instance_lock = threading.Lock()


def get_investigator_management_service() -> InvestigatorManagementService:
    """Return the singleton ``InvestigatorManagementService``."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = InvestigatorManagementService()
    return _instance


def reset_investigator_management_service() -> None:
    """Reset the singleton (useful for tests)."""
    global _instance
    with _instance_lock:
        _instance = None
