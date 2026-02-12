"""Medical Coding Management Service (MED-CODE).

Manages medical coding operations: MedDRA coding of adverse events, WHO Drug
coding of concomitant medications, dictionary version management, auto-coding
rules, coding query resolution, batch coding workflow, and medical coding
operational metrics.

Usage:
    from app.services.medical_coding_service import get_medical_coding_service

    svc = get_medical_coding_service()
    entries = svc.list_coding_entries()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.medical_coding import (
    AutoCodingRule,
    AutoCodingRuleCreate,
    AutoCodingRuleUpdate,
    CodingBatch,
    CodingBatchCreate,
    CodingBatchUpdate,
    CodingEntry,
    CodingEntryCreate,
    CodingEntryUpdate,
    CodingPriority,
    CodingQuery,
    CodingQueryCreate,
    CodingQueryUpdate,
    CodingStatus,
    DictionaryType,
    DictionaryVersion,
    DictionaryVersionCreate,
    DictionaryVersionUpdate,
    MedDRALevel,
    MedicalCodingMetrics,
    QueryStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class MedicalCodingService:
    """In-memory Medical Coding Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._dictionary_versions: dict[str, DictionaryVersion] = {}
        self._coding_entries: dict[str, CodingEntry] = {}
        self._auto_coding_rules: dict[str, AutoCodingRule] = {}
        self._coding_queries: dict[str, CodingQuery] = {}
        self._coding_batches: dict[str, CodingBatch] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic medical coding data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Dictionary Versions ---
        dict_versions_data = [
            {"id": "DV-001", "dictionary_type": DictionaryType.MEDDRA, "version": "26.1", "release_date": now - timedelta(days=180), "effective_date": now - timedelta(days=150), "total_terms": 83000, "active": True, "loaded_by": "system_admin", "loaded_at": now - timedelta(days=150), "notes": "MedDRA v26.1 quarterly update"},
            {"id": "DV-002", "dictionary_type": DictionaryType.MEDDRA, "version": "26.0", "release_date": now - timedelta(days=365), "effective_date": now - timedelta(days=335), "expiry_date": now - timedelta(days=150), "total_terms": 82500, "active": False, "loaded_by": "system_admin", "loaded_at": now - timedelta(days=335), "migration_status": "completed", "notes": "Superseded by v26.1"},
            {"id": "DV-003", "dictionary_type": DictionaryType.WHO_DRUG, "version": "2024-Q3", "release_date": now - timedelta(days=120), "effective_date": now - timedelta(days=90), "total_terms": 175000, "active": True, "loaded_by": "coding_lead", "loaded_at": now - timedelta(days=90), "notes": "WHO Drug Global B3 2024-Q3"},
            {"id": "DV-004", "dictionary_type": DictionaryType.WHO_DRUG, "version": "2024-Q2", "release_date": now - timedelta(days=210), "effective_date": now - timedelta(days=180), "expiry_date": now - timedelta(days=90), "total_terms": 174500, "active": False, "loaded_by": "coding_lead", "loaded_at": now - timedelta(days=180), "migration_status": "completed", "notes": "Superseded by 2024-Q3"},
            {"id": "DV-005", "dictionary_type": DictionaryType.SNOMED, "version": "2024-07", "release_date": now - timedelta(days=160), "effective_date": now - timedelta(days=130), "total_terms": 360000, "active": True, "loaded_by": "system_admin", "loaded_at": now - timedelta(days=130)},
            {"id": "DV-006", "dictionary_type": DictionaryType.ICD10, "version": "2024", "release_date": now - timedelta(days=300), "effective_date": now - timedelta(days=270), "total_terms": 72000, "active": True, "loaded_by": "system_admin", "loaded_at": now - timedelta(days=270)},
            {"id": "DV-007", "dictionary_type": DictionaryType.ATC, "version": "2024", "release_date": now - timedelta(days=200), "effective_date": now - timedelta(days=170), "total_terms": 6500, "active": True, "loaded_by": "coding_lead", "loaded_at": now - timedelta(days=170)},
            {"id": "DV-008", "dictionary_type": DictionaryType.LOINC, "version": "2.77", "release_date": now - timedelta(days=140), "effective_date": now - timedelta(days=110), "total_terms": 98000, "active": True, "loaded_by": "system_admin", "loaded_at": now - timedelta(days=110)},
            {"id": "DV-009", "dictionary_type": DictionaryType.MEDDRA, "version": "25.1", "release_date": now - timedelta(days=540), "effective_date": now - timedelta(days=510), "expiry_date": now - timedelta(days=335), "total_terms": 81000, "active": False, "loaded_by": "system_admin", "loaded_at": now - timedelta(days=510), "migration_status": "completed"},
            {"id": "DV-010", "dictionary_type": DictionaryType.WHO_DRUG, "version": "2024-Q1", "release_date": now - timedelta(days=300), "effective_date": now - timedelta(days=270), "expiry_date": now - timedelta(days=180), "total_terms": 174000, "active": False, "loaded_by": "coding_lead", "loaded_at": now - timedelta(days=270), "migration_status": "completed"},
            {"id": "DV-011", "dictionary_type": DictionaryType.SNOMED, "version": "2024-01", "release_date": now - timedelta(days=340), "effective_date": now - timedelta(days=310), "expiry_date": now - timedelta(days=130), "total_terms": 358000, "active": False, "loaded_by": "system_admin", "loaded_at": now - timedelta(days=310), "migration_status": "completed"},
            {"id": "DV-012", "dictionary_type": DictionaryType.ICD10, "version": "2023", "release_date": now - timedelta(days=660), "effective_date": now - timedelta(days=630), "expiry_date": now - timedelta(days=270), "total_terms": 71500, "active": False, "loaded_by": "system_admin", "loaded_at": now - timedelta(days=630), "migration_status": "completed"},
        ]

        for dv in dict_versions_data:
            self._dictionary_versions[dv["id"]] = DictionaryVersion(**dv)

        # --- 15 Coding Entries ---
        coding_entries_data = [
            # EYLEA trial - MedDRA coded AEs
            {"id": "CE-001", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1001", "source_term": "eye pain", "dictionary_type": DictionaryType.MEDDRA, "dictionary_version": "26.1", "coded_term": "Eye pain", "coded_code": "10015958", "meddra_pt": "Eye pain", "meddra_soc": "Eye disorders", "meddra_llt": "Eye pain", "meddra_hlt": "Ocular discomfort symptoms", "status": CodingStatus.APPROVED, "priority": CodingPriority.HIGH, "auto_code_confidence": 0.98, "coded_by": "auto_coder", "coded_date": now - timedelta(days=80), "verified_by": "dr.chen", "verified_date": now - timedelta(days=78), "source_form": "AE_CRF", "source_field": "AETERM", "created_at": now - timedelta(days=85)},
            {"id": "CE-002", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1002", "source_term": "blurred vision", "dictionary_type": DictionaryType.MEDDRA, "dictionary_version": "26.1", "coded_term": "Vision blurred", "coded_code": "10047513", "meddra_pt": "Vision blurred", "meddra_soc": "Eye disorders", "meddra_llt": "Blurred vision", "meddra_hlt": "Visual acuity disorders", "status": CodingStatus.VERIFIED, "priority": CodingPriority.MEDIUM, "auto_code_confidence": 0.95, "coded_by": "auto_coder", "coded_date": now - timedelta(days=75), "verified_by": "dr.chen", "verified_date": now - timedelta(days=73), "source_form": "AE_CRF", "source_field": "AETERM", "created_at": now - timedelta(days=80)},
            {"id": "CE-003", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1003", "source_term": "vitreous floaters", "dictionary_type": DictionaryType.MEDDRA, "dictionary_version": "26.1", "coded_term": "Vitreous floaters", "coded_code": "10047654", "meddra_pt": "Vitreous floaters", "meddra_soc": "Eye disorders", "meddra_llt": "Vitreous floaters", "meddra_hlt": "Vitreous structural change, deposit and degeneration", "status": CodingStatus.AUTO_CODED, "priority": CodingPriority.LOW, "auto_code_confidence": 0.99, "coded_by": "auto_coder", "coded_date": now - timedelta(days=60), "source_form": "AE_CRF", "source_field": "AETERM", "created_at": now - timedelta(days=65)},
            {"id": "CE-004", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1004", "source_term": "mild headache after injection", "dictionary_type": DictionaryType.MEDDRA, "dictionary_version": "26.1", "status": CodingStatus.QUERY_OPEN, "priority": CodingPriority.HIGH, "source_form": "AE_CRF", "source_field": "AETERM", "created_at": now - timedelta(days=40)},
            {"id": "CE-005", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1005", "source_term": "increased IOP", "dictionary_type": DictionaryType.MEDDRA, "dictionary_version": "26.1", "coded_term": "Intraocular pressure increased", "coded_code": "10022806", "meddra_pt": "Intraocular pressure increased", "meddra_soc": "Eye disorders", "meddra_llt": "Raised intraocular pressure", "status": CodingStatus.MANUALLY_CODED, "priority": CodingPriority.HIGH, "coded_by": "coder_jones", "coded_date": now - timedelta(days=30), "source_form": "AE_CRF", "source_field": "AETERM", "created_at": now - timedelta(days=50)},

            # DUPIXENT trial - MedDRA + WHO Drug coded
            {"id": "CE-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2001", "source_term": "injection site reaction", "dictionary_type": DictionaryType.MEDDRA, "dictionary_version": "26.1", "coded_term": "Injection site reaction", "coded_code": "10022095", "meddra_pt": "Injection site reaction", "meddra_soc": "General disorders and administration site conditions", "meddra_llt": "Injection site reaction", "status": CodingStatus.APPROVED, "priority": CodingPriority.MEDIUM, "auto_code_confidence": 0.97, "coded_by": "auto_coder", "coded_date": now - timedelta(days=90), "verified_by": "dr.martinez", "verified_date": now - timedelta(days=88), "source_form": "AE_CRF", "source_field": "AETERM", "created_at": now - timedelta(days=95)},
            {"id": "CE-007", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2002", "source_term": "conjunctivitis", "dictionary_type": DictionaryType.MEDDRA, "dictionary_version": "26.1", "coded_term": "Conjunctivitis", "coded_code": "10010741", "meddra_pt": "Conjunctivitis", "meddra_soc": "Eye disorders", "meddra_llt": "Conjunctivitis", "meddra_hlt": "Conjunctival infections, irritations and inflammations", "status": CodingStatus.VERIFIED, "priority": CodingPriority.HIGH, "auto_code_confidence": 0.96, "coded_by": "auto_coder", "coded_date": now - timedelta(days=70), "verified_by": "dr.martinez", "verified_date": now - timedelta(days=68), "source_form": "AE_CRF", "source_field": "AETERM", "created_at": now - timedelta(days=75)},
            {"id": "CE-008", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2003", "source_term": "Ibuprofen 400mg", "dictionary_type": DictionaryType.WHO_DRUG, "dictionary_version": "2024-Q3", "coded_term": "Ibuprofen", "coded_code": "M01AE01", "who_drug_name": "Ibuprofen", "who_drug_atc": "M01AE01", "status": CodingStatus.APPROVED, "priority": CodingPriority.LOW, "auto_code_confidence": 0.99, "coded_by": "auto_coder", "coded_date": now - timedelta(days=85), "verified_by": "pharm_smith", "verified_date": now - timedelta(days=83), "source_form": "CM_CRF", "source_field": "CMTRT", "created_at": now - timedelta(days=90)},
            {"id": "CE-009", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2004", "source_term": "skin rash with itching", "dictionary_type": DictionaryType.MEDDRA, "dictionary_version": "26.1", "status": CodingStatus.PENDING, "priority": CodingPriority.URGENT, "source_form": "AE_CRF", "source_field": "AETERM", "created_at": now - timedelta(days=20)},
            {"id": "CE-010", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2005", "source_term": "Cetirizine 10mg daily", "dictionary_type": DictionaryType.WHO_DRUG, "dictionary_version": "2024-Q3", "coded_term": "Cetirizine", "coded_code": "R06AE07", "who_drug_name": "Cetirizine", "who_drug_atc": "R06AE07", "status": CodingStatus.AUTO_CODED, "priority": CodingPriority.LOW, "auto_code_confidence": 0.98, "coded_by": "auto_coder", "coded_date": now - timedelta(days=45), "source_form": "CM_CRF", "source_field": "CMTRT", "created_at": now - timedelta(days=50)},

            # LIBTAYO trial - MedDRA + WHO Drug coded
            {"id": "CE-011", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3001", "source_term": "fatigue", "dictionary_type": DictionaryType.MEDDRA, "dictionary_version": "26.1", "coded_term": "Fatigue", "coded_code": "10016256", "meddra_pt": "Fatigue", "meddra_soc": "General disorders and administration site conditions", "meddra_llt": "Fatigue", "meddra_hlt": "Asthenic conditions", "status": CodingStatus.APPROVED, "priority": CodingPriority.MEDIUM, "auto_code_confidence": 0.99, "coded_by": "auto_coder", "coded_date": now - timedelta(days=100), "verified_by": "dr.liu", "verified_date": now - timedelta(days=98), "source_form": "AE_CRF", "source_field": "AETERM", "created_at": now - timedelta(days=105)},
            {"id": "CE-012", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3002", "source_term": "immune related colitis", "dictionary_type": DictionaryType.MEDDRA, "dictionary_version": "26.1", "coded_term": "Colitis", "coded_code": "10009887", "meddra_pt": "Colitis", "meddra_soc": "Gastrointestinal disorders", "meddra_llt": "Colitis", "meddra_hlt": "Colitis (excl infective)", "status": CodingStatus.MANUALLY_CODED, "priority": CodingPriority.URGENT, "coded_by": "coder_patel", "coded_date": now - timedelta(days=55), "source_form": "AE_CRF", "source_field": "AETERM", "created_at": now - timedelta(days=60)},
            {"id": "CE-013", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3003", "source_term": "Ondansetron 8mg IV", "dictionary_type": DictionaryType.WHO_DRUG, "dictionary_version": "2024-Q3", "coded_term": "Ondansetron", "coded_code": "A04AA01", "who_drug_name": "Ondansetron", "who_drug_atc": "A04AA01", "status": CodingStatus.VERIFIED, "priority": CodingPriority.LOW, "auto_code_confidence": 0.97, "coded_by": "auto_coder", "coded_date": now - timedelta(days=70), "verified_by": "pharm_smith", "verified_date": now - timedelta(days=68), "source_form": "CM_CRF", "source_field": "CMTRT", "created_at": now - timedelta(days=75)},
            {"id": "CE-014", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3004", "source_term": "thyroid function abnormal", "dictionary_type": DictionaryType.MEDDRA, "dictionary_version": "26.1", "status": CodingStatus.QUERY_ANSWERED, "priority": CodingPriority.HIGH, "source_form": "AE_CRF", "source_field": "AETERM", "created_at": now - timedelta(days=35)},
            {"id": "CE-015", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3005", "source_term": "pneumonitis", "dictionary_type": DictionaryType.MEDDRA, "dictionary_version": "26.1", "coded_term": "Pneumonitis", "coded_code": "10035742", "meddra_pt": "Pneumonitis", "meddra_soc": "Respiratory, thoracic and mediastinal disorders", "meddra_llt": "Pneumonitis", "meddra_hlt": "Interstitial lung diseases", "status": CodingStatus.APPROVED, "priority": CodingPriority.URGENT, "auto_code_confidence": 0.94, "coded_by": "auto_coder", "coded_date": now - timedelta(days=28), "verified_by": "dr.liu", "verified_date": now - timedelta(days=26), "source_form": "AE_CRF", "source_field": "AETERM", "created_at": now - timedelta(days=30)},
        ]

        for ce in coding_entries_data:
            self._coding_entries[ce["id"]] = CodingEntry(**ce)

        # --- 12 Auto-Coding Rules ---
        auto_rules_data = [
            {"id": "ACR-001", "trial_id": None, "dictionary_type": DictionaryType.MEDDRA, "source_pattern": "headache", "target_code": "10019211", "target_term": "Headache", "confidence_threshold": 0.95, "match_type": "exact", "active": True, "hit_count": 342, "created_by": "coding_admin", "created_at": now - timedelta(days=200), "last_used": now - timedelta(days=2)},
            {"id": "ACR-002", "trial_id": None, "dictionary_type": DictionaryType.MEDDRA, "source_pattern": "nausea", "target_code": "10028813", "target_term": "Nausea", "confidence_threshold": 0.95, "match_type": "exact", "active": True, "hit_count": 278, "created_by": "coding_admin", "created_at": now - timedelta(days=200), "last_used": now - timedelta(days=1)},
            {"id": "ACR-003", "trial_id": None, "dictionary_type": DictionaryType.MEDDRA, "source_pattern": "fatigue", "target_code": "10016256", "target_term": "Fatigue", "confidence_threshold": 0.95, "match_type": "exact", "active": True, "hit_count": 456, "created_by": "coding_admin", "created_at": now - timedelta(days=200), "last_used": now - timedelta(days=1)},
            {"id": "ACR-004", "trial_id": EYLEA_TRIAL, "dictionary_type": DictionaryType.MEDDRA, "source_pattern": "eye pain", "target_code": "10015958", "target_term": "Eye pain", "confidence_threshold": 0.90, "match_type": "exact", "active": True, "hit_count": 89, "created_by": "coder_jones", "created_at": now - timedelta(days=150), "last_used": now - timedelta(days=5)},
            {"id": "ACR-005", "trial_id": EYLEA_TRIAL, "dictionary_type": DictionaryType.MEDDRA, "source_pattern": "vitreous floater%", "target_code": "10047654", "target_term": "Vitreous floaters", "confidence_threshold": 0.92, "match_type": "wildcard", "active": True, "hit_count": 45, "created_by": "coder_jones", "created_at": now - timedelta(days=140), "last_used": now - timedelta(days=10)},
            {"id": "ACR-006", "trial_id": DUPIXENT_TRIAL, "dictionary_type": DictionaryType.MEDDRA, "source_pattern": "injection site%", "target_code": "10022095", "target_term": "Injection site reaction", "confidence_threshold": 0.88, "match_type": "wildcard", "active": True, "hit_count": 167, "created_by": "coder_jones", "created_at": now - timedelta(days=130), "last_used": now - timedelta(days=3)},
            {"id": "ACR-007", "trial_id": None, "dictionary_type": DictionaryType.WHO_DRUG, "source_pattern": "ibuprofen%", "target_code": "M01AE01", "target_term": "Ibuprofen", "confidence_threshold": 0.95, "match_type": "wildcard", "active": True, "hit_count": 523, "created_by": "pharm_smith", "created_at": now - timedelta(days=180), "last_used": now - timedelta(days=1)},
            {"id": "ACR-008", "trial_id": None, "dictionary_type": DictionaryType.WHO_DRUG, "source_pattern": "paracetamol%", "target_code": "N02BE01", "target_term": "Paracetamol", "confidence_threshold": 0.95, "match_type": "wildcard", "active": True, "hit_count": 410, "created_by": "pharm_smith", "created_at": now - timedelta(days=180), "last_used": now - timedelta(days=2)},
            {"id": "ACR-009", "trial_id": LIBTAYO_TRIAL, "dictionary_type": DictionaryType.MEDDRA, "source_pattern": "pneumonitis", "target_code": "10035742", "target_term": "Pneumonitis", "confidence_threshold": 0.90, "match_type": "exact", "active": True, "hit_count": 34, "created_by": "coder_patel", "created_at": now - timedelta(days=100), "last_used": now - timedelta(days=15)},
            {"id": "ACR-010", "trial_id": None, "dictionary_type": DictionaryType.MEDDRA, "source_pattern": "diarrhoea", "target_code": "10012735", "target_term": "Diarrhoea", "confidence_threshold": 0.95, "match_type": "exact", "active": True, "hit_count": 198, "created_by": "coding_admin", "created_at": now - timedelta(days=200), "last_used": now - timedelta(days=4)},
            {"id": "ACR-011", "trial_id": None, "dictionary_type": DictionaryType.MEDDRA, "source_pattern": "rash%", "target_code": "10037844", "target_term": "Rash", "confidence_threshold": 0.80, "match_type": "wildcard", "active": False, "hit_count": 56, "created_by": "coding_admin", "created_at": now - timedelta(days=250), "last_used": now - timedelta(days=60)},
            {"id": "ACR-012", "trial_id": None, "dictionary_type": DictionaryType.WHO_DRUG, "source_pattern": "aspirin%", "target_code": "B01AC06", "target_term": "Acetylsalicylic acid", "confidence_threshold": 0.93, "match_type": "wildcard", "active": True, "hit_count": 312, "created_by": "pharm_smith", "created_at": now - timedelta(days=170), "last_used": now - timedelta(days=3)},
        ]

        for acr in auto_rules_data:
            self._auto_coding_rules[acr["id"]] = AutoCodingRule(**acr)

        # --- 10 Coding Queries ---
        coding_queries_data = [
            {"id": "CQ-001", "coding_entry_id": "CE-004", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1004", "query_text": "Source term 'mild headache after injection' is ambiguous. Is the headache an AE or a procedure-related symptom? Please clarify if this is a new onset headache.", "status": QueryStatus.OPEN, "priority": CodingPriority.HIGH, "assigned_to": "site_101_crc", "site_id": "SITE-101", "due_date": now + timedelta(days=7), "opened_by": "coder_jones", "opened_date": now - timedelta(days=38)},
            {"id": "CQ-002", "coding_entry_id": "CE-014", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3004", "query_text": "Source term 'thyroid function abnormal' needs clarification. Is this hypothyroidism or hyperthyroidism? Lab values needed for accurate MedDRA coding.", "status": QueryStatus.ANSWERED, "priority": CodingPriority.HIGH, "assigned_to": "site_107_pi", "response_text": "This is hypothyroidism based on elevated TSH (8.2 mIU/L) and low free T4 (0.6 ng/dL). Please code as hypothyroidism.", "response_by": "dr.foster_site107", "response_date": now - timedelta(days=28), "site_id": "SITE-107", "due_date": now - timedelta(days=25), "opened_by": "coder_patel", "opened_date": now - timedelta(days=33)},
            {"id": "CQ-003", "coding_entry_id": "CE-009", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2004", "query_text": "Source term 'skin rash with itching' - please specify the type of rash (maculopapular, urticarial, etc.) and body location for accurate MedDRA PT selection.", "status": QueryStatus.OPEN, "priority": CodingPriority.URGENT, "assigned_to": "site_105_crc", "site_id": "SITE-105", "due_date": now + timedelta(days=5), "opened_by": "coder_jones", "opened_date": now - timedelta(days=18)},
            {"id": "CQ-004", "coding_entry_id": "CE-005", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1005", "query_text": "Confirm IOP measurement value and whether the increase was from baseline or a new finding post-injection.", "status": QueryStatus.CLOSED, "priority": CodingPriority.MEDIUM, "assigned_to": "site_102_crc", "response_text": "IOP increased from 14 to 28 mmHg post-injection. New finding, resolved within 24 hours.", "response_by": "nurse_chen_site102", "response_date": now - timedelta(days=42), "site_id": "SITE-102", "due_date": now - timedelta(days=35), "opened_by": "coder_jones", "opened_date": now - timedelta(days=48), "closed_date": now - timedelta(days=40)},
            {"id": "CQ-005", "coding_entry_id": "CE-012", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3002", "query_text": "Source term includes 'immune related' qualifier. Should this be coded to 'Colitis' PT or 'Immune-mediated colitis' LLT?", "status": QueryStatus.CLOSED, "priority": CodingPriority.HIGH, "assigned_to": "medical_monitor", "response_text": "Per coding convention for immunotherapy trials, code to PT 'Colitis' and flag as immune-related in supplemental qualifier.", "response_by": "dr.liu_mm", "response_date": now - timedelta(days=52), "site_id": None, "due_date": now - timedelta(days=48), "opened_by": "coder_patel", "opened_date": now - timedelta(days=58), "closed_date": now - timedelta(days=50)},
            {"id": "CQ-006", "coding_entry_id": "CE-002", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1002", "query_text": "Subject reported 'blurred vision'. Is this a change from pre-existing condition or a new onset? Duration and severity needed.", "status": QueryStatus.CLOSED, "priority": CodingPriority.MEDIUM, "assigned_to": "site_101_crc", "response_text": "New onset, transient blurred vision lasting 2 hours post-injection. Mild severity. Not pre-existing.", "response_by": "crc_johnson_site101", "response_date": now - timedelta(days=72), "site_id": "SITE-101", "due_date": now - timedelta(days=68), "opened_by": "coder_jones", "opened_date": now - timedelta(days=78), "closed_date": now - timedelta(days=70)},
            {"id": "CQ-007", "coding_entry_id": "CE-007", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2002", "query_text": "Conjunctivitis reported - is this allergic, bacterial, or viral? Different MedDRA PTs apply based on etiology.", "status": QueryStatus.CLOSED, "priority": CodingPriority.MEDIUM, "assigned_to": "site_104_pi", "response_text": "Non-infectious conjunctivitis, consistent with known dupilumab-associated conjunctivitis. No cultures obtained.", "response_by": "dr.williams_site104", "response_date": now - timedelta(days=65), "site_id": "SITE-104", "due_date": now - timedelta(days=60), "opened_by": "coder_jones", "opened_date": now - timedelta(days=73), "closed_date": now - timedelta(days=63)},
            {"id": "CQ-008", "coding_entry_id": "CE-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2001", "query_text": "Injection site reaction - please specify the manifestation (erythema, swelling, pain, induration) for most specific LLT coding.", "status": QueryStatus.CANCELLED, "priority": CodingPriority.LOW, "assigned_to": "site_104_crc", "site_id": "SITE-104", "opened_by": "coder_jones", "opened_date": now - timedelta(days=93)},
            {"id": "CQ-009", "coding_entry_id": "CE-015", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3005", "query_text": "Pneumonitis grade and CTCAE version used for grading? Important for SAE determination.", "status": QueryStatus.ANSWERED, "priority": CodingPriority.URGENT, "assigned_to": "site_107_pi", "response_text": "Grade 2 pneumonitis per CTCAE v5.0. Required hospitalization for IV steroids. Resolved after 14 days.", "response_by": "dr.foster_site107", "response_date": now - timedelta(days=25), "site_id": "SITE-107", "due_date": now - timedelta(days=22), "opened_by": "coder_patel", "opened_date": now - timedelta(days=29)},
            {"id": "CQ-010", "coding_entry_id": "CE-011", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3001", "query_text": "Fatigue reported as Grade 1. Is this a continuation of baseline fatigue or new onset during treatment?", "status": QueryStatus.CLOSED, "priority": CodingPriority.LOW, "assigned_to": "site_107_crc", "response_text": "New onset fatigue starting Cycle 2 Day 1. Not present at baseline per ECOG assessment.", "response_by": "crc_lee_site107", "response_date": now - timedelta(days=96), "site_id": "SITE-107", "due_date": now - timedelta(days=90), "opened_by": "coder_patel", "opened_date": now - timedelta(days=103), "closed_date": now - timedelta(days=94)},
        ]

        for cq in coding_queries_data:
            self._coding_queries[cq["id"]] = CodingQuery(**cq)

        # --- 10 Coding Batches ---
        coding_batches_data = [
            {"id": "CB-001", "trial_id": EYLEA_TRIAL, "dictionary_type": DictionaryType.MEDDRA, "batch_name": "EYLEA AE Batch Week 12", "total_entries": 45, "coded_entries": 42, "auto_coded": 38, "manually_coded": 4, "pending_entries": 3, "queries_raised": 2, "status": "in_progress", "started_by": "coding_lead", "started_at": now - timedelta(days=90)},
            {"id": "CB-002", "trial_id": EYLEA_TRIAL, "dictionary_type": DictionaryType.MEDDRA, "batch_name": "EYLEA AE Batch Week 24", "total_entries": 62, "coded_entries": 62, "auto_coded": 55, "manually_coded": 7, "pending_entries": 0, "queries_raised": 5, "status": "completed", "started_by": "coding_lead", "started_at": now - timedelta(days=60), "completed_at": now - timedelta(days=45)},
            {"id": "CB-003", "trial_id": EYLEA_TRIAL, "dictionary_type": DictionaryType.WHO_DRUG, "batch_name": "EYLEA ConMed Batch Q3", "total_entries": 120, "coded_entries": 118, "auto_coded": 112, "manually_coded": 6, "pending_entries": 2, "queries_raised": 1, "status": "in_progress", "started_by": "pharm_smith", "started_at": now - timedelta(days=50)},
            {"id": "CB-004", "trial_id": DUPIXENT_TRIAL, "dictionary_type": DictionaryType.MEDDRA, "batch_name": "Dupixent AE Batch Week 16", "total_entries": 78, "coded_entries": 78, "auto_coded": 70, "manually_coded": 8, "pending_entries": 0, "queries_raised": 4, "status": "completed", "started_by": "coding_lead", "started_at": now - timedelta(days=100), "completed_at": now - timedelta(days=80)},
            {"id": "CB-005", "trial_id": DUPIXENT_TRIAL, "dictionary_type": DictionaryType.MEDDRA, "batch_name": "Dupixent AE Batch Week 24", "total_entries": 55, "coded_entries": 48, "auto_coded": 40, "manually_coded": 8, "pending_entries": 7, "queries_raised": 3, "status": "in_progress", "started_by": "coding_lead", "started_at": now - timedelta(days=40)},
            {"id": "CB-006", "trial_id": DUPIXENT_TRIAL, "dictionary_type": DictionaryType.WHO_DRUG, "batch_name": "Dupixent ConMed Batch Q3", "total_entries": 95, "coded_entries": 95, "auto_coded": 90, "manually_coded": 5, "pending_entries": 0, "queries_raised": 0, "status": "completed", "started_by": "pharm_smith", "started_at": now - timedelta(days=70), "completed_at": now - timedelta(days=55)},
            {"id": "CB-007", "trial_id": LIBTAYO_TRIAL, "dictionary_type": DictionaryType.MEDDRA, "batch_name": "Libtayo AE Batch Cycle 4", "total_entries": 40, "coded_entries": 40, "auto_coded": 32, "manually_coded": 8, "pending_entries": 0, "queries_raised": 6, "status": "completed", "started_by": "coding_lead", "started_at": now - timedelta(days=110), "completed_at": now - timedelta(days=90)},
            {"id": "CB-008", "trial_id": LIBTAYO_TRIAL, "dictionary_type": DictionaryType.MEDDRA, "batch_name": "Libtayo AE Batch Cycle 8", "total_entries": 52, "coded_entries": 45, "auto_coded": 35, "manually_coded": 10, "pending_entries": 7, "queries_raised": 4, "status": "in_progress", "started_by": "coding_lead", "started_at": now - timedelta(days=45)},
            {"id": "CB-009", "trial_id": LIBTAYO_TRIAL, "dictionary_type": DictionaryType.WHO_DRUG, "batch_name": "Libtayo ConMed Batch Q3", "total_entries": 85, "coded_entries": 85, "auto_coded": 80, "manually_coded": 5, "pending_entries": 0, "queries_raised": 1, "status": "completed", "started_by": "pharm_smith", "started_at": now - timedelta(days=65), "completed_at": now - timedelta(days=50)},
            {"id": "CB-010", "trial_id": LIBTAYO_TRIAL, "dictionary_type": DictionaryType.MEDDRA, "batch_name": "Libtayo SAE Urgent Coding", "total_entries": 12, "coded_entries": 10, "auto_coded": 6, "manually_coded": 4, "pending_entries": 2, "queries_raised": 3, "status": "in_progress", "started_by": "coder_patel", "started_at": now - timedelta(days=15)},
        ]

        for cb in coding_batches_data:
            self._coding_batches[cb["id"]] = CodingBatch(**cb)

    # ------------------------------------------------------------------
    # Dictionary Version Management
    # ------------------------------------------------------------------

    def list_dictionary_versions(
        self,
        *,
        dictionary_type: DictionaryType | None = None,
        active: bool | None = None,
    ) -> list[DictionaryVersion]:
        """List dictionary versions with optional filters."""
        with self._lock:
            result = list(self._dictionary_versions.values())

        if dictionary_type is not None:
            result = [dv for dv in result if dv.dictionary_type == dictionary_type]
        if active is not None:
            result = [dv for dv in result if dv.active == active]

        return sorted(result, key=lambda dv: dv.id)

    def get_dictionary_version(self, version_id: str) -> DictionaryVersion | None:
        """Get a single dictionary version by ID."""
        with self._lock:
            return self._dictionary_versions.get(version_id)

    def create_dictionary_version(self, payload: DictionaryVersionCreate) -> DictionaryVersion:
        """Create a new dictionary version."""
        version_id = f"DV-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        version = DictionaryVersion(
            id=version_id,
            dictionary_type=payload.dictionary_type,
            version=payload.version,
            release_date=payload.release_date,
            effective_date=payload.effective_date,
            total_terms=payload.total_terms,
            active=True,
            loaded_by=payload.loaded_by,
            loaded_at=now,
        )
        with self._lock:
            self._dictionary_versions[version_id] = version
        logger.info("Created dictionary version %s: %s %s", version_id, payload.dictionary_type.value, payload.version)
        return version

    def update_dictionary_version(
        self, version_id: str, payload: DictionaryVersionUpdate
    ) -> DictionaryVersion | None:
        """Update an existing dictionary version."""
        with self._lock:
            existing = self._dictionary_versions.get(version_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DictionaryVersion(**data)
            self._dictionary_versions[version_id] = updated
        return updated

    def delete_dictionary_version(self, version_id: str) -> bool:
        """Delete a dictionary version. Returns True if deleted."""
        with self._lock:
            if version_id in self._dictionary_versions:
                del self._dictionary_versions[version_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Coding Entry Management
    # ------------------------------------------------------------------

    def list_coding_entries(
        self,
        *,
        trial_id: str | None = None,
        status: CodingStatus | None = None,
        dictionary_type: DictionaryType | None = None,
        priority: CodingPriority | None = None,
    ) -> list[CodingEntry]:
        """List coding entries with optional filters."""
        with self._lock:
            result = list(self._coding_entries.values())

        if trial_id is not None:
            result = [ce for ce in result if ce.trial_id == trial_id]
        if status is not None:
            result = [ce for ce in result if ce.status == status]
        if dictionary_type is not None:
            result = [ce for ce in result if ce.dictionary_type == dictionary_type]
        if priority is not None:
            result = [ce for ce in result if ce.priority == priority]

        return sorted(result, key=lambda ce: ce.id)

    def get_coding_entry(self, entry_id: str) -> CodingEntry | None:
        """Get a single coding entry by ID."""
        with self._lock:
            return self._coding_entries.get(entry_id)

    def create_coding_entry(self, payload: CodingEntryCreate) -> CodingEntry:
        """Create a new coding entry."""
        entry_id = f"CE-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        entry = CodingEntry(
            id=entry_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            source_term=payload.source_term,
            dictionary_type=payload.dictionary_type,
            dictionary_version=payload.dictionary_version,
            priority=payload.priority,
            source_form=payload.source_form,
            source_field=payload.source_field,
            status=CodingStatus.PENDING,
            created_at=now,
        )
        with self._lock:
            self._coding_entries[entry_id] = entry
        logger.info("Created coding entry %s: trial=%s term='%s'", entry_id, payload.trial_id, payload.source_term)
        return entry

    def update_coding_entry(
        self, entry_id: str, payload: CodingEntryUpdate
    ) -> CodingEntry | None:
        """Update an existing coding entry."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._coding_entries.get(entry_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set coded_date when coded_by is provided
            if "coded_by" in updates and updates["coded_by"] is not None and existing.coded_date is None:
                updates["coded_date"] = now
            # Auto-set verified_date when verified_by is provided
            if "verified_by" in updates and updates["verified_by"] is not None and existing.verified_date is None:
                updates["verified_date"] = now

            data.update(updates)
            updated = CodingEntry(**data)
            self._coding_entries[entry_id] = updated
        return updated

    def delete_coding_entry(self, entry_id: str) -> bool:
        """Delete a coding entry. Returns True if deleted."""
        with self._lock:
            if entry_id in self._coding_entries:
                del self._coding_entries[entry_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Auto-Coding Rule Management
    # ------------------------------------------------------------------

    def list_auto_coding_rules(
        self,
        *,
        trial_id: str | None = None,
        dictionary_type: DictionaryType | None = None,
        active: bool | None = None,
    ) -> list[AutoCodingRule]:
        """List auto-coding rules with optional filters."""
        with self._lock:
            result = list(self._auto_coding_rules.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if dictionary_type is not None:
            result = [r for r in result if r.dictionary_type == dictionary_type]
        if active is not None:
            result = [r for r in result if r.active == active]

        return sorted(result, key=lambda r: r.id)

    def get_auto_coding_rule(self, rule_id: str) -> AutoCodingRule | None:
        """Get a single auto-coding rule by ID."""
        with self._lock:
            return self._auto_coding_rules.get(rule_id)

    def create_auto_coding_rule(self, payload: AutoCodingRuleCreate) -> AutoCodingRule:
        """Create a new auto-coding rule."""
        rule_id = f"ACR-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        rule = AutoCodingRule(
            id=rule_id,
            trial_id=payload.trial_id,
            dictionary_type=payload.dictionary_type,
            source_pattern=payload.source_pattern,
            target_code=payload.target_code,
            target_term=payload.target_term,
            confidence_threshold=payload.confidence_threshold,
            match_type=payload.match_type,
            active=True,
            hit_count=0,
            created_by=payload.created_by,
            created_at=now,
        )
        with self._lock:
            self._auto_coding_rules[rule_id] = rule
        logger.info("Created auto-coding rule %s: '%s' -> %s", rule_id, payload.source_pattern, payload.target_code)
        return rule

    def update_auto_coding_rule(
        self, rule_id: str, payload: AutoCodingRuleUpdate
    ) -> AutoCodingRule | None:
        """Update an existing auto-coding rule."""
        with self._lock:
            existing = self._auto_coding_rules.get(rule_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AutoCodingRule(**data)
            self._auto_coding_rules[rule_id] = updated
        return updated

    def delete_auto_coding_rule(self, rule_id: str) -> bool:
        """Delete an auto-coding rule. Returns True if deleted."""
        with self._lock:
            if rule_id in self._auto_coding_rules:
                del self._auto_coding_rules[rule_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Coding Query Management
    # ------------------------------------------------------------------

    def list_coding_queries(
        self,
        *,
        trial_id: str | None = None,
        status: QueryStatus | None = None,
        priority: CodingPriority | None = None,
    ) -> list[CodingQuery]:
        """List coding queries with optional filters."""
        with self._lock:
            result = list(self._coding_queries.values())

        if trial_id is not None:
            result = [cq for cq in result if cq.trial_id == trial_id]
        if status is not None:
            result = [cq for cq in result if cq.status == status]
        if priority is not None:
            result = [cq for cq in result if cq.priority == priority]

        return sorted(result, key=lambda cq: cq.id)

    def get_coding_query(self, query_id: str) -> CodingQuery | None:
        """Get a single coding query by ID."""
        with self._lock:
            return self._coding_queries.get(query_id)

    def create_coding_query(self, payload: CodingQueryCreate) -> CodingQuery:
        """Create a new coding query."""
        query_id = f"CQ-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        query = CodingQuery(
            id=query_id,
            coding_entry_id=payload.coding_entry_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            query_text=payload.query_text,
            status=QueryStatus.OPEN,
            priority=payload.priority,
            assigned_to=payload.assigned_to,
            site_id=payload.site_id,
            due_date=payload.due_date,
            opened_by=payload.opened_by,
            opened_date=now,
        )
        with self._lock:
            self._coding_queries[query_id] = query
        logger.info("Created coding query %s for entry %s", query_id, payload.coding_entry_id)
        return query

    def update_coding_query(
        self, query_id: str, payload: CodingQueryUpdate
    ) -> CodingQuery | None:
        """Update an existing coding query."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._coding_queries.get(query_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set response_date when response_by is provided
            if "response_by" in updates and updates["response_by"] is not None and existing.response_date is None:
                updates["response_date"] = now
            # Auto-set closed_date when status transitions to closed
            if "status" in updates and updates["status"] == QueryStatus.CLOSED and existing.closed_date is None:
                updates["closed_date"] = now

            data.update(updates)
            updated = CodingQuery(**data)
            self._coding_queries[query_id] = updated
        return updated

    def delete_coding_query(self, query_id: str) -> bool:
        """Delete a coding query. Returns True if deleted."""
        with self._lock:
            if query_id in self._coding_queries:
                del self._coding_queries[query_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Coding Batch Management
    # ------------------------------------------------------------------

    def list_coding_batches(
        self,
        *,
        trial_id: str | None = None,
        dictionary_type: DictionaryType | None = None,
        status: str | None = None,
    ) -> list[CodingBatch]:
        """List coding batches with optional filters."""
        with self._lock:
            result = list(self._coding_batches.values())

        if trial_id is not None:
            result = [cb for cb in result if cb.trial_id == trial_id]
        if dictionary_type is not None:
            result = [cb for cb in result if cb.dictionary_type == dictionary_type]
        if status is not None:
            result = [cb for cb in result if cb.status == status]

        return sorted(result, key=lambda cb: cb.id)

    def get_coding_batch(self, batch_id: str) -> CodingBatch | None:
        """Get a single coding batch by ID."""
        with self._lock:
            return self._coding_batches.get(batch_id)

    def create_coding_batch(self, payload: CodingBatchCreate) -> CodingBatch:
        """Create a new coding batch."""
        batch_id = f"CB-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        batch = CodingBatch(
            id=batch_id,
            trial_id=payload.trial_id,
            dictionary_type=payload.dictionary_type,
            batch_name=payload.batch_name,
            total_entries=0,
            coded_entries=0,
            auto_coded=0,
            manually_coded=0,
            pending_entries=0,
            queries_raised=0,
            status="in_progress",
            started_by=payload.started_by,
            started_at=now,
        )
        with self._lock:
            self._coding_batches[batch_id] = batch
        logger.info("Created coding batch %s: '%s'", batch_id, payload.batch_name)
        return batch

    def update_coding_batch(
        self, batch_id: str, payload: CodingBatchUpdate
    ) -> CodingBatch | None:
        """Update an existing coding batch."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._coding_batches.get(batch_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completed_at when status transitions to completed
            if "status" in updates and updates["status"] == "completed" and existing.completed_at is None:
                updates["completed_at"] = now

            data.update(updates)
            updated = CodingBatch(**data)
            self._coding_batches[batch_id] = updated
        return updated

    def delete_coding_batch(self, batch_id: str) -> bool:
        """Delete a coding batch. Returns True if deleted."""
        with self._lock:
            if batch_id in self._coding_batches:
                del self._coding_batches[batch_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> MedicalCodingMetrics:
        """Compute aggregated medical coding metrics."""
        with self._lock:
            dict_versions = list(self._dictionary_versions.values())
            entries = list(self._coding_entries.values())
            rules = list(self._auto_coding_rules.values())
            queries = list(self._coding_queries.values())
            batches = list(self._coding_batches.values())

        if trial_id is not None:
            entries = [e for e in entries if e.trial_id == trial_id]
            rules = [r for r in rules if r.trial_id == trial_id or r.trial_id is None]
            queries = [q for q in queries if q.trial_id == trial_id]
            batches = [b for b in batches if b.trial_id == trial_id]

        # Dictionary version metrics
        active_versions = sum(1 for dv in dict_versions if dv.active)

        # Entries by status
        entries_by_status: dict[str, int] = {}
        for e in entries:
            key = e.status.value
            entries_by_status[key] = entries_by_status.get(key, 0) + 1

        # Entries by dictionary
        entries_by_dictionary: dict[str, int] = {}
        for e in entries:
            key = e.dictionary_type.value
            entries_by_dictionary[key] = entries_by_dictionary.get(key, 0) + 1

        # Auto-code rate
        coded_entries = [e for e in entries if e.status != CodingStatus.PENDING]
        auto_coded = sum(1 for e in entries if e.status == CodingStatus.AUTO_CODED or (e.auto_code_confidence is not None and e.auto_code_confidence >= 0.9))
        auto_code_rate = (auto_coded / len(entries) * 100.0) if entries else 0.0

        # Rules
        active_rules = sum(1 for r in rules if r.active)

        # Queries by status
        queries_by_status: dict[str, int] = {}
        for q in queries:
            key = q.status.value
            queries_by_status[key] = queries_by_status.get(key, 0) + 1

        open_queries = sum(1 for q in queries if q.status == QueryStatus.OPEN)

        # Average query resolution days
        resolved_queries = [
            q for q in queries
            if q.closed_date is not None and q.opened_date is not None
        ]
        if resolved_queries:
            total_days = sum(
                (q.closed_date - q.opened_date).total_seconds() / 86400.0
                for q in resolved_queries
            )
            avg_query_resolution = round(total_days / len(resolved_queries), 1)
        else:
            avg_query_resolution = 0.0

        # Batches
        completed_batches = sum(1 for b in batches if b.status == "completed")

        return MedicalCodingMetrics(
            total_dictionary_versions=len(dict_versions),
            active_versions=active_versions,
            total_coding_entries=len(entries),
            entries_by_status=entries_by_status,
            entries_by_dictionary=entries_by_dictionary,
            auto_code_rate_pct=round(auto_code_rate, 1),
            total_auto_coding_rules=len(rules),
            active_rules=active_rules,
            total_queries=len(queries),
            queries_by_status=queries_by_status,
            open_queries=open_queries,
            avg_query_resolution_days=avg_query_resolution,
            total_batches=len(batches),
            completed_batches=completed_batches,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: MedicalCodingService | None = None
_instance_lock = threading.Lock()


def get_medical_coding_service() -> MedicalCodingService:
    """Return the singleton MedicalCodingService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MedicalCodingService()
    return _instance


def reset_medical_coding_service() -> MedicalCodingService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = MedicalCodingService()
    return _instance
