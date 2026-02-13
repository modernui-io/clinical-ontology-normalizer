"""External Data Integration Service (EXT-DATA).

Manages external data integration operations: data source registry,
integration pipeline tracking, data quality validation, mapping
configuration, and transfer log management with integration metrics.

Usage:
    from app.services.external_data_integration_service import (
        get_external_data_integration_service,
    )

    svc = get_external_data_integration_service()
    sources = svc.list_data_sources()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.external_data_integration import (
    ConnectionProtocol,
    DataQualityValidation,
    DataQualityValidationCreate,
    DataQualityValidationUpdate,
    DataSourceRegistry,
    DataSourceRegistryCreate,
    DataSourceRegistryUpdate,
    ExternalDataIntegrationMetrics,
    IntegrationPipeline,
    IntegrationPipelineCreate,
    IntegrationPipelineUpdate,
    MappingConfiguration,
    MappingConfigurationCreate,
    MappingConfigurationUpdate,
    PipelineStatus,
    SourceType,
    TransferDirection,
    TransferLog,
    TransferLogCreate,
    TransferLogUpdate,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ExternalDataIntegrationService:
    """In-memory External Data Integration engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._data_sources: dict[str, DataSourceRegistry] = {}
        self._pipelines: dict[str, IntegrationPipeline] = {}
        self._validations: dict[str, DataQualityValidation] = {}
        self._mappings: dict[str, MappingConfiguration] = {}
        self._transfer_logs: dict[str, TransferLog] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic external data integration data."""
        now = datetime.now(timezone.utc)

        # --- 12 Data Sources ---
        sources_data = [
            {
                "id": "DS-001",
                "trial_id": EYLEA_TRIAL,
                "source_name": "Medidata Rave EDC",
                "source_type": SourceType.EDC,
                "connection_protocol": ConnectionProtocol.REST_API,
                "endpoint_url": "https://rave.medidata.com/api/v2",
                "is_active": True,
                "vendor_name": "Medidata Solutions",
                "data_format": "JSON",
                "refresh_frequency": "hourly",
                "last_successful_sync": now - timedelta(hours=1),
                "total_records_synced": 145230,
                "authentication_method": "oauth2",
                "ssl_required": True,
                "registered_by": "Dr. Sarah Chen",
                "notes": "Primary EDC system for EYLEA trial. OAuth2 client credentials flow.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "DS-002",
                "trial_id": EYLEA_TRIAL,
                "source_name": "Quest Diagnostics Lab",
                "source_type": SourceType.LABORATORY,
                "connection_protocol": ConnectionProtocol.HL7_FHIR,
                "endpoint_url": "https://fhir.questdiagnostics.com/r4",
                "is_active": True,
                "vendor_name": "Quest Diagnostics",
                "data_format": "FHIR R4",
                "refresh_frequency": "daily",
                "last_successful_sync": now - timedelta(hours=12),
                "total_records_synced": 87540,
                "authentication_method": "api_key",
                "ssl_required": True,
                "registered_by": "Dr. James Wright",
                "notes": "Central lab results via HL7 FHIR R4. Daily batch sync.",
                "created_at": now - timedelta(days=195),
            },
            {
                "id": "DS-003",
                "trial_id": EYLEA_TRIAL,
                "source_name": "Heidelberg OCT Imaging",
                "source_type": SourceType.IMAGING,
                "connection_protocol": ConnectionProtocol.SFTP,
                "endpoint_url": "sftp://imaging.heidelberg.com:22",
                "is_active": True,
                "vendor_name": "Heidelberg Engineering",
                "data_format": "DICOM",
                "refresh_frequency": "weekly",
                "last_successful_sync": now - timedelta(days=3),
                "total_records_synced": 12450,
                "authentication_method": "ssh_key",
                "ssl_required": True,
                "registered_by": "Dr. Sarah Chen",
                "notes": "Retinal OCT imaging data. Weekly SFTP transfer of DICOM files.",
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "DS-004",
                "trial_id": DUPIXENT_TRIAL,
                "source_name": "Oracle Clinical One EDC",
                "source_type": SourceType.EDC,
                "connection_protocol": ConnectionProtocol.REST_API,
                "endpoint_url": "https://clinicalone.oracle.com/api/v3",
                "is_active": True,
                "vendor_name": "Oracle Health Sciences",
                "data_format": "JSON",
                "refresh_frequency": "hourly",
                "last_successful_sync": now - timedelta(hours=2),
                "total_records_synced": 203100,
                "authentication_method": "oauth2",
                "ssl_required": True,
                "registered_by": "Dr. Maria Lopez",
                "notes": "Primary EDC for DUPIXENT trial. Hourly incremental sync.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "DS-005",
                "trial_id": DUPIXENT_TRIAL,
                "source_name": "Actigraph Wearable Hub",
                "source_type": SourceType.WEARABLE,
                "connection_protocol": ConnectionProtocol.REST_API,
                "endpoint_url": "https://api.actigraph.com/v2/studies",
                "is_active": True,
                "vendor_name": "ActiGraph LLC",
                "data_format": "JSON",
                "refresh_frequency": "daily",
                "last_successful_sync": now - timedelta(hours=18),
                "total_records_synced": 340200,
                "authentication_method": "api_key",
                "ssl_required": True,
                "registered_by": "Dr. Robert Kim",
                "notes": "Wearable actigraphy data. Sleep and activity metrics for eczema patients.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "DS-006",
                "trial_id": DUPIXENT_TRIAL,
                "source_name": "LabCorp Central Lab",
                "source_type": SourceType.LABORATORY,
                "connection_protocol": ConnectionProtocol.CDISC_ODM,
                "endpoint_url": "https://cdisc.labcorp.com/odm",
                "is_active": True,
                "vendor_name": "LabCorp Drug Development",
                "data_format": "CDISC ODM XML",
                "refresh_frequency": "daily",
                "last_successful_sync": now - timedelta(hours=8),
                "total_records_synced": 92340,
                "authentication_method": "certificate",
                "ssl_required": True,
                "registered_by": "Dr. Maria Lopez",
                "notes": "Central lab via CDISC ODM. mTLS with client certificate auth.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "DS-007",
                "trial_id": LIBTAYO_TRIAL,
                "source_name": "Veeva Vault CDMS",
                "source_type": SourceType.EDC,
                "connection_protocol": ConnectionProtocol.REST_API,
                "endpoint_url": "https://regeneron.veevavault.com/api/v24.1",
                "is_active": True,
                "vendor_name": "Veeva Systems",
                "data_format": "JSON",
                "refresh_frequency": "hourly",
                "last_successful_sync": now - timedelta(minutes=45),
                "total_records_synced": 178900,
                "authentication_method": "session_token",
                "ssl_required": True,
                "registered_by": "Dr. Angela Park",
                "notes": "Veeva Vault CDMS for LIBTAYO oncology trial. Session-based auth.",
                "created_at": now - timedelta(days=210),
            },
            {
                "id": "DS-008",
                "trial_id": LIBTAYO_TRIAL,
                "source_name": "Hospital EHR Feed - Memorial Sloan Kettering",
                "source_type": SourceType.EHR,
                "connection_protocol": ConnectionProtocol.HL7_FHIR,
                "endpoint_url": "https://fhir.mskcc.org/r4",
                "is_active": True,
                "vendor_name": "Epic Systems",
                "data_format": "FHIR R4",
                "refresh_frequency": "daily",
                "last_successful_sync": now - timedelta(hours=6),
                "total_records_synced": 45200,
                "authentication_method": "smart_on_fhir",
                "ssl_required": True,
                "registered_by": "Dr. Angela Park",
                "notes": "EHR data feed from MSK via SMART on FHIR. Concomitant medications and vitals.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "DS-009",
                "trial_id": LIBTAYO_TRIAL,
                "source_name": "RECIST Imaging Archive",
                "source_type": SourceType.IMAGING,
                "connection_protocol": ConnectionProtocol.SFTP,
                "endpoint_url": "sftp://imaging-archive.regeneron.com:2222",
                "is_active": True,
                "vendor_name": "Radiant Imaging CRO",
                "data_format": "DICOM",
                "refresh_frequency": "weekly",
                "last_successful_sync": now - timedelta(days=2),
                "total_records_synced": 18700,
                "authentication_method": "ssh_key",
                "ssl_required": True,
                "registered_by": "Dr. William Torres",
                "notes": "Tumor response imaging per RECIST 1.1 criteria. Bi-weekly scans.",
                "created_at": now - timedelta(days=205),
            },
            {
                "id": "DS-010",
                "trial_id": EYLEA_TRIAL,
                "source_name": "National Eye Institute Registry",
                "source_type": SourceType.REGISTRY,
                "connection_protocol": ConnectionProtocol.DATABASE_LINK,
                "endpoint_url": "jdbc:postgresql://nei-registry.nih.gov:5432/vision_registry",
                "is_active": False,
                "vendor_name": "NIH/NEI",
                "data_format": "CSV",
                "refresh_frequency": "monthly",
                "last_successful_sync": now - timedelta(days=35),
                "total_records_synced": 5200,
                "authentication_method": "api_key",
                "ssl_required": True,
                "registered_by": "Dr. James Wright",
                "notes": "External registry linkage for long-term outcomes. Currently paused pending DUA renewal.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "DS-011",
                "trial_id": DUPIXENT_TRIAL,
                "source_name": "Patient ePRO App",
                "source_type": SourceType.WEARABLE,
                "connection_protocol": ConnectionProtocol.REST_API,
                "endpoint_url": "https://epro-api.clinphone.com/v1",
                "is_active": True,
                "vendor_name": "Signant Health",
                "data_format": "JSON",
                "refresh_frequency": "daily",
                "last_successful_sync": now - timedelta(hours=4),
                "total_records_synced": 128400,
                "authentication_method": "api_key",
                "ssl_required": True,
                "registered_by": "Dr. Robert Kim",
                "notes": "Electronic patient-reported outcomes. DLQI, EASI, NRS scores.",
                "created_at": now - timedelta(days=168),
            },
            {
                "id": "DS-012",
                "trial_id": LIBTAYO_TRIAL,
                "source_name": "Genomics Biomarker Platform",
                "source_type": SourceType.LABORATORY,
                "connection_protocol": ConnectionProtocol.FILE_IMPORT,
                "endpoint_url": None,
                "is_active": True,
                "vendor_name": "Foundation Medicine",
                "data_format": "VCF",
                "refresh_frequency": "weekly",
                "last_successful_sync": now - timedelta(days=5),
                "total_records_synced": 3420,
                "authentication_method": "api_key",
                "ssl_required": True,
                "registered_by": "Dr. Angela Park",
                "notes": "Tumor genomic profiling data. PD-L1 expression and TMB results.",
                "created_at": now - timedelta(days=195),
            },
        ]

        for s in sources_data:
            self._data_sources[s["id"]] = DataSourceRegistry(**s)

        # --- 12 Integration Pipelines ---
        pipelines_data = [
            {
                "id": "PIP-001",
                "trial_id": EYLEA_TRIAL,
                "source_id": "DS-001",
                "pipeline_name": "EYLEA EDC Incremental Sync",
                "status": PipelineStatus.ACTIVE,
                "direction": TransferDirection.INBOUND,
                "schedule_cron": "0 * * * *",
                "last_run_date": now - timedelta(hours=1),
                "next_run_date": now + timedelta(minutes=15),
                "total_runs": 4320,
                "successful_runs": 4298,
                "failed_runs": 22,
                "avg_processing_seconds": 45.2,
                "error_threshold": 5,
                "auto_retry": True,
                "managed_by": "Data Integration Team",
                "notes": "Hourly incremental sync. Retries up to 3 times on failure.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "PIP-002",
                "trial_id": EYLEA_TRIAL,
                "source_id": "DS-002",
                "pipeline_name": "Quest Lab Results Import",
                "status": PipelineStatus.ACTIVE,
                "direction": TransferDirection.INBOUND,
                "schedule_cron": "0 6 * * *",
                "last_run_date": now - timedelta(hours=12),
                "next_run_date": now + timedelta(hours=12),
                "total_runs": 195,
                "successful_runs": 192,
                "failed_runs": 3,
                "avg_processing_seconds": 120.5,
                "error_threshold": 3,
                "auto_retry": True,
                "managed_by": "Lab Data Team",
                "notes": "Daily 6AM batch import of lab results. FHIR Bundle processing.",
                "created_at": now - timedelta(days=195),
            },
            {
                "id": "PIP-003",
                "trial_id": EYLEA_TRIAL,
                "source_id": "DS-003",
                "pipeline_name": "OCT Imaging Transfer",
                "status": PipelineStatus.ACTIVE,
                "direction": TransferDirection.INBOUND,
                "schedule_cron": "0 2 * * 1",
                "last_run_date": now - timedelta(days=3),
                "next_run_date": now + timedelta(days=4),
                "total_runs": 28,
                "successful_runs": 27,
                "failed_runs": 1,
                "avg_processing_seconds": 1800.0,
                "error_threshold": 2,
                "auto_retry": False,
                "managed_by": "Imaging Data Team",
                "notes": "Weekly Monday 2AM SFTP transfer. Large DICOM files require extended processing.",
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "PIP-004",
                "trial_id": DUPIXENT_TRIAL,
                "source_id": "DS-004",
                "pipeline_name": "DUPIXENT EDC Real-time Sync",
                "status": PipelineStatus.ACTIVE,
                "direction": TransferDirection.BIDIRECTIONAL,
                "schedule_cron": "*/30 * * * *",
                "last_run_date": now - timedelta(minutes=28),
                "next_run_date": now + timedelta(minutes=2),
                "total_runs": 8640,
                "successful_runs": 8615,
                "failed_runs": 25,
                "avg_processing_seconds": 22.8,
                "error_threshold": 10,
                "auto_retry": True,
                "managed_by": "Data Integration Team",
                "notes": "Bi-directional sync every 30 minutes. Query and edit reconciliation.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "PIP-005",
                "trial_id": DUPIXENT_TRIAL,
                "source_id": "DS-005",
                "pipeline_name": "Wearable Actigraphy Import",
                "status": PipelineStatus.ACTIVE,
                "direction": TransferDirection.INBOUND,
                "schedule_cron": "0 4 * * *",
                "last_run_date": now - timedelta(hours=18),
                "next_run_date": now + timedelta(hours=6),
                "total_runs": 170,
                "successful_runs": 165,
                "failed_runs": 5,
                "avg_processing_seconds": 300.0,
                "error_threshold": 5,
                "auto_retry": True,
                "managed_by": "Digital Endpoints Team",
                "notes": "Daily import of actigraphy summary metrics. 5-min epoch data.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "PIP-006",
                "trial_id": DUPIXENT_TRIAL,
                "source_id": "DS-006",
                "pipeline_name": "LabCorp ODM Import",
                "status": PipelineStatus.PAUSED,
                "direction": TransferDirection.INBOUND,
                "schedule_cron": "0 5 * * *",
                "last_run_date": now - timedelta(days=3),
                "next_run_date": None,
                "total_runs": 172,
                "successful_runs": 170,
                "failed_runs": 2,
                "avg_processing_seconds": 95.0,
                "error_threshold": 3,
                "auto_retry": True,
                "managed_by": "Lab Data Team",
                "notes": "PAUSED: Certificate renewal in progress. Expected resume in 48h.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "PIP-007",
                "trial_id": LIBTAYO_TRIAL,
                "source_id": "DS-007",
                "pipeline_name": "Veeva CDMS Hourly Sync",
                "status": PipelineStatus.ACTIVE,
                "direction": TransferDirection.INBOUND,
                "schedule_cron": "15 * * * *",
                "last_run_date": now - timedelta(minutes=45),
                "next_run_date": now + timedelta(minutes=15),
                "total_runs": 5040,
                "successful_runs": 5020,
                "failed_runs": 20,
                "avg_processing_seconds": 38.5,
                "error_threshold": 5,
                "auto_retry": True,
                "managed_by": "Data Integration Team",
                "notes": "Hourly at :15. Session token auto-refresh before each run.",
                "created_at": now - timedelta(days=210),
            },
            {
                "id": "PIP-008",
                "trial_id": LIBTAYO_TRIAL,
                "source_id": "DS-008",
                "pipeline_name": "MSK EHR Data Feed",
                "status": PipelineStatus.ACTIVE,
                "direction": TransferDirection.INBOUND,
                "schedule_cron": "0 3 * * *",
                "last_run_date": now - timedelta(hours=6),
                "next_run_date": now + timedelta(hours=18),
                "total_runs": 200,
                "successful_runs": 196,
                "failed_runs": 4,
                "avg_processing_seconds": 180.0,
                "error_threshold": 3,
                "auto_retry": True,
                "managed_by": "EHR Integration Team",
                "notes": "Daily 3AM pull of concomitant medications and vitals from MSK Epic.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "PIP-009",
                "trial_id": LIBTAYO_TRIAL,
                "source_id": "DS-009",
                "pipeline_name": "RECIST Imaging Pipeline",
                "status": PipelineStatus.ACTIVE,
                "direction": TransferDirection.INBOUND,
                "schedule_cron": "0 1 * * 3",
                "last_run_date": now - timedelta(days=2),
                "next_run_date": now + timedelta(days=5),
                "total_runs": 30,
                "successful_runs": 29,
                "failed_runs": 1,
                "avg_processing_seconds": 2400.0,
                "error_threshold": 2,
                "auto_retry": False,
                "managed_by": "Imaging Data Team",
                "notes": "Weekly Wednesday 1AM. RECIST 1.1 measurement extraction after transfer.",
                "created_at": now - timedelta(days=205),
            },
            {
                "id": "PIP-010",
                "trial_id": EYLEA_TRIAL,
                "source_id": "DS-010",
                "pipeline_name": "NEI Registry Linkage",
                "status": PipelineStatus.PAUSED,
                "direction": TransferDirection.INBOUND,
                "schedule_cron": "0 0 1 * *",
                "last_run_date": now - timedelta(days=35),
                "next_run_date": None,
                "total_runs": 5,
                "successful_runs": 5,
                "failed_runs": 0,
                "avg_processing_seconds": 600.0,
                "error_threshold": 1,
                "auto_retry": False,
                "managed_by": "Registry Team",
                "notes": "PAUSED: Data Use Agreement under renewal. Monthly registry linkage.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "PIP-011",
                "trial_id": DUPIXENT_TRIAL,
                "source_id": "DS-011",
                "pipeline_name": "ePRO Data Import",
                "status": PipelineStatus.ACTIVE,
                "direction": TransferDirection.INBOUND,
                "schedule_cron": "0 7 * * *",
                "last_run_date": now - timedelta(hours=4),
                "next_run_date": now + timedelta(hours=20),
                "total_runs": 168,
                "successful_runs": 167,
                "failed_runs": 1,
                "avg_processing_seconds": 55.0,
                "error_threshold": 3,
                "auto_retry": True,
                "managed_by": "Patient Data Team",
                "notes": "Daily ePRO import at 7AM. DLQI, EASI, NRS scores and compliance.",
                "created_at": now - timedelta(days=168),
            },
            {
                "id": "PIP-012",
                "trial_id": LIBTAYO_TRIAL,
                "source_id": "DS-012",
                "pipeline_name": "Genomics Biomarker Import",
                "status": PipelineStatus.TESTING,
                "direction": TransferDirection.INBOUND,
                "schedule_cron": "0 0 * * 5",
                "last_run_date": now - timedelta(days=5),
                "next_run_date": now + timedelta(days=2),
                "total_runs": 8,
                "successful_runs": 6,
                "failed_runs": 2,
                "avg_processing_seconds": 450.0,
                "error_threshold": 2,
                "auto_retry": False,
                "managed_by": "Biomarker Team",
                "notes": "TESTING: VCF parsing pipeline under validation. Friday midnight runs.",
                "created_at": now - timedelta(days=195),
            },
        ]

        for p in pipelines_data:
            self._pipelines[p["id"]] = IntegrationPipeline(**p)

        # --- 12 Data Quality Validations ---
        validations_data = [
            {
                "id": "DQV-001",
                "trial_id": EYLEA_TRIAL,
                "pipeline_id": "PIP-001",
                "validation_name": "EDC Subject ID Consistency",
                "validation_date": now - timedelta(hours=1),
                "severity": ValidationSeverity.INFO,
                "records_validated": 1200,
                "records_passed": 1200,
                "records_failed": 0,
                "pass_rate_pct": 100.0,
                "rule_description": "Verify all subject IDs match enrollment registry format (EYLEA-XXX-XXXX).",
                "failure_details": [],
                "auto_resolved": False,
                "resolved": True,
                "resolved_by": None,
                "validated_by": "Automated Validator",
                "notes": "All subject IDs conform to expected format.",
                "created_at": now - timedelta(hours=1),
            },
            {
                "id": "DQV-002",
                "trial_id": EYLEA_TRIAL,
                "pipeline_id": "PIP-002",
                "validation_name": "Lab Range Plausibility Check",
                "validation_date": now - timedelta(hours=12),
                "severity": ValidationSeverity.WARNING,
                "records_validated": 450,
                "records_passed": 443,
                "records_failed": 7,
                "pass_rate_pct": 98.4,
                "rule_description": "Validate lab values fall within physiological plausible ranges.",
                "failure_details": [
                    "Subject EYLEA-001-0042: ALT value 2450 U/L exceeds upper plausible limit",
                    "Subject EYLEA-003-0018: Hemoglobin -2.1 g/dL (negative value)",
                    "Subject EYLEA-001-0067: Creatinine 45.0 mg/dL exceeds plausible range",
                ],
                "auto_resolved": False,
                "resolved": False,
                "resolved_by": None,
                "validated_by": "Lab Data Validator",
                "notes": "7 out-of-range values flagged for manual review by data management.",
                "created_at": now - timedelta(hours=12),
            },
            {
                "id": "DQV-003",
                "trial_id": EYLEA_TRIAL,
                "pipeline_id": "PIP-003",
                "validation_name": "DICOM Header Integrity",
                "validation_date": now - timedelta(days=3),
                "severity": ValidationSeverity.ERROR,
                "records_validated": 320,
                "records_passed": 315,
                "records_failed": 5,
                "pass_rate_pct": 98.4,
                "rule_description": "Validate DICOM headers contain required study/series/instance UIDs.",
                "failure_details": [
                    "5 DICOM files missing StudyInstanceUID",
                    "Affected site: EYLEA-003 (Memphis)",
                ],
                "auto_resolved": False,
                "resolved": False,
                "resolved_by": None,
                "validated_by": "Imaging Validator",
                "notes": "Site EYLEA-003 PACS system misconfigured. Ticket opened with site.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "DQV-004",
                "trial_id": DUPIXENT_TRIAL,
                "pipeline_id": "PIP-004",
                "validation_name": "EDC-CTMS Subject Reconciliation",
                "validation_date": now - timedelta(minutes=28),
                "severity": ValidationSeverity.INFO,
                "records_validated": 890,
                "records_passed": 890,
                "records_failed": 0,
                "pass_rate_pct": 100.0,
                "rule_description": "Cross-reference EDC subjects with CTMS enrollment to detect discrepancies.",
                "failure_details": [],
                "auto_resolved": False,
                "resolved": True,
                "resolved_by": None,
                "validated_by": "Automated Validator",
                "notes": "All 890 subjects reconciled successfully.",
                "created_at": now - timedelta(minutes=28),
            },
            {
                "id": "DQV-005",
                "trial_id": DUPIXENT_TRIAL,
                "pipeline_id": "PIP-005",
                "validation_name": "Wearable Data Completeness",
                "validation_date": now - timedelta(hours=18),
                "severity": ValidationSeverity.WARNING,
                "records_validated": 2800,
                "records_passed": 2650,
                "records_failed": 150,
                "pass_rate_pct": 94.6,
                "rule_description": "Verify wearable data has >= 20h/day wear time for valid epoch calculation.",
                "failure_details": [
                    "150 patient-days below 20h wear time threshold",
                    "Top non-compliant sites: DUP-005 (Chicago), DUP-008 (Dallas)",
                ],
                "auto_resolved": False,
                "resolved": False,
                "resolved_by": None,
                "validated_by": "Digital Endpoints Validator",
                "notes": "Site compliance outreach initiated for DUP-005 and DUP-008.",
                "created_at": now - timedelta(hours=18),
            },
            {
                "id": "DQV-006",
                "trial_id": DUPIXENT_TRIAL,
                "pipeline_id": "PIP-006",
                "validation_name": "ODM Schema Conformance",
                "validation_date": now - timedelta(days=3),
                "severity": ValidationSeverity.CRITICAL,
                "records_validated": 520,
                "records_passed": 0,
                "records_failed": 520,
                "pass_rate_pct": 0.0,
                "rule_description": "Validate incoming ODM XML against CDISC ODM 1.3.2 schema definition.",
                "failure_details": [
                    "Certificate expired: TLS handshake failure",
                    "All 520 records in batch rejected due to transport failure",
                    "No data corruption - records remain at source pending re-transfer",
                ],
                "auto_resolved": False,
                "resolved": False,
                "resolved_by": None,
                "validated_by": "ODM Validator",
                "notes": "Root cause: mTLS client certificate expired. Pipeline paused. Renewal in progress.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "DQV-007",
                "trial_id": LIBTAYO_TRIAL,
                "pipeline_id": "PIP-007",
                "validation_name": "Veeva CDMS Data Type Check",
                "validation_date": now - timedelta(minutes=45),
                "severity": ValidationSeverity.INFO,
                "records_validated": 980,
                "records_passed": 978,
                "records_failed": 2,
                "pass_rate_pct": 99.8,
                "rule_description": "Verify all fields conform to expected data types (date, numeric, coded).",
                "failure_details": [
                    "2 date fields with non-ISO format (MM/DD/YYYY instead of YYYY-MM-DD)",
                ],
                "auto_resolved": True,
                "resolved": True,
                "resolved_by": "Auto-Transform",
                "validated_by": "Type Validator",
                "notes": "Auto-resolved: date format transformation applied successfully.",
                "created_at": now - timedelta(minutes=45),
            },
            {
                "id": "DQV-008",
                "trial_id": LIBTAYO_TRIAL,
                "pipeline_id": "PIP-008",
                "validation_name": "EHR Medication Code Mapping",
                "validation_date": now - timedelta(hours=6),
                "severity": ValidationSeverity.WARNING,
                "records_validated": 340,
                "records_passed": 325,
                "records_failed": 15,
                "pass_rate_pct": 95.6,
                "rule_description": "Verify all RxNorm medication codes map to study concomitant medication dictionary.",
                "failure_details": [
                    "15 RxNorm codes not found in study medication dictionary",
                    "Most common unmapped: herbal supplements and OTC vitamins",
                ],
                "auto_resolved": False,
                "resolved": False,
                "resolved_by": None,
                "validated_by": "Medication Validator",
                "notes": "Dictionary update request submitted to include missing OTC codes.",
                "created_at": now - timedelta(hours=6),
            },
            {
                "id": "DQV-009",
                "trial_id": LIBTAYO_TRIAL,
                "pipeline_id": "PIP-009",
                "validation_name": "RECIST Measurement Consistency",
                "validation_date": now - timedelta(days=2),
                "severity": ValidationSeverity.ERROR,
                "records_validated": 180,
                "records_passed": 174,
                "records_failed": 6,
                "pass_rate_pct": 96.7,
                "rule_description": "Validate tumor measurements against RECIST 1.1 criteria and baseline references.",
                "failure_details": [
                    "3 target lesions exceed 150% growth without progression event",
                    "2 new lesion measurements below minimum measurable threshold (10mm)",
                    "1 lymph node measurement recorded on short axis instead of long axis",
                ],
                "auto_resolved": False,
                "resolved": False,
                "resolved_by": None,
                "validated_by": "RECIST Validator",
                "notes": "Queries issued to reading radiologists for clarification.",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "DQV-010",
                "trial_id": EYLEA_TRIAL,
                "pipeline_id": "PIP-001",
                "validation_name": "Visit Window Compliance",
                "validation_date": now - timedelta(hours=2),
                "severity": ValidationSeverity.WARNING,
                "records_validated": 600,
                "records_passed": 572,
                "records_failed": 28,
                "pass_rate_pct": 95.3,
                "rule_description": "Verify assessment dates fall within protocol-defined visit windows (+/- 7 days).",
                "failure_details": [
                    "28 assessments performed outside visit window",
                    "14 early visits (avg 3 days early)",
                    "14 late visits (avg 5 days late)",
                ],
                "auto_resolved": False,
                "resolved": False,
                "resolved_by": None,
                "validated_by": "Protocol Validator",
                "notes": "Protocol deviations documented. No impact on primary endpoint assessment.",
                "created_at": now - timedelta(hours=2),
            },
            {
                "id": "DQV-011",
                "trial_id": DUPIXENT_TRIAL,
                "pipeline_id": "PIP-011",
                "validation_name": "ePRO Completion Rate Audit",
                "validation_date": now - timedelta(hours=4),
                "severity": ValidationSeverity.INFO,
                "records_validated": 1500,
                "records_passed": 1425,
                "records_failed": 75,
                "pass_rate_pct": 95.0,
                "rule_description": "Verify ePRO questionnaire completion rates exceed 90% threshold per site.",
                "failure_details": [
                    "3 sites below 90% completion threshold",
                    "DUP-005: 85%, DUP-011: 87%, DUP-014: 89%",
                ],
                "auto_resolved": False,
                "resolved": False,
                "resolved_by": None,
                "validated_by": "ePRO Validator",
                "notes": "Site engagement plan activated for under-performing sites.",
                "created_at": now - timedelta(hours=4),
            },
            {
                "id": "DQV-012",
                "trial_id": LIBTAYO_TRIAL,
                "pipeline_id": "PIP-012",
                "validation_name": "VCF Format Validation",
                "validation_date": now - timedelta(days=5),
                "severity": ValidationSeverity.BLOCKING,
                "records_validated": 45,
                "records_passed": 38,
                "records_failed": 7,
                "pass_rate_pct": 84.4,
                "rule_description": "Validate VCF files conform to VCF 4.3 specification with required INFO fields.",
                "failure_details": [
                    "7 VCF files missing required INFO fields (DP, AF, FILTER)",
                    "Files from batch FND-2024-B12 affected",
                    "Pipeline blocked pending vendor correction",
                ],
                "auto_resolved": False,
                "resolved": False,
                "resolved_by": None,
                "validated_by": "Genomics Validator",
                "notes": "Blocking: vendor notified. Expected corrected batch within 5 business days.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for v in validations_data:
            self._validations[v["id"]] = DataQualityValidation(**v)

        # --- 12 Mapping Configurations ---
        mappings_data = [
            {
                "id": "MAP-001",
                "trial_id": EYLEA_TRIAL,
                "source_id": "DS-001",
                "mapping_name": "EDC Subject ID to CDASH SUBJID",
                "source_field": "rave.subject_key",
                "target_field": "DM.SUBJID",
                "transformation_rule": "direct",
                "data_type_source": "string",
                "data_type_target": "string",
                "is_required": True,
                "default_value": None,
                "lookup_table": None,
                "version": "1.0",
                "validated": True,
                "created_by": "Data Standards Team",
                "approved_by": "Dr. Sarah Chen",
                "notes": "Direct mapping. No transformation required.",
                "created_at": now - timedelta(days=198),
            },
            {
                "id": "MAP-002",
                "trial_id": EYLEA_TRIAL,
                "source_id": "DS-002",
                "mapping_name": "LOINC to CDASH LBTESTCD",
                "source_field": "observation.code.coding[0].code",
                "target_field": "LB.LBTESTCD",
                "transformation_rule": "lookup",
                "data_type_source": "string",
                "data_type_target": "string",
                "is_required": True,
                "default_value": None,
                "lookup_table": "loinc_to_cdash_lb",
                "version": "2.1",
                "validated": True,
                "created_by": "Lab Standards Team",
                "approved_by": "Dr. James Wright",
                "notes": "LOINC code lookup to CDASH lab test code. Version 2.1 adds 45 new mappings.",
                "created_at": now - timedelta(days=193),
            },
            {
                "id": "MAP-003",
                "trial_id": EYLEA_TRIAL,
                "source_id": "DS-002",
                "mapping_name": "Lab Value Unit Conversion",
                "source_field": "observation.valueQuantity.value",
                "target_field": "LB.LBSTRESN",
                "transformation_rule": "unit_conversion",
                "data_type_source": "decimal",
                "data_type_target": "float",
                "is_required": True,
                "default_value": None,
                "lookup_table": "unit_conversion_factors",
                "version": "1.2",
                "validated": True,
                "created_by": "Lab Standards Team",
                "approved_by": "Dr. James Wright",
                "notes": "Converts SI to conventional units where applicable. Factor lookup table.",
                "created_at": now - timedelta(days=193),
            },
            {
                "id": "MAP-004",
                "trial_id": DUPIXENT_TRIAL,
                "source_id": "DS-004",
                "mapping_name": "Oracle Visit to CDASH VISIT",
                "source_field": "clinicalone.event_name",
                "target_field": "SV.VISIT",
                "transformation_rule": "regex_extract",
                "data_type_source": "string",
                "data_type_target": "string",
                "is_required": True,
                "default_value": "UNSCHEDULED",
                "lookup_table": None,
                "version": "1.0",
                "validated": True,
                "created_by": "Data Standards Team",
                "approved_by": "Dr. Maria Lopez",
                "notes": "Regex extraction of visit number from Oracle event name. Default to UNSCHEDULED.",
                "created_at": now - timedelta(days=178),
            },
            {
                "id": "MAP-005",
                "trial_id": DUPIXENT_TRIAL,
                "source_id": "DS-005",
                "mapping_name": "Actigraph Epoch to Daily Summary",
                "source_field": "epoch.activity_count",
                "target_field": "FA.FAORRES",
                "transformation_rule": "aggregation",
                "data_type_source": "integer",
                "data_type_target": "float",
                "is_required": False,
                "default_value": "0",
                "lookup_table": None,
                "version": "1.1",
                "validated": True,
                "created_by": "Digital Endpoints Team",
                "approved_by": "Dr. Robert Kim",
                "notes": "Aggregate 5-min epochs to daily activity summary. Mean, median, and total.",
                "created_at": now - timedelta(days=168),
            },
            {
                "id": "MAP-006",
                "trial_id": DUPIXENT_TRIAL,
                "source_id": "DS-006",
                "mapping_name": "ODM ItemOID to CDASH Variable",
                "source_field": "ItemData.@ItemOID",
                "target_field": "CDASH.variable_name",
                "transformation_rule": "lookup",
                "data_type_source": "string",
                "data_type_target": "string",
                "is_required": True,
                "default_value": None,
                "lookup_table": "odm_to_cdash_mapping",
                "version": "1.0",
                "validated": False,
                "created_by": "Lab Standards Team",
                "approved_by": None,
                "notes": "Pending validation due to pipeline pause. 342 of 380 items mapped.",
                "created_at": now - timedelta(days=173),
            },
            {
                "id": "MAP-007",
                "trial_id": LIBTAYO_TRIAL,
                "source_id": "DS-007",
                "mapping_name": "Veeva Form to CDASH AE Domain",
                "source_field": "vault.ae_form",
                "target_field": "AE.AETERM",
                "transformation_rule": "composite",
                "data_type_source": "object",
                "data_type_target": "string",
                "is_required": True,
                "default_value": None,
                "lookup_table": None,
                "version": "2.0",
                "validated": True,
                "created_by": "Safety Data Team",
                "approved_by": "Dr. Angela Park",
                "notes": "Composite mapping: concatenate verbatim term from multiple Veeva fields.",
                "created_at": now - timedelta(days=208),
            },
            {
                "id": "MAP-008",
                "trial_id": LIBTAYO_TRIAL,
                "source_id": "DS-008",
                "mapping_name": "RxNorm to WHO Drug Dictionary",
                "source_field": "medicationReference.code",
                "target_field": "CM.CMDECOD",
                "transformation_rule": "lookup",
                "data_type_source": "string",
                "data_type_target": "string",
                "is_required": True,
                "default_value": "UNMAPPED",
                "lookup_table": "rxnorm_to_whodrug",
                "version": "1.3",
                "validated": True,
                "created_by": "Coding Team",
                "approved_by": "Dr. William Torres",
                "notes": "RxNorm to WHO Drug Dictionary B3 mapping. Default UNMAPPED for manual coding.",
                "created_at": now - timedelta(days=198),
            },
            {
                "id": "MAP-009",
                "trial_id": LIBTAYO_TRIAL,
                "source_id": "DS-009",
                "mapping_name": "DICOM Measurement to RECIST TR",
                "source_field": "dicom.measurement.length_mm",
                "target_field": "TR.TRORRES",
                "transformation_rule": "unit_conversion",
                "data_type_source": "float",
                "data_type_target": "float",
                "is_required": True,
                "default_value": None,
                "lookup_table": None,
                "version": "1.0",
                "validated": True,
                "created_by": "Imaging Standards Team",
                "approved_by": "Dr. Angela Park",
                "notes": "DICOM measurement in mm to RECIST tumor response domain. Direct numeric.",
                "created_at": now - timedelta(days=203),
            },
            {
                "id": "MAP-010",
                "trial_id": EYLEA_TRIAL,
                "source_id": "DS-003",
                "mapping_name": "OCT Layer Thickness Extraction",
                "source_field": "dicom.oct.retinal_thickness",
                "target_field": "OE.OEORRES",
                "transformation_rule": "composite",
                "data_type_source": "float",
                "data_type_target": "float",
                "is_required": True,
                "default_value": None,
                "lookup_table": None,
                "version": "1.1",
                "validated": True,
                "created_by": "Imaging Standards Team",
                "approved_by": "Dr. Sarah Chen",
                "notes": "Extract central subfield thickness from OCT B-scan data.",
                "created_at": now - timedelta(days=188),
            },
            {
                "id": "MAP-011",
                "trial_id": DUPIXENT_TRIAL,
                "source_id": "DS-011",
                "mapping_name": "ePRO DLQI Score Mapping",
                "source_field": "epro.dlqi.total_score",
                "target_field": "QS.QSORRES",
                "transformation_rule": "direct",
                "data_type_source": "integer",
                "data_type_target": "integer",
                "is_required": True,
                "default_value": None,
                "lookup_table": None,
                "version": "1.0",
                "validated": True,
                "created_by": "Patient Data Team",
                "approved_by": "Dr. Robert Kim",
                "notes": "Direct mapping of DLQI total score (0-30). No transformation needed.",
                "created_at": now - timedelta(days=166),
            },
            {
                "id": "MAP-012",
                "trial_id": LIBTAYO_TRIAL,
                "source_id": "DS-012",
                "mapping_name": "VCF Variant to Biomarker Domain",
                "source_field": "vcf.variant.annotation",
                "target_field": "BM.BMORRES",
                "transformation_rule": "composite",
                "data_type_source": "string",
                "data_type_target": "string",
                "is_required": True,
                "default_value": None,
                "lookup_table": None,
                "version": "0.9",
                "validated": False,
                "created_by": "Biomarker Team",
                "approved_by": None,
                "notes": "Draft mapping. VCF annotation to SDTM BM domain. Under validation.",
                "created_at": now - timedelta(days=190),
            },
        ]

        for m in mappings_data:
            self._mappings[m["id"]] = MappingConfiguration(**m)

        # --- 12 Transfer Logs ---
        transfer_logs_data = [
            {
                "id": "TL-001",
                "trial_id": EYLEA_TRIAL,
                "pipeline_id": "PIP-001",
                "transfer_date": now - timedelta(hours=1),
                "direction": TransferDirection.INBOUND,
                "records_sent": 0,
                "records_received": 342,
                "records_rejected": 0,
                "file_size_bytes": 524288,
                "duration_seconds": 42.3,
                "status": "completed",
                "error_message": None,
                "checksum": "sha256:a1b2c3d4e5f6789012345678abcdef01",
                "acknowledged_by_target": True,
                "initiated_by": "Scheduler",
                "notes": "Routine hourly sync. 342 new/updated CRF records.",
                "created_at": now - timedelta(hours=1),
            },
            {
                "id": "TL-002",
                "trial_id": EYLEA_TRIAL,
                "pipeline_id": "PIP-002",
                "transfer_date": now - timedelta(hours=12),
                "direction": TransferDirection.INBOUND,
                "records_sent": 0,
                "records_received": 1250,
                "records_rejected": 7,
                "file_size_bytes": 2097152,
                "duration_seconds": 118.7,
                "status": "completed_with_warnings",
                "error_message": "7 records failed plausibility validation",
                "checksum": "sha256:b2c3d4e5f67890123456789abcdef012",
                "acknowledged_by_target": True,
                "initiated_by": "Scheduler",
                "notes": "Daily lab import. 7 out-of-range values quarantined for review.",
                "created_at": now - timedelta(hours=12),
            },
            {
                "id": "TL-003",
                "trial_id": EYLEA_TRIAL,
                "pipeline_id": "PIP-003",
                "transfer_date": now - timedelta(days=3),
                "direction": TransferDirection.INBOUND,
                "records_sent": 0,
                "records_received": 320,
                "records_rejected": 5,
                "file_size_bytes": 1073741824,
                "duration_seconds": 1782.4,
                "status": "completed_with_warnings",
                "error_message": "5 DICOM files with missing StudyInstanceUID",
                "checksum": "sha256:c3d4e5f678901234567890abcdef0123",
                "acknowledged_by_target": True,
                "initiated_by": "Scheduler",
                "notes": "Weekly OCT imaging transfer. 1GB total. 5 files quarantined.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "TL-004",
                "trial_id": DUPIXENT_TRIAL,
                "pipeline_id": "PIP-004",
                "transfer_date": now - timedelta(minutes=28),
                "direction": TransferDirection.BIDIRECTIONAL,
                "records_sent": 45,
                "records_received": 180,
                "records_rejected": 0,
                "file_size_bytes": 262144,
                "duration_seconds": 21.5,
                "status": "completed",
                "error_message": None,
                "checksum": "sha256:d4e5f6789012345678901abcdef01234",
                "acknowledged_by_target": True,
                "initiated_by": "Scheduler",
                "notes": "Bi-directional sync. 45 queries sent, 180 CRF updates received.",
                "created_at": now - timedelta(minutes=28),
            },
            {
                "id": "TL-005",
                "trial_id": DUPIXENT_TRIAL,
                "pipeline_id": "PIP-005",
                "transfer_date": now - timedelta(hours=18),
                "direction": TransferDirection.INBOUND,
                "records_sent": 0,
                "records_received": 2800,
                "records_rejected": 150,
                "file_size_bytes": 8388608,
                "duration_seconds": 295.2,
                "status": "completed_with_warnings",
                "error_message": "150 patient-days below wear time threshold",
                "checksum": "sha256:e5f67890123456789012abcdef012345",
                "acknowledged_by_target": True,
                "initiated_by": "Scheduler",
                "notes": "Daily actigraphy import. 150 records flagged for low wear time.",
                "created_at": now - timedelta(hours=18),
            },
            {
                "id": "TL-006",
                "trial_id": DUPIXENT_TRIAL,
                "pipeline_id": "PIP-006",
                "transfer_date": now - timedelta(days=3),
                "direction": TransferDirection.INBOUND,
                "records_sent": 0,
                "records_received": 0,
                "records_rejected": 520,
                "file_size_bytes": 0,
                "duration_seconds": 5.2,
                "status": "failed",
                "error_message": "TLS handshake failure: client certificate expired",
                "checksum": None,
                "acknowledged_by_target": False,
                "initiated_by": "Scheduler",
                "notes": "Complete failure. Certificate expired. Pipeline paused.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "TL-007",
                "trial_id": LIBTAYO_TRIAL,
                "pipeline_id": "PIP-007",
                "transfer_date": now - timedelta(minutes=45),
                "direction": TransferDirection.INBOUND,
                "records_sent": 0,
                "records_received": 520,
                "records_rejected": 2,
                "file_size_bytes": 786432,
                "duration_seconds": 37.1,
                "status": "completed",
                "error_message": None,
                "checksum": "sha256:f6789012345678901234abcdef0123456",
                "acknowledged_by_target": True,
                "initiated_by": "Scheduler",
                "notes": "Hourly Veeva sync. 2 records auto-corrected (date format).",
                "created_at": now - timedelta(minutes=45),
            },
            {
                "id": "TL-008",
                "trial_id": LIBTAYO_TRIAL,
                "pipeline_id": "PIP-008",
                "transfer_date": now - timedelta(hours=6),
                "direction": TransferDirection.INBOUND,
                "records_sent": 0,
                "records_received": 340,
                "records_rejected": 15,
                "file_size_bytes": 1048576,
                "duration_seconds": 175.8,
                "status": "completed_with_warnings",
                "error_message": "15 unmapped RxNorm codes",
                "checksum": "sha256:6789012345678901234abcdef01234567",
                "acknowledged_by_target": True,
                "initiated_by": "Scheduler",
                "notes": "Daily EHR pull. 15 medication codes pending dictionary update.",
                "created_at": now - timedelta(hours=6),
            },
            {
                "id": "TL-009",
                "trial_id": LIBTAYO_TRIAL,
                "pipeline_id": "PIP-009",
                "transfer_date": now - timedelta(days=2),
                "direction": TransferDirection.INBOUND,
                "records_sent": 0,
                "records_received": 180,
                "records_rejected": 6,
                "file_size_bytes": 536870912,
                "duration_seconds": 2380.5,
                "status": "completed_with_warnings",
                "error_message": "6 RECIST measurement inconsistencies",
                "checksum": "sha256:789012345678901234abcdef012345678",
                "acknowledged_by_target": True,
                "initiated_by": "Scheduler",
                "notes": "Weekly RECIST imaging. 512MB. 6 measurements queried.",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "TL-010",
                "trial_id": EYLEA_TRIAL,
                "pipeline_id": "PIP-001",
                "transfer_date": now - timedelta(hours=2),
                "direction": TransferDirection.INBOUND,
                "records_sent": 0,
                "records_received": 285,
                "records_rejected": 0,
                "file_size_bytes": 450560,
                "duration_seconds": 38.9,
                "status": "completed",
                "error_message": None,
                "checksum": "sha256:89012345678901234abcdef0123456789",
                "acknowledged_by_target": True,
                "initiated_by": "Scheduler",
                "notes": "Routine hourly sync. Clean batch - no rejections.",
                "created_at": now - timedelta(hours=2),
            },
            {
                "id": "TL-011",
                "trial_id": DUPIXENT_TRIAL,
                "pipeline_id": "PIP-011",
                "transfer_date": now - timedelta(hours=4),
                "direction": TransferDirection.INBOUND,
                "records_sent": 0,
                "records_received": 1500,
                "records_rejected": 75,
                "file_size_bytes": 3145728,
                "duration_seconds": 52.8,
                "status": "completed_with_warnings",
                "error_message": "75 records below completion threshold",
                "checksum": "sha256:9012345678901234abcdef01234567890",
                "acknowledged_by_target": True,
                "initiated_by": "Scheduler",
                "notes": "Daily ePRO import. 75 incomplete questionnaires flagged.",
                "created_at": now - timedelta(hours=4),
            },
            {
                "id": "TL-012",
                "trial_id": LIBTAYO_TRIAL,
                "pipeline_id": "PIP-012",
                "transfer_date": now - timedelta(days=5),
                "direction": TransferDirection.INBOUND,
                "records_sent": 0,
                "records_received": 45,
                "records_rejected": 7,
                "file_size_bytes": 15728640,
                "duration_seconds": 442.1,
                "status": "completed_with_warnings",
                "error_message": "7 VCF files failed format validation",
                "checksum": "sha256:012345678901234abcdef012345678901",
                "acknowledged_by_target": False,
                "initiated_by": "Scheduler",
                "notes": "Weekly genomics import. 7 VCF files rejected. Vendor notified.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for t in transfer_logs_data:
            self._transfer_logs[t["id"]] = TransferLog(**t)

    # ------------------------------------------------------------------
    # Data Sources
    # ------------------------------------------------------------------

    def list_data_sources(
        self,
        *,
        trial_id: str | None = None,
        source_type: SourceType | None = None,
        connection_protocol: ConnectionProtocol | None = None,
        is_active: bool | None = None,
    ) -> list[DataSourceRegistry]:
        """List data sources with optional filters."""
        with self._lock:
            result = list(self._data_sources.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if source_type is not None:
            result = [s for s in result if s.source_type == source_type]
        if connection_protocol is not None:
            result = [s for s in result if s.connection_protocol == connection_protocol]
        if is_active is not None:
            result = [s for s in result if s.is_active == is_active]

        return sorted(result, key=lambda s: s.created_at, reverse=True)

    def get_data_source(self, source_id: str) -> DataSourceRegistry | None:
        """Get a single data source by ID."""
        with self._lock:
            return self._data_sources.get(source_id)

    def create_data_source(self, payload: DataSourceRegistryCreate) -> DataSourceRegistry:
        """Create a new data source."""
        now = datetime.now(timezone.utc)
        source_id = f"DS-{uuid4().hex[:8].upper()}"
        source = DataSourceRegistry(
            id=source_id,
            trial_id=payload.trial_id,
            source_name=payload.source_name,
            source_type=payload.source_type,
            connection_protocol=payload.connection_protocol,
            endpoint_url=None,
            is_active=True,
            vendor_name=payload.vendor_name,
            data_format=payload.data_format,
            refresh_frequency="daily",
            last_successful_sync=None,
            total_records_synced=0,
            authentication_method="api_key",
            ssl_required=True,
            registered_by=payload.registered_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._data_sources[source_id] = source
        logger.info("Created data source %s for trial %s", source_id, payload.trial_id)
        return source

    def update_data_source(
        self, source_id: str, payload: DataSourceRegistryUpdate
    ) -> DataSourceRegistry | None:
        """Update an existing data source."""
        with self._lock:
            existing = self._data_sources.get(source_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DataSourceRegistry(**data)
            self._data_sources[source_id] = updated
        return updated

    def delete_data_source(self, source_id: str) -> bool:
        """Delete a data source. Returns True if deleted."""
        with self._lock:
            if source_id in self._data_sources:
                del self._data_sources[source_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Integration Pipelines
    # ------------------------------------------------------------------

    def list_pipelines(
        self,
        *,
        trial_id: str | None = None,
        status: PipelineStatus | None = None,
        source_id: str | None = None,
    ) -> list[IntegrationPipeline]:
        """List integration pipelines with optional filters."""
        with self._lock:
            result = list(self._pipelines.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if status is not None:
            result = [p for p in result if p.status == status]
        if source_id is not None:
            result = [p for p in result if p.source_id == source_id]

        return sorted(result, key=lambda p: p.created_at, reverse=True)

    def get_pipeline(self, pipeline_id: str) -> IntegrationPipeline | None:
        """Get a single integration pipeline by ID."""
        with self._lock:
            return self._pipelines.get(pipeline_id)

    def create_pipeline(self, payload: IntegrationPipelineCreate) -> IntegrationPipeline:
        """Create a new integration pipeline."""
        now = datetime.now(timezone.utc)
        pipeline_id = f"PIP-{uuid4().hex[:8].upper()}"
        pipeline = IntegrationPipeline(
            id=pipeline_id,
            trial_id=payload.trial_id,
            source_id=payload.source_id,
            pipeline_name=payload.pipeline_name,
            status=PipelineStatus.CONFIGURED,
            direction=payload.direction,
            schedule_cron=payload.schedule_cron,
            last_run_date=None,
            next_run_date=None,
            total_runs=0,
            successful_runs=0,
            failed_runs=0,
            avg_processing_seconds=0.0,
            error_threshold=5,
            auto_retry=True,
            managed_by=payload.managed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._pipelines[pipeline_id] = pipeline
        logger.info("Created pipeline %s for trial %s", pipeline_id, payload.trial_id)
        return pipeline

    def update_pipeline(
        self, pipeline_id: str, payload: IntegrationPipelineUpdate
    ) -> IntegrationPipeline | None:
        """Update an existing integration pipeline."""
        with self._lock:
            existing = self._pipelines.get(pipeline_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = IntegrationPipeline(**data)
            self._pipelines[pipeline_id] = updated
        return updated

    def delete_pipeline(self, pipeline_id: str) -> bool:
        """Delete an integration pipeline. Returns True if deleted."""
        with self._lock:
            if pipeline_id in self._pipelines:
                del self._pipelines[pipeline_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Data Quality Validations
    # ------------------------------------------------------------------

    def list_validations(
        self,
        *,
        trial_id: str | None = None,
        severity: ValidationSeverity | None = None,
        pipeline_id: str | None = None,
        resolved: bool | None = None,
    ) -> list[DataQualityValidation]:
        """List data quality validations with optional filters."""
        with self._lock:
            result = list(self._validations.values())

        if trial_id is not None:
            result = [v for v in result if v.trial_id == trial_id]
        if severity is not None:
            result = [v for v in result if v.severity == severity]
        if pipeline_id is not None:
            result = [v for v in result if v.pipeline_id == pipeline_id]
        if resolved is not None:
            result = [v for v in result if v.resolved == resolved]

        return sorted(result, key=lambda v: v.validation_date, reverse=True)

    def get_validation(self, validation_id: str) -> DataQualityValidation | None:
        """Get a single data quality validation by ID."""
        with self._lock:
            return self._validations.get(validation_id)

    def create_validation(self, payload: DataQualityValidationCreate) -> DataQualityValidation:
        """Create a new data quality validation."""
        now = datetime.now(timezone.utc)
        validation_id = f"DQV-{uuid4().hex[:8].upper()}"
        validation = DataQualityValidation(
            id=validation_id,
            trial_id=payload.trial_id,
            pipeline_id=payload.pipeline_id,
            validation_name=payload.validation_name,
            validation_date=now,
            severity=payload.severity,
            records_validated=payload.records_validated,
            records_passed=payload.records_validated,
            records_failed=0,
            pass_rate_pct=100.0,
            rule_description=payload.rule_description,
            failure_details=[],
            auto_resolved=False,
            resolved=False,
            resolved_by=None,
            validated_by=payload.validated_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._validations[validation_id] = validation
        logger.info("Created validation %s for trial %s", validation_id, payload.trial_id)
        return validation

    def update_validation(
        self, validation_id: str, payload: DataQualityValidationUpdate
    ) -> DataQualityValidation | None:
        """Update an existing data quality validation."""
        with self._lock:
            existing = self._validations.get(validation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DataQualityValidation(**data)
            self._validations[validation_id] = updated
        return updated

    def delete_validation(self, validation_id: str) -> bool:
        """Delete a data quality validation. Returns True if deleted."""
        with self._lock:
            if validation_id in self._validations:
                del self._validations[validation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Mapping Configurations
    # ------------------------------------------------------------------

    def list_mappings(
        self,
        *,
        trial_id: str | None = None,
        source_id: str | None = None,
        validated: bool | None = None,
    ) -> list[MappingConfiguration]:
        """List mapping configurations with optional filters."""
        with self._lock:
            result = list(self._mappings.values())

        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if source_id is not None:
            result = [m for m in result if m.source_id == source_id]
        if validated is not None:
            result = [m for m in result if m.validated == validated]

        return sorted(result, key=lambda m: m.created_at, reverse=True)

    def get_mapping(self, mapping_id: str) -> MappingConfiguration | None:
        """Get a single mapping configuration by ID."""
        with self._lock:
            return self._mappings.get(mapping_id)

    def create_mapping(self, payload: MappingConfigurationCreate) -> MappingConfiguration:
        """Create a new mapping configuration."""
        now = datetime.now(timezone.utc)
        mapping_id = f"MAP-{uuid4().hex[:8].upper()}"
        mapping = MappingConfiguration(
            id=mapping_id,
            trial_id=payload.trial_id,
            source_id=payload.source_id,
            mapping_name=payload.mapping_name,
            source_field=payload.source_field,
            target_field=payload.target_field,
            transformation_rule=payload.transformation_rule,
            data_type_source="string",
            data_type_target="string",
            is_required=True,
            default_value=None,
            lookup_table=None,
            version="1.0",
            validated=False,
            created_by=payload.created_by,
            approved_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._mappings[mapping_id] = mapping
        logger.info("Created mapping %s for trial %s", mapping_id, payload.trial_id)
        return mapping

    def update_mapping(
        self, mapping_id: str, payload: MappingConfigurationUpdate
    ) -> MappingConfiguration | None:
        """Update an existing mapping configuration."""
        with self._lock:
            existing = self._mappings.get(mapping_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MappingConfiguration(**data)
            self._mappings[mapping_id] = updated
        return updated

    def delete_mapping(self, mapping_id: str) -> bool:
        """Delete a mapping configuration. Returns True if deleted."""
        with self._lock:
            if mapping_id in self._mappings:
                del self._mappings[mapping_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Transfer Logs
    # ------------------------------------------------------------------

    def list_transfer_logs(
        self,
        *,
        trial_id: str | None = None,
        pipeline_id: str | None = None,
        direction: TransferDirection | None = None,
        status: str | None = None,
    ) -> list[TransferLog]:
        """List transfer logs with optional filters."""
        with self._lock:
            result = list(self._transfer_logs.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if pipeline_id is not None:
            result = [t for t in result if t.pipeline_id == pipeline_id]
        if direction is not None:
            result = [t for t in result if t.direction == direction]
        if status is not None:
            result = [t for t in result if t.status == status]

        return sorted(result, key=lambda t: t.transfer_date, reverse=True)

    def get_transfer_log(self, log_id: str) -> TransferLog | None:
        """Get a single transfer log by ID."""
        with self._lock:
            return self._transfer_logs.get(log_id)

    def create_transfer_log(self, payload: TransferLogCreate) -> TransferLog:
        """Create a new transfer log."""
        now = datetime.now(timezone.utc)
        log_id = f"TL-{uuid4().hex[:8].upper()}"
        log = TransferLog(
            id=log_id,
            trial_id=payload.trial_id,
            pipeline_id=payload.pipeline_id,
            transfer_date=now,
            direction=payload.direction,
            records_sent=payload.records_sent,
            records_received=payload.records_received,
            records_rejected=0,
            file_size_bytes=0,
            duration_seconds=0.0,
            status="in_progress",
            error_message=None,
            checksum=None,
            acknowledged_by_target=False,
            initiated_by=payload.initiated_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._transfer_logs[log_id] = log
        logger.info("Created transfer log %s for trial %s", log_id, payload.trial_id)
        return log

    def update_transfer_log(
        self, log_id: str, payload: TransferLogUpdate
    ) -> TransferLog | None:
        """Update an existing transfer log."""
        with self._lock:
            existing = self._transfer_logs.get(log_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TransferLog(**data)
            self._transfer_logs[log_id] = updated
        return updated

    def delete_transfer_log(self, log_id: str) -> bool:
        """Delete a transfer log. Returns True if deleted."""
        with self._lock:
            if log_id in self._transfer_logs:
                del self._transfer_logs[log_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ExternalDataIntegrationMetrics:
        """Compute aggregated external data integration metrics."""
        with self._lock:
            sources = list(self._data_sources.values())
            pipelines = list(self._pipelines.values())
            validations = list(self._validations.values())
            mappings = list(self._mappings.values())
            transfers = list(self._transfer_logs.values())

        # Sources by type
        sources_by_type: dict[str, int] = {}
        for s in sources:
            key = s.source_type.value
            sources_by_type[key] = sources_by_type.get(key, 0) + 1

        # Sources by protocol
        sources_by_protocol: dict[str, int] = {}
        for s in sources:
            key = s.connection_protocol.value
            sources_by_protocol[key] = sources_by_protocol.get(key, 0) + 1

        # Active sources
        active_sources = sum(1 for s in sources if s.is_active)

        # Pipelines by status
        pipelines_by_status: dict[str, int] = {}
        for p in pipelines:
            key = p.status.value
            pipelines_by_status[key] = pipelines_by_status.get(key, 0) + 1

        # Active pipelines
        active_pipelines = sum(1 for p in pipelines if p.status == PipelineStatus.ACTIVE)

        # Validations by severity
        validations_by_severity: dict[str, int] = {}
        for v in validations:
            key = v.severity.value
            validations_by_severity[key] = validations_by_severity.get(key, 0) + 1

        # Unresolved validations
        unresolved_validations = sum(1 for v in validations if not v.resolved)

        # Validated mappings
        validated_mappings = sum(1 for m in mappings if m.validated)

        # Transfers by direction
        transfers_by_direction: dict[str, int] = {}
        for t in transfers:
            key = t.direction.value
            transfers_by_direction[key] = transfers_by_direction.get(key, 0) + 1

        # Total records transferred
        total_records_transferred = sum(
            t.records_received + t.records_sent for t in transfers
        )

        return ExternalDataIntegrationMetrics(
            total_data_sources=len(sources),
            sources_by_type=sources_by_type,
            sources_by_protocol=sources_by_protocol,
            active_sources=active_sources,
            total_pipelines=len(pipelines),
            pipelines_by_status=pipelines_by_status,
            active_pipelines=active_pipelines,
            total_validations=len(validations),
            validations_by_severity=validations_by_severity,
            unresolved_validations=unresolved_validations,
            total_mappings=len(mappings),
            validated_mappings=validated_mappings,
            total_transfers=len(transfers),
            transfers_by_direction=transfers_by_direction,
            total_records_transferred=total_records_transferred,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ExternalDataIntegrationService | None = None
_instance_lock = threading.Lock()


def get_external_data_integration_service() -> ExternalDataIntegrationService:
    """Return the singleton ExternalDataIntegrationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ExternalDataIntegrationService()
    return _instance


def reset_external_data_integration_service() -> ExternalDataIntegrationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ExternalDataIntegrationService()
    return _instance
