"""Clinical Data Transfer Management Service (DATA-XFER).

Manages data transfers between sponsors, CROs, labs, and regulatory authorities:
transfer agreements, transfer execution tracking, data validation checks,
reconciliation, secure file transfer monitoring, and transfer metrics.

Usage:
    from app.services.data_transfer_service import (
        get_data_transfer_service,
    )

    svc = get_data_transfer_service()
    agreements = svc.list_agreements()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.data_transfer import (
    AgreementStatus,
    DataTransferAgreement,
    DataTransferAgreementCreate,
    DataTransferAgreementUpdate,
    DataTransferExecution,
    DataTransferExecutionCreate,
    DataTransferExecutionUpdate,
    DataTransferMetrics,
    TransferDirection,
    TransferFrequency,
    TransferMethod,
    TransferReconciliation,
    TransferReconciliationCreate,
    TransferReconciliationUpdate,
    TransferStatus,
    TransferValidation,
    TransferValidationCreate,
    ValidationResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class DataTransferService:
    """In-memory Clinical Data Transfer Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._agreements: dict[str, DataTransferAgreement] = {}
        self._executions: dict[str, DataTransferExecution] = {}
        self._validations: dict[str, TransferValidation] = {}
        self._reconciliations: dict[str, TransferReconciliation] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic data transfer data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Data Transfer Agreements ---
        agreements_data = [
            # EYLEA trial agreements
            {"id": "DTA-001", "trial_id": EYLEA_TRIAL, "partner_name": "Covance Central Lab", "partner_type": "central_lab", "direction": TransferDirection.INBOUND, "transfer_method": TransferMethod.SFTP, "frequency": TransferFrequency.DAILY, "data_types": ["lab_results", "biomarker_data", "sample_tracking"], "encryption_required": True, "status": AgreementStatus.ACTIVE, "effective_date": now - timedelta(days=365), "expiry_date": now + timedelta(days=365), "responsible_person": "Dr. Sarah Mitchell", "technical_contact": "james.wu@covance.com", "created_at": now - timedelta(days=400)},
            {"id": "DTA-002", "trial_id": EYLEA_TRIAL, "partner_name": "ICON CRO", "partner_type": "cro", "direction": TransferDirection.OUTBOUND, "transfer_method": TransferMethod.API, "frequency": TransferFrequency.REAL_TIME, "data_types": ["edc_data", "query_responses", "monitoring_reports"], "encryption_required": True, "status": AgreementStatus.ACTIVE, "effective_date": now - timedelta(days=350), "expiry_date": now + timedelta(days=380), "responsible_person": "Dr. Michael Torres", "technical_contact": "api-support@icon.com", "created_at": now - timedelta(days=380)},
            {"id": "DTA-003", "trial_id": EYLEA_TRIAL, "partner_name": "FDA CDER", "partner_type": "regulatory_authority", "direction": TransferDirection.OUTBOUND, "transfer_method": TransferMethod.ENCRYPTED_EMAIL, "frequency": TransferFrequency.MILESTONE_BASED, "data_types": ["safety_reports", "annual_reports", "ind_amendments"], "encryption_required": True, "status": AgreementStatus.ACTIVE, "effective_date": now - timedelta(days=300), "expiry_date": now + timedelta(days=400), "responsible_person": "Dr. Jennifer Adams", "technical_contact": "esub@fda.gov", "created_at": now - timedelta(days=330)},
            {"id": "DTA-004", "trial_id": EYLEA_TRIAL, "partner_name": "BioClinica Imaging", "partner_type": "imaging_vendor", "direction": TransferDirection.INBOUND, "transfer_method": TransferMethod.CLOUD_SHARE, "frequency": TransferFrequency.WEEKLY, "data_types": ["oct_images", "retinal_scans", "grading_reports"], "encryption_required": True, "status": AgreementStatus.ACTIVE, "effective_date": now - timedelta(days=340), "expiry_date": now + timedelta(days=390), "responsible_person": "Dr. Robert Chang", "technical_contact": "transfers@bioclinica.com", "created_at": now - timedelta(days=370)},

            # DUPIXENT trial agreements
            {"id": "DTA-005", "trial_id": DUPIXENT_TRIAL, "partner_name": "PPD Clinical Research", "partner_type": "cro", "direction": TransferDirection.BIDIRECTIONAL, "transfer_method": TransferMethod.SFTP, "frequency": TransferFrequency.DAILY, "data_types": ["edc_data", "monitoring_data", "site_data"], "encryption_required": True, "status": AgreementStatus.ACTIVE, "effective_date": now - timedelta(days=280), "expiry_date": now + timedelta(days=450), "responsible_person": "Dr. Angela Martinez", "technical_contact": "sftp-admin@ppd.com", "created_at": now - timedelta(days=310)},
            {"id": "DTA-006", "trial_id": DUPIXENT_TRIAL, "partner_name": "Quest Diagnostics", "partner_type": "central_lab", "direction": TransferDirection.INBOUND, "transfer_method": TransferMethod.API, "frequency": TransferFrequency.REAL_TIME, "data_types": ["lab_results", "ige_levels", "eosinophil_counts"], "encryption_required": True, "status": AgreementStatus.ACTIVE, "effective_date": now - timedelta(days=260), "expiry_date": now + timedelta(days=470), "responsible_person": "Dr. David Nakamura", "technical_contact": "api@quest.com", "created_at": now - timedelta(days=290)},
            {"id": "DTA-007", "trial_id": DUPIXENT_TRIAL, "partner_name": "EMA", "partner_type": "regulatory_authority", "direction": TransferDirection.OUTBOUND, "transfer_method": TransferMethod.ENCRYPTED_EMAIL, "frequency": TransferFrequency.MILESTONE_BASED, "data_types": ["clinical_study_reports", "psur_reports", "variation_applications"], "encryption_required": True, "status": AgreementStatus.ACTIVE, "effective_date": now - timedelta(days=240), "expiry_date": now + timedelta(days=490), "responsible_person": "Dr. Patricia Sullivan", "technical_contact": "submissions@ema.europa.eu", "created_at": now - timedelta(days=270)},
            {"id": "DTA-008", "trial_id": DUPIXENT_TRIAL, "partner_name": "Medidata RAVE", "partner_type": "edc_vendor", "direction": TransferDirection.BIDIRECTIONAL, "transfer_method": TransferMethod.DIRECT_DATABASE, "frequency": TransferFrequency.REAL_TIME, "data_types": ["crf_data", "edit_checks", "discrepancy_management"], "encryption_required": True, "status": AgreementStatus.ACTIVE, "effective_date": now - timedelta(days=275), "expiry_date": now + timedelta(days=455), "responsible_person": "Dr. Thomas Berg", "technical_contact": "integration@medidata.com", "created_at": now - timedelta(days=300)},

            # LIBTAYO trial agreements
            {"id": "DTA-009", "trial_id": LIBTAYO_TRIAL, "partner_name": "Parexel International", "partner_type": "cro", "direction": TransferDirection.BIDIRECTIONAL, "transfer_method": TransferMethod.SFTP, "frequency": TransferFrequency.DAILY, "data_types": ["edc_data", "recist_assessments", "tumor_measurements"], "encryption_required": True, "status": AgreementStatus.ACTIVE, "effective_date": now - timedelta(days=200), "expiry_date": now + timedelta(days=530), "responsible_person": "Dr. Catherine Liu", "technical_contact": "sftp@parexel.com", "created_at": now - timedelta(days=230)},
            {"id": "DTA-010", "trial_id": LIBTAYO_TRIAL, "partner_name": "Foundation Medicine", "partner_type": "genomics_lab", "direction": TransferDirection.INBOUND, "transfer_method": TransferMethod.API, "frequency": TransferFrequency.WEEKLY, "data_types": ["genomic_profiles", "tmb_scores", "msi_status"], "encryption_required": True, "status": AgreementStatus.ACTIVE, "effective_date": now - timedelta(days=180), "expiry_date": now + timedelta(days=550), "responsible_person": "Dr. Andrew Foster", "technical_contact": "api@foundationmedicine.com", "created_at": now - timedelta(days=210)},
            {"id": "DTA-011", "trial_id": LIBTAYO_TRIAL, "partner_name": "PMDA Japan", "partner_type": "regulatory_authority", "direction": TransferDirection.OUTBOUND, "transfer_method": TransferMethod.PHYSICAL_MEDIA, "frequency": TransferFrequency.ON_DEMAND, "data_types": ["clinical_data_packages", "ctd_modules", "safety_updates"], "encryption_required": True, "status": AgreementStatus.SUSPENDED, "effective_date": now - timedelta(days=150), "expiry_date": now + timedelta(days=580), "responsible_person": "Dr. Natalie Wong", "technical_contact": "submissions@pmda.go.jp", "created_at": now - timedelta(days=180)},
            {"id": "DTA-012", "trial_id": LIBTAYO_TRIAL, "partner_name": "Tempus AI", "partner_type": "analytics_vendor", "direction": TransferDirection.OUTBOUND, "transfer_method": TransferMethod.CLOUD_SHARE, "frequency": TransferFrequency.MONTHLY, "data_types": ["anonymized_clinical_data", "imaging_features", "outcome_data"], "encryption_required": True, "status": AgreementStatus.DRAFT, "effective_date": None, "expiry_date": None, "responsible_person": "Dr. Gregory Harris", "technical_contact": "data-intake@tempus.com", "created_at": now - timedelta(days=30)},
        ]

        for a in agreements_data:
            self._agreements[a["id"]] = DataTransferAgreement(**a)

        # --- 15 Data Transfer Executions ---
        executions_data = [
            # EYLEA executions
            {"id": "DTE-001", "agreement_id": "DTA-001", "trial_id": EYLEA_TRIAL, "transfer_date": now - timedelta(days=1), "direction": TransferDirection.INBOUND, "status": TransferStatus.COMPLETED, "records_expected": 450, "records_transferred": 450, "records_failed": 0, "file_count": 3, "total_size_bytes": 52428800, "started_at": now - timedelta(days=1, hours=2), "completed_at": now - timedelta(days=1, hours=1), "duration_seconds": 3600, "error_message": None, "initiated_by": "automated_scheduler"},
            {"id": "DTE-002", "agreement_id": "DTA-001", "trial_id": EYLEA_TRIAL, "transfer_date": now - timedelta(days=2), "direction": TransferDirection.INBOUND, "status": TransferStatus.COMPLETED, "records_expected": 380, "records_transferred": 380, "records_failed": 0, "file_count": 3, "total_size_bytes": 45875200, "started_at": now - timedelta(days=2, hours=2), "completed_at": now - timedelta(days=2, hours=1, minutes=30), "duration_seconds": 1800, "error_message": None, "initiated_by": "automated_scheduler"},
            {"id": "DTE-003", "agreement_id": "DTA-002", "trial_id": EYLEA_TRIAL, "transfer_date": now - timedelta(hours=6), "direction": TransferDirection.OUTBOUND, "status": TransferStatus.COMPLETED, "records_expected": 1200, "records_transferred": 1200, "records_failed": 0, "file_count": 1, "total_size_bytes": 8388608, "started_at": now - timedelta(hours=6), "completed_at": now - timedelta(hours=5, minutes=45), "duration_seconds": 900, "error_message": None, "initiated_by": "api_trigger"},
            {"id": "DTE-004", "agreement_id": "DTA-003", "trial_id": EYLEA_TRIAL, "transfer_date": now - timedelta(days=30), "direction": TransferDirection.OUTBOUND, "status": TransferStatus.COMPLETED, "records_expected": 1, "records_transferred": 1, "records_failed": 0, "file_count": 5, "total_size_bytes": 104857600, "started_at": now - timedelta(days=30, hours=4), "completed_at": now - timedelta(days=30, hours=2), "duration_seconds": 7200, "error_message": None, "initiated_by": "Dr. Jennifer Adams"},
            {"id": "DTE-005", "agreement_id": "DTA-004", "trial_id": EYLEA_TRIAL, "transfer_date": now - timedelta(days=3), "direction": TransferDirection.INBOUND, "status": TransferStatus.FAILED, "records_expected": 200, "records_transferred": 85, "records_failed": 115, "file_count": 8, "total_size_bytes": 2147483648, "started_at": now - timedelta(days=3, hours=1), "completed_at": now - timedelta(days=3, minutes=30), "duration_seconds": 1800, "error_message": "Connection timeout after 1800s. 115 DICOM files failed checksum validation.", "initiated_by": "automated_scheduler"},

            # DUPIXENT executions
            {"id": "DTE-006", "agreement_id": "DTA-005", "trial_id": DUPIXENT_TRIAL, "transfer_date": now - timedelta(days=1), "direction": TransferDirection.BIDIRECTIONAL, "status": TransferStatus.COMPLETED, "records_expected": 890, "records_transferred": 890, "records_failed": 0, "file_count": 6, "total_size_bytes": 67108864, "started_at": now - timedelta(days=1, hours=3), "completed_at": now - timedelta(days=1, hours=2), "duration_seconds": 3600, "error_message": None, "initiated_by": "automated_scheduler"},
            {"id": "DTE-007", "agreement_id": "DTA-006", "trial_id": DUPIXENT_TRIAL, "transfer_date": now - timedelta(hours=2), "direction": TransferDirection.INBOUND, "status": TransferStatus.COMPLETED, "records_expected": 320, "records_transferred": 320, "records_failed": 0, "file_count": 1, "total_size_bytes": 4194304, "started_at": now - timedelta(hours=2), "completed_at": now - timedelta(hours=1, minutes=50), "duration_seconds": 600, "error_message": None, "initiated_by": "api_trigger"},
            {"id": "DTE-008", "agreement_id": "DTA-007", "trial_id": DUPIXENT_TRIAL, "transfer_date": now - timedelta(days=60), "direction": TransferDirection.OUTBOUND, "status": TransferStatus.COMPLETED, "records_expected": 1, "records_transferred": 1, "records_failed": 0, "file_count": 12, "total_size_bytes": 209715200, "started_at": now - timedelta(days=60, hours=6), "completed_at": now - timedelta(days=60, hours=3), "duration_seconds": 10800, "error_message": None, "initiated_by": "Dr. Patricia Sullivan"},
            {"id": "DTE-009", "agreement_id": "DTA-008", "trial_id": DUPIXENT_TRIAL, "transfer_date": now - timedelta(hours=1), "direction": TransferDirection.BIDIRECTIONAL, "status": TransferStatus.IN_PROGRESS, "records_expected": 500, "records_transferred": 250, "records_failed": 0, "file_count": 2, "total_size_bytes": 16777216, "started_at": now - timedelta(hours=1), "completed_at": None, "duration_seconds": None, "error_message": None, "initiated_by": "automated_scheduler"},
            {"id": "DTE-010", "agreement_id": "DTA-005", "trial_id": DUPIXENT_TRIAL, "transfer_date": now - timedelta(days=5), "direction": TransferDirection.BIDIRECTIONAL, "status": TransferStatus.PARTIALLY_COMPLETED, "records_expected": 750, "records_transferred": 680, "records_failed": 70, "file_count": 6, "total_size_bytes": 58720256, "started_at": now - timedelta(days=5, hours=2), "completed_at": now - timedelta(days=5, hours=1), "duration_seconds": 3600, "error_message": "70 records failed schema validation for EASI scoring fields.", "initiated_by": "automated_scheduler"},

            # LIBTAYO executions
            {"id": "DTE-011", "agreement_id": "DTA-009", "trial_id": LIBTAYO_TRIAL, "transfer_date": now - timedelta(days=1), "direction": TransferDirection.BIDIRECTIONAL, "status": TransferStatus.COMPLETED, "records_expected": 560, "records_transferred": 560, "records_failed": 0, "file_count": 4, "total_size_bytes": 41943040, "started_at": now - timedelta(days=1, hours=2), "completed_at": now - timedelta(days=1, hours=1, minutes=15), "duration_seconds": 2700, "error_message": None, "initiated_by": "automated_scheduler"},
            {"id": "DTE-012", "agreement_id": "DTA-010", "trial_id": LIBTAYO_TRIAL, "transfer_date": now - timedelta(days=7), "direction": TransferDirection.INBOUND, "status": TransferStatus.COMPLETED, "records_expected": 45, "records_transferred": 45, "records_failed": 0, "file_count": 45, "total_size_bytes": 524288000, "started_at": now - timedelta(days=7, hours=4), "completed_at": now - timedelta(days=7, hours=2), "duration_seconds": 7200, "error_message": None, "initiated_by": "automated_scheduler"},
            {"id": "DTE-013", "agreement_id": "DTA-009", "trial_id": LIBTAYO_TRIAL, "transfer_date": now + timedelta(days=1), "direction": TransferDirection.BIDIRECTIONAL, "status": TransferStatus.SCHEDULED, "records_expected": 600, "records_transferred": 0, "records_failed": 0, "file_count": 0, "total_size_bytes": 0, "started_at": None, "completed_at": None, "duration_seconds": None, "error_message": None, "initiated_by": "automated_scheduler"},
            {"id": "DTE-014", "agreement_id": "DTA-009", "trial_id": LIBTAYO_TRIAL, "transfer_date": now - timedelta(days=10), "direction": TransferDirection.BIDIRECTIONAL, "status": TransferStatus.CANCELLED, "records_expected": 400, "records_transferred": 0, "records_failed": 0, "file_count": 0, "total_size_bytes": 0, "started_at": None, "completed_at": None, "duration_seconds": None, "error_message": "Cancelled due to system maintenance window.", "initiated_by": "Dr. Catherine Liu"},
            {"id": "DTE-015", "agreement_id": "DTA-010", "trial_id": LIBTAYO_TRIAL, "transfer_date": now - timedelta(days=14), "direction": TransferDirection.INBOUND, "status": TransferStatus.COMPLETED, "records_expected": 30, "records_transferred": 30, "records_failed": 0, "file_count": 30, "total_size_bytes": 314572800, "started_at": now - timedelta(days=14, hours=3), "completed_at": now - timedelta(days=14, hours=1), "duration_seconds": 7200, "error_message": None, "initiated_by": "automated_scheduler"},
        ]

        for e in executions_data:
            self._executions[e["id"]] = DataTransferExecution(**e)

        # --- 12 Transfer Validations ---
        validations_data = [
            {"id": "DTV-001", "execution_id": "DTE-001", "validation_type": "schema_validation", "result": ValidationResult.PASSED, "records_checked": 450, "records_passed": 450, "records_failed": 0, "issues": [], "validated_by": "automated_validator", "validated_date": now - timedelta(days=1, minutes=45)},
            {"id": "DTV-002", "execution_id": "DTE-001", "validation_type": "referential_integrity", "result": ValidationResult.PASSED, "records_checked": 450, "records_passed": 448, "records_failed": 2, "issues": ["2 orphan patient references corrected during import"], "validated_by": "automated_validator", "validated_date": now - timedelta(days=1, minutes=30)},
            {"id": "DTV-003", "execution_id": "DTE-002", "validation_type": "schema_validation", "result": ValidationResult.PASSED, "records_checked": 380, "records_passed": 380, "records_failed": 0, "issues": [], "validated_by": "automated_validator", "validated_date": now - timedelta(days=2, minutes=45)},
            {"id": "DTV-004", "execution_id": "DTE-003", "validation_type": "format_check", "result": ValidationResult.PASSED, "records_checked": 1200, "records_passed": 1200, "records_failed": 0, "issues": [], "validated_by": "api_validator", "validated_date": now - timedelta(hours=5, minutes=30)},
            {"id": "DTV-005", "execution_id": "DTE-005", "validation_type": "checksum_validation", "result": ValidationResult.FAILED, "records_checked": 200, "records_passed": 85, "records_failed": 115, "issues": ["115 DICOM files failed MD5 checksum", "Network interruption detected at file 86", "Partial transfer requires re-send"], "validated_by": "automated_validator", "validated_date": now - timedelta(days=3, minutes=15)},
            {"id": "DTV-006", "execution_id": "DTE-006", "validation_type": "schema_validation", "result": ValidationResult.PASSED, "records_checked": 890, "records_passed": 890, "records_failed": 0, "issues": [], "validated_by": "automated_validator", "validated_date": now - timedelta(days=1, minutes=50)},
            {"id": "DTV-007", "execution_id": "DTE-007", "validation_type": "range_check", "result": ValidationResult.WARNINGS, "records_checked": 320, "records_passed": 315, "records_failed": 0, "issues": ["5 IgE values outside expected range (>5000 IU/mL) - flagged for clinical review"], "validated_by": "automated_validator", "validated_date": now - timedelta(hours=1, minutes=40)},
            {"id": "DTV-008", "execution_id": "DTE-008", "validation_type": "completeness_check", "result": ValidationResult.PASSED, "records_checked": 1, "records_passed": 1, "records_failed": 0, "issues": [], "validated_by": "Dr. Patricia Sullivan", "validated_date": now - timedelta(days=60, hours=2)},
            {"id": "DTV-009", "execution_id": "DTE-010", "validation_type": "schema_validation", "result": ValidationResult.FAILED, "records_checked": 750, "records_passed": 680, "records_failed": 70, "issues": ["70 records missing required EASI scoring fields", "Field 'easi_total_score' null in 70 records"], "validated_by": "automated_validator", "validated_date": now - timedelta(days=5, minutes=45)},
            {"id": "DTV-010", "execution_id": "DTE-011", "validation_type": "schema_validation", "result": ValidationResult.PASSED, "records_checked": 560, "records_passed": 560, "records_failed": 0, "issues": [], "validated_by": "automated_validator", "validated_date": now - timedelta(days=1, minutes=50)},
            {"id": "DTV-011", "execution_id": "DTE-012", "validation_type": "format_check", "result": ValidationResult.PASSED, "records_checked": 45, "records_passed": 45, "records_failed": 0, "issues": [], "validated_by": "genomics_validator", "validated_date": now - timedelta(days=7, hours=1)},
            {"id": "DTV-012", "execution_id": "DTE-009", "validation_type": "in_progress_check", "result": ValidationResult.PENDING, "records_checked": 250, "records_passed": 250, "records_failed": 0, "issues": [], "validated_by": "automated_validator", "validated_date": now - timedelta(minutes=30)},
        ]

        for v in validations_data:
            self._validations[v["id"]] = TransferValidation(**v)

        # --- 10 Transfer Reconciliations ---
        reconciliations_data = [
            {"id": "DTR-001", "execution_id": "DTE-001", "source_record_count": 450, "target_record_count": 450, "matched_records": 450, "unmatched_records": 0, "reconciled": True, "reconciled_by": "automated_reconciler", "reconciled_date": now - timedelta(days=1, minutes=15), "discrepancy_notes": None},
            {"id": "DTR-002", "execution_id": "DTE-002", "source_record_count": 380, "target_record_count": 380, "matched_records": 380, "unmatched_records": 0, "reconciled": True, "reconciled_by": "automated_reconciler", "reconciled_date": now - timedelta(days=2, minutes=15), "discrepancy_notes": None},
            {"id": "DTR-003", "execution_id": "DTE-003", "source_record_count": 1200, "target_record_count": 1200, "matched_records": 1200, "unmatched_records": 0, "reconciled": True, "reconciled_by": "api_reconciler", "reconciled_date": now - timedelta(hours=5, minutes=15), "discrepancy_notes": None},
            {"id": "DTR-004", "execution_id": "DTE-005", "source_record_count": 200, "target_record_count": 85, "matched_records": 85, "unmatched_records": 115, "reconciled": False, "reconciled_by": None, "reconciled_date": None, "discrepancy_notes": "115 files failed transfer. Source has 200, target received only 85. Re-transfer required."},
            {"id": "DTR-005", "execution_id": "DTE-006", "source_record_count": 890, "target_record_count": 890, "matched_records": 890, "unmatched_records": 0, "reconciled": True, "reconciled_by": "automated_reconciler", "reconciled_date": now - timedelta(days=1, minutes=30), "discrepancy_notes": None},
            {"id": "DTR-006", "execution_id": "DTE-007", "source_record_count": 320, "target_record_count": 320, "matched_records": 320, "unmatched_records": 0, "reconciled": True, "reconciled_by": "api_reconciler", "reconciled_date": now - timedelta(hours=1, minutes=20), "discrepancy_notes": None},
            {"id": "DTR-007", "execution_id": "DTE-010", "source_record_count": 750, "target_record_count": 680, "matched_records": 680, "unmatched_records": 70, "reconciled": False, "reconciled_by": None, "reconciled_date": None, "discrepancy_notes": "70 records failed schema validation. Source count 750 does not match target count 680."},
            {"id": "DTR-008", "execution_id": "DTE-011", "source_record_count": 560, "target_record_count": 560, "matched_records": 560, "unmatched_records": 0, "reconciled": True, "reconciled_by": "automated_reconciler", "reconciled_date": now - timedelta(days=1, minutes=45), "discrepancy_notes": None},
            {"id": "DTR-009", "execution_id": "DTE-012", "source_record_count": 45, "target_record_count": 45, "matched_records": 45, "unmatched_records": 0, "reconciled": True, "reconciled_by": "genomics_reconciler", "reconciled_date": now - timedelta(days=7, minutes=30), "discrepancy_notes": None},
            {"id": "DTR-010", "execution_id": "DTE-015", "source_record_count": 30, "target_record_count": 30, "matched_records": 30, "unmatched_records": 0, "reconciled": True, "reconciled_by": "genomics_reconciler", "reconciled_date": now - timedelta(days=14, minutes=30), "discrepancy_notes": None},
        ]

        for r in reconciliations_data:
            self._reconciliations[r["id"]] = TransferReconciliation(**r)

    # ------------------------------------------------------------------
    # Agreement Management
    # ------------------------------------------------------------------

    def list_agreements(
        self,
        *,
        trial_id: str | None = None,
        direction: TransferDirection | None = None,
        method: TransferMethod | None = None,
        status: AgreementStatus | None = None,
        frequency: TransferFrequency | None = None,
    ) -> list[DataTransferAgreement]:
        """List transfer agreements with optional filters."""
        with self._lock:
            result = list(self._agreements.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if direction is not None:
            result = [a for a in result if a.direction == direction]
        if method is not None:
            result = [a for a in result if a.transfer_method == method]
        if status is not None:
            result = [a for a in result if a.status == status]
        if frequency is not None:
            result = [a for a in result if a.frequency == frequency]

        return sorted(result, key=lambda a: a.id)

    def get_agreement(self, agreement_id: str) -> DataTransferAgreement | None:
        """Get a single agreement by ID."""
        with self._lock:
            return self._agreements.get(agreement_id)

    def create_agreement(self, payload: DataTransferAgreementCreate) -> DataTransferAgreement:
        """Create a new transfer agreement."""
        agreement_id = f"DTA-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        agreement = DataTransferAgreement(
            id=agreement_id,
            trial_id=payload.trial_id,
            partner_name=payload.partner_name,
            partner_type=payload.partner_type,
            direction=payload.direction,
            transfer_method=payload.transfer_method,
            frequency=payload.frequency,
            data_types=payload.data_types,
            encryption_required=payload.encryption_required,
            status=AgreementStatus.DRAFT,
            effective_date=None,
            expiry_date=None,
            responsible_person=payload.responsible_person,
            technical_contact=payload.technical_contact,
            created_at=now,
        )
        with self._lock:
            self._agreements[agreement_id] = agreement
        logger.info("Created transfer agreement %s: %s", agreement_id, payload.partner_name)
        return agreement

    def update_agreement(
        self, agreement_id: str, payload: DataTransferAgreementUpdate
    ) -> DataTransferAgreement | None:
        """Update an existing agreement."""
        with self._lock:
            existing = self._agreements.get(agreement_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DataTransferAgreement(**data)
            self._agreements[agreement_id] = updated
        return updated

    def delete_agreement(self, agreement_id: str) -> bool:
        """Delete an agreement. Returns True if deleted."""
        with self._lock:
            if agreement_id in self._agreements:
                del self._agreements[agreement_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Execution Management
    # ------------------------------------------------------------------

    def list_executions(
        self,
        *,
        trial_id: str | None = None,
        agreement_id: str | None = None,
        direction: TransferDirection | None = None,
        status: TransferStatus | None = None,
    ) -> list[DataTransferExecution]:
        """List transfer executions with optional filters."""
        with self._lock:
            result = list(self._executions.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        if agreement_id is not None:
            result = [e for e in result if e.agreement_id == agreement_id]
        if direction is not None:
            result = [e for e in result if e.direction == direction]
        if status is not None:
            result = [e for e in result if e.status == status]

        return sorted(result, key=lambda e: e.transfer_date, reverse=True)

    def get_execution(self, execution_id: str) -> DataTransferExecution | None:
        """Get a single execution by ID."""
        with self._lock:
            return self._executions.get(execution_id)

    def create_execution(self, payload: DataTransferExecutionCreate) -> DataTransferExecution:
        """Create a new transfer execution."""
        execution_id = f"DTE-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)

        # Validate agreement exists
        with self._lock:
            agreement = self._agreements.get(payload.agreement_id)
            if agreement is None:
                raise ValueError(f"Agreement '{payload.agreement_id}' not found")

        execution = DataTransferExecution(
            id=execution_id,
            agreement_id=payload.agreement_id,
            trial_id=payload.trial_id,
            transfer_date=now,
            direction=payload.direction,
            status=TransferStatus.SCHEDULED,
            records_expected=payload.records_expected,
            records_transferred=0,
            records_failed=0,
            file_count=payload.file_count,
            total_size_bytes=0,
            started_at=None,
            completed_at=None,
            duration_seconds=None,
            error_message=None,
            initiated_by=payload.initiated_by,
        )
        with self._lock:
            self._executions[execution_id] = execution
        logger.info(
            "Created transfer execution %s: agreement=%s trial=%s",
            execution_id, payload.agreement_id, payload.trial_id,
        )
        return execution

    def update_execution(
        self, execution_id: str, payload: DataTransferExecutionUpdate
    ) -> DataTransferExecution | None:
        """Update an existing execution."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._executions.get(execution_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set timestamps based on status transitions
            if "status" in updates:
                new_status = updates["status"]
                if new_status == TransferStatus.IN_PROGRESS and existing.started_at is None:
                    updates["started_at"] = now
                elif new_status in (
                    TransferStatus.COMPLETED,
                    TransferStatus.FAILED,
                    TransferStatus.PARTIALLY_COMPLETED,
                ):
                    if existing.completed_at is None:
                        updates["completed_at"] = now
                    if existing.started_at is not None and existing.duration_seconds is None:
                        started = existing.started_at
                        completed = updates.get("completed_at", now)
                        updates["duration_seconds"] = int(
                            (completed - started).total_seconds()
                        )

            data.update(updates)
            updated = DataTransferExecution(**data)
            self._executions[execution_id] = updated
        return updated

    def delete_execution(self, execution_id: str) -> bool:
        """Delete an execution. Returns True if deleted."""
        with self._lock:
            if execution_id in self._executions:
                del self._executions[execution_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Validation Management
    # ------------------------------------------------------------------

    def list_validations(
        self,
        *,
        execution_id: str | None = None,
        result: ValidationResult | None = None,
    ) -> list[TransferValidation]:
        """List transfer validations with optional filters."""
        with self._lock:
            items = list(self._validations.values())

        if execution_id is not None:
            items = [v for v in items if v.execution_id == execution_id]
        if result is not None:
            items = [v for v in items if v.result == result]

        return sorted(items, key=lambda v: v.validated_date, reverse=True)

    def get_validation(self, validation_id: str) -> TransferValidation | None:
        """Get a single validation by ID."""
        with self._lock:
            return self._validations.get(validation_id)

    def create_validation(self, payload: TransferValidationCreate) -> TransferValidation:
        """Create a new transfer validation."""
        validation_id = f"DTV-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)

        # Validate execution exists
        with self._lock:
            execution = self._executions.get(payload.execution_id)
            if execution is None:
                raise ValueError(f"Execution '{payload.execution_id}' not found")

        validation = TransferValidation(
            id=validation_id,
            execution_id=payload.execution_id,
            validation_type=payload.validation_type,
            result=payload.result,
            records_checked=payload.records_checked,
            records_passed=payload.records_passed,
            records_failed=payload.records_failed,
            issues=payload.issues,
            validated_by=payload.validated_by,
            validated_date=now,
        )
        with self._lock:
            self._validations[validation_id] = validation
        logger.info(
            "Created validation %s: execution=%s type=%s result=%s",
            validation_id, payload.execution_id, payload.validation_type,
            payload.result.value,
        )
        return validation

    def delete_validation(self, validation_id: str) -> bool:
        """Delete a validation. Returns True if deleted."""
        with self._lock:
            if validation_id in self._validations:
                del self._validations[validation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Reconciliation Management
    # ------------------------------------------------------------------

    def list_reconciliations(
        self,
        *,
        execution_id: str | None = None,
        reconciled: bool | None = None,
    ) -> list[TransferReconciliation]:
        """List transfer reconciliations with optional filters."""
        with self._lock:
            items = list(self._reconciliations.values())

        if execution_id is not None:
            items = [r for r in items if r.execution_id == execution_id]
        if reconciled is not None:
            items = [r for r in items if r.reconciled == reconciled]

        return sorted(items, key=lambda r: r.id)

    def get_reconciliation(self, reconciliation_id: str) -> TransferReconciliation | None:
        """Get a single reconciliation by ID."""
        with self._lock:
            return self._reconciliations.get(reconciliation_id)

    def create_reconciliation(self, payload: TransferReconciliationCreate) -> TransferReconciliation:
        """Create a new reconciliation record."""
        reconciliation_id = f"DTR-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)

        # Validate execution exists
        with self._lock:
            execution = self._executions.get(payload.execution_id)
            if execution is None:
                raise ValueError(f"Execution '{payload.execution_id}' not found")

        # Auto-determine reconciled status
        is_reconciled = (
            payload.matched_records == payload.source_record_count
            and payload.matched_records == payload.target_record_count
        )

        reconciliation = TransferReconciliation(
            id=reconciliation_id,
            execution_id=payload.execution_id,
            source_record_count=payload.source_record_count,
            target_record_count=payload.target_record_count,
            matched_records=payload.matched_records,
            unmatched_records=payload.unmatched_records,
            reconciled=is_reconciled,
            reconciled_by=payload.reconciled_by if is_reconciled else None,
            reconciled_date=now if is_reconciled else None,
            discrepancy_notes=payload.discrepancy_notes,
        )
        with self._lock:
            self._reconciliations[reconciliation_id] = reconciliation
        logger.info(
            "Created reconciliation %s: execution=%s reconciled=%s",
            reconciliation_id, payload.execution_id, is_reconciled,
        )
        return reconciliation

    def update_reconciliation(
        self, reconciliation_id: str, payload: TransferReconciliationUpdate
    ) -> TransferReconciliation | None:
        """Update an existing reconciliation."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._reconciliations.get(reconciliation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set reconciled_date when reconciled is set to True
            if updates.get("reconciled") is True and not existing.reconciled:
                updates["reconciled_date"] = now

            data.update(updates)
            updated = TransferReconciliation(**data)
            self._reconciliations[reconciliation_id] = updated
        return updated

    def delete_reconciliation(self, reconciliation_id: str) -> bool:
        """Delete a reconciliation. Returns True if deleted."""
        with self._lock:
            if reconciliation_id in self._reconciliations:
                del self._reconciliations[reconciliation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> DataTransferMetrics:
        """Compute aggregated data transfer metrics."""
        with self._lock:
            agreements = list(self._agreements.values())
            executions = list(self._executions.values())
            validations = list(self._validations.values())
            reconciliations = list(self._reconciliations.values())

        if trial_id is not None:
            agreements = [a for a in agreements if a.trial_id == trial_id]
            executions = [e for e in executions if e.trial_id == trial_id]
            # Filter validations/reconciliations by execution IDs in trial
            exec_ids = {e.id for e in executions}
            validations = [v for v in validations if v.execution_id in exec_ids]
            reconciliations = [r for r in reconciliations if r.execution_id in exec_ids]

        # Agreements by status
        agreements_by_status: dict[str, int] = {}
        for a in agreements:
            key = a.status.value
            agreements_by_status[key] = agreements_by_status.get(key, 0) + 1

        # Agreements by method
        agreements_by_method: dict[str, int] = {}
        for a in agreements:
            key = a.transfer_method.value
            agreements_by_method[key] = agreements_by_method.get(key, 0) + 1

        # Executions by status
        executions_by_status: dict[str, int] = {}
        for e in executions:
            key = e.status.value
            executions_by_status[key] = executions_by_status.get(key, 0) + 1

        # Successful and failed transfers
        successful_transfers = sum(
            1 for e in executions if e.status == TransferStatus.COMPLETED
        )
        failed_transfers = sum(
            1 for e in executions if e.status == TransferStatus.FAILED
        )

        # Total records transferred
        total_records_transferred = sum(e.records_transferred for e in executions)

        # Validations
        validations_passed = sum(
            1 for v in validations if v.result == ValidationResult.PASSED
        )
        validations_failed = sum(
            1 for v in validations if v.result == ValidationResult.FAILED
        )

        # Reconciliations
        reconciled_count = sum(1 for r in reconciliations if r.reconciled)

        # Average transfer duration from completed executions
        completed_with_duration = [
            e for e in executions
            if e.status == TransferStatus.COMPLETED and e.duration_seconds is not None
        ]
        if completed_with_duration:
            avg_duration = sum(
                e.duration_seconds for e in completed_with_duration  # type: ignore[misc]
            ) / len(completed_with_duration)
        else:
            avg_duration = 0.0

        return DataTransferMetrics(
            total_agreements=len(agreements),
            agreements_by_status=agreements_by_status,
            agreements_by_method=agreements_by_method,
            total_executions=len(executions),
            executions_by_status=executions_by_status,
            successful_transfers=successful_transfers,
            failed_transfers=failed_transfers,
            total_records_transferred=total_records_transferred,
            total_validations=len(validations),
            validations_passed=validations_passed,
            validations_failed=validations_failed,
            total_reconciliations=len(reconciliations),
            reconciled_count=reconciled_count,
            avg_transfer_duration_seconds=round(avg_duration, 1),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: DataTransferService | None = None
_instance_lock = threading.Lock()


def get_data_transfer_service() -> DataTransferService:
    """Return the singleton DataTransferService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DataTransferService()
    return _instance


def reset_data_transfer_service() -> DataTransferService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = DataTransferService()
    return _instance
