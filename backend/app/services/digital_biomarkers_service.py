"""Digital Biomarkers Management (DIGI-BIO) Service.

Manages digital biomarker operations: digital endpoint definitions, wearable
data collection streams, algorithm validation, digital measure scoring,
regulatory qualification, and digital biomarker operational metrics.

Usage:
    from app.services.digital_biomarkers_service import (
        get_digital_biomarkers_service,
    )

    svc = get_digital_biomarkers_service()
    endpoints = svc.list_endpoints(trial_id="...")
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.digital_biomarkers import (
    AlgorithmStatus,
    AlgorithmValidation,
    AlgorithmValidationCreate,
    AlgorithmValidationUpdate,
    DataStream,
    DataStreamCreate,
    DataStreamUpdate,
    DeviceType,
    DigitalBiomarkerMetrics,
    DigitalEndpoint,
    DigitalEndpointCreate,
    DigitalEndpointUpdate,
    DigitalMeasureScore,
    DigitalMeasureScoreCreate,
    DigitalMeasureScoreUpdate,
    EndpointQualification,
    RegulatoryQualification,
    RegulatoryQualificationCreate,
    RegulatoryQualificationUpdate,
    ScoringStatus,
    StreamStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class DigitalBiomarkersService:
    """In-memory Digital Biomarkers Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._endpoints: dict[str, DigitalEndpoint] = {}
        self._streams: dict[str, DataStream] = {}
        self._algorithms: dict[str, AlgorithmValidation] = {}
        self._scores: dict[str, DigitalMeasureScore] = {}
        self._qualifications: dict[str, RegulatoryQualification] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic digital biomarker data across trials."""
        now = datetime.now(timezone.utc)

        # --- Digital Endpoints ---
        endpoint_defs = [
            {
                "id": "DEP-001",
                "trial_id": EYLEA_TRIAL,
                "endpoint_name": "Daily Step Count",
                "description": "Total daily steps measured via wrist-worn accelerometer as a mobility endpoint in wet AMD patients",
                "device_type": DeviceType.ACCELEROMETER,
                "measure_type": "physical_activity",
                "unit": "steps/day",
                "collection_frequency": "continuous",
                "qualification_level": EndpointQualification.FIT_FOR_PURPOSE,
                "clinically_meaningful_change": 1500.0,
                "test_retest_icc": 0.92,
                "sensitivity_to_change": 0.78,
                "regulatory_reference": "FDA DHT Guidance 2024",
                "concept_of_interest": "Physical mobility",
                "context_of_use": "Exploratory endpoint to assess functional vision impact on daily mobility",
                "created_by": "Dr. Sarah Chen",
            },
            {
                "id": "DEP-002",
                "trial_id": EYLEA_TRIAL,
                "endpoint_name": "Visual Task Completion Time",
                "description": "Time to complete standardized near-vision tasks on smartphone app",
                "device_type": DeviceType.SMARTPHONE_SENSOR,
                "measure_type": "visual_function",
                "unit": "seconds",
                "collection_frequency": "twice_daily",
                "qualification_level": EndpointQualification.EXPLORATORY,
                "clinically_meaningful_change": 5.0,
                "test_retest_icc": 0.88,
                "sensitivity_to_change": 0.65,
                "regulatory_reference": None,
                "concept_of_interest": "Near visual acuity",
                "context_of_use": "Exploratory endpoint measuring functional vision in daily activities",
                "created_by": "Dr. James Park",
            },
            {
                "id": "DEP-003",
                "trial_id": DUPIXENT_TRIAL,
                "endpoint_name": "Nocturnal Scratch Events",
                "description": "Number of nocturnal scratching episodes detected via wrist actigraphy in atopic dermatitis patients",
                "device_type": DeviceType.ACTIGRAPHY,
                "measure_type": "pruritus_activity",
                "unit": "events/night",
                "collection_frequency": "nightly",
                "qualification_level": EndpointQualification.QUALIFIED,
                "clinically_meaningful_change": 8.0,
                "test_retest_icc": 0.85,
                "sensitivity_to_change": 0.82,
                "regulatory_reference": "FDA-2023-D-0815 Digital Endpoints Qualification",
                "concept_of_interest": "Nocturnal pruritus severity",
                "context_of_use": "Secondary endpoint for nocturnal itch assessment in moderate-to-severe AD",
                "created_by": "Dr. Amanda Li",
            },
            {
                "id": "DEP-004",
                "trial_id": DUPIXENT_TRIAL,
                "endpoint_name": "Sleep Quality Index",
                "description": "Composite sleep quality score derived from actigraphy: sleep efficiency, latency, wake after sleep onset",
                "device_type": DeviceType.SMARTWATCH,
                "measure_type": "sleep_quality",
                "unit": "score (0-100)",
                "collection_frequency": "nightly",
                "qualification_level": EndpointQualification.FIT_FOR_PURPOSE,
                "clinically_meaningful_change": 10.0,
                "test_retest_icc": 0.90,
                "sensitivity_to_change": 0.75,
                "regulatory_reference": None,
                "concept_of_interest": "Sleep disturbance from itch",
                "context_of_use": "Exploratory endpoint assessing itch-related sleep disruption",
                "created_by": "Dr. Amanda Li",
            },
            {
                "id": "DEP-005",
                "trial_id": DUPIXENT_TRIAL,
                "endpoint_name": "Skin Temperature Differential",
                "description": "Temperature differential between lesional and non-lesional skin measured by biosensor patch",
                "device_type": DeviceType.BIOSENSOR_PATCH,
                "measure_type": "skin_inflammation",
                "unit": "delta_celsius",
                "collection_frequency": "continuous",
                "qualification_level": EndpointQualification.EXPLORATORY,
                "clinically_meaningful_change": 0.5,
                "test_retest_icc": 0.79,
                "sensitivity_to_change": 0.68,
                "regulatory_reference": None,
                "concept_of_interest": "Local skin inflammation",
                "context_of_use": "Exploratory biomarker for local inflammatory activity",
                "created_by": "Dr. Robert Kim",
            },
            {
                "id": "DEP-006",
                "trial_id": LIBTAYO_TRIAL,
                "endpoint_name": "Resting Heart Rate Variability",
                "description": "HRV derived from PPG sensor as a biomarker for autonomic function in oncology patients",
                "device_type": DeviceType.PPG_SENSOR,
                "measure_type": "cardiac_autonomic",
                "unit": "ms (RMSSD)",
                "collection_frequency": "daily",
                "qualification_level": EndpointQualification.EXPLORATORY,
                "clinically_meaningful_change": 8.0,
                "test_retest_icc": 0.83,
                "sensitivity_to_change": 0.60,
                "regulatory_reference": None,
                "concept_of_interest": "Autonomic nervous system function",
                "context_of_use": "Exploratory safety endpoint for immune-related cardiotoxicity",
                "created_by": "Dr. Michael Torres",
            },
            {
                "id": "DEP-007",
                "trial_id": LIBTAYO_TRIAL,
                "endpoint_name": "6-Minute Walk Distance Proxy",
                "description": "GPS-validated outdoor walking distance extrapolated from daily accelerometry",
                "device_type": DeviceType.SMARTWATCH,
                "measure_type": "functional_capacity",
                "unit": "meters",
                "collection_frequency": "daily",
                "qualification_level": EndpointQualification.FIT_FOR_PURPOSE,
                "clinically_meaningful_change": 30.0,
                "test_retest_icc": 0.91,
                "sensitivity_to_change": 0.74,
                "regulatory_reference": "FDA DHT Guidance 2024",
                "concept_of_interest": "Exercise capacity",
                "context_of_use": "Secondary endpoint for functional status in NSCLC patients",
                "created_by": "Dr. Michael Torres",
            },
            {
                "id": "DEP-008",
                "trial_id": LIBTAYO_TRIAL,
                "endpoint_name": "Continuous SpO2 Monitoring",
                "description": "Continuous pulse oximetry via wrist-worn PPG for early hypoxia detection",
                "device_type": DeviceType.PPG_SENSOR,
                "measure_type": "respiratory",
                "unit": "% SpO2",
                "collection_frequency": "continuous",
                "qualification_level": EndpointQualification.EXPLORATORY,
                "clinically_meaningful_change": 3.0,
                "test_retest_icc": 0.87,
                "sensitivity_to_change": 0.72,
                "regulatory_reference": None,
                "concept_of_interest": "Oxygen saturation",
                "context_of_use": "Safety monitoring for immune-related pneumonitis",
                "created_by": "Dr. Lisa Wang",
            },
            {
                "id": "DEP-009",
                "trial_id": EYLEA_TRIAL,
                "endpoint_name": "Contrast Sensitivity via App",
                "description": "Contrast sensitivity measured by validated smartphone application for visual function",
                "device_type": DeviceType.SMARTPHONE_SENSOR,
                "measure_type": "visual_function",
                "unit": "logCS",
                "collection_frequency": "weekly",
                "qualification_level": EndpointQualification.EXPLORATORY,
                "clinically_meaningful_change": 0.15,
                "test_retest_icc": 0.86,
                "sensitivity_to_change": 0.70,
                "regulatory_reference": None,
                "concept_of_interest": "Contrast sensitivity function",
                "context_of_use": "Exploratory endpoint for visual quality beyond acuity",
                "created_by": "Dr. Sarah Chen",
            },
            {
                "id": "DEP-010",
                "trial_id": LIBTAYO_TRIAL,
                "endpoint_name": "ECG QTc Interval Monitoring",
                "description": "Continuous QTc interval monitoring via single-lead ECG patch for cardiotoxicity",
                "device_type": DeviceType.ECG_PATCH,
                "measure_type": "cardiac_rhythm",
                "unit": "ms",
                "collection_frequency": "continuous",
                "qualification_level": EndpointQualification.REGULATORY_ACCEPTED,
                "clinically_meaningful_change": 30.0,
                "test_retest_icc": 0.95,
                "sensitivity_to_change": 0.88,
                "regulatory_reference": "ICH E14/S7B Q&A R3",
                "concept_of_interest": "QTc prolongation",
                "context_of_use": "Safety endpoint for drug-induced QT prolongation surveillance",
                "created_by": "Dr. Lisa Wang",
            },
            {
                "id": "DEP-011",
                "trial_id": DUPIXENT_TRIAL,
                "endpoint_name": "Daily Physical Activity Level",
                "description": "Accelerometer-derived activity level categorization in AD patients",
                "device_type": DeviceType.ACCELEROMETER,
                "measure_type": "physical_activity",
                "unit": "minutes_moderate_vigorous",
                "collection_frequency": "daily",
                "qualification_level": EndpointQualification.EXPLORATORY,
                "clinically_meaningful_change": 15.0,
                "test_retest_icc": 0.89,
                "sensitivity_to_change": 0.64,
                "regulatory_reference": None,
                "concept_of_interest": "Physical activity impairment from skin disease",
                "context_of_use": "Exploratory endpoint for activity impact of moderate-to-severe AD",
                "created_by": "Dr. Robert Kim",
            },
        ]

        for ep_def in endpoint_defs:
            ep = DigitalEndpoint(
                created_at=now - timedelta(days=90),
                **ep_def,
            )
            self._endpoints[ep.id] = ep

        # --- Data Streams ---
        stream_defs = [
            {
                "id": "DST-001", "endpoint_id": "DEP-001", "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001", "device_type": DeviceType.ACCELEROMETER,
                "device_serial": "ACT-2024-A1001", "status": StreamStatus.ACTIVE,
                "start_date": now - timedelta(days=60), "sampling_rate_hz": 50.0,
                "total_data_points": 5184000, "wear_time_hours": 1320.0,
                "compliance_pct": 91.7, "data_quality_score": 0.94, "site_id": "SITE-101",
            },
            {
                "id": "DST-002", "endpoint_id": "DEP-001", "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002", "device_type": DeviceType.ACCELEROMETER,
                "device_serial": "ACT-2024-A1002", "status": StreamStatus.ACTIVE,
                "start_date": now - timedelta(days=55), "sampling_rate_hz": 50.0,
                "total_data_points": 4752000, "wear_time_hours": 1188.0,
                "compliance_pct": 88.3, "data_quality_score": 0.91, "site_id": "SITE-101",
            },
            {
                "id": "DST-003", "endpoint_id": "DEP-002", "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001", "device_type": DeviceType.SMARTPHONE_SENSOR,
                "device_serial": None, "status": StreamStatus.ACTIVE,
                "start_date": now - timedelta(days=58), "sampling_rate_hz": None,
                "total_data_points": 116, "wear_time_hours": 0.0,
                "compliance_pct": 95.0, "data_quality_score": 0.97, "site_id": "SITE-101",
            },
            {
                "id": "DST-004", "endpoint_id": "DEP-003", "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001", "device_type": DeviceType.ACTIGRAPHY,
                "device_serial": "ACT-2024-W2001", "status": StreamStatus.ACTIVE,
                "start_date": now - timedelta(days=45), "sampling_rate_hz": 32.0,
                "total_data_points": 1382400, "wear_time_hours": 360.0,
                "compliance_pct": 93.5, "data_quality_score": 0.92, "site_id": "SITE-201",
            },
            {
                "id": "DST-005", "endpoint_id": "DEP-004", "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001", "device_type": DeviceType.SMARTWATCH,
                "device_serial": "SW-2024-G3001", "status": StreamStatus.ACTIVE,
                "start_date": now - timedelta(days=45), "sampling_rate_hz": 25.0,
                "total_data_points": 972000, "wear_time_hours": 340.0,
                "compliance_pct": 90.2, "data_quality_score": 0.89, "site_id": "SITE-201",
            },
            {
                "id": "DST-006", "endpoint_id": "DEP-005", "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002", "device_type": DeviceType.BIOSENSOR_PATCH,
                "device_serial": "BSP-2024-P4001", "status": StreamStatus.PAUSED,
                "start_date": now - timedelta(days=30), "sampling_rate_hz": 1.0,
                "total_data_points": 86400, "wear_time_hours": 168.0,
                "compliance_pct": 70.0, "data_quality_score": 0.78, "site_id": "SITE-202",
            },
            {
                "id": "DST-007", "endpoint_id": "DEP-006", "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001", "device_type": DeviceType.PPG_SENSOR,
                "device_serial": "PPG-2024-H5001", "status": StreamStatus.ACTIVE,
                "start_date": now - timedelta(days=40), "sampling_rate_hz": 100.0,
                "total_data_points": 8640000, "wear_time_hours": 720.0,
                "compliance_pct": 85.0, "data_quality_score": 0.86, "site_id": "SITE-301",
            },
            {
                "id": "DST-008", "endpoint_id": "DEP-007", "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001", "device_type": DeviceType.SMARTWATCH,
                "device_serial": "SW-2024-G3002", "status": StreamStatus.ACTIVE,
                "start_date": now - timedelta(days=40), "sampling_rate_hz": 50.0,
                "total_data_points": 4320000, "wear_time_hours": 700.0,
                "compliance_pct": 87.5, "data_quality_score": 0.90, "site_id": "SITE-301",
            },
            {
                "id": "DST-009", "endpoint_id": "DEP-010", "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002", "device_type": DeviceType.ECG_PATCH,
                "device_serial": "ECG-2024-C6001", "status": StreamStatus.COMPLETED,
                "start_date": now - timedelta(days=90), "end_date": now - timedelta(days=5),
                "sampling_rate_hz": 256.0, "total_data_points": 22118400,
                "wear_time_hours": 2040.0, "compliance_pct": 94.2,
                "data_quality_score": 0.96, "site_id": "SITE-302",
            },
            {
                "id": "DST-010", "endpoint_id": "DEP-003", "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003", "device_type": DeviceType.ACTIGRAPHY,
                "device_serial": "ACT-2024-W2002", "status": StreamStatus.ERROR,
                "start_date": now - timedelta(days=20), "sampling_rate_hz": 32.0,
                "total_data_points": 23040, "wear_time_hours": 12.0,
                "compliance_pct": 15.0, "data_quality_score": 0.35, "site_id": "SITE-201",
            },
            {
                "id": "DST-011", "endpoint_id": "DEP-011", "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001", "device_type": DeviceType.ACCELEROMETER,
                "device_serial": "ACT-2024-A3001", "status": StreamStatus.ACTIVE,
                "start_date": now - timedelta(days=42), "sampling_rate_hz": 50.0,
                "total_data_points": 3628800, "wear_time_hours": 840.0,
                "compliance_pct": 83.3, "data_quality_score": 0.88, "site_id": "SITE-201",
            },
        ]

        for st_def in stream_defs:
            stream = DataStream(**st_def)
            self._streams[stream.id] = stream

        # --- Algorithm Validations ---
        algo_defs = [
            {
                "id": "ALG-001", "endpoint_id": "DEP-001",
                "algorithm_name": "StepDetect-CNN", "version": "2.1.0",
                "status": AlgorithmStatus.LOCKED,
                "accuracy": 0.965, "precision": 0.958, "recall": 0.972,
                "f1_score": 0.965, "auc_roc": 0.991,
                "training_samples": 125000, "validation_samples": 31250,
                "reference_method": "OptiTrack motion capture",
                "bland_altman_bias": -12.5, "bland_altman_loa": 245.0,
                "validated_by": "Dr. Wei Zhang", "validation_date": now - timedelta(days=120),
                "locked_date": now - timedelta(days=100),
            },
            {
                "id": "ALG-002", "endpoint_id": "DEP-002",
                "algorithm_name": "VisualTaskTimer-v1", "version": "1.0.3",
                "status": AlgorithmStatus.CLINICAL_VALIDATION,
                "accuracy": 0.934, "precision": 0.941, "recall": 0.927,
                "f1_score": 0.934, "auc_roc": 0.978,
                "training_samples": 45000, "validation_samples": 11250,
                "reference_method": "Manual stopwatch + video review",
                "bland_altman_bias": 0.3, "bland_altman_loa": 2.1,
                "validated_by": "Dr. Priya Sharma",
                "validation_date": now - timedelta(days=45),
                "locked_date": None,
            },
            {
                "id": "ALG-003", "endpoint_id": "DEP-003",
                "algorithm_name": "ScratchDetect-LSTM", "version": "3.2.1",
                "status": AlgorithmStatus.LOCKED,
                "accuracy": 0.942, "precision": 0.938, "recall": 0.946,
                "f1_score": 0.942, "auc_roc": 0.985,
                "training_samples": 89000, "validation_samples": 22250,
                "reference_method": "Infrared video polysomnography",
                "bland_altman_bias": -0.8, "bland_altman_loa": 3.5,
                "validated_by": "Dr. Amanda Li",
                "validation_date": now - timedelta(days=90),
                "locked_date": now - timedelta(days=75),
            },
            {
                "id": "ALG-004", "endpoint_id": "DEP-004",
                "algorithm_name": "SleepScore-Ensemble", "version": "1.5.0",
                "status": AlgorithmStatus.CLINICAL_VALIDATION,
                "accuracy": 0.912, "precision": 0.905, "recall": 0.919,
                "f1_score": 0.912, "auc_roc": 0.968,
                "training_samples": 67000, "validation_samples": 16750,
                "reference_method": "Polysomnography (PSG)",
                "bland_altman_bias": 2.1, "bland_altman_loa": 8.5,
                "validated_by": None, "validation_date": None, "locked_date": None,
            },
            {
                "id": "ALG-005", "endpoint_id": "DEP-005",
                "algorithm_name": "TempDiff-Calibrated", "version": "0.8.2",
                "status": AlgorithmStatus.ANALYTICAL_VALIDATION,
                "accuracy": 0.878, "precision": 0.865, "recall": 0.891,
                "f1_score": 0.878, "auc_roc": 0.945,
                "training_samples": 23000, "validation_samples": 5750,
                "reference_method": "Thermography imaging",
                "bland_altman_bias": 0.05, "bland_altman_loa": 0.4,
                "validated_by": None, "validation_date": None, "locked_date": None,
            },
            {
                "id": "ALG-006", "endpoint_id": "DEP-006",
                "algorithm_name": "HRV-FreqDomain", "version": "2.0.0",
                "status": AlgorithmStatus.LOCKED,
                "accuracy": 0.951, "precision": 0.948, "recall": 0.954,
                "f1_score": 0.951, "auc_roc": 0.989,
                "training_samples": 102000, "validation_samples": 25500,
                "reference_method": "Holter ECG monitor",
                "bland_altman_bias": -1.2, "bland_altman_loa": 6.8,
                "validated_by": "Dr. Michael Torres",
                "validation_date": now - timedelta(days=60),
                "locked_date": now - timedelta(days=50),
            },
            {
                "id": "ALG-007", "endpoint_id": "DEP-007",
                "algorithm_name": "WalkDist-GPS-Fusion", "version": "1.3.0",
                "status": AlgorithmStatus.CLINICAL_VALIDATION,
                "accuracy": 0.923, "precision": 0.918, "recall": 0.928,
                "f1_score": 0.923, "auc_roc": 0.976,
                "training_samples": 55000, "validation_samples": 13750,
                "reference_method": "Measured walking track + GPS",
                "bland_altman_bias": 5.0, "bland_altman_loa": 22.0,
                "validated_by": None, "validation_date": None, "locked_date": None,
            },
            {
                "id": "ALG-008", "endpoint_id": "DEP-008",
                "algorithm_name": "SpO2-PPG-Corrected", "version": "1.1.2",
                "status": AlgorithmStatus.LOCKED,
                "accuracy": 0.973, "precision": 0.969, "recall": 0.977,
                "f1_score": 0.973, "auc_roc": 0.994,
                "training_samples": 150000, "validation_samples": 37500,
                "reference_method": "ABG blood gas analysis",
                "bland_altman_bias": 0.1, "bland_altman_loa": 1.8,
                "validated_by": "Dr. Lisa Wang",
                "validation_date": now - timedelta(days=80),
                "locked_date": now - timedelta(days=70),
            },
            {
                "id": "ALG-009", "endpoint_id": "DEP-009",
                "algorithm_name": "ContrastSens-Adaptive", "version": "0.5.0",
                "status": AlgorithmStatus.DEVELOPMENT,
                "accuracy": 0.845, "precision": 0.830, "recall": 0.860,
                "f1_score": 0.845, "auc_roc": 0.920,
                "training_samples": 12000, "validation_samples": 3000,
                "reference_method": "Pelli-Robson chart",
                "bland_altman_bias": -0.08, "bland_altman_loa": 0.25,
                "validated_by": None, "validation_date": None, "locked_date": None,
            },
            {
                "id": "ALG-010", "endpoint_id": "DEP-010",
                "algorithm_name": "QTc-AutoDetect", "version": "4.0.1",
                "status": AlgorithmStatus.LOCKED,
                "accuracy": 0.988, "precision": 0.985, "recall": 0.991,
                "f1_score": 0.988, "auc_roc": 0.998,
                "training_samples": 210000, "validation_samples": 52500,
                "reference_method": "12-lead Holter ECG with cardiologist review",
                "bland_altman_bias": -0.5, "bland_altman_loa": 4.2,
                "validated_by": "Dr. Lisa Wang",
                "validation_date": now - timedelta(days=150),
                "locked_date": now - timedelta(days=140),
            },
            {
                "id": "ALG-011", "endpoint_id": "DEP-011",
                "algorithm_name": "MVPA-Classifier", "version": "1.0.0",
                "status": AlgorithmStatus.DEVELOPMENT,
                "accuracy": 0.890, "precision": 0.882, "recall": 0.898,
                "f1_score": 0.890, "auc_roc": 0.952,
                "training_samples": 34000, "validation_samples": 8500,
                "reference_method": "Direct observation + video annotation",
                "bland_altman_bias": 1.5, "bland_altman_loa": 7.0,
                "validated_by": None, "validation_date": None, "locked_date": None,
            },
        ]

        for algo_def in algo_defs:
            algo = AlgorithmValidation(
                created_at=now - timedelta(days=180),
                **algo_def,
            )
            self._algorithms[algo.id] = algo

        # --- Digital Measure Scores ---
        score_defs = [
            {
                "id": "DMS-001", "stream_id": "DST-001", "endpoint_id": "DEP-001",
                "subject_id": "SUBJ-E001", "trial_id": EYLEA_TRIAL, "algorithm_id": "ALG-001",
                "score_value": 7245.0, "score_unit": "steps/day",
                "scoring_status": ScoringStatus.QC_PASSED, "visit": "Week 4",
                "measurement_period_start": now - timedelta(days=35),
                "measurement_period_end": now - timedelta(days=28),
                "wear_time_hours": 156.0, "minimum_wear_met": True,
                "qc_flag": None, "scored_date": now - timedelta(days=25),
            },
            {
                "id": "DMS-002", "stream_id": "DST-001", "endpoint_id": "DEP-001",
                "subject_id": "SUBJ-E001", "trial_id": EYLEA_TRIAL, "algorithm_id": "ALG-001",
                "score_value": 7890.0, "score_unit": "steps/day",
                "scoring_status": ScoringStatus.QC_PASSED, "visit": "Week 8",
                "measurement_period_start": now - timedelta(days=14),
                "measurement_period_end": now - timedelta(days=7),
                "wear_time_hours": 160.0, "minimum_wear_met": True,
                "qc_flag": None, "scored_date": now - timedelta(days=5),
            },
            {
                "id": "DMS-003", "stream_id": "DST-003", "endpoint_id": "DEP-002",
                "subject_id": "SUBJ-E001", "trial_id": EYLEA_TRIAL, "algorithm_id": "ALG-002",
                "score_value": 42.5, "score_unit": "seconds",
                "scoring_status": ScoringStatus.SCORED, "visit": "Week 4",
                "measurement_period_start": now - timedelta(days=35),
                "measurement_period_end": now - timedelta(days=28),
                "wear_time_hours": 0.0, "minimum_wear_met": True,
                "qc_flag": None, "scored_date": now - timedelta(days=24),
            },
            {
                "id": "DMS-004", "stream_id": "DST-004", "endpoint_id": "DEP-003",
                "subject_id": "SUBJ-D001", "trial_id": DUPIXENT_TRIAL, "algorithm_id": "ALG-003",
                "score_value": 18.0, "score_unit": "events/night",
                "scoring_status": ScoringStatus.QC_PASSED, "visit": "Week 2",
                "measurement_period_start": now - timedelta(days=38),
                "measurement_period_end": now - timedelta(days=31),
                "wear_time_hours": 56.0, "minimum_wear_met": True,
                "qc_flag": None, "scored_date": now - timedelta(days=28),
            },
            {
                "id": "DMS-005", "stream_id": "DST-004", "endpoint_id": "DEP-003",
                "subject_id": "SUBJ-D001", "trial_id": DUPIXENT_TRIAL, "algorithm_id": "ALG-003",
                "score_value": 12.0, "score_unit": "events/night",
                "scoring_status": ScoringStatus.QC_PASSED, "visit": "Week 4",
                "measurement_period_start": now - timedelta(days=24),
                "measurement_period_end": now - timedelta(days=17),
                "wear_time_hours": 54.0, "minimum_wear_met": True,
                "qc_flag": None, "scored_date": now - timedelta(days=14),
            },
            {
                "id": "DMS-006", "stream_id": "DST-005", "endpoint_id": "DEP-004",
                "subject_id": "SUBJ-D001", "trial_id": DUPIXENT_TRIAL, "algorithm_id": "ALG-004",
                "score_value": 62.0, "score_unit": "score (0-100)",
                "scoring_status": ScoringStatus.SCORED, "visit": "Week 4",
                "measurement_period_start": now - timedelta(days=24),
                "measurement_period_end": now - timedelta(days=17),
                "wear_time_hours": 48.0, "minimum_wear_met": True,
                "qc_flag": None, "scored_date": now - timedelta(days=13),
            },
            {
                "id": "DMS-007", "stream_id": "DST-007", "endpoint_id": "DEP-006",
                "subject_id": "SUBJ-L001", "trial_id": LIBTAYO_TRIAL, "algorithm_id": "ALG-006",
                "score_value": 34.5, "score_unit": "ms (RMSSD)",
                "scoring_status": ScoringStatus.QC_PASSED, "visit": "Week 4",
                "measurement_period_start": now - timedelta(days=28),
                "measurement_period_end": now - timedelta(days=21),
                "wear_time_hours": 144.0, "minimum_wear_met": True,
                "qc_flag": None, "scored_date": now - timedelta(days=18),
            },
            {
                "id": "DMS-008", "stream_id": "DST-008", "endpoint_id": "DEP-007",
                "subject_id": "SUBJ-L001", "trial_id": LIBTAYO_TRIAL, "algorithm_id": "ALG-007",
                "score_value": 412.0, "score_unit": "meters",
                "scoring_status": ScoringStatus.QC_PASSED, "visit": "Week 4",
                "measurement_period_start": now - timedelta(days=28),
                "measurement_period_end": now - timedelta(days=21),
                "wear_time_hours": 140.0, "minimum_wear_met": True,
                "qc_flag": None, "scored_date": now - timedelta(days=17),
            },
            {
                "id": "DMS-009", "stream_id": "DST-009", "endpoint_id": "DEP-010",
                "subject_id": "SUBJ-L002", "trial_id": LIBTAYO_TRIAL, "algorithm_id": "ALG-010",
                "score_value": 445.0, "score_unit": "ms",
                "scoring_status": ScoringStatus.QC_PASSED, "visit": "Week 12",
                "measurement_period_start": now - timedelta(days=14),
                "measurement_period_end": now - timedelta(days=7),
                "wear_time_hours": 168.0, "minimum_wear_met": True,
                "qc_flag": None, "scored_date": now - timedelta(days=4),
            },
            {
                "id": "DMS-010", "stream_id": "DST-010", "endpoint_id": "DEP-003",
                "subject_id": "SUBJ-D003", "trial_id": DUPIXENT_TRIAL, "algorithm_id": "ALG-003",
                "score_value": None, "score_unit": "events/night",
                "scoring_status": ScoringStatus.QC_FAILED, "visit": "Week 1",
                "measurement_period_start": now - timedelta(days=18),
                "measurement_period_end": now - timedelta(days=11),
                "wear_time_hours": 8.0, "minimum_wear_met": False,
                "qc_flag": "Insufficient wear time: 8h < 40h minimum",
                "scored_date": now - timedelta(days=9),
            },
            {
                "id": "DMS-011", "stream_id": "DST-002", "endpoint_id": "DEP-001",
                "subject_id": "SUBJ-E002", "trial_id": EYLEA_TRIAL, "algorithm_id": "ALG-001",
                "score_value": 5120.0, "score_unit": "steps/day",
                "scoring_status": ScoringStatus.ADJUDICATED, "visit": "Week 4",
                "measurement_period_start": now - timedelta(days=35),
                "measurement_period_end": now - timedelta(days=28),
                "wear_time_hours": 148.0, "minimum_wear_met": True,
                "qc_flag": "Low step count flagged for adjudication",
                "scored_date": now - timedelta(days=22),
            },
        ]

        for sc_def in score_defs:
            score = DigitalMeasureScore(**sc_def)
            self._scores[score.id] = score

        # --- Regulatory Qualifications ---
        qual_defs = [
            {
                "id": "RQU-001", "endpoint_id": "DEP-003",
                "regulatory_authority": "FDA",
                "qualification_type": "Biomarker Qualification",
                "submission_date": now - timedelta(days=60),
                "status": "under_review",
                "feedback": "Initial review feedback: additional V&V data requested for diverse populations",
                "qualification_date": None,
                "context_of_use": "Secondary endpoint for nocturnal pruritus in moderate-to-severe atopic dermatitis",
                "evidence_package": [
                    "Analytical validation report v2.1",
                    "Clinical validation study report",
                    "V&V protocol and SAP",
                    "Literature review of actigraphy in pruritus",
                ],
                "responsible_person": "Dr. Amanda Li",
            },
            {
                "id": "RQU-002", "endpoint_id": "DEP-010",
                "regulatory_authority": "FDA",
                "qualification_type": "Medical Device De Novo",
                "submission_date": now - timedelta(days=200),
                "status": "qualified",
                "feedback": "Qualification granted for continuous QTc monitoring in oncology trials",
                "qualification_date": now - timedelta(days=90),
                "context_of_use": "Safety endpoint for drug-induced QT prolongation surveillance in oncology",
                "evidence_package": [
                    "510(k) predicate comparison",
                    "Clinical validation study (n=500)",
                    "Bench testing report",
                    "Software validation report",
                    "Biocompatibility testing",
                ],
                "responsible_person": "Dr. Lisa Wang",
            },
            {
                "id": "RQU-003", "endpoint_id": "DEP-001",
                "regulatory_authority": "EMA",
                "qualification_type": "Novel Methodology Qualification",
                "submission_date": None,
                "status": "planning",
                "feedback": None,
                "qualification_date": None,
                "context_of_use": "Exploratory endpoint for mobility in ophthalmology trials",
                "evidence_package": [
                    "Concept paper draft",
                    "Preliminary validation data summary",
                ],
                "responsible_person": "Dr. Sarah Chen",
            },
            {
                "id": "RQU-004", "endpoint_id": "DEP-003",
                "regulatory_authority": "EMA",
                "qualification_type": "Biomarker Qualification",
                "submission_date": now - timedelta(days=30),
                "status": "submitted",
                "feedback": None,
                "qualification_date": None,
                "context_of_use": "Secondary endpoint for nocturnal pruritus in moderate-to-severe AD",
                "evidence_package": [
                    "Qualification advice letter",
                    "Clinical validation report",
                    "Literature review",
                ],
                "responsible_person": "Dr. Amanda Li",
            },
            {
                "id": "RQU-005", "endpoint_id": "DEP-007",
                "regulatory_authority": "FDA",
                "qualification_type": "Biomarker Qualification",
                "submission_date": None,
                "status": "planning",
                "feedback": None,
                "qualification_date": None,
                "context_of_use": "Secondary endpoint for functional capacity in NSCLC",
                "evidence_package": [
                    "Concept of interest summary",
                    "Preliminary analytical validation data",
                ],
                "responsible_person": "Dr. Michael Torres",
            },
            {
                "id": "RQU-006", "endpoint_id": "DEP-004",
                "regulatory_authority": "FDA",
                "qualification_type": "Drug Development Tool Qualification",
                "submission_date": None,
                "status": "planning",
                "feedback": None,
                "qualification_date": None,
                "context_of_use": "Exploratory endpoint assessing itch-related sleep disruption in AD",
                "evidence_package": [],
                "responsible_person": "Dr. Amanda Li",
            },
            {
                "id": "RQU-007", "endpoint_id": "DEP-006",
                "regulatory_authority": "FDA",
                "qualification_type": "Biomarker Qualification",
                "submission_date": now - timedelta(days=15),
                "status": "submitted",
                "feedback": None,
                "qualification_date": None,
                "context_of_use": "Exploratory safety endpoint for immune-related cardiotoxicity in IO trials",
                "evidence_package": [
                    "Analytical validation report",
                    "Clinical validation study interim results",
                    "Literature review of HRV in oncology",
                ],
                "responsible_person": "Dr. Michael Torres",
            },
            {
                "id": "RQU-008", "endpoint_id": "DEP-010",
                "regulatory_authority": "EMA",
                "qualification_type": "Scientific Advice",
                "submission_date": now - timedelta(days=45),
                "status": "under_review",
                "feedback": "EMA CHMP scientific advice pending on single-lead ECG patch use",
                "qualification_date": None,
                "context_of_use": "Safety endpoint for QTc monitoring in thorough QT studies",
                "evidence_package": [
                    "Scientific advice briefing document",
                    "Clinical data package",
                ],
                "responsible_person": "Dr. Lisa Wang",
            },
            {
                "id": "RQU-009", "endpoint_id": "DEP-005",
                "regulatory_authority": "FDA",
                "qualification_type": "Letter of Intent",
                "submission_date": None,
                "status": "planning",
                "feedback": None,
                "qualification_date": None,
                "context_of_use": "Exploratory biomarker for local inflammatory activity in AD",
                "evidence_package": [],
                "responsible_person": "Dr. Robert Kim",
            },
            {
                "id": "RQU-010", "endpoint_id": "DEP-008",
                "regulatory_authority": "FDA",
                "qualification_type": "Biomarker Qualification",
                "submission_date": now - timedelta(days=100),
                "status": "under_review",
                "feedback": "Pending additional data on diverse skin pigmentation populations",
                "qualification_date": None,
                "context_of_use": "Safety monitoring for immune-related pneumonitis detection",
                "evidence_package": [
                    "Analytical validation report",
                    "Clinical validation study report",
                    "Skin pigmentation bias analysis",
                ],
                "responsible_person": "Dr. Lisa Wang",
            },
        ]

        for q_def in qual_defs:
            qual = RegulatoryQualification(
                created_at=now - timedelta(days=120),
                **q_def,
            )
            self._qualifications[qual.id] = qual

        logger.info(
            "Seeded digital biomarkers: %d endpoints, %d streams, "
            "%d algorithms, %d scores, %d qualifications",
            len(self._endpoints),
            len(self._streams),
            len(self._algorithms),
            len(self._scores),
            len(self._qualifications),
        )

    # ------------------------------------------------------------------
    # Digital Endpoints CRUD
    # ------------------------------------------------------------------

    def create_endpoint(self, payload: DigitalEndpointCreate) -> DigitalEndpoint:
        now = datetime.now(timezone.utc)
        ep_id = f"DEP-{uuid4().hex[:8].upper()}"
        ep = DigitalEndpoint(
            id=ep_id,
            trial_id=payload.trial_id,
            endpoint_name=payload.endpoint_name,
            description=payload.description,
            device_type=payload.device_type,
            measure_type=payload.measure_type,
            unit=payload.unit,
            collection_frequency=payload.collection_frequency,
            concept_of_interest=payload.concept_of_interest,
            context_of_use=payload.context_of_use,
            created_by=payload.created_by,
            created_at=now,
        )
        with self._lock:
            self._endpoints[ep_id] = ep
        logger.info("Created digital endpoint %s: %s", ep_id, payload.endpoint_name)
        return ep

    def get_endpoint(self, endpoint_id: str) -> DigitalEndpoint | None:
        with self._lock:
            return self._endpoints.get(endpoint_id)

    def list_endpoints(self, *, trial_id: str | None = None) -> list[DigitalEndpoint]:
        with self._lock:
            result = list(self._endpoints.values())
        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        return sorted(result, key=lambda e: e.created_at, reverse=True)

    def update_endpoint(self, endpoint_id: str, payload: DigitalEndpointUpdate) -> DigitalEndpoint | None:
        with self._lock:
            existing = self._endpoints.get(endpoint_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DigitalEndpoint(**data)
            self._endpoints[endpoint_id] = updated
        return updated

    def delete_endpoint(self, endpoint_id: str) -> bool:
        with self._lock:
            if endpoint_id in self._endpoints:
                del self._endpoints[endpoint_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Data Streams CRUD
    # ------------------------------------------------------------------

    def create_stream(self, payload: DataStreamCreate) -> DataStream:
        now = datetime.now(timezone.utc)
        stream_id = f"DST-{uuid4().hex[:8].upper()}"
        stream = DataStream(
            id=stream_id,
            endpoint_id=payload.endpoint_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            device_type=payload.device_type,
            device_serial=payload.device_serial,
            sampling_rate_hz=payload.sampling_rate_hz,
            site_id=payload.site_id,
            start_date=now,
        )
        with self._lock:
            self._streams[stream_id] = stream
        logger.info("Created data stream %s for endpoint %s", stream_id, payload.endpoint_id)
        return stream

    def get_stream(self, stream_id: str) -> DataStream | None:
        with self._lock:
            return self._streams.get(stream_id)

    def list_streams(
        self,
        *,
        trial_id: str | None = None,
        endpoint_id: str | None = None,
    ) -> list[DataStream]:
        with self._lock:
            result = list(self._streams.values())
        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if endpoint_id is not None:
            result = [s for s in result if s.endpoint_id == endpoint_id]
        return result

    def update_stream(self, stream_id: str, payload: DataStreamUpdate) -> DataStream | None:
        with self._lock:
            existing = self._streams.get(stream_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DataStream(**data)
            self._streams[stream_id] = updated
        return updated

    def delete_stream(self, stream_id: str) -> bool:
        with self._lock:
            if stream_id in self._streams:
                del self._streams[stream_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Algorithm Validations CRUD
    # ------------------------------------------------------------------

    def create_algorithm(self, payload: AlgorithmValidationCreate) -> AlgorithmValidation:
        now = datetime.now(timezone.utc)
        algo_id = f"ALG-{uuid4().hex[:8].upper()}"
        algo = AlgorithmValidation(
            id=algo_id,
            endpoint_id=payload.endpoint_id,
            algorithm_name=payload.algorithm_name,
            version=payload.version,
            reference_method=payload.reference_method,
            created_at=now,
        )
        with self._lock:
            self._algorithms[algo_id] = algo
        logger.info("Created algorithm %s: %s v%s", algo_id, payload.algorithm_name, payload.version)
        return algo

    def get_algorithm(self, algorithm_id: str) -> AlgorithmValidation | None:
        with self._lock:
            return self._algorithms.get(algorithm_id)

    def list_algorithms(self, *, endpoint_id: str | None = None) -> list[AlgorithmValidation]:
        with self._lock:
            result = list(self._algorithms.values())
        if endpoint_id is not None:
            result = [a for a in result if a.endpoint_id == endpoint_id]
        return sorted(result, key=lambda a: a.created_at, reverse=True)

    def update_algorithm(self, algorithm_id: str, payload: AlgorithmValidationUpdate) -> AlgorithmValidation | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._algorithms.get(algorithm_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set validation_date and locked_date on status transitions
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = AlgorithmStatus(new_status)
                if new_status == AlgorithmStatus.LOCKED and existing.status != AlgorithmStatus.LOCKED:
                    data["locked_date"] = now
                if new_status in (AlgorithmStatus.CLINICAL_VALIDATION, AlgorithmStatus.LOCKED):
                    if existing.validation_date is None:
                        data["validation_date"] = now
            if "validated_by" in updates and updates["validated_by"] and existing.validation_date is None:
                data["validation_date"] = now
            data.update(updates)
            updated = AlgorithmValidation(**data)
            self._algorithms[algorithm_id] = updated
        return updated

    def delete_algorithm(self, algorithm_id: str) -> bool:
        with self._lock:
            if algorithm_id in self._algorithms:
                del self._algorithms[algorithm_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Digital Measure Scores CRUD
    # ------------------------------------------------------------------

    def create_score(self, payload: DigitalMeasureScoreCreate) -> DigitalMeasureScore:
        score_id = f"DMS-{uuid4().hex[:8].upper()}"
        score = DigitalMeasureScore(
            id=score_id,
            stream_id=payload.stream_id,
            endpoint_id=payload.endpoint_id,
            subject_id=payload.subject_id,
            trial_id=payload.trial_id,
            algorithm_id=payload.algorithm_id,
            score_value=payload.score_value,
            score_unit=payload.score_unit,
            measurement_period_start=payload.measurement_period_start,
            measurement_period_end=payload.measurement_period_end,
            visit=payload.visit,
        )
        with self._lock:
            self._scores[score_id] = score
        logger.info("Created digital measure score %s for endpoint %s", score_id, payload.endpoint_id)
        return score

    def get_score(self, score_id: str) -> DigitalMeasureScore | None:
        with self._lock:
            return self._scores.get(score_id)

    def list_scores(
        self,
        *,
        trial_id: str | None = None,
        endpoint_id: str | None = None,
    ) -> list[DigitalMeasureScore]:
        with self._lock:
            result = list(self._scores.values())
        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if endpoint_id is not None:
            result = [s for s in result if s.endpoint_id == endpoint_id]
        return result

    def update_score(self, score_id: str, payload: DigitalMeasureScoreUpdate) -> DigitalMeasureScore | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._scores.get(score_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set scored_date on status transition to scored/qc_passed
            if "scoring_status" in updates:
                new_status = updates["scoring_status"]
                if isinstance(new_status, str):
                    new_status = ScoringStatus(new_status)
                if new_status in (ScoringStatus.SCORED, ScoringStatus.QC_PASSED, ScoringStatus.ADJUDICATED):
                    if existing.scored_date is None:
                        data["scored_date"] = now
            data.update(updates)
            updated = DigitalMeasureScore(**data)
            self._scores[score_id] = updated
        return updated

    def delete_score(self, score_id: str) -> bool:
        with self._lock:
            if score_id in self._scores:
                del self._scores[score_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Regulatory Qualifications CRUD
    # ------------------------------------------------------------------

    def create_qualification(self, payload: RegulatoryQualificationCreate) -> RegulatoryQualification:
        now = datetime.now(timezone.utc)
        qual_id = f"RQU-{uuid4().hex[:8].upper()}"
        qual = RegulatoryQualification(
            id=qual_id,
            endpoint_id=payload.endpoint_id,
            regulatory_authority=payload.regulatory_authority,
            qualification_type=payload.qualification_type,
            context_of_use=payload.context_of_use,
            responsible_person=payload.responsible_person,
            evidence_package=payload.evidence_package,
            created_at=now,
        )
        with self._lock:
            self._qualifications[qual_id] = qual
        logger.info("Created regulatory qualification %s for endpoint %s", qual_id, payload.endpoint_id)
        return qual

    def get_qualification(self, qualification_id: str) -> RegulatoryQualification | None:
        with self._lock:
            return self._qualifications.get(qualification_id)

    def list_qualifications(self, *, endpoint_id: str | None = None) -> list[RegulatoryQualification]:
        with self._lock:
            result = list(self._qualifications.values())
        if endpoint_id is not None:
            result = [q for q in result if q.endpoint_id == endpoint_id]
        return sorted(result, key=lambda q: q.created_at, reverse=True)

    def update_qualification(
        self, qualification_id: str, payload: RegulatoryQualificationUpdate
    ) -> RegulatoryQualification | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._qualifications.get(qualification_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set qualification_date when status becomes qualified
            if "status" in updates and updates["status"] == "qualified" and existing.status != "qualified":
                data["qualification_date"] = now
            data.update(updates)
            updated = RegulatoryQualification(**data)
            self._qualifications[qualification_id] = updated
        return updated

    def delete_qualification(self, qualification_id: str) -> bool:
        with self._lock:
            if qualification_id in self._qualifications:
                del self._qualifications[qualification_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> DigitalBiomarkerMetrics:
        """Compute aggregated digital biomarker operational metrics."""
        with self._lock:
            endpoints = list(self._endpoints.values())
            streams = list(self._streams.values())
            algorithms = list(self._algorithms.values())
            scores = list(self._scores.values())
            qualifications = list(self._qualifications.values())

        # Endpoints by device
        endpoints_by_device: dict[str, int] = {}
        for ep in endpoints:
            key = ep.device_type.value
            endpoints_by_device[key] = endpoints_by_device.get(key, 0) + 1

        # Endpoints by qualification
        endpoints_by_qual: dict[str, int] = {}
        for ep in endpoints:
            key = ep.qualification_level.value
            endpoints_by_qual[key] = endpoints_by_qual.get(key, 0) + 1

        # Streams by status
        streams_by_status: dict[str, int] = {}
        for s in streams:
            key = s.status.value
            streams_by_status[key] = streams_by_status.get(key, 0) + 1

        # Average compliance
        compliance_values = [s.compliance_pct for s in streams if s.compliance_pct > 0]
        avg_compliance = round(sum(compliance_values) / max(1, len(compliance_values)), 1)

        # Algorithms by status
        algorithms_by_status: dict[str, int] = {}
        locked_count = 0
        for a in algorithms:
            key = a.status.value
            algorithms_by_status[key] = algorithms_by_status.get(key, 0) + 1
            if a.status == AlgorithmStatus.LOCKED:
                locked_count += 1

        # Scores by status
        scores_by_status: dict[str, int] = {}
        qc_passed = 0
        qc_total = 0
        for sc in scores:
            key = sc.scoring_status.value
            scores_by_status[key] = scores_by_status.get(key, 0) + 1
            if sc.scoring_status in (ScoringStatus.QC_PASSED, ScoringStatus.QC_FAILED):
                qc_total += 1
                if sc.scoring_status == ScoringStatus.QC_PASSED:
                    qc_passed += 1

        qc_pass_rate = round(qc_passed / max(1, qc_total) * 100, 1)

        # Qualifications by status
        qualifications_by_status: dict[str, int] = {}
        for q in qualifications:
            qualifications_by_status[q.status] = qualifications_by_status.get(q.status, 0) + 1

        return DigitalBiomarkerMetrics(
            total_endpoints=len(endpoints),
            endpoints_by_device=endpoints_by_device,
            endpoints_by_qualification=endpoints_by_qual,
            total_streams=len(streams),
            streams_by_status=streams_by_status,
            avg_compliance_pct=avg_compliance,
            total_algorithms=len(algorithms),
            algorithms_by_status=algorithms_by_status,
            locked_algorithms=locked_count,
            total_scores=len(scores),
            scores_by_status=scores_by_status,
            qc_pass_rate_pct=qc_pass_rate,
            total_qualifications=len(qualifications),
            qualifications_by_status=qualifications_by_status,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: DigitalBiomarkersService | None = None
_instance_lock = threading.Lock()


def get_digital_biomarkers_service() -> DigitalBiomarkersService:
    """Return the singleton DigitalBiomarkersService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DigitalBiomarkersService()
    return _instance


def reset_digital_biomarkers_service() -> DigitalBiomarkersService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = DigitalBiomarkersService()
    return _instance
