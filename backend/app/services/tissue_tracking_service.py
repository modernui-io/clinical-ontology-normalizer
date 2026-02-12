"""Tissue Tracking Management Service (TISSUE-TRK).

Manages tissue specimen operations: tissue collection tracking, FFPE block
management, slide preparation, pathology review workflow, tissue shipment
tracking, and tissue tracking operational metrics.

Usage:
    from app.services.tissue_tracking_service import (
        get_tissue_tracking_service,
    )

    svc = get_tissue_tracking_service()
    specimens = svc.list_specimens()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.tissue_tracking import (
    FFPEBlock,
    FFPEBlockCreate,
    FFPEBlockUpdate,
    PathologyResult,
    PathologyReview,
    PathologyReviewCreate,
    PathologyReviewUpdate,
    PreservationMethod,
    SlideStatus,
    SpecimenStatus,
    TissueShipment,
    TissueShipmentCreate,
    TissueShipmentUpdate,
    TissueSlide,
    TissueSlideCreate,
    TissueSlideUpdate,
    TissueSpecimen,
    TissueSpecimenCreate,
    TissueSpecimenUpdate,
    TissueTrackingMetrics,
    TissueType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class TissueTrackingService:
    """In-memory Tissue Tracking Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._specimens: dict[str, TissueSpecimen] = {}
        self._blocks: dict[str, FFPEBlock] = {}
        self._slides: dict[str, TissueSlide] = {}
        self._reviews: dict[str, PathologyReview] = {}
        self._shipments: dict[str, TissueShipment] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic tissue tracking data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Tissue Specimens ---
        specimens_data = [
            # EYLEA trial specimens (retinal/ocular biopsies)
            {"id": "TSP-001", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1001", "site_id": "SITE-101", "tissue_type": TissueType.BIOPSY, "preservation_method": PreservationMethod.FFPE, "status": SpecimenStatus.STORED, "collection_date": now - timedelta(days=90), "body_site": "Retina", "laterality": "Left", "tumor_type": None, "specimen_weight_mg": 12.5, "block_count": 3, "sections_available": 18, "quality_score": 0.92, "ischemia_time_minutes": 8, "collected_by": "Dr. Sarah Kim", "pathologist": "Dr. James Chen", "storage_location": "Freezer-A3-Shelf2", "created_at": now - timedelta(days=90)},
            {"id": "TSP-002", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1002", "site_id": "SITE-101", "tissue_type": TissueType.FINE_NEEDLE_ASPIRATE, "preservation_method": PreservationMethod.FRESH_FROZEN, "status": SpecimenStatus.STORED, "collection_date": now - timedelta(days=85), "body_site": "Vitreous humor", "laterality": "Right", "tumor_type": None, "specimen_weight_mg": 5.2, "block_count": 1, "sections_available": 6, "quality_score": 0.88, "ischemia_time_minutes": 5, "collected_by": "Dr. Michael Torres", "pathologist": "Dr. James Chen", "storage_location": "Freezer-A3-Shelf3", "created_at": now - timedelta(days=85)},
            {"id": "TSP-003", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1003", "site_id": "SITE-102", "tissue_type": TissueType.BIOPSY, "preservation_method": PreservationMethod.FFPE, "status": SpecimenStatus.PROCESSING, "collection_date": now - timedelta(days=30), "body_site": "Choroid", "laterality": "Left", "tumor_type": None, "specimen_weight_mg": 8.7, "block_count": 2, "sections_available": 10, "quality_score": 0.85, "ischemia_time_minutes": 12, "collected_by": "Dr. Laura Patel", "pathologist": None, "storage_location": None, "created_at": now - timedelta(days=30)},
            {"id": "TSP-004", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1004", "site_id": "SITE-102", "tissue_type": TissueType.CORE_NEEDLE, "preservation_method": PreservationMethod.FFPE, "status": SpecimenStatus.IN_TRANSIT, "collection_date": now - timedelta(days=10), "body_site": "Eyelid lesion", "laterality": "Right", "tumor_type": "Squamous cell", "specimen_weight_mg": 15.3, "block_count": 0, "sections_available": 0, "quality_score": None, "ischemia_time_minutes": 6, "collected_by": "Dr. Sarah Kim", "pathologist": None, "storage_location": None, "created_at": now - timedelta(days=10)},

            # DUPIXENT trial specimens (skin biopsies for atopic dermatitis)
            {"id": "TSP-005", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2001", "site_id": "SITE-104", "tissue_type": TissueType.PUNCH, "preservation_method": PreservationMethod.FFPE, "status": SpecimenStatus.STORED, "collection_date": now - timedelta(days=100), "body_site": "Antecubital fossa", "laterality": "Left", "tumor_type": None, "specimen_weight_mg": 22.0, "block_count": 4, "sections_available": 24, "quality_score": 0.95, "ischemia_time_minutes": 3, "collected_by": "Dr. Angela Martinez", "pathologist": "Dr. Robert Williams", "storage_location": "Freezer-B1-Shelf1", "created_at": now - timedelta(days=100)},
            {"id": "TSP-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2002", "site_id": "SITE-104", "tissue_type": TissueType.PUNCH, "preservation_method": PreservationMethod.FFPE, "status": SpecimenStatus.STORED, "collection_date": now - timedelta(days=95), "body_site": "Popliteal fossa", "laterality": "Right", "tumor_type": None, "specimen_weight_mg": 18.5, "block_count": 3, "sections_available": 15, "quality_score": 0.91, "ischemia_time_minutes": 4, "collected_by": "Dr. David Nakamura", "pathologist": "Dr. Robert Williams", "storage_location": "Freezer-B1-Shelf2", "created_at": now - timedelta(days=95)},
            {"id": "TSP-007", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2003", "site_id": "SITE-105", "tissue_type": TissueType.PUNCH, "preservation_method": PreservationMethod.RNA_LATER, "status": SpecimenStatus.QUALITY_FAILED, "collection_date": now - timedelta(days=60), "body_site": "Dorsal hand", "laterality": "Right", "tumor_type": None, "specimen_weight_mg": 10.1, "block_count": 0, "sections_available": 0, "quality_score": 0.35, "ischemia_time_minutes": 25, "collected_by": "Dr. Patricia Sullivan", "pathologist": None, "storage_location": None, "created_at": now - timedelta(days=60)},
            {"id": "TSP-008", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2004", "site_id": "SITE-105", "tissue_type": TissueType.BIOPSY, "preservation_method": PreservationMethod.FFPE, "status": SpecimenStatus.RECEIVED, "collection_date": now - timedelta(days=15), "body_site": "Flexural crease", "laterality": "Left", "tumor_type": None, "specimen_weight_mg": 14.8, "block_count": 0, "sections_available": 0, "quality_score": None, "ischemia_time_minutes": 7, "collected_by": "Dr. Angela Martinez", "pathologist": None, "storage_location": None, "created_at": now - timedelta(days=15)},

            # LIBTAYO trial specimens (tumor biopsies for oncology)
            {"id": "TSP-009", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3001", "site_id": "SITE-107", "tissue_type": TissueType.CORE_NEEDLE, "preservation_method": PreservationMethod.FFPE, "status": SpecimenStatus.STORED, "collection_date": now - timedelta(days=110), "body_site": "Lung", "laterality": "Right", "tumor_type": "Non-small cell lung cancer", "specimen_weight_mg": 35.0, "block_count": 6, "sections_available": 30, "quality_score": 0.93, "ischemia_time_minutes": 10, "collected_by": "Dr. Andrew Foster", "pathologist": "Dr. Catherine Liu", "storage_location": "Freezer-C2-Shelf1", "created_at": now - timedelta(days=110)},
            {"id": "TSP-010", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3002", "site_id": "SITE-107", "tissue_type": TissueType.EXCISIONAL, "preservation_method": PreservationMethod.FFPE, "status": SpecimenStatus.STORED, "collection_date": now - timedelta(days=105), "body_site": "Cutaneous SCC", "laterality": None, "tumor_type": "Squamous cell carcinoma", "specimen_weight_mg": 120.5, "block_count": 8, "sections_available": 40, "quality_score": 0.97, "ischemia_time_minutes": 15, "collected_by": "Dr. Natalie Wong", "pathologist": "Dr. Catherine Liu", "storage_location": "Freezer-C2-Shelf2", "created_at": now - timedelta(days=105)},
            {"id": "TSP-011", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3003", "site_id": "SITE-108", "tissue_type": TissueType.CORE_NEEDLE, "preservation_method": PreservationMethod.SNAP_FROZEN, "status": SpecimenStatus.STORED, "collection_date": now - timedelta(days=80), "body_site": "Liver metastasis", "laterality": "Right", "tumor_type": "Hepatocellular carcinoma", "specimen_weight_mg": 28.3, "block_count": 4, "sections_available": 20, "quality_score": 0.89, "ischemia_time_minutes": 8, "collected_by": "Dr. Gregory Harris", "pathologist": "Dr. Catherine Liu", "storage_location": "Freezer-C3-Shelf1", "created_at": now - timedelta(days=80)},
            {"id": "TSP-012", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3004", "site_id": "SITE-108", "tissue_type": TissueType.BONE_MARROW, "preservation_method": PreservationMethod.FRESH, "status": SpecimenStatus.COLLECTED, "collection_date": now - timedelta(days=5), "body_site": "Iliac crest", "laterality": "Left", "tumor_type": "Lymphoma staging", "specimen_weight_mg": 45.0, "block_count": 0, "sections_available": 0, "quality_score": None, "ischemia_time_minutes": 2, "collected_by": "Dr. Maria Santos", "pathologist": None, "storage_location": None, "created_at": now - timedelta(days=5)},
        ]

        for s in specimens_data:
            self._specimens[s["id"]] = TissueSpecimen(**s)

        # --- 15 FFPE Blocks ---
        blocks_data = [
            {"id": "BLK-001", "specimen_id": "TSP-001", "block_identifier": "TSP-001-A1", "fixation_time_hours": 24.0, "embedding_date": now - timedelta(days=89), "sections_cut": 6, "sections_remaining": 12, "thickness_microns": 4.0, "tumor_content_pct": None, "necrosis_pct": None, "storage_location": "Block-Cabinet-A1", "temperature_c": 22.0, "quality_adequate": True, "created_at": now - timedelta(days=89)},
            {"id": "BLK-002", "specimen_id": "TSP-001", "block_identifier": "TSP-001-A2", "fixation_time_hours": 24.0, "embedding_date": now - timedelta(days=89), "sections_cut": 4, "sections_remaining": 8, "thickness_microns": 4.0, "tumor_content_pct": None, "necrosis_pct": None, "storage_location": "Block-Cabinet-A1", "temperature_c": 22.0, "quality_adequate": True, "created_at": now - timedelta(days=89)},
            {"id": "BLK-003", "specimen_id": "TSP-001", "block_identifier": "TSP-001-A3", "fixation_time_hours": 24.0, "embedding_date": now - timedelta(days=89), "sections_cut": 2, "sections_remaining": 6, "thickness_microns": 5.0, "tumor_content_pct": None, "necrosis_pct": None, "storage_location": "Block-Cabinet-A1", "temperature_c": 22.0, "quality_adequate": True, "created_at": now - timedelta(days=89)},
            {"id": "BLK-004", "specimen_id": "TSP-002", "block_identifier": "TSP-002-B1", "fixation_time_hours": None, "embedding_date": now - timedelta(days=84), "sections_cut": 3, "sections_remaining": 3, "thickness_microns": 4.0, "tumor_content_pct": None, "necrosis_pct": None, "storage_location": "Cryo-Cabinet-A2", "temperature_c": -80.0, "quality_adequate": True, "created_at": now - timedelta(days=84)},
            {"id": "BLK-005", "specimen_id": "TSP-005", "block_identifier": "TSP-005-C1", "fixation_time_hours": 18.0, "embedding_date": now - timedelta(days=99), "sections_cut": 8, "sections_remaining": 10, "thickness_microns": 4.0, "tumor_content_pct": None, "necrosis_pct": 2.0, "storage_location": "Block-Cabinet-B1", "temperature_c": 22.0, "quality_adequate": True, "created_at": now - timedelta(days=99)},
            {"id": "BLK-006", "specimen_id": "TSP-005", "block_identifier": "TSP-005-C2", "fixation_time_hours": 18.0, "embedding_date": now - timedelta(days=99), "sections_cut": 6, "sections_remaining": 8, "thickness_microns": 4.0, "tumor_content_pct": None, "necrosis_pct": 1.5, "storage_location": "Block-Cabinet-B1", "temperature_c": 22.0, "quality_adequate": True, "created_at": now - timedelta(days=99)},
            {"id": "BLK-007", "specimen_id": "TSP-006", "block_identifier": "TSP-006-D1", "fixation_time_hours": 20.0, "embedding_date": now - timedelta(days=94), "sections_cut": 5, "sections_remaining": 7, "thickness_microns": 4.0, "tumor_content_pct": None, "necrosis_pct": None, "storage_location": "Block-Cabinet-B2", "temperature_c": 22.0, "quality_adequate": True, "created_at": now - timedelta(days=94)},
            {"id": "BLK-008", "specimen_id": "TSP-006", "block_identifier": "TSP-006-D2", "fixation_time_hours": 20.0, "embedding_date": now - timedelta(days=94), "sections_cut": 4, "sections_remaining": 6, "thickness_microns": 4.0, "tumor_content_pct": None, "necrosis_pct": None, "storage_location": "Block-Cabinet-B2", "temperature_c": 22.0, "quality_adequate": True, "created_at": now - timedelta(days=94)},
            {"id": "BLK-009", "specimen_id": "TSP-009", "block_identifier": "TSP-009-E1", "fixation_time_hours": 22.0, "embedding_date": now - timedelta(days=109), "sections_cut": 10, "sections_remaining": 12, "thickness_microns": 4.0, "tumor_content_pct": 65.0, "necrosis_pct": 5.0, "storage_location": "Block-Cabinet-C1", "temperature_c": 22.0, "quality_adequate": True, "created_at": now - timedelta(days=109)},
            {"id": "BLK-010", "specimen_id": "TSP-009", "block_identifier": "TSP-009-E2", "fixation_time_hours": 22.0, "embedding_date": now - timedelta(days=109), "sections_cut": 6, "sections_remaining": 8, "thickness_microns": 4.0, "tumor_content_pct": 70.0, "necrosis_pct": 3.0, "storage_location": "Block-Cabinet-C1", "temperature_c": 22.0, "quality_adequate": True, "created_at": now - timedelta(days=109)},
            {"id": "BLK-011", "specimen_id": "TSP-010", "block_identifier": "TSP-010-F1", "fixation_time_hours": 24.0, "embedding_date": now - timedelta(days=104), "sections_cut": 12, "sections_remaining": 14, "thickness_microns": 4.0, "tumor_content_pct": 80.0, "necrosis_pct": 8.0, "storage_location": "Block-Cabinet-C2", "temperature_c": 22.0, "quality_adequate": True, "created_at": now - timedelta(days=104)},
            {"id": "BLK-012", "specimen_id": "TSP-010", "block_identifier": "TSP-010-F2", "fixation_time_hours": 24.0, "embedding_date": now - timedelta(days=104), "sections_cut": 8, "sections_remaining": 10, "thickness_microns": 4.0, "tumor_content_pct": 75.0, "necrosis_pct": 6.0, "storage_location": "Block-Cabinet-C2", "temperature_c": 22.0, "quality_adequate": True, "created_at": now - timedelta(days=104)},
            {"id": "BLK-013", "specimen_id": "TSP-011", "block_identifier": "TSP-011-G1", "fixation_time_hours": None, "embedding_date": now - timedelta(days=79), "sections_cut": 8, "sections_remaining": 10, "thickness_microns": 4.0, "tumor_content_pct": 55.0, "necrosis_pct": 10.0, "storage_location": "Cryo-Cabinet-C3", "temperature_c": -80.0, "quality_adequate": True, "created_at": now - timedelta(days=79)},
            {"id": "BLK-014", "specimen_id": "TSP-011", "block_identifier": "TSP-011-G2", "fixation_time_hours": None, "embedding_date": now - timedelta(days=79), "sections_cut": 4, "sections_remaining": 6, "thickness_microns": 5.0, "tumor_content_pct": 50.0, "necrosis_pct": 12.0, "storage_location": "Cryo-Cabinet-C3", "temperature_c": -80.0, "quality_adequate": False, "created_at": now - timedelta(days=79)},
            {"id": "BLK-015", "specimen_id": "TSP-003", "block_identifier": "TSP-003-H1", "fixation_time_hours": 20.0, "embedding_date": now - timedelta(days=29), "sections_cut": 2, "sections_remaining": 8, "thickness_microns": 4.0, "tumor_content_pct": None, "necrosis_pct": None, "storage_location": "Block-Cabinet-A2", "temperature_c": 22.0, "quality_adequate": True, "created_at": now - timedelta(days=29)},
        ]

        for b in blocks_data:
            self._blocks[b["id"]] = FFPEBlock(**b)

        # --- 12 Tissue Slides ---
        slides_data = [
            {"id": "SLD-001", "block_id": "BLK-001", "specimen_id": "TSP-001", "slide_identifier": "TSP-001-A1-S01", "stain_type": "H&E", "status": SlideStatus.REVIEWED, "section_number": 1, "preparation_date": now - timedelta(days=88), "staining_date": now - timedelta(days=87), "scanner_used": "Hamamatsu NanoZoomer", "scan_resolution": "40x", "image_file_path": "/slides/TSP-001-A1-S01.svs", "prepared_by": "Tech Lisa Park", "reviewed_by": "Dr. James Chen", "review_date": now - timedelta(days=85), "created_at": now - timedelta(days=88)},
            {"id": "SLD-002", "block_id": "BLK-001", "specimen_id": "TSP-001", "slide_identifier": "TSP-001-A1-S02", "stain_type": "PAS", "status": SlideStatus.REVIEWED, "section_number": 2, "preparation_date": now - timedelta(days=88), "staining_date": now - timedelta(days=87), "scanner_used": "Hamamatsu NanoZoomer", "scan_resolution": "40x", "image_file_path": "/slides/TSP-001-A1-S02.svs", "prepared_by": "Tech Lisa Park", "reviewed_by": "Dr. James Chen", "review_date": now - timedelta(days=85), "created_at": now - timedelta(days=88)},
            {"id": "SLD-003", "block_id": "BLK-005", "specimen_id": "TSP-005", "slide_identifier": "TSP-005-C1-S01", "stain_type": "H&E", "status": SlideStatus.REVIEWED, "section_number": 1, "preparation_date": now - timedelta(days=98), "staining_date": now - timedelta(days=97), "scanner_used": "Aperio AT2", "scan_resolution": "20x", "image_file_path": "/slides/TSP-005-C1-S01.svs", "prepared_by": "Tech David Kim", "reviewed_by": "Dr. Robert Williams", "review_date": now - timedelta(days=95), "created_at": now - timedelta(days=98)},
            {"id": "SLD-004", "block_id": "BLK-005", "specimen_id": "TSP-005", "slide_identifier": "TSP-005-C1-S02", "stain_type": "CD3 IHC", "status": SlideStatus.REVIEWED, "section_number": 2, "preparation_date": now - timedelta(days=98), "staining_date": now - timedelta(days=96), "scanner_used": "Aperio AT2", "scan_resolution": "20x", "image_file_path": "/slides/TSP-005-C1-S02.svs", "prepared_by": "Tech David Kim", "reviewed_by": "Dr. Robert Williams", "review_date": now - timedelta(days=93), "created_at": now - timedelta(days=98)},
            {"id": "SLD-005", "block_id": "BLK-009", "specimen_id": "TSP-009", "slide_identifier": "TSP-009-E1-S01", "stain_type": "H&E", "status": SlideStatus.REVIEWED, "section_number": 1, "preparation_date": now - timedelta(days=108), "staining_date": now - timedelta(days=107), "scanner_used": "Leica Aperio GT 450", "scan_resolution": "40x", "image_file_path": "/slides/TSP-009-E1-S01.svs", "prepared_by": "Tech Rachel Adams", "reviewed_by": "Dr. Catherine Liu", "review_date": now - timedelta(days=105), "created_at": now - timedelta(days=108)},
            {"id": "SLD-006", "block_id": "BLK-009", "specimen_id": "TSP-009", "slide_identifier": "TSP-009-E1-S02", "stain_type": "PD-L1 IHC (22C3)", "status": SlideStatus.REVIEWED, "section_number": 2, "preparation_date": now - timedelta(days=108), "staining_date": now - timedelta(days=106), "scanner_used": "Leica Aperio GT 450", "scan_resolution": "40x", "image_file_path": "/slides/TSP-009-E1-S02.svs", "prepared_by": "Tech Rachel Adams", "reviewed_by": "Dr. Catherine Liu", "review_date": now - timedelta(days=103), "created_at": now - timedelta(days=108)},
            {"id": "SLD-007", "block_id": "BLK-011", "specimen_id": "TSP-010", "slide_identifier": "TSP-010-F1-S01", "stain_type": "H&E", "status": SlideStatus.REVIEWED, "section_number": 1, "preparation_date": now - timedelta(days=103), "staining_date": now - timedelta(days=102), "scanner_used": "Leica Aperio GT 450", "scan_resolution": "40x", "image_file_path": "/slides/TSP-010-F1-S01.svs", "prepared_by": "Tech Rachel Adams", "reviewed_by": "Dr. Catherine Liu", "review_date": now - timedelta(days=100), "created_at": now - timedelta(days=103)},
            {"id": "SLD-008", "block_id": "BLK-011", "specimen_id": "TSP-010", "slide_identifier": "TSP-010-F1-S02", "stain_type": "PD-L1 IHC (22C3)", "status": SlideStatus.STAINED, "section_number": 2, "preparation_date": now - timedelta(days=103), "staining_date": now - timedelta(days=101), "scanner_used": None, "scan_resolution": None, "image_file_path": None, "prepared_by": "Tech Rachel Adams", "reviewed_by": None, "review_date": None, "created_at": now - timedelta(days=103)},
            {"id": "SLD-009", "block_id": "BLK-013", "specimen_id": "TSP-011", "slide_identifier": "TSP-011-G1-S01", "stain_type": "H&E", "status": SlideStatus.UNDER_REVIEW, "section_number": 1, "preparation_date": now - timedelta(days=78), "staining_date": now - timedelta(days=77), "scanner_used": "Hamamatsu NanoZoomer", "scan_resolution": "40x", "image_file_path": "/slides/TSP-011-G1-S01.svs", "prepared_by": "Tech Lisa Park", "reviewed_by": None, "review_date": None, "created_at": now - timedelta(days=78)},
            {"id": "SLD-010", "block_id": "BLK-015", "specimen_id": "TSP-003", "slide_identifier": "TSP-003-H1-S01", "stain_type": "H&E", "status": SlideStatus.PREPARED, "section_number": 1, "preparation_date": now - timedelta(days=28), "staining_date": None, "scanner_used": None, "scan_resolution": None, "image_file_path": None, "prepared_by": "Tech David Kim", "reviewed_by": None, "review_date": None, "created_at": now - timedelta(days=28)},
            {"id": "SLD-011", "block_id": "BLK-006", "specimen_id": "TSP-005", "slide_identifier": "TSP-005-C2-S01", "stain_type": "CD4 IHC", "status": SlideStatus.ARCHIVED, "section_number": 1, "preparation_date": now - timedelta(days=97), "staining_date": now - timedelta(days=96), "scanner_used": "Aperio AT2", "scan_resolution": "20x", "image_file_path": "/slides/TSP-005-C2-S01.svs", "prepared_by": "Tech David Kim", "reviewed_by": "Dr. Robert Williams", "review_date": now - timedelta(days=90), "created_at": now - timedelta(days=97)},
            {"id": "SLD-012", "block_id": "BLK-010", "specimen_id": "TSP-009", "slide_identifier": "TSP-009-E2-S01", "stain_type": "Ki-67 IHC", "status": SlideStatus.RESCANNED, "section_number": 1, "preparation_date": now - timedelta(days=107), "staining_date": now - timedelta(days=106), "scanner_used": "Leica Aperio GT 450", "scan_resolution": "40x", "image_file_path": "/slides/TSP-009-E2-S01-v2.svs", "prepared_by": "Tech Rachel Adams", "reviewed_by": None, "review_date": None, "created_at": now - timedelta(days=107)},
        ]

        for sl in slides_data:
            self._slides[sl["id"]] = TissueSlide(**sl)

        # --- 10 Pathology Reviews ---
        reviews_data = [
            {"id": "PRV-001", "specimen_id": "TSP-001", "slide_id": "SLD-001", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1001", "reviewer": "Dr. James Chen", "review_date": now - timedelta(days=85), "result": PathologyResult.NEGATIVE, "diagnosis": "No pathologic abnormality identified in retinal tissue", "biomarker_name": None, "biomarker_result": None, "scoring_method": None, "score_value": None, "tumor_cellularity_pct": None, "comments": "Normal retinal architecture preserved", "adjudication_required": False, "adjudicated_by": None, "created_at": now - timedelta(days=85)},
            {"id": "PRV-002", "specimen_id": "TSP-005", "slide_id": "SLD-003", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2001", "reviewer": "Dr. Robert Williams", "review_date": now - timedelta(days=95), "result": PathologyResult.POSITIVE, "diagnosis": "Spongiotic dermatitis consistent with atopic dermatitis", "biomarker_name": "CD3", "biomarker_result": "Elevated", "scoring_method": "Semi-quantitative", "score_value": "3+", "tumor_cellularity_pct": None, "comments": "Dense perivascular T-cell infiltrate with spongiosis and acanthosis", "adjudication_required": False, "adjudicated_by": None, "created_at": now - timedelta(days=95)},
            {"id": "PRV-003", "specimen_id": "TSP-005", "slide_id": "SLD-004", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2001", "reviewer": "Dr. Robert Williams", "review_date": now - timedelta(days=93), "result": PathologyResult.POSITIVE, "diagnosis": "CD3+ T-cell infiltrate confirmed in lesional skin", "biomarker_name": "CD3", "biomarker_result": "Positive", "scoring_method": "IHC visual scoring", "score_value": "Moderate-to-dense", "tumor_cellularity_pct": None, "comments": "Consistent with Th2-mediated inflammatory process", "adjudication_required": False, "adjudicated_by": None, "created_at": now - timedelta(days=93)},
            {"id": "PRV-004", "specimen_id": "TSP-009", "slide_id": "SLD-005", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3001", "reviewer": "Dr. Catherine Liu", "review_date": now - timedelta(days=105), "result": PathologyResult.POSITIVE, "diagnosis": "Non-small cell lung carcinoma, adenocarcinoma subtype", "biomarker_name": None, "biomarker_result": None, "scoring_method": None, "score_value": None, "tumor_cellularity_pct": 65.0, "comments": "Moderately differentiated adenocarcinoma with acinar and papillary growth patterns", "adjudication_required": False, "adjudicated_by": None, "created_at": now - timedelta(days=105)},
            {"id": "PRV-005", "specimen_id": "TSP-009", "slide_id": "SLD-006", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3001", "reviewer": "Dr. Catherine Liu", "review_date": now - timedelta(days=103), "result": PathologyResult.POSITIVE, "diagnosis": "PD-L1 expression detected", "biomarker_name": "PD-L1", "biomarker_result": "Positive", "scoring_method": "TPS (Tumor Proportion Score)", "score_value": "60%", "tumor_cellularity_pct": 65.0, "comments": "TPS >= 50%, eligible for first-line cemiplimab monotherapy", "adjudication_required": False, "adjudicated_by": None, "created_at": now - timedelta(days=103)},
            {"id": "PRV-006", "specimen_id": "TSP-010", "slide_id": "SLD-007", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3002", "reviewer": "Dr. Catherine Liu", "review_date": now - timedelta(days=100), "result": PathologyResult.POSITIVE, "diagnosis": "Cutaneous squamous cell carcinoma, well-differentiated", "biomarker_name": None, "biomarker_result": None, "scoring_method": None, "score_value": None, "tumor_cellularity_pct": 80.0, "comments": "Well-differentiated SCC with keratinization. Surgical margins clear.", "adjudication_required": False, "adjudicated_by": None, "created_at": now - timedelta(days=100)},
            {"id": "PRV-007", "specimen_id": "TSP-011", "slide_id": "SLD-009", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3003", "reviewer": "Dr. Gregory Harris", "review_date": now - timedelta(days=75), "result": PathologyResult.EQUIVOCAL, "diagnosis": "Atypical hepatocellular proliferation, cannot exclude HCC", "biomarker_name": "Glypican-3", "biomarker_result": "Weakly positive", "scoring_method": "IHC", "score_value": "1+", "tumor_cellularity_pct": 55.0, "comments": "Equivocal Glypican-3 staining. Recommend additional markers (HSP70, GS).", "adjudication_required": True, "adjudicated_by": None, "created_at": now - timedelta(days=75)},
            {"id": "PRV-008", "specimen_id": "TSP-006", "slide_id": None, "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2002", "reviewer": "Dr. Robert Williams", "review_date": now - timedelta(days=90), "result": PathologyResult.POSITIVE, "diagnosis": "Eczematous dermatitis with mixed inflammatory infiltrate", "biomarker_name": None, "biomarker_result": None, "scoring_method": None, "score_value": None, "tumor_cellularity_pct": None, "comments": "Findings consistent with moderate atopic dermatitis", "adjudication_required": False, "adjudicated_by": None, "created_at": now - timedelta(days=90)},
            {"id": "PRV-009", "specimen_id": "TSP-002", "slide_id": None, "trial_id": EYLEA_TRIAL, "subject_id": "PT-1002", "reviewer": "Dr. James Chen", "review_date": now - timedelta(days=82), "result": PathologyResult.INSUFFICIENT, "diagnosis": "Insufficient tissue for definitive evaluation", "biomarker_name": None, "biomarker_result": None, "scoring_method": None, "score_value": None, "tumor_cellularity_pct": None, "comments": "Vitreous aspirate with scant cellularity. Re-biopsy recommended.", "adjudication_required": False, "adjudicated_by": None, "created_at": now - timedelta(days=82)},
            {"id": "PRV-010", "specimen_id": "TSP-003", "slide_id": None, "trial_id": EYLEA_TRIAL, "subject_id": "PT-1003", "reviewer": "Dr. Laura Patel", "review_date": now - timedelta(days=25), "result": PathologyResult.PENDING, "diagnosis": None, "biomarker_name": None, "biomarker_result": None, "scoring_method": None, "score_value": None, "tumor_cellularity_pct": None, "comments": "Specimen received, processing in progress", "adjudication_required": False, "adjudicated_by": None, "created_at": now - timedelta(days=25)},
        ]

        for r in reviews_data:
            self._reviews[r["id"]] = PathologyReview(**r)

        # --- 10 Tissue Shipments ---
        shipments_data = [
            {"id": "SHP-001", "trial_id": EYLEA_TRIAL, "origin_site_id": "SITE-101", "destination_lab": "Central Path Lab - Bascom Palmer", "shipment_date": now - timedelta(days=91), "arrival_date": now - timedelta(days=90), "specimen_count": 2, "tracking_number": "1Z999AA10123456784", "courier": "World Courier", "temperature_condition": "Ambient (15-25C)", "temperature_monitored": True, "excursion_detected": False, "status": "delivered", "received_by": "Tech Lisa Park", "created_at": now - timedelta(days=91)},
            {"id": "SHP-002", "trial_id": EYLEA_TRIAL, "origin_site_id": "SITE-102", "destination_lab": "Central Path Lab - Bascom Palmer", "shipment_date": now - timedelta(days=31), "arrival_date": now - timedelta(days=30), "specimen_count": 1, "tracking_number": "1Z999AA10123456785", "courier": "World Courier", "temperature_condition": "Ambient (15-25C)", "temperature_monitored": True, "excursion_detected": False, "status": "delivered", "received_by": "Tech Lisa Park", "created_at": now - timedelta(days=31)},
            {"id": "SHP-003", "trial_id": EYLEA_TRIAL, "origin_site_id": "SITE-102", "destination_lab": "Central Path Lab - Bascom Palmer", "shipment_date": now - timedelta(days=11), "arrival_date": None, "specimen_count": 1, "tracking_number": "1Z999AA10123456786", "courier": "Marken", "temperature_condition": "Ambient (15-25C)", "temperature_monitored": True, "excursion_detected": False, "status": "in_transit", "received_by": None, "created_at": now - timedelta(days=11)},
            {"id": "SHP-004", "trial_id": DUPIXENT_TRIAL, "origin_site_id": "SITE-104", "destination_lab": "Dermpath Central - NYU", "shipment_date": now - timedelta(days=101), "arrival_date": now - timedelta(days=100), "specimen_count": 2, "tracking_number": "1Z999BB20123456787", "courier": "Fisher BioServices", "temperature_condition": "Ambient (15-25C)", "temperature_monitored": True, "excursion_detected": False, "status": "delivered", "received_by": "Tech David Kim", "created_at": now - timedelta(days=101)},
            {"id": "SHP-005", "trial_id": DUPIXENT_TRIAL, "origin_site_id": "SITE-105", "destination_lab": "Dermpath Central - NYU", "shipment_date": now - timedelta(days=61), "arrival_date": now - timedelta(days=60), "specimen_count": 1, "tracking_number": "1Z999BB20123456788", "courier": "Fisher BioServices", "temperature_condition": "Cold chain (2-8C)", "temperature_monitored": True, "excursion_detected": True, "status": "delivered", "received_by": "Tech David Kim", "created_at": now - timedelta(days=61)},
            {"id": "SHP-006", "trial_id": DUPIXENT_TRIAL, "origin_site_id": "SITE-105", "destination_lab": "Dermpath Central - NYU", "shipment_date": now - timedelta(days=16), "arrival_date": now - timedelta(days=15), "specimen_count": 1, "tracking_number": "1Z999BB20123456789", "courier": "Marken", "temperature_condition": "Ambient (15-25C)", "temperature_monitored": True, "excursion_detected": False, "status": "delivered", "received_by": "Tech David Kim", "created_at": now - timedelta(days=16)},
            {"id": "SHP-007", "trial_id": LIBTAYO_TRIAL, "origin_site_id": "SITE-107", "destination_lab": "Oncopath Central - MSK", "shipment_date": now - timedelta(days=111), "arrival_date": now - timedelta(days=110), "specimen_count": 2, "tracking_number": "1Z999CC30123456790", "courier": "World Courier", "temperature_condition": "Ambient (15-25C)", "temperature_monitored": True, "excursion_detected": False, "status": "delivered", "received_by": "Tech Rachel Adams", "created_at": now - timedelta(days=111)},
            {"id": "SHP-008", "trial_id": LIBTAYO_TRIAL, "origin_site_id": "SITE-108", "destination_lab": "Oncopath Central - MSK", "shipment_date": now - timedelta(days=81), "arrival_date": now - timedelta(days=80), "specimen_count": 1, "tracking_number": "1Z999CC30123456791", "courier": "World Courier", "temperature_condition": "Dry ice (-60 to -80C)", "temperature_monitored": True, "excursion_detected": False, "status": "delivered", "received_by": "Tech Rachel Adams", "created_at": now - timedelta(days=81)},
            {"id": "SHP-009", "trial_id": LIBTAYO_TRIAL, "origin_site_id": "SITE-108", "destination_lab": "Oncopath Central - MSK", "shipment_date": now - timedelta(days=6), "arrival_date": None, "specimen_count": 1, "tracking_number": "1Z999CC30123456792", "courier": "Marken", "temperature_condition": "Ambient (15-25C)", "temperature_monitored": True, "excursion_detected": False, "status": "in_transit", "received_by": None, "created_at": now - timedelta(days=6)},
            {"id": "SHP-010", "trial_id": LIBTAYO_TRIAL, "origin_site_id": "SITE-107", "destination_lab": "Reference Lab - Quest Diagnostics", "shipment_date": now - timedelta(days=50), "arrival_date": now - timedelta(days=49), "specimen_count": 3, "tracking_number": "1Z999CC30123456793", "courier": "Fisher BioServices", "temperature_condition": "Dry ice (-60 to -80C)", "temperature_monitored": True, "excursion_detected": True, "status": "delivered", "received_by": "Tech Mark Johnson", "created_at": now - timedelta(days=50)},
        ]

        for sh in shipments_data:
            self._shipments[sh["id"]] = TissueShipment(**sh)

    # ------------------------------------------------------------------
    # Specimen CRUD
    # ------------------------------------------------------------------

    def list_specimens(
        self,
        *,
        trial_id: str | None = None,
        status: SpecimenStatus | None = None,
        tissue_type: TissueType | None = None,
    ) -> list[TissueSpecimen]:
        """List tissue specimens with optional filters."""
        with self._lock:
            result = list(self._specimens.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if status is not None:
            result = [s for s in result if s.status == status]
        if tissue_type is not None:
            result = [s for s in result if s.tissue_type == tissue_type]

        return sorted(result, key=lambda s: s.collection_date, reverse=True)

    def get_specimen(self, specimen_id: str) -> TissueSpecimen | None:
        """Get a single specimen by ID."""
        with self._lock:
            return self._specimens.get(specimen_id)

    def create_specimen(self, payload: TissueSpecimenCreate) -> TissueSpecimen:
        """Create a new tissue specimen."""
        now = datetime.now(timezone.utc)
        specimen_id = f"TSP-{uuid4().hex[:8].upper()}"
        specimen = TissueSpecimen(
            id=specimen_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            tissue_type=payload.tissue_type,
            preservation_method=payload.preservation_method,
            status=SpecimenStatus.COLLECTED,
            collection_date=now,
            body_site=payload.body_site,
            laterality=payload.laterality,
            tumor_type=payload.tumor_type,
            collected_by=payload.collected_by,
            created_at=now,
        )
        with self._lock:
            self._specimens[specimen_id] = specimen
        logger.info("Created tissue specimen %s for trial %s", specimen_id, payload.trial_id)
        return specimen

    def update_specimen(
        self, specimen_id: str, payload: TissueSpecimenUpdate
    ) -> TissueSpecimen | None:
        """Update an existing tissue specimen."""
        with self._lock:
            existing = self._specimens.get(specimen_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TissueSpecimen(**data)
            self._specimens[specimen_id] = updated
        return updated

    def delete_specimen(self, specimen_id: str) -> bool:
        """Delete a specimen. Returns True if deleted."""
        with self._lock:
            if specimen_id in self._specimens:
                del self._specimens[specimen_id]
                return True
            return False

    # ------------------------------------------------------------------
    # FFPE Block CRUD
    # ------------------------------------------------------------------

    def list_blocks(
        self,
        *,
        specimen_id: str | None = None,
    ) -> list[FFPEBlock]:
        """List FFPE blocks with optional specimen filter."""
        with self._lock:
            result = list(self._blocks.values())

        if specimen_id is not None:
            result = [b for b in result if b.specimen_id == specimen_id]

        return sorted(result, key=lambda b: b.id)

    def get_block(self, block_id: str) -> FFPEBlock | None:
        """Get a single block by ID."""
        with self._lock:
            return self._blocks.get(block_id)

    def create_block(self, payload: FFPEBlockCreate) -> FFPEBlock:
        """Create a new FFPE block."""
        now = datetime.now(timezone.utc)
        block_id = f"BLK-{uuid4().hex[:8].upper()}"
        block = FFPEBlock(
            id=block_id,
            specimen_id=payload.specimen_id,
            block_identifier=payload.block_identifier,
            fixation_time_hours=payload.fixation_time_hours,
            embedding_date=now,
            thickness_microns=payload.thickness_microns,
            created_at=now,
        )
        with self._lock:
            self._blocks[block_id] = block
        logger.info("Created FFPE block %s for specimen %s", block_id, payload.specimen_id)
        return block

    def update_block(
        self, block_id: str, payload: FFPEBlockUpdate
    ) -> FFPEBlock | None:
        """Update an existing FFPE block."""
        with self._lock:
            existing = self._blocks.get(block_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = FFPEBlock(**data)
            self._blocks[block_id] = updated
        return updated

    def delete_block(self, block_id: str) -> bool:
        """Delete a block. Returns True if deleted."""
        with self._lock:
            if block_id in self._blocks:
                del self._blocks[block_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Tissue Slide CRUD
    # ------------------------------------------------------------------

    def list_slides(
        self,
        *,
        specimen_id: str | None = None,
        block_id: str | None = None,
        status: SlideStatus | None = None,
    ) -> list[TissueSlide]:
        """List tissue slides with optional filters."""
        with self._lock:
            result = list(self._slides.values())

        if specimen_id is not None:
            result = [s for s in result if s.specimen_id == specimen_id]
        if block_id is not None:
            result = [s for s in result if s.block_id == block_id]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.id)

    def get_slide(self, slide_id: str) -> TissueSlide | None:
        """Get a single slide by ID."""
        with self._lock:
            return self._slides.get(slide_id)

    def create_slide(self, payload: TissueSlideCreate) -> TissueSlide:
        """Create a new tissue slide."""
        now = datetime.now(timezone.utc)
        slide_id = f"SLD-{uuid4().hex[:8].upper()}"
        slide = TissueSlide(
            id=slide_id,
            block_id=payload.block_id,
            specimen_id=payload.specimen_id,
            slide_identifier=payload.slide_identifier,
            stain_type=payload.stain_type,
            status=SlideStatus.PREPARED,
            section_number=payload.section_number,
            preparation_date=now,
            prepared_by=payload.prepared_by,
            created_at=now,
        )
        with self._lock:
            self._slides[slide_id] = slide
        logger.info("Created tissue slide %s for block %s", slide_id, payload.block_id)
        return slide

    def update_slide(
        self, slide_id: str, payload: TissueSlideUpdate
    ) -> TissueSlide | None:
        """Update an existing tissue slide."""
        with self._lock:
            existing = self._slides.get(slide_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TissueSlide(**data)
            self._slides[slide_id] = updated
        return updated

    def delete_slide(self, slide_id: str) -> bool:
        """Delete a slide. Returns True if deleted."""
        with self._lock:
            if slide_id in self._slides:
                del self._slides[slide_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Pathology Review CRUD
    # ------------------------------------------------------------------

    def list_reviews(
        self,
        *,
        trial_id: str | None = None,
        specimen_id: str | None = None,
        result: PathologyResult | None = None,
    ) -> list[PathologyReview]:
        """List pathology reviews with optional filters."""
        with self._lock:
            items = list(self._reviews.values())

        if trial_id is not None:
            items = [r for r in items if r.trial_id == trial_id]
        if specimen_id is not None:
            items = [r for r in items if r.specimen_id == specimen_id]
        if result is not None:
            items = [r for r in items if r.result == result]

        return sorted(items, key=lambda r: r.review_date, reverse=True)

    def get_review(self, review_id: str) -> PathologyReview | None:
        """Get a single review by ID."""
        with self._lock:
            return self._reviews.get(review_id)

    def create_review(self, payload: PathologyReviewCreate) -> PathologyReview:
        """Create a new pathology review."""
        now = datetime.now(timezone.utc)
        review_id = f"PRV-{uuid4().hex[:8].upper()}"
        review = PathologyReview(
            id=review_id,
            specimen_id=payload.specimen_id,
            slide_id=payload.slide_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            reviewer=payload.reviewer,
            review_date=now,
            result=PathologyResult.PENDING,
            biomarker_name=payload.biomarker_name,
            created_at=now,
        )
        with self._lock:
            self._reviews[review_id] = review
        logger.info("Created pathology review %s for specimen %s", review_id, payload.specimen_id)
        return review

    def update_review(
        self, review_id: str, payload: PathologyReviewUpdate
    ) -> PathologyReview | None:
        """Update an existing pathology review."""
        with self._lock:
            existing = self._reviews.get(review_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PathologyReview(**data)
            self._reviews[review_id] = updated
        return updated

    def delete_review(self, review_id: str) -> bool:
        """Delete a review. Returns True if deleted."""
        with self._lock:
            if review_id in self._reviews:
                del self._reviews[review_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Tissue Shipment CRUD
    # ------------------------------------------------------------------

    def list_shipments(
        self,
        *,
        trial_id: str | None = None,
        status: str | None = None,
    ) -> list[TissueShipment]:
        """List tissue shipments with optional filters."""
        with self._lock:
            result = list(self._shipments.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.shipment_date, reverse=True)

    def get_shipment(self, shipment_id: str) -> TissueShipment | None:
        """Get a single shipment by ID."""
        with self._lock:
            return self._shipments.get(shipment_id)

    def create_shipment(self, payload: TissueShipmentCreate) -> TissueShipment:
        """Create a new tissue shipment."""
        now = datetime.now(timezone.utc)
        shipment_id = f"SHP-{uuid4().hex[:8].upper()}"
        shipment = TissueShipment(
            id=shipment_id,
            trial_id=payload.trial_id,
            origin_site_id=payload.origin_site_id,
            destination_lab=payload.destination_lab,
            shipment_date=now,
            specimen_count=payload.specimen_count,
            tracking_number=payload.tracking_number,
            courier=payload.courier,
            temperature_condition=payload.temperature_condition,
            status="in_transit",
            created_at=now,
        )
        with self._lock:
            self._shipments[shipment_id] = shipment
        logger.info("Created tissue shipment %s for trial %s", shipment_id, payload.trial_id)
        return shipment

    def update_shipment(
        self, shipment_id: str, payload: TissueShipmentUpdate
    ) -> TissueShipment | None:
        """Update an existing tissue shipment."""
        with self._lock:
            existing = self._shipments.get(shipment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TissueShipment(**data)
            self._shipments[shipment_id] = updated
        return updated

    def delete_shipment(self, shipment_id: str) -> bool:
        """Delete a shipment. Returns True if deleted."""
        with self._lock:
            if shipment_id in self._shipments:
                del self._shipments[shipment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> TissueTrackingMetrics:
        """Compute aggregated tissue tracking metrics."""
        with self._lock:
            specimens = list(self._specimens.values())
            blocks = list(self._blocks.values())
            slides = list(self._slides.values())
            reviews = list(self._reviews.values())
            shipments = list(self._shipments.values())

        if trial_id is not None:
            specimen_ids = {s.id for s in specimens if s.trial_id == trial_id}
            specimens = [s for s in specimens if s.trial_id == trial_id]
            blocks = [b for b in blocks if b.specimen_id in specimen_ids]
            slides = [sl for sl in slides if sl.specimen_id in specimen_ids]
            reviews = [r for r in reviews if r.trial_id == trial_id]
            shipments = [sh for sh in shipments if sh.trial_id == trial_id]

        # Specimens by type
        specimens_by_type: dict[str, int] = {}
        for s in specimens:
            key = s.tissue_type.value
            specimens_by_type[key] = specimens_by_type.get(key, 0) + 1

        # Specimens by status
        specimens_by_status: dict[str, int] = {}
        for s in specimens:
            key = s.status.value
            specimens_by_status[key] = specimens_by_status.get(key, 0) + 1

        # Specimens by preservation
        specimens_by_preservation: dict[str, int] = {}
        for s in specimens:
            key = s.preservation_method.value
            specimens_by_preservation[key] = specimens_by_preservation.get(key, 0) + 1

        # Slides by status
        slides_by_status: dict[str, int] = {}
        for sl in slides:
            key = sl.status.value
            slides_by_status[key] = slides_by_status.get(key, 0) + 1

        # Reviews by result
        reviews_by_result: dict[str, int] = {}
        for r in reviews:
            key = r.result.value
            reviews_by_result[key] = reviews_by_result.get(key, 0) + 1

        # Pending reviews
        pending_reviews = sum(1 for r in reviews if r.result == PathologyResult.PENDING)

        # Shipments with excursions
        shipments_with_excursions = sum(1 for sh in shipments if sh.excursion_detected)

        return TissueTrackingMetrics(
            total_specimens=len(specimens),
            specimens_by_type=specimens_by_type,
            specimens_by_status=specimens_by_status,
            specimens_by_preservation=specimens_by_preservation,
            total_blocks=len(blocks),
            total_slides=len(slides),
            slides_by_status=slides_by_status,
            total_reviews=len(reviews),
            reviews_by_result=reviews_by_result,
            pending_reviews=pending_reviews,
            total_shipments=len(shipments),
            shipments_with_excursions=shipments_with_excursions,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: TissueTrackingService | None = None
_instance_lock = threading.Lock()


def get_tissue_tracking_service() -> TissueTrackingService:
    """Return the singleton TissueTrackingService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = TissueTrackingService()
    return _instance


def reset_tissue_tracking_service() -> TissueTrackingService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = TissueTrackingService()
    return _instance
