"""Clinical Imaging Management Service (IMG-MGMT).

Manages medical imaging operations: imaging study definitions, image acquisition
tracking, central reader assignments, RECIST/disease assessments, reader
training/qualification, image quality reviews, and imaging metrics.

Usage:
    from app.services.imaging_management_service import (
        get_imaging_management_service,
    )

    svc = get_imaging_management_service()
    studies = svc.list_studies()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.imaging_management import (
    AssessmentCriteria,
    CentralReader,
    CentralReaderCreate,
    CentralReaderUpdate,
    DiseaseAssessment,
    DiseaseAssessmentCreate,
    ImageAcquisition,
    ImageAcquisitionCreate,
    ImageAcquisitionUpdate,
    ImageQualityReview,
    ImageQualityReviewCreate,
    ImageStatus,
    ImagingManagementMetrics,
    ImagingModality,
    ImagingStudy,
    ImagingStudyCreate,
    ImagingStudyUpdate,
    OverallResponse,
    QCOutcome,
    QualificationStatus,
    ReadingDesign,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ImagingManagementService:
    """In-memory Clinical Imaging Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._studies: dict[str, ImagingStudy] = {}
        self._acquisitions: dict[str, ImageAcquisition] = {}
        self._readers: dict[str, CentralReader] = {}
        self._assessments: dict[str, DiseaseAssessment] = {}
        self._qc_reviews: dict[str, ImageQualityReview] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic imaging management data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- Imaging Studies ---
        studies_data = [
            {
                "id": "IMG-STUDY-001",
                "trial_id": EYLEA_TRIAL,
                "title": "EYLEA Retinal Imaging Sub-study",
                "modalities": [ImagingModality.OCT, ImagingModality.FUNDUS_PHOTO],
                "assessment_criteria": AssessmentCriteria.ETDRS,
                "reading_design": ReadingDesign.DUAL_READER,
                "blinded": True,
                "assessment_schedule": ["Screening", "Week 4", "Week 8", "Week 12", "Week 24", "Week 52"],
                "total_subjects": 245,
                "charter_version": "3.1",
                "vendor": "Digital Angiography Reading Center",
                "status": "active",
                "created_at": now - timedelta(days=365),
            },
            {
                "id": "IMG-STUDY-002",
                "trial_id": EYLEA_TRIAL,
                "title": "EYLEA Fluorescein Angiography Assessment",
                "modalities": [ImagingModality.FUNDUS_PHOTO],
                "assessment_criteria": AssessmentCriteria.ETDRS,
                "reading_design": ReadingDesign.SINGLE_READER,
                "blinded": True,
                "assessment_schedule": ["Screening", "Week 12", "Week 24", "Week 52"],
                "total_subjects": 180,
                "charter_version": "2.0",
                "vendor": "Fundus Photo Reading Center",
                "status": "active",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "IMG-STUDY-003",
                "trial_id": DUPIXENT_TRIAL,
                "title": "DUPIXENT Dermatology Photography Assessment",
                "modalities": [ImagingModality.FUNDUS_PHOTO],
                "assessment_criteria": AssessmentCriteria.EASI,
                "reading_design": ReadingDesign.DUAL_READER,
                "blinded": True,
                "assessment_schedule": ["Baseline", "Week 4", "Week 8", "Week 16", "Week 24"],
                "total_subjects": 310,
                "charter_version": "2.2",
                "vendor": "DermImaging Core Lab",
                "status": "active",
                "created_at": now - timedelta(days=280),
            },
            {
                "id": "IMG-STUDY-004",
                "trial_id": DUPIXENT_TRIAL,
                "title": "DUPIXENT Skin Lesion Photography Sub-study",
                "modalities": [ImagingModality.FUNDUS_PHOTO],
                "assessment_criteria": AssessmentCriteria.EASI,
                "reading_design": ReadingDesign.CONSENSUS,
                "blinded": True,
                "assessment_schedule": ["Baseline", "Week 16", "Week 24"],
                "total_subjects": 150,
                "charter_version": "1.1",
                "vendor": "DermImaging Core Lab",
                "status": "active",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "IMG-STUDY-005",
                "trial_id": LIBTAYO_TRIAL,
                "title": "LIBTAYO RECIST 1.1 Tumor Assessment",
                "modalities": [ImagingModality.CT, ImagingModality.MRI],
                "assessment_criteria": AssessmentCriteria.RECIST_1_1,
                "reading_design": ReadingDesign.DUAL_READER,
                "blinded": True,
                "assessment_schedule": ["Screening", "Week 8", "Week 16", "Week 24", "Week 36", "Week 52"],
                "total_subjects": 420,
                "charter_version": "4.0",
                "vendor": "Radiology Core Lab International",
                "status": "active",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "IMG-STUDY-006",
                "trial_id": LIBTAYO_TRIAL,
                "title": "LIBTAYO Brain Metastasis MRI Assessment",
                "modalities": [ImagingModality.MRI],
                "assessment_criteria": AssessmentCriteria.RANO,
                "reading_design": ReadingDesign.ADJUDICATION,
                "blinded": True,
                "assessment_schedule": ["Screening", "Week 12", "Week 24", "Week 52"],
                "total_subjects": 85,
                "charter_version": "1.3",
                "vendor": "Radiology Core Lab International",
                "status": "active",
                "created_at": now - timedelta(days=350),
            },
            {
                "id": "IMG-STUDY-007",
                "trial_id": LIBTAYO_TRIAL,
                "title": "LIBTAYO PET-CT Response Monitoring",
                "modalities": [ImagingModality.PET_CT, ImagingModality.CT],
                "assessment_criteria": AssessmentCriteria.LUGANO,
                "reading_design": ReadingDesign.DUAL_READER,
                "blinded": True,
                "assessment_schedule": ["Screening", "Week 16", "Week 52"],
                "total_subjects": 200,
                "charter_version": "2.1",
                "vendor": "PET Imaging Core Lab",
                "status": "active",
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "IMG-STUDY-008",
                "trial_id": EYLEA_TRIAL,
                "title": "EYLEA Macular Thickness OCT Analysis",
                "modalities": [ImagingModality.OCT],
                "assessment_criteria": AssessmentCriteria.ETDRS,
                "reading_design": ReadingDesign.SINGLE_READER,
                "blinded": True,
                "assessment_schedule": ["Screening", "Week 4", "Week 12", "Week 24"],
                "total_subjects": 190,
                "charter_version": "1.5",
                "vendor": "Digital Angiography Reading Center",
                "status": "active",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "IMG-STUDY-009",
                "trial_id": LIBTAYO_TRIAL,
                "title": "LIBTAYO Bone Metastasis Assessment",
                "modalities": [ImagingModality.CT, ImagingModality.DEXA],
                "assessment_criteria": AssessmentCriteria.RECIST_1_1,
                "reading_design": ReadingDesign.SINGLE_READER,
                "blinded": False,
                "assessment_schedule": ["Screening", "Week 24", "Week 52"],
                "total_subjects": 60,
                "charter_version": "1.0",
                "vendor": "Radiology Core Lab International",
                "status": "active",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "IMG-STUDY-010",
                "trial_id": DUPIXENT_TRIAL,
                "title": "DUPIXENT Chest X-ray Safety Monitoring",
                "modalities": [ImagingModality.XRAY],
                "assessment_criteria": AssessmentCriteria.CUSTOM,
                "reading_design": ReadingDesign.SINGLE_READER,
                "blinded": False,
                "assessment_schedule": ["Screening", "Week 52"],
                "total_subjects": 310,
                "charter_version": "1.0",
                "vendor": "Safety Imaging Services",
                "status": "active",
                "created_at": now - timedelta(days=280),
            },
        ]

        for s in studies_data:
            self._studies[s["id"]] = ImagingStudy(**s)

        # --- Image Acquisitions ---
        acquisitions_data = [
            # EYLEA OCT/Fundus acquisitions
            {
                "id": "ACQ-001",
                "study_id": "IMG-STUDY-001",
                "subject_id": "SUBJ-E001",
                "visit": "Screening",
                "modality": ImagingModality.OCT,
                "acquisition_date": now - timedelta(days=90),
                "site_id": "SITE-101",
                "status": ImageStatus.READ_COMPLETE,
                "upload_date": now - timedelta(days=89),
                "file_count": 128,
                "total_size_mb": 256.4,
                "series_description": "Macular cube 512x128",
                "slice_thickness_mm": 0.003,
                "contrast_used": False,
                "technologist": "Maria Chen",
            },
            {
                "id": "ACQ-002",
                "study_id": "IMG-STUDY-001",
                "subject_id": "SUBJ-E001",
                "visit": "Week 4",
                "modality": ImagingModality.OCT,
                "acquisition_date": now - timedelta(days=62),
                "site_id": "SITE-101",
                "status": ImageStatus.QC_PASSED,
                "upload_date": now - timedelta(days=61),
                "file_count": 128,
                "total_size_mb": 261.2,
                "series_description": "Macular cube 512x128",
                "slice_thickness_mm": 0.003,
                "contrast_used": False,
                "technologist": "Maria Chen",
            },
            {
                "id": "ACQ-003",
                "study_id": "IMG-STUDY-001",
                "subject_id": "SUBJ-E002",
                "visit": "Screening",
                "modality": ImagingModality.FUNDUS_PHOTO,
                "acquisition_date": now - timedelta(days=85),
                "site_id": "SITE-102",
                "status": ImageStatus.ASSIGNED,
                "upload_date": now - timedelta(days=84),
                "file_count": 7,
                "total_size_mb": 45.3,
                "series_description": "7-field fundus photography",
                "slice_thickness_mm": None,
                "contrast_used": False,
                "technologist": "James Wilson",
            },
            {
                "id": "ACQ-004",
                "study_id": "IMG-STUDY-001",
                "subject_id": "SUBJ-E003",
                "visit": "Week 8",
                "modality": ImagingModality.OCT,
                "acquisition_date": now - timedelta(days=30),
                "site_id": "SITE-101",
                "status": ImageStatus.UPLOADED,
                "upload_date": now - timedelta(days=29),
                "file_count": 128,
                "total_size_mb": 248.7,
                "series_description": "Macular cube 512x128",
                "slice_thickness_mm": 0.003,
                "contrast_used": False,
                "technologist": "Maria Chen",
            },
            # DUPIXENT photography acquisitions
            {
                "id": "ACQ-005",
                "study_id": "IMG-STUDY-003",
                "subject_id": "SUBJ-D001",
                "visit": "Baseline",
                "modality": ImagingModality.FUNDUS_PHOTO,
                "acquisition_date": now - timedelta(days=120),
                "site_id": "SITE-103",
                "status": ImageStatus.READ_COMPLETE,
                "upload_date": now - timedelta(days=119),
                "file_count": 12,
                "total_size_mb": 78.5,
                "series_description": "Standardized EASI body surface photography",
                "slice_thickness_mm": None,
                "contrast_used": False,
                "technologist": "Sarah Johnson",
            },
            {
                "id": "ACQ-006",
                "study_id": "IMG-STUDY-003",
                "subject_id": "SUBJ-D001",
                "visit": "Week 16",
                "modality": ImagingModality.FUNDUS_PHOTO,
                "acquisition_date": now - timedelta(days=8),
                "site_id": "SITE-103",
                "status": ImageStatus.QC_PASSED,
                "upload_date": now - timedelta(days=7),
                "file_count": 12,
                "total_size_mb": 81.2,
                "series_description": "Standardized EASI body surface photography",
                "slice_thickness_mm": None,
                "contrast_used": False,
                "technologist": "Sarah Johnson",
            },
            # LIBTAYO CT/MRI acquisitions
            {
                "id": "ACQ-007",
                "study_id": "IMG-STUDY-005",
                "subject_id": "SUBJ-L001",
                "visit": "Screening",
                "modality": ImagingModality.CT,
                "acquisition_date": now - timedelta(days=150),
                "site_id": "SITE-104",
                "status": ImageStatus.READ_COMPLETE,
                "upload_date": now - timedelta(days=149),
                "file_count": 450,
                "total_size_mb": 512.8,
                "series_description": "Chest/Abdomen/Pelvis with contrast",
                "slice_thickness_mm": 2.5,
                "contrast_used": True,
                "technologist": "Robert Kim",
            },
            {
                "id": "ACQ-008",
                "study_id": "IMG-STUDY-005",
                "subject_id": "SUBJ-L001",
                "visit": "Week 8",
                "modality": ImagingModality.CT,
                "acquisition_date": now - timedelta(days=94),
                "site_id": "SITE-104",
                "status": ImageStatus.READ_COMPLETE,
                "upload_date": now - timedelta(days=93),
                "file_count": 465,
                "total_size_mb": 528.3,
                "series_description": "Chest/Abdomen/Pelvis with contrast",
                "slice_thickness_mm": 2.5,
                "contrast_used": True,
                "technologist": "Robert Kim",
            },
            {
                "id": "ACQ-009",
                "study_id": "IMG-STUDY-005",
                "subject_id": "SUBJ-L002",
                "visit": "Screening",
                "modality": ImagingModality.MRI,
                "acquisition_date": now - timedelta(days=140),
                "site_id": "SITE-105",
                "status": ImageStatus.READ_COMPLETE,
                "upload_date": now - timedelta(days=139),
                "file_count": 320,
                "total_size_mb": 384.5,
                "series_description": "Brain MRI with gadolinium",
                "slice_thickness_mm": 1.0,
                "contrast_used": True,
                "technologist": "Emily Davis",
            },
            {
                "id": "ACQ-010",
                "study_id": "IMG-STUDY-005",
                "subject_id": "SUBJ-L003",
                "visit": "Week 16",
                "modality": ImagingModality.CT,
                "acquisition_date": now - timedelta(days=14),
                "site_id": "SITE-106",
                "status": ImageStatus.QC_FAILED,
                "upload_date": now - timedelta(days=13),
                "file_count": 380,
                "total_size_mb": 445.1,
                "series_description": "Chest/Abdomen/Pelvis with contrast",
                "slice_thickness_mm": 5.0,
                "contrast_used": True,
                "technologist": "Michael Brown",
            },
            {
                "id": "ACQ-011",
                "study_id": "IMG-STUDY-005",
                "subject_id": "SUBJ-L004",
                "visit": "Week 8",
                "modality": ImagingModality.CT,
                "acquisition_date": now - timedelta(days=45),
                "site_id": "SITE-104",
                "status": ImageStatus.ASSIGNED,
                "upload_date": now - timedelta(days=44),
                "file_count": 470,
                "total_size_mb": 535.2,
                "series_description": "Chest/Abdomen/Pelvis with contrast",
                "slice_thickness_mm": 2.5,
                "contrast_used": True,
                "technologist": "Robert Kim",
            },
            {
                "id": "ACQ-012",
                "study_id": "IMG-STUDY-006",
                "subject_id": "SUBJ-L005",
                "visit": "Screening",
                "modality": ImagingModality.MRI,
                "acquisition_date": now - timedelta(days=100),
                "site_id": "SITE-105",
                "status": ImageStatus.READ_COMPLETE,
                "upload_date": now - timedelta(days=99),
                "file_count": 280,
                "total_size_mb": 342.6,
                "series_description": "Brain MRI T1 post-gad and FLAIR",
                "slice_thickness_mm": 1.0,
                "contrast_used": True,
                "technologist": "Emily Davis",
            },
            {
                "id": "ACQ-013",
                "study_id": "IMG-STUDY-003",
                "subject_id": "SUBJ-D002",
                "visit": "Baseline",
                "modality": ImagingModality.FUNDUS_PHOTO,
                "acquisition_date": now - timedelta(days=60),
                "site_id": "SITE-103",
                "status": ImageStatus.PENDING_UPLOAD,
                "upload_date": None,
                "file_count": 0,
                "total_size_mb": 0,
                "series_description": "Standardized EASI body surface photography",
                "slice_thickness_mm": None,
                "contrast_used": False,
                "technologist": "Sarah Johnson",
            },
            {
                "id": "ACQ-014",
                "study_id": "IMG-STUDY-007",
                "subject_id": "SUBJ-L006",
                "visit": "Screening",
                "modality": ImagingModality.PET_CT,
                "acquisition_date": now - timedelta(days=70),
                "site_id": "SITE-106",
                "status": ImageStatus.QUERY_RAISED,
                "upload_date": now - timedelta(days=69),
                "file_count": 600,
                "total_size_mb": 780.3,
                "series_description": "Whole body FDG PET-CT",
                "slice_thickness_mm": 3.0,
                "contrast_used": True,
                "technologist": "Michael Brown",
            },
        ]

        for a in acquisitions_data:
            self._acquisitions[a["id"]] = ImageAcquisition(**a)

        # --- Central Readers ---
        readers_data = [
            {
                "id": "RDR-001",
                "name": "Dr. Elizabeth Warren",
                "specialty": "Neuroradiology",
                "institution": "Johns Hopkins Radiology",
                "qualification_status": QualificationStatus.QUALIFIED,
                "qualified_modalities": [ImagingModality.MRI, ImagingModality.CT],
                "qualified_criteria": [AssessmentCriteria.RECIST_1_1, AssessmentCriteria.RANO],
                "training_completed_date": now - timedelta(days=500),
                "cases_read": 342,
                "agreement_rate": 94.2,
                "active": True,
            },
            {
                "id": "RDR-002",
                "name": "Dr. Michael Torres",
                "specialty": "Oncologic Radiology",
                "institution": "MD Anderson Imaging",
                "qualification_status": QualificationStatus.QUALIFIED,
                "qualified_modalities": [ImagingModality.CT, ImagingModality.PET_CT],
                "qualified_criteria": [AssessmentCriteria.RECIST_1_1, AssessmentCriteria.LUGANO],
                "training_completed_date": now - timedelta(days=400),
                "cases_read": 289,
                "agreement_rate": 91.8,
                "active": True,
            },
            {
                "id": "RDR-003",
                "name": "Dr. Sarah Kim",
                "specialty": "Retinal Imaging",
                "institution": "Bascom Palmer Eye Institute",
                "qualification_status": QualificationStatus.QUALIFIED,
                "qualified_modalities": [ImagingModality.OCT, ImagingModality.FUNDUS_PHOTO],
                "qualified_criteria": [AssessmentCriteria.ETDRS],
                "training_completed_date": now - timedelta(days=600),
                "cases_read": 518,
                "agreement_rate": 96.5,
                "active": True,
            },
            {
                "id": "RDR-004",
                "name": "Dr. Raj Patel",
                "specialty": "Musculoskeletal Radiology",
                "institution": "Hospital for Special Surgery",
                "qualification_status": QualificationStatus.QUALIFIED,
                "qualified_modalities": [ImagingModality.MRI, ImagingModality.CT, ImagingModality.DEXA],
                "qualified_criteria": [AssessmentCriteria.RECIST_1_1],
                "training_completed_date": now - timedelta(days=350),
                "cases_read": 195,
                "agreement_rate": 89.7,
                "active": True,
            },
            {
                "id": "RDR-005",
                "name": "Dr. Anna Petrov",
                "specialty": "Dermatologic Imaging",
                "institution": "Cleveland Clinic Dermatology",
                "qualification_status": QualificationStatus.QUALIFIED,
                "qualified_modalities": [ImagingModality.FUNDUS_PHOTO],
                "qualified_criteria": [AssessmentCriteria.EASI],
                "training_completed_date": now - timedelta(days=450),
                "cases_read": 410,
                "agreement_rate": 93.1,
                "active": True,
            },
            {
                "id": "RDR-006",
                "name": "Dr. James Liu",
                "specialty": "Nuclear Medicine",
                "institution": "Memorial Sloan Kettering",
                "qualification_status": QualificationStatus.PROVISIONALLY_QUALIFIED,
                "qualified_modalities": [ImagingModality.PET_CT],
                "qualified_criteria": [AssessmentCriteria.LUGANO],
                "training_completed_date": now - timedelta(days=60),
                "cases_read": 45,
                "agreement_rate": 87.5,
                "active": True,
            },
            {
                "id": "RDR-007",
                "name": "Dr. Karen Smith",
                "specialty": "Retinal Imaging",
                "institution": "Wills Eye Hospital",
                "qualification_status": QualificationStatus.IN_TRAINING,
                "qualified_modalities": [ImagingModality.OCT],
                "qualified_criteria": [],
                "training_completed_date": None,
                "cases_read": 12,
                "agreement_rate": None,
                "active": True,
            },
            {
                "id": "RDR-008",
                "name": "Dr. David Park",
                "specialty": "Thoracic Radiology",
                "institution": "Brigham and Women's Hospital",
                "qualification_status": QualificationStatus.QUALIFIED,
                "qualified_modalities": [ImagingModality.CT, ImagingModality.MRI],
                "qualified_criteria": [AssessmentCriteria.RECIST_1_1, AssessmentCriteria.IRECIST],
                "training_completed_date": now - timedelta(days=300),
                "cases_read": 267,
                "agreement_rate": 92.4,
                "active": True,
            },
            {
                "id": "RDR-009",
                "name": "Dr. Catherine Lee",
                "specialty": "Oncologic Radiology",
                "institution": "Dana-Farber Cancer Institute",
                "qualification_status": QualificationStatus.REQUALIFICATION_DUE,
                "qualified_modalities": [ImagingModality.CT, ImagingModality.MRI],
                "qualified_criteria": [AssessmentCriteria.RECIST_1_1],
                "training_completed_date": now - timedelta(days=730),
                "cases_read": 156,
                "agreement_rate": 88.3,
                "active": True,
            },
            {
                "id": "RDR-010",
                "name": "Dr. Thomas Wright",
                "specialty": "Neuroradiology",
                "institution": "UCSF Radiology",
                "qualification_status": QualificationStatus.DISQUALIFIED,
                "qualified_modalities": [ImagingModality.MRI],
                "qualified_criteria": [AssessmentCriteria.RANO],
                "training_completed_date": now - timedelta(days=800),
                "cases_read": 78,
                "agreement_rate": 72.1,
                "active": False,
            },
            {
                "id": "RDR-011",
                "name": "Dr. Lisa Chen",
                "specialty": "Dermatologic Imaging",
                "institution": "Stanford Dermatology",
                "qualification_status": QualificationStatus.QUALIFIED,
                "qualified_modalities": [ImagingModality.FUNDUS_PHOTO],
                "qualified_criteria": [AssessmentCriteria.EASI, AssessmentCriteria.CUSTOM],
                "training_completed_date": now - timedelta(days=380),
                "cases_read": 325,
                "agreement_rate": 95.0,
                "active": True,
            },
        ]

        for r in readers_data:
            self._readers[r["id"]] = CentralReader(**r)

        # --- Disease Assessments ---
        assessments_data = [
            # EYLEA ETDRS assessments
            {
                "id": "DA-001",
                "acquisition_id": "ACQ-001",
                "reader_id": "RDR-003",
                "assessment_criteria": AssessmentCriteria.ETDRS,
                "timepoint": "Screening",
                "target_lesion_count": 0,
                "target_lesion_sum_mm": None,
                "non_target_status": None,
                "new_lesions": False,
                "overall_response": None,
                "best_overall_response": None,
                "percent_change_from_baseline": None,
                "percent_change_from_nadir": None,
                "assessment_date": now - timedelta(days=85),
                "comments": "Baseline OCT: CRT 385 um, subretinal fluid present. ETDRS letter score 62.",
            },
            {
                "id": "DA-002",
                "acquisition_id": "ACQ-005",
                "reader_id": "RDR-005",
                "assessment_criteria": AssessmentCriteria.EASI,
                "timepoint": "Baseline",
                "target_lesion_count": 0,
                "target_lesion_sum_mm": None,
                "non_target_status": None,
                "new_lesions": False,
                "overall_response": None,
                "best_overall_response": None,
                "percent_change_from_baseline": None,
                "percent_change_from_nadir": None,
                "assessment_date": now - timedelta(days=115),
                "comments": "Baseline EASI score: 28.4. Moderate-to-severe involvement of trunk and extremities.",
            },
            # LIBTAYO RECIST assessments
            {
                "id": "DA-003",
                "acquisition_id": "ACQ-007",
                "reader_id": "RDR-001",
                "assessment_criteria": AssessmentCriteria.RECIST_1_1,
                "timepoint": "Screening",
                "target_lesion_count": 3,
                "target_lesion_sum_mm": 85.2,
                "non_target_status": "present",
                "new_lesions": False,
                "overall_response": None,
                "best_overall_response": None,
                "percent_change_from_baseline": 0.0,
                "percent_change_from_nadir": 0.0,
                "assessment_date": now - timedelta(days=145),
                "comments": "Baseline: 3 target lesions (lung 42mm, liver 28mm, lymph node 15.2mm).",
            },
            {
                "id": "DA-004",
                "acquisition_id": "ACQ-008",
                "reader_id": "RDR-001",
                "assessment_criteria": AssessmentCriteria.RECIST_1_1,
                "timepoint": "Week 8",
                "target_lesion_count": 3,
                "target_lesion_sum_mm": 62.4,
                "non_target_status": "present",
                "new_lesions": False,
                "overall_response": OverallResponse.PARTIAL_RESPONSE,
                "best_overall_response": OverallResponse.PARTIAL_RESPONSE,
                "percent_change_from_baseline": -26.8,
                "percent_change_from_nadir": -26.8,
                "assessment_date": now - timedelta(days=89),
                "comments": "PR confirmed. Target lesion sum decreased from 85.2mm to 62.4mm (-26.8%).",
            },
            {
                "id": "DA-005",
                "acquisition_id": "ACQ-008",
                "reader_id": "RDR-002",
                "assessment_criteria": AssessmentCriteria.RECIST_1_1,
                "timepoint": "Week 8",
                "target_lesion_count": 3,
                "target_lesion_sum_mm": 64.1,
                "non_target_status": "present",
                "new_lesions": False,
                "overall_response": OverallResponse.PARTIAL_RESPONSE,
                "best_overall_response": OverallResponse.PARTIAL_RESPONSE,
                "percent_change_from_baseline": -24.8,
                "percent_change_from_nadir": -24.8,
                "assessment_date": now - timedelta(days=88),
                "comments": "Reader 2 agrees: PR. Target sum 64.1mm (-24.8% from baseline).",
            },
            {
                "id": "DA-006",
                "acquisition_id": "ACQ-009",
                "reader_id": "RDR-001",
                "assessment_criteria": AssessmentCriteria.RANO,
                "timepoint": "Screening",
                "target_lesion_count": 2,
                "target_lesion_sum_mm": 45.0,
                "non_target_status": "present",
                "new_lesions": False,
                "overall_response": None,
                "best_overall_response": None,
                "percent_change_from_baseline": 0.0,
                "percent_change_from_nadir": 0.0,
                "assessment_date": now - timedelta(days=135),
                "comments": "RANO baseline: 2 enhancing lesions (30mm x 25mm, 15mm x 12mm).",
            },
            {
                "id": "DA-007",
                "acquisition_id": "ACQ-012",
                "reader_id": "RDR-001",
                "assessment_criteria": AssessmentCriteria.RANO,
                "timepoint": "Screening",
                "target_lesion_count": 1,
                "target_lesion_sum_mm": 22.5,
                "non_target_status": None,
                "new_lesions": False,
                "overall_response": None,
                "best_overall_response": None,
                "percent_change_from_baseline": 0.0,
                "percent_change_from_nadir": 0.0,
                "assessment_date": now - timedelta(days=95),
                "comments": "Single enhancing brain lesion, 22.5mm bidimensional product.",
            },
            {
                "id": "DA-008",
                "acquisition_id": "ACQ-007",
                "reader_id": "RDR-008",
                "assessment_criteria": AssessmentCriteria.RECIST_1_1,
                "timepoint": "Screening",
                "target_lesion_count": 3,
                "target_lesion_sum_mm": 84.0,
                "non_target_status": "present",
                "new_lesions": False,
                "overall_response": None,
                "best_overall_response": None,
                "percent_change_from_baseline": 0.0,
                "percent_change_from_nadir": 0.0,
                "assessment_date": now - timedelta(days=144),
                "comments": "Reader 2 baseline: 3 target lesions sum 84.0mm.",
            },
            {
                "id": "DA-009",
                "acquisition_id": "ACQ-005",
                "reader_id": "RDR-011",
                "assessment_criteria": AssessmentCriteria.EASI,
                "timepoint": "Baseline",
                "target_lesion_count": 0,
                "target_lesion_sum_mm": None,
                "non_target_status": None,
                "new_lesions": False,
                "overall_response": None,
                "best_overall_response": None,
                "percent_change_from_baseline": None,
                "percent_change_from_nadir": None,
                "assessment_date": now - timedelta(days=114),
                "comments": "Reader 2 baseline EASI: 27.8. Consistent with reader 1 assessment.",
            },
            {
                "id": "DA-010",
                "acquisition_id": "ACQ-008",
                "reader_id": "RDR-004",
                "assessment_criteria": AssessmentCriteria.RECIST_1_1,
                "timepoint": "Week 8",
                "target_lesion_count": 3,
                "target_lesion_sum_mm": 50.1,
                "non_target_status": "absent",
                "new_lesions": False,
                "overall_response": OverallResponse.PARTIAL_RESPONSE,
                "best_overall_response": OverallResponse.PARTIAL_RESPONSE,
                "percent_change_from_baseline": -41.2,
                "percent_change_from_nadir": -41.2,
                "assessment_date": now - timedelta(days=87),
                "comments": "Adjudicator read: deep PR. Sum 50.1mm (-41.2%).",
            },
            {
                "id": "DA-011",
                "acquisition_id": "ACQ-014",
                "reader_id": "RDR-002",
                "assessment_criteria": AssessmentCriteria.LUGANO,
                "timepoint": "Screening",
                "target_lesion_count": 4,
                "target_lesion_sum_mm": 120.0,
                "non_target_status": "present",
                "new_lesions": False,
                "overall_response": None,
                "best_overall_response": None,
                "percent_change_from_baseline": 0.0,
                "percent_change_from_nadir": 0.0,
                "assessment_date": now - timedelta(days=65),
                "comments": "Lugano baseline: 4 measurable lesions, SPD 120.0.",
            },
            {
                "id": "DA-012",
                "acquisition_id": "ACQ-001",
                "reader_id": "RDR-003",
                "assessment_criteria": AssessmentCriteria.ETDRS,
                "timepoint": "Screening",
                "target_lesion_count": 0,
                "target_lesion_sum_mm": None,
                "non_target_status": None,
                "new_lesions": False,
                "overall_response": OverallResponse.STABLE_DISEASE,
                "best_overall_response": OverallResponse.STABLE_DISEASE,
                "percent_change_from_baseline": 0.0,
                "percent_change_from_nadir": 0.0,
                "assessment_date": now - timedelta(days=84),
                "comments": "Follow-up read confirming baseline characteristics.",
            },
        ]

        for a in assessments_data:
            self._assessments[a["id"]] = DiseaseAssessment(**a)

        # --- Image Quality Reviews ---
        qc_data = [
            {
                "id": "QC-001",
                "acquisition_id": "ACQ-001",
                "reviewer": "QC Technician A",
                "review_date": now - timedelta(days=88),
                "outcome": QCOutcome.PASS,
                "issues": [],
                "protocol_compliant": True,
                "resolution_adequate": True,
                "coverage_adequate": True,
                "action_required": None,
            },
            {
                "id": "QC-002",
                "acquisition_id": "ACQ-002",
                "reviewer": "QC Technician A",
                "review_date": now - timedelta(days=60),
                "outcome": QCOutcome.PASS,
                "issues": [],
                "protocol_compliant": True,
                "resolution_adequate": True,
                "coverage_adequate": True,
                "action_required": None,
            },
            {
                "id": "QC-003",
                "acquisition_id": "ACQ-003",
                "reviewer": "QC Technician B",
                "review_date": now - timedelta(days=83),
                "outcome": QCOutcome.MINOR_DEVIATION,
                "issues": ["Slight motion artifact in field 3"],
                "protocol_compliant": True,
                "resolution_adequate": True,
                "coverage_adequate": True,
                "action_required": "Note in reader instructions; acceptable for grading.",
            },
            {
                "id": "QC-004",
                "acquisition_id": "ACQ-005",
                "reviewer": "QC Technician C",
                "review_date": now - timedelta(days=118),
                "outcome": QCOutcome.PASS,
                "issues": [],
                "protocol_compliant": True,
                "resolution_adequate": True,
                "coverage_adequate": True,
                "action_required": None,
            },
            {
                "id": "QC-005",
                "acquisition_id": "ACQ-006",
                "reviewer": "QC Technician C",
                "review_date": now - timedelta(days=6),
                "outcome": QCOutcome.PASS,
                "issues": [],
                "protocol_compliant": True,
                "resolution_adequate": True,
                "coverage_adequate": True,
                "action_required": None,
            },
            {
                "id": "QC-006",
                "acquisition_id": "ACQ-007",
                "reviewer": "QC Technician D",
                "review_date": now - timedelta(days=148),
                "outcome": QCOutcome.PASS,
                "issues": [],
                "protocol_compliant": True,
                "resolution_adequate": True,
                "coverage_adequate": True,
                "action_required": None,
            },
            {
                "id": "QC-007",
                "acquisition_id": "ACQ-008",
                "reviewer": "QC Technician D",
                "review_date": now - timedelta(days=92),
                "outcome": QCOutcome.MINOR_DEVIATION,
                "issues": ["Breathing artifact on lower lung fields"],
                "protocol_compliant": True,
                "resolution_adequate": True,
                "coverage_adequate": True,
                "action_required": "Acceptable for target lesion assessment.",
            },
            {
                "id": "QC-008",
                "acquisition_id": "ACQ-009",
                "reviewer": "QC Technician D",
                "review_date": now - timedelta(days=138),
                "outcome": QCOutcome.PASS,
                "issues": [],
                "protocol_compliant": True,
                "resolution_adequate": True,
                "coverage_adequate": True,
                "action_required": None,
            },
            {
                "id": "QC-009",
                "acquisition_id": "ACQ-010",
                "reviewer": "QC Technician D",
                "review_date": now - timedelta(days=12),
                "outcome": QCOutcome.FAIL,
                "issues": [
                    "Slice thickness 5mm exceeds protocol maximum 3mm",
                    "Inadequate contrast timing for portal venous phase",
                ],
                "protocol_compliant": False,
                "resolution_adequate": False,
                "coverage_adequate": True,
                "action_required": "Rescan required with correct slice thickness and contrast timing.",
            },
            {
                "id": "QC-010",
                "acquisition_id": "ACQ-012",
                "reviewer": "QC Technician D",
                "review_date": now - timedelta(days=98),
                "outcome": QCOutcome.PASS,
                "issues": [],
                "protocol_compliant": True,
                "resolution_adequate": True,
                "coverage_adequate": True,
                "action_required": None,
            },
            {
                "id": "QC-011",
                "acquisition_id": "ACQ-014",
                "reviewer": "QC Technician E",
                "review_date": now - timedelta(days=68),
                "outcome": QCOutcome.MAJOR_DEVIATION,
                "issues": ["SUV calibration outside acceptable range", "Missing attenuation correction series"],
                "protocol_compliant": False,
                "resolution_adequate": True,
                "coverage_adequate": True,
                "action_required": "Recalibration required. Query raised to site.",
            },
            {
                "id": "QC-012",
                "acquisition_id": "ACQ-011",
                "reviewer": "QC Technician D",
                "review_date": now - timedelta(days=43),
                "outcome": QCOutcome.PASS,
                "issues": [],
                "protocol_compliant": True,
                "resolution_adequate": True,
                "coverage_adequate": True,
                "action_required": None,
            },
            {
                "id": "QC-013",
                "acquisition_id": "ACQ-004",
                "reviewer": "QC Technician A",
                "review_date": now - timedelta(days=28),
                "outcome": QCOutcome.RESCAN_REQUIRED,
                "issues": ["Significant signal loss in foveal region", "Incomplete macular coverage"],
                "protocol_compliant": False,
                "resolution_adequate": False,
                "coverage_adequate": False,
                "action_required": "Rescan required with proper alignment and full macular coverage.",
            },
        ]

        for q in qc_data:
            self._qc_reviews[q["id"]] = ImageQualityReview(**q)

    # ------------------------------------------------------------------
    # Imaging Study CRUD
    # ------------------------------------------------------------------

    def list_studies(
        self,
        *,
        trial_id: str | None = None,
        modality: ImagingModality | None = None,
        criteria: AssessmentCriteria | None = None,
    ) -> list[ImagingStudy]:
        """List imaging studies with optional filters."""
        with self._lock:
            result = list(self._studies.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if modality is not None:
            result = [s for s in result if modality in s.modalities]
        if criteria is not None:
            result = [s for s in result if s.assessment_criteria == criteria]

        return sorted(result, key=lambda s: s.id)

    def get_study(self, study_id: str) -> ImagingStudy | None:
        """Get a single imaging study by ID."""
        with self._lock:
            return self._studies.get(study_id)

    def create_study(self, payload: ImagingStudyCreate) -> ImagingStudy:
        """Create a new imaging study."""
        study_id = f"IMG-STUDY-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        study = ImagingStudy(
            id=study_id,
            trial_id=payload.trial_id,
            title=payload.title,
            modalities=payload.modalities,
            assessment_criteria=payload.assessment_criteria,
            reading_design=payload.reading_design,
            blinded=payload.blinded,
            assessment_schedule=payload.assessment_schedule,
            total_subjects=0,
            charter_version=payload.charter_version,
            vendor=payload.vendor,
            status="active",
            created_at=now,
        )
        with self._lock:
            self._studies[study_id] = study
        logger.info("Created imaging study %s: %s", study_id, payload.title)
        return study

    def update_study(self, study_id: str, payload: ImagingStudyUpdate) -> ImagingStudy | None:
        """Update an existing imaging study."""
        with self._lock:
            existing = self._studies.get(study_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ImagingStudy(**data)
            self._studies[study_id] = updated
        return updated

    def delete_study(self, study_id: str) -> bool:
        """Delete an imaging study. Returns True if deleted."""
        with self._lock:
            if study_id in self._studies:
                del self._studies[study_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Image Acquisition CRUD
    # ------------------------------------------------------------------

    def list_acquisitions(
        self,
        *,
        study_id: str | None = None,
        modality: ImagingModality | None = None,
        status: ImageStatus | None = None,
    ) -> list[ImageAcquisition]:
        """List image acquisitions with optional filters."""
        with self._lock:
            result = list(self._acquisitions.values())

        if study_id is not None:
            result = [a for a in result if a.study_id == study_id]
        if modality is not None:
            result = [a for a in result if a.modality == modality]
        if status is not None:
            result = [a for a in result if a.status == status]

        return sorted(result, key=lambda a: a.id)

    def get_acquisition(self, acquisition_id: str) -> ImageAcquisition | None:
        """Get a single image acquisition by ID."""
        with self._lock:
            return self._acquisitions.get(acquisition_id)

    def create_acquisition(self, payload: ImageAcquisitionCreate) -> ImageAcquisition:
        """Create a new image acquisition."""
        acq_id = f"ACQ-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        acq = ImageAcquisition(
            id=acq_id,
            study_id=payload.study_id,
            subject_id=payload.subject_id,
            visit=payload.visit,
            modality=payload.modality,
            acquisition_date=now,
            site_id=payload.site_id,
            status=ImageStatus.PENDING_UPLOAD,
            upload_date=None,
            file_count=0,
            total_size_mb=0,
            series_description=payload.series_description,
            slice_thickness_mm=payload.slice_thickness_mm,
            contrast_used=payload.contrast_used,
            technologist=payload.technologist,
        )
        with self._lock:
            self._acquisitions[acq_id] = acq
        logger.info("Created image acquisition %s for study %s", acq_id, payload.study_id)
        return acq

    def update_acquisition(self, acquisition_id: str, payload: ImageAcquisitionUpdate) -> ImageAcquisition | None:
        """Update an existing image acquisition."""
        with self._lock:
            existing = self._acquisitions.get(acquisition_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set upload_date when status changes to uploaded
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = ImageStatus(new_status)
                if new_status == ImageStatus.UPLOADED and existing.status == ImageStatus.PENDING_UPLOAD:
                    data["upload_date"] = datetime.now(timezone.utc)
            data.update(updates)
            updated = ImageAcquisition(**data)
            self._acquisitions[acquisition_id] = updated
        return updated

    def delete_acquisition(self, acquisition_id: str) -> bool:
        """Delete an image acquisition. Returns True if deleted."""
        with self._lock:
            if acquisition_id in self._acquisitions:
                del self._acquisitions[acquisition_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Central Reader CRUD
    # ------------------------------------------------------------------

    def list_readers(
        self,
        *,
        qualification_status: QualificationStatus | None = None,
        modality: ImagingModality | None = None,
    ) -> list[CentralReader]:
        """List central readers with optional filters."""
        with self._lock:
            result = list(self._readers.values())

        if qualification_status is not None:
            result = [r for r in result if r.qualification_status == qualification_status]
        if modality is not None:
            result = [r for r in result if modality in r.qualified_modalities]

        return sorted(result, key=lambda r: r.id)

    def get_reader(self, reader_id: str) -> CentralReader | None:
        """Get a single central reader by ID."""
        with self._lock:
            return self._readers.get(reader_id)

    def create_reader(self, payload: CentralReaderCreate) -> CentralReader:
        """Create a new central reader."""
        reader_id = f"RDR-{uuid4().hex[:8].upper()}"
        reader = CentralReader(
            id=reader_id,
            name=payload.name,
            specialty=payload.specialty,
            institution=payload.institution,
            qualification_status=QualificationStatus.IN_TRAINING,
            qualified_modalities=payload.qualified_modalities,
            qualified_criteria=payload.qualified_criteria,
            training_completed_date=None,
            cases_read=0,
            agreement_rate=None,
            active=True,
        )
        with self._lock:
            self._readers[reader_id] = reader
        logger.info("Created central reader %s: %s", reader_id, payload.name)
        return reader

    def update_reader(self, reader_id: str, payload: CentralReaderUpdate) -> CentralReader | None:
        """Update an existing central reader."""
        with self._lock:
            existing = self._readers.get(reader_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set training_completed_date when qualified
            if "qualification_status" in updates:
                new_status = updates["qualification_status"]
                if isinstance(new_status, str):
                    new_status = QualificationStatus(new_status)
                if new_status == QualificationStatus.QUALIFIED and existing.training_completed_date is None:
                    data["training_completed_date"] = datetime.now(timezone.utc)
            data.update(updates)
            updated = CentralReader(**data)
            self._readers[reader_id] = updated
        return updated

    def delete_reader(self, reader_id: str) -> bool:
        """Delete a central reader. Returns True if deleted."""
        with self._lock:
            if reader_id in self._readers:
                del self._readers[reader_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Disease Assessment CRUD
    # ------------------------------------------------------------------

    def list_assessments(
        self,
        *,
        acquisition_id: str | None = None,
        reader_id: str | None = None,
        criteria: AssessmentCriteria | None = None,
    ) -> list[DiseaseAssessment]:
        """List disease assessments with optional filters."""
        with self._lock:
            result = list(self._assessments.values())

        if acquisition_id is not None:
            result = [a for a in result if a.acquisition_id == acquisition_id]
        if reader_id is not None:
            result = [a for a in result if a.reader_id == reader_id]
        if criteria is not None:
            result = [a for a in result if a.assessment_criteria == criteria]

        return sorted(result, key=lambda a: a.id)

    def get_assessment(self, assessment_id: str) -> DiseaseAssessment | None:
        """Get a single disease assessment by ID."""
        with self._lock:
            return self._assessments.get(assessment_id)

    def create_assessment(self, payload: DiseaseAssessmentCreate) -> DiseaseAssessment:
        """Create a new disease assessment."""
        assessment_id = f"DA-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        assessment = DiseaseAssessment(
            id=assessment_id,
            acquisition_id=payload.acquisition_id,
            reader_id=payload.reader_id,
            assessment_criteria=payload.assessment_criteria,
            timepoint=payload.timepoint,
            target_lesion_count=payload.target_lesion_count,
            target_lesion_sum_mm=payload.target_lesion_sum_mm,
            non_target_status=payload.non_target_status,
            new_lesions=payload.new_lesions,
            overall_response=payload.overall_response,
            best_overall_response=payload.overall_response,
            percent_change_from_baseline=payload.percent_change_from_baseline,
            percent_change_from_nadir=payload.percent_change_from_nadir,
            assessment_date=now,
            comments=payload.comments,
        )
        with self._lock:
            self._assessments[assessment_id] = assessment
        logger.info("Created disease assessment %s for acquisition %s", assessment_id, payload.acquisition_id)
        return assessment

    def delete_assessment(self, assessment_id: str) -> bool:
        """Delete a disease assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._assessments:
                del self._assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Image Quality Review CRUD
    # ------------------------------------------------------------------

    def list_qc_reviews(
        self,
        *,
        acquisition_id: str | None = None,
        outcome: QCOutcome | None = None,
    ) -> list[ImageQualityReview]:
        """List image quality reviews with optional filters."""
        with self._lock:
            result = list(self._qc_reviews.values())

        if acquisition_id is not None:
            result = [q for q in result if q.acquisition_id == acquisition_id]
        if outcome is not None:
            result = [q for q in result if q.outcome == outcome]

        return sorted(result, key=lambda q: q.id)

    def get_qc_review(self, qc_id: str) -> ImageQualityReview | None:
        """Get a single image quality review by ID."""
        with self._lock:
            return self._qc_reviews.get(qc_id)

    def create_qc_review(self, payload: ImageQualityReviewCreate) -> ImageQualityReview:
        """Create a new image quality review."""
        qc_id = f"QC-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        qc = ImageQualityReview(
            id=qc_id,
            acquisition_id=payload.acquisition_id,
            reviewer=payload.reviewer,
            review_date=now,
            outcome=payload.outcome,
            issues=payload.issues,
            protocol_compliant=payload.protocol_compliant,
            resolution_adequate=payload.resolution_adequate,
            coverage_adequate=payload.coverage_adequate,
            action_required=payload.action_required,
        )
        with self._lock:
            self._qc_reviews[qc_id] = qc
        logger.info("Created QC review %s for acquisition %s: %s", qc_id, payload.acquisition_id, payload.outcome.value)
        return qc

    def delete_qc_review(self, qc_id: str) -> bool:
        """Delete an image quality review. Returns True if deleted."""
        with self._lock:
            if qc_id in self._qc_reviews:
                del self._qc_reviews[qc_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ImagingManagementMetrics:
        """Compute aggregated imaging management metrics."""
        with self._lock:
            studies = list(self._studies.values())
            acquisitions = list(self._acquisitions.values())
            readers = list(self._readers.values())
            assessments = list(self._assessments.values())
            qc_reviews = list(self._qc_reviews.values())

        # Acquisitions by status
        acq_by_status: dict[str, int] = {}
        for a in acquisitions:
            key = a.status.value
            acq_by_status[key] = acq_by_status.get(key, 0) + 1

        # Acquisitions by modality
        acq_by_modality: dict[str, int] = {}
        for a in acquisitions:
            key = a.modality.value
            acq_by_modality[key] = acq_by_modality.get(key, 0) + 1

        # Reader stats
        qualified_readers = sum(
            1 for r in readers
            if r.qualification_status == QualificationStatus.QUALIFIED
        )
        readers_by_status: dict[str, int] = {}
        for r in readers:
            key = r.qualification_status.value
            readers_by_status[key] = readers_by_status.get(key, 0) + 1

        # Assessments by response
        assessments_by_response: dict[str, int] = {}
        for a in assessments:
            if a.overall_response is not None:
                key = a.overall_response.value
                assessments_by_response[key] = assessments_by_response.get(key, 0) + 1

        # QC stats
        qc_by_outcome: dict[str, int] = {}
        for q in qc_reviews:
            key = q.outcome.value
            qc_by_outcome[key] = qc_by_outcome.get(key, 0) + 1

        # QC pass rate: (pass + minor_deviation) / total * 100
        total_qc = len(qc_reviews)
        passing = sum(
            1 for q in qc_reviews
            if q.outcome in (QCOutcome.PASS, QCOutcome.MINOR_DEVIATION)
        )
        qc_pass_rate = round((passing / total_qc * 100) if total_qc > 0 else 0.0, 1)

        # Average reader agreement rate (from readers with agreement_rate set)
        agreement_rates = [r.agreement_rate for r in readers if r.agreement_rate is not None]
        avg_agreement = round(
            (sum(agreement_rates) / len(agreement_rates)) if agreement_rates else 0.0, 1
        )

        return ImagingManagementMetrics(
            total_studies=len(studies),
            total_acquisitions=len(acquisitions),
            acquisitions_by_status=acq_by_status,
            acquisitions_by_modality=acq_by_modality,
            total_readers=len(readers),
            qualified_readers=qualified_readers,
            readers_by_status=readers_by_status,
            total_assessments=len(assessments),
            assessments_by_response=assessments_by_response,
            total_qc_reviews=len(qc_reviews),
            qc_by_outcome=qc_by_outcome,
            qc_pass_rate=qc_pass_rate,
            avg_reader_agreement_rate=avg_agreement,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ImagingManagementService | None = None
_instance_lock = threading.Lock()


def get_imaging_management_service() -> ImagingManagementService:
    """Return the singleton ImagingManagementService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ImagingManagementService()
    return _instance


def reset_imaging_management_service() -> ImagingManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ImagingManagementService()
    return _instance
