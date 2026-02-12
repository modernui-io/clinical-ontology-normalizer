"""CDISC Standards Management Service (CDISC-STD).

Manages CDISC compliance: SDTM domain mapping, ADaM dataset definitions,
controlled terminology management, define.xml generation, conformance
validation, and CDISC operational metrics.

Usage:
    from app.services.cdisc_standards_service import (
        get_cdisc_standards_service,
    )

    svc = get_cdisc_standards_service()
    domains = svc.list_sdtm_domains()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.cdisc_standards import (
    ADaMDataset,
    ADaMDatasetCreate,
    ADaMDatasetUpdate,
    CDISCMetrics,
    CDISCStandard,
    ConformanceResult,
    ConformanceResultCreate,
    ConformanceResultUpdate,
    ControlledTerm,
    ControlledTermCreate,
    DefineXML,
    DefineXMLCreate,
    DefineXMLUpdate,
    DomainClass,
    MappingStatus,
    SDTMDomain,
    SDTMDomainCreate,
    SDTMDomainUpdate,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class CDISCStandardsService:
    """In-memory CDISC Standards Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._sdtm_domains: dict[str, SDTMDomain] = {}
        self._adam_datasets: dict[str, ADaMDataset] = {}
        self._controlled_terms: dict[str, ControlledTerm] = {}
        self._define_xmls: dict[str, DefineXML] = {}
        self._conformance_results: dict[str, ConformanceResult] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic CDISC data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- SDTM Domains (12 records) ---
        sdtm_data = [
            {"id": "SDTM-001", "trial_id": EYLEA_TRIAL, "domain_code": "DM", "domain_name": "Demographics", "domain_class": DomainClass.SPECIAL_PURPOSE, "sdtm_version": "3.4", "description": "Subject demographic and baseline data for EYLEA HD trial", "key_variables": ["STUDYID", "USUBJID"], "total_variables": 25, "mapped_variables": 25, "status": MappingStatus.VALIDATED, "source_datasets": ["RAW_DM", "EDC_DM"], "programmer": "John Smith", "reviewer": "Jane Doe", "created_at": now - timedelta(days=120)},
            {"id": "SDTM-002", "trial_id": EYLEA_TRIAL, "domain_code": "AE", "domain_name": "Adverse Events", "domain_class": DomainClass.EVENTS, "sdtm_version": "3.4", "description": "Adverse event data for EYLEA HD Phase III", "key_variables": ["STUDYID", "USUBJID", "AESEQ"], "total_variables": 32, "mapped_variables": 30, "status": MappingStatus.MAPPED, "source_datasets": ["RAW_AE", "EDC_AE", "SAE_LOG"], "programmer": "John Smith", "reviewer": "Jane Doe", "created_at": now - timedelta(days=115)},
            {"id": "SDTM-003", "trial_id": EYLEA_TRIAL, "domain_code": "LB", "domain_name": "Laboratory Test Results", "domain_class": DomainClass.FINDINGS, "sdtm_version": "3.4", "description": "Central and local lab results for EYLEA HD", "key_variables": ["STUDYID", "USUBJID", "LBSEQ"], "total_variables": 40, "mapped_variables": 35, "status": MappingStatus.IN_PROGRESS, "source_datasets": ["CENTRAL_LAB", "LOCAL_LAB"], "programmer": "Sarah Chen", "reviewer": None, "created_at": now - timedelta(days=110)},
            {"id": "SDTM-004", "trial_id": EYLEA_TRIAL, "domain_code": "CM", "domain_name": "Concomitant Medications", "domain_class": DomainClass.INTERVENTIONS, "sdtm_version": "3.4", "description": "Prior and concomitant medication records", "key_variables": ["STUDYID", "USUBJID", "CMSEQ"], "total_variables": 28, "mapped_variables": 28, "status": MappingStatus.APPROVED, "source_datasets": ["RAW_CM"], "programmer": "Sarah Chen", "reviewer": "Michael Brown", "created_at": now - timedelta(days=105)},
            {"id": "SDTM-005", "trial_id": DUPIXENT_TRIAL, "domain_code": "DM", "domain_name": "Demographics", "domain_class": DomainClass.SPECIAL_PURPOSE, "sdtm_version": "3.4", "description": "Subject demographic data for Dupixent atopic dermatitis trial", "key_variables": ["STUDYID", "USUBJID"], "total_variables": 25, "mapped_variables": 25, "status": MappingStatus.VALIDATED, "source_datasets": ["RAW_DM"], "programmer": "Lisa Wang", "reviewer": "Robert Kim", "created_at": now - timedelta(days=100)},
            {"id": "SDTM-006", "trial_id": DUPIXENT_TRIAL, "domain_code": "QS", "domain_name": "Questionnaires", "domain_class": DomainClass.FINDINGS, "sdtm_version": "3.4", "description": "EASI, IGA, DLQI, NRS questionnaire results", "key_variables": ["STUDYID", "USUBJID", "QSSEQ"], "total_variables": 22, "mapped_variables": 18, "status": MappingStatus.IN_PROGRESS, "source_datasets": ["EDC_QS", "EASI_SCORES"], "programmer": "Lisa Wang", "reviewer": None, "created_at": now - timedelta(days=95)},
            {"id": "SDTM-007", "trial_id": DUPIXENT_TRIAL, "domain_code": "EX", "domain_name": "Exposure", "domain_class": DomainClass.INTERVENTIONS, "sdtm_version": "3.4", "description": "Dupixent dosing and exposure data", "key_variables": ["STUDYID", "USUBJID", "EXSEQ"], "total_variables": 20, "mapped_variables": 20, "status": MappingStatus.APPROVED, "source_datasets": ["IRT_DOSING", "EDC_EX"], "programmer": "David Park", "reviewer": "Robert Kim", "created_at": now - timedelta(days=90)},
            {"id": "SDTM-008", "trial_id": DUPIXENT_TRIAL, "domain_code": "VS", "domain_name": "Vital Signs", "domain_class": DomainClass.FINDINGS, "sdtm_version": "3.4", "description": "Vital signs measurements for Dupixent trial", "key_variables": ["STUDYID", "USUBJID", "VSSEQ"], "total_variables": 18, "mapped_variables": 18, "status": MappingStatus.VALIDATED, "source_datasets": ["EDC_VS"], "programmer": "David Park", "reviewer": "Robert Kim", "created_at": now - timedelta(days=85)},
            {"id": "SDTM-009", "trial_id": LIBTAYO_TRIAL, "domain_code": "DM", "domain_name": "Demographics", "domain_class": DomainClass.SPECIAL_PURPOSE, "sdtm_version": "3.4", "description": "Subject demographic data for Libtayo oncology trial", "key_variables": ["STUDYID", "USUBJID"], "total_variables": 25, "mapped_variables": 22, "status": MappingStatus.MAPPED, "source_datasets": ["RAW_DM", "SITE_DM"], "programmer": "Emily Zhang", "reviewer": None, "created_at": now - timedelta(days=80)},
            {"id": "SDTM-010", "trial_id": LIBTAYO_TRIAL, "domain_code": "RS", "domain_name": "Disease Response", "domain_class": DomainClass.FINDINGS, "sdtm_version": "3.4", "description": "RECIST 1.1 tumor response assessments", "key_variables": ["STUDYID", "USUBJID", "RSSEQ"], "total_variables": 30, "mapped_variables": 15, "status": MappingStatus.IN_PROGRESS, "source_datasets": ["IMAGING_RS", "IRC_RS"], "programmer": "Emily Zhang", "reviewer": None, "created_at": now - timedelta(days=75)},
            {"id": "SDTM-011", "trial_id": LIBTAYO_TRIAL, "domain_code": "TU", "domain_name": "Tumor/Lesion Identification", "domain_class": DomainClass.FINDINGS, "sdtm_version": "3.4", "description": "Target and non-target lesion identification", "key_variables": ["STUDYID", "USUBJID", "TUSEQ"], "total_variables": 24, "mapped_variables": 0, "status": MappingStatus.NOT_STARTED, "source_datasets": ["IMAGING_TU"], "programmer": "Emily Zhang", "reviewer": None, "created_at": now - timedelta(days=70)},
            {"id": "SDTM-012", "trial_id": LIBTAYO_TRIAL, "domain_code": "TA", "domain_name": "Trial Arms", "domain_class": DomainClass.TRIAL_DESIGN, "sdtm_version": "3.4", "description": "Trial arm definitions for Libtayo study", "key_variables": ["STUDYID", "ARMCD"], "total_variables": 8, "mapped_variables": 8, "status": MappingStatus.APPROVED, "source_datasets": ["PROTOCOL"], "programmer": "Emily Zhang", "reviewer": "Mark Lee", "created_at": now - timedelta(days=65)},
        ]

        for d in sdtm_data:
            self._sdtm_domains[d["id"]] = SDTMDomain(**d)

        # --- ADaM Datasets (10 records) ---
        adam_data = [
            {"id": "ADAM-001", "trial_id": EYLEA_TRIAL, "dataset_name": "ADSL", "dataset_label": "Subject-Level Analysis Dataset", "adam_version": "1.3", "source_domains": ["DM", "EX", "DS"], "total_variables": 60, "derived_variables": 35, "status": MappingStatus.VALIDATED, "analysis_purpose": "Subject-level baseline and disposition", "population_flag": "SAFFL", "programmer": "John Smith", "reviewer": "Jane Doe", "created_at": now - timedelta(days=100)},
            {"id": "ADAM-002", "trial_id": EYLEA_TRIAL, "dataset_name": "ADAE", "dataset_label": "Adverse Event Analysis Dataset", "adam_version": "1.3", "source_domains": ["AE", "ADSL"], "total_variables": 45, "derived_variables": 20, "status": MappingStatus.MAPPED, "analysis_purpose": "Adverse event analysis including TEAEs", "population_flag": "SAFFL", "programmer": "John Smith", "reviewer": None, "created_at": now - timedelta(days=95)},
            {"id": "ADAM-003", "trial_id": EYLEA_TRIAL, "dataset_name": "ADBCVA", "dataset_label": "BCVA Analysis Dataset", "adam_version": "1.3", "source_domains": ["OE", "ADSL"], "total_variables": 50, "derived_variables": 30, "status": MappingStatus.IN_PROGRESS, "analysis_purpose": "Primary efficacy: Best Corrected Visual Acuity", "population_flag": "ITTFL", "programmer": "Sarah Chen", "reviewer": None, "created_at": now - timedelta(days=90)},
            {"id": "ADAM-004", "trial_id": DUPIXENT_TRIAL, "dataset_name": "ADSL", "dataset_label": "Subject-Level Analysis Dataset", "adam_version": "1.3", "source_domains": ["DM", "EX", "DS"], "total_variables": 55, "derived_variables": 30, "status": MappingStatus.APPROVED, "analysis_purpose": "Subject-level baseline and disposition", "population_flag": "SAFFL", "programmer": "Lisa Wang", "reviewer": "Robert Kim", "created_at": now - timedelta(days=85)},
            {"id": "ADAM-005", "trial_id": DUPIXENT_TRIAL, "dataset_name": "ADEASI", "dataset_label": "EASI Score Analysis Dataset", "adam_version": "1.3", "source_domains": ["QS", "ADSL"], "total_variables": 40, "derived_variables": 25, "status": MappingStatus.MAPPED, "analysis_purpose": "Primary efficacy: EASI-75 response rate", "population_flag": "ITTFL", "programmer": "Lisa Wang", "reviewer": None, "created_at": now - timedelta(days=80)},
            {"id": "ADAM-006", "trial_id": DUPIXENT_TRIAL, "dataset_name": "ADIGA", "dataset_label": "IGA Score Analysis Dataset", "adam_version": "1.3", "source_domains": ["QS", "ADSL"], "total_variables": 35, "derived_variables": 18, "status": MappingStatus.IN_PROGRESS, "analysis_purpose": "Co-primary efficacy: IGA 0/1 response", "population_flag": "ITTFL", "programmer": "David Park", "reviewer": None, "created_at": now - timedelta(days=75)},
            {"id": "ADAM-007", "trial_id": LIBTAYO_TRIAL, "dataset_name": "ADSL", "dataset_label": "Subject-Level Analysis Dataset", "adam_version": "1.3", "source_domains": ["DM", "EX", "DS"], "total_variables": 65, "derived_variables": 40, "status": MappingStatus.VALIDATED, "analysis_purpose": "Subject-level baseline and disposition", "population_flag": "SAFFL", "programmer": "Emily Zhang", "reviewer": "Mark Lee", "created_at": now - timedelta(days=70)},
            {"id": "ADAM-008", "trial_id": LIBTAYO_TRIAL, "dataset_name": "ADRS", "dataset_label": "Tumor Response Analysis Dataset", "adam_version": "1.3", "source_domains": ["RS", "TU", "ADSL"], "total_variables": 55, "derived_variables": 35, "status": MappingStatus.IN_PROGRESS, "analysis_purpose": "Primary efficacy: ORR per RECIST 1.1", "population_flag": "ITTFL", "programmer": "Emily Zhang", "reviewer": None, "created_at": now - timedelta(days=65)},
            {"id": "ADAM-009", "trial_id": LIBTAYO_TRIAL, "dataset_name": "ADTTE", "dataset_label": "Time-to-Event Analysis Dataset", "adam_version": "1.3", "source_domains": ["RS", "DS", "ADSL"], "total_variables": 30, "derived_variables": 20, "status": MappingStatus.NOT_STARTED, "analysis_purpose": "Secondary efficacy: PFS and OS", "population_flag": "ITTFL", "programmer": "Emily Zhang", "reviewer": None, "created_at": now - timedelta(days=60)},
            {"id": "ADAM-010", "trial_id": EYLEA_TRIAL, "dataset_name": "ADLB", "dataset_label": "Laboratory Analysis Dataset", "adam_version": "1.3", "source_domains": ["LB", "ADSL"], "total_variables": 42, "derived_variables": 15, "status": MappingStatus.MAPPED, "analysis_purpose": "Safety laboratory analysis", "population_flag": "SAFFL", "programmer": "Sarah Chen", "reviewer": "Jane Doe", "created_at": now - timedelta(days=55)},
        ]

        for a in adam_data:
            self._adam_datasets[a["id"]] = ADaMDataset(**a)

        # --- Controlled Terms (12 records) ---
        ct_data = [
            {"id": "CT-001", "trial_id": None, "codelist_code": "C66726", "codelist_name": "Sex", "term_code": "C16576", "term_value": "F", "decoded_value": "Female", "ct_version": "2024-03-29", "standard": CDISCStandard.SDTM, "extensible": False, "custom": False, "created_at": now - timedelta(days=200)},
            {"id": "CT-002", "trial_id": None, "codelist_code": "C66726", "codelist_name": "Sex", "term_code": "C20197", "term_value": "M", "decoded_value": "Male", "ct_version": "2024-03-29", "standard": CDISCStandard.SDTM, "extensible": False, "custom": False, "created_at": now - timedelta(days=200)},
            {"id": "CT-003", "trial_id": None, "codelist_code": "C66742", "codelist_name": "Race", "term_code": "C41261", "term_value": "ASIAN", "decoded_value": "Asian", "ct_version": "2024-03-29", "standard": CDISCStandard.SDTM, "extensible": True, "custom": False, "created_at": now - timedelta(days=200)},
            {"id": "CT-004", "trial_id": None, "codelist_code": "C66767", "codelist_name": "Severity/Intensity Scale for AE", "term_code": "C41338", "term_value": "MILD", "decoded_value": "Mild", "ct_version": "2024-03-29", "standard": CDISCStandard.SDTM, "extensible": False, "custom": False, "created_at": now - timedelta(days=195)},
            {"id": "CT-005", "trial_id": None, "codelist_code": "C66767", "codelist_name": "Severity/Intensity Scale for AE", "term_code": "C41339", "term_value": "MODERATE", "decoded_value": "Moderate", "ct_version": "2024-03-29", "standard": CDISCStandard.SDTM, "extensible": False, "custom": False, "created_at": now - timedelta(days=195)},
            {"id": "CT-006", "trial_id": None, "codelist_code": "C66767", "codelist_name": "Severity/Intensity Scale for AE", "term_code": "C41340", "term_value": "SEVERE", "decoded_value": "Severe", "ct_version": "2024-03-29", "standard": CDISCStandard.SDTM, "extensible": False, "custom": False, "created_at": now - timedelta(days=195)},
            {"id": "CT-007", "trial_id": None, "codelist_code": "C66728", "codelist_name": "Unit", "term_code": "C28253", "term_value": "mg", "decoded_value": "Milligram", "ct_version": "2024-03-29", "standard": CDISCStandard.SDTM, "extensible": True, "custom": False, "created_at": now - timedelta(days=190)},
            {"id": "CT-008", "trial_id": None, "codelist_code": "C71113", "codelist_name": "Lab Test Code", "term_code": "C64849", "term_value": "ALT", "decoded_value": "Alanine Aminotransferase", "ct_version": "2024-03-29", "standard": CDISCStandard.SDTM, "extensible": True, "custom": False, "created_at": now - timedelta(days=185)},
            {"id": "CT-009", "trial_id": EYLEA_TRIAL, "codelist_code": "EYLEA_ROUTE", "codelist_name": "Route of Administration", "term_code": "EYLEA_IVT", "term_value": "INTRAVITREAL", "decoded_value": "Intravitreal Injection", "ct_version": "2024-03-29", "standard": CDISCStandard.SDTM, "extensible": True, "custom": True, "created_at": now - timedelta(days=180)},
            {"id": "CT-010", "trial_id": DUPIXENT_TRIAL, "codelist_code": "DUPX_SCORE", "codelist_name": "EASI Score Category", "term_code": "DUPX_EASI75", "term_value": "EASI75", "decoded_value": "EASI-75 Response", "ct_version": "2024-03-29", "standard": CDISCStandard.ADAM, "extensible": True, "custom": True, "created_at": now - timedelta(days=175)},
            {"id": "CT-011", "trial_id": LIBTAYO_TRIAL, "codelist_code": "LIBT_RESP", "codelist_name": "RECIST Response Category", "term_code": "LIBT_PR", "term_value": "PR", "decoded_value": "Partial Response", "ct_version": "2024-03-29", "standard": CDISCStandard.ADAM, "extensible": True, "custom": True, "created_at": now - timedelta(days=170)},
            {"id": "CT-012", "trial_id": None, "codelist_code": "C66731", "codelist_name": "Yes No", "term_code": "C49488", "term_value": "Y", "decoded_value": "Yes", "ct_version": "2024-03-29", "standard": CDISCStandard.CDASH, "extensible": False, "custom": False, "created_at": now - timedelta(days=200)},
        ]

        for c in ct_data:
            self._controlled_terms[c["id"]] = ControlledTerm(**c)

        # --- Define XMLs (10 records) ---
        define_data = [
            {"id": "DEF-001", "trial_id": EYLEA_TRIAL, "standard": CDISCStandard.SDTM, "version": "2.1.0", "file_name": "define-sdtm-eylea.xml", "status": "final", "total_datasets": 15, "total_variables": 280, "total_codelists": 45, "total_methods": 12, "total_comments": 30, "generated_date": now - timedelta(days=30), "validated": True, "validation_errors": 0, "author": "John Smith", "created_at": now - timedelta(days=60)},
            {"id": "DEF-002", "trial_id": EYLEA_TRIAL, "standard": CDISCStandard.ADAM, "version": "2.1.0", "file_name": "define-adam-eylea.xml", "status": "draft", "total_datasets": 8, "total_variables": 220, "total_codelists": 30, "total_methods": 25, "total_comments": 15, "generated_date": now - timedelta(days=15), "validated": False, "validation_errors": 3, "author": "John Smith", "created_at": now - timedelta(days=50)},
            {"id": "DEF-003", "trial_id": DUPIXENT_TRIAL, "standard": CDISCStandard.SDTM, "version": "2.1.0", "file_name": "define-sdtm-dupixent.xml", "status": "final", "total_datasets": 18, "total_variables": 320, "total_codelists": 55, "total_methods": 15, "total_comments": 40, "generated_date": now - timedelta(days=25), "validated": True, "validation_errors": 0, "author": "Lisa Wang", "created_at": now - timedelta(days=55)},
            {"id": "DEF-004", "trial_id": DUPIXENT_TRIAL, "standard": CDISCStandard.ADAM, "version": "2.1.0", "file_name": "define-adam-dupixent.xml", "status": "review", "total_datasets": 6, "total_variables": 180, "total_codelists": 25, "total_methods": 18, "total_comments": 10, "generated_date": now - timedelta(days=10), "validated": True, "validation_errors": 2, "author": "Lisa Wang", "created_at": now - timedelta(days=45)},
            {"id": "DEF-005", "trial_id": LIBTAYO_TRIAL, "standard": CDISCStandard.SDTM, "version": "2.1.0", "file_name": "define-sdtm-libtayo.xml", "status": "draft", "total_datasets": 20, "total_variables": 350, "total_codelists": 60, "total_methods": 20, "total_comments": 25, "generated_date": None, "validated": False, "validation_errors": 8, "author": "Emily Zhang", "created_at": now - timedelta(days=40)},
            {"id": "DEF-006", "trial_id": LIBTAYO_TRIAL, "standard": CDISCStandard.ADAM, "version": "2.1.0", "file_name": "define-adam-libtayo.xml", "status": "draft", "total_datasets": 5, "total_variables": 150, "total_codelists": 20, "total_methods": 15, "total_comments": 8, "generated_date": None, "validated": False, "validation_errors": 5, "author": "Emily Zhang", "created_at": now - timedelta(days=35)},
            {"id": "DEF-007", "trial_id": EYLEA_TRIAL, "standard": CDISCStandard.SEND, "version": "2.1.0", "file_name": "define-send-eylea.xml", "status": "final", "total_datasets": 10, "total_variables": 120, "total_codelists": 30, "total_methods": 5, "total_comments": 10, "generated_date": now - timedelta(days=90), "validated": True, "validation_errors": 0, "author": "Sarah Chen", "created_at": now - timedelta(days=120)},
            {"id": "DEF-008", "trial_id": DUPIXENT_TRIAL, "standard": CDISCStandard.DEFINE_XML, "version": "2.1.0", "file_name": "define-consolidated-dupixent.xml", "status": "final", "total_datasets": 24, "total_variables": 500, "total_codelists": 80, "total_methods": 33, "total_comments": 50, "generated_date": now - timedelta(days=20), "validated": True, "validation_errors": 0, "author": "David Park", "created_at": now - timedelta(days=30)},
            {"id": "DEF-009", "trial_id": LIBTAYO_TRIAL, "standard": CDISCStandard.CDASH, "version": "2.1.0", "file_name": "define-cdash-libtayo.xml", "status": "review", "total_datasets": 12, "total_variables": 200, "total_codelists": 40, "total_methods": 0, "total_comments": 20, "generated_date": now - timedelta(days=5), "validated": False, "validation_errors": 1, "author": "Mark Lee", "created_at": now - timedelta(days=25)},
            {"id": "DEF-010", "trial_id": EYLEA_TRIAL, "standard": CDISCStandard.DEFINE_XML, "version": "2.1.0", "file_name": "define-consolidated-eylea.xml", "status": "review", "total_datasets": 23, "total_variables": 500, "total_codelists": 75, "total_methods": 37, "total_comments": 45, "generated_date": now - timedelta(days=8), "validated": True, "validation_errors": 1, "author": "Jane Doe", "created_at": now - timedelta(days=20)},
        ]

        for d in define_data:
            self._define_xmls[d["id"]] = DefineXML(**d)

        # --- Conformance Results (15 records) ---
        conformance_data = [
            {"id": "CFR-001", "trial_id": EYLEA_TRIAL, "standard": CDISCStandard.SDTM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=28), "dataset_name": "DM", "rule_id": "SD0020", "severity": ValidationSeverity.ERROR, "message": "Missing required variable ARMCD in DM domain", "variable": "ARMCD", "record_count": 0, "status": "resolved", "resolution": "Added ARMCD variable from randomization data", "resolved_by": "John Smith", "resolved_date": now - timedelta(days=25)},
            {"id": "CFR-002", "trial_id": EYLEA_TRIAL, "standard": CDISCStandard.SDTM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=28), "dataset_name": "AE", "rule_id": "SD0055", "severity": ValidationSeverity.WARNING, "message": "AESER values not consistent with AESEV for 12 records", "variable": "AESER", "record_count": 12, "status": "open", "resolution": None, "resolved_by": None, "resolved_date": None},
            {"id": "CFR-003", "trial_id": EYLEA_TRIAL, "standard": CDISCStandard.SDTM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=28), "dataset_name": "LB", "rule_id": "SD0072", "severity": ValidationSeverity.ERROR, "message": "LBORRESU missing for 45 lab records", "variable": "LBORRESU", "record_count": 45, "status": "open", "resolution": None, "resolved_by": None, "resolved_date": None},
            {"id": "CFR-004", "trial_id": EYLEA_TRIAL, "standard": CDISCStandard.ADAM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=20), "dataset_name": "ADSL", "rule_id": "AD0015", "severity": ValidationSeverity.NOTICE, "message": "TRTDUR derived differently than ADaM IG recommendation", "variable": "TRTDUR", "record_count": 0, "status": "open", "resolution": None, "resolved_by": None, "resolved_date": None},
            {"id": "CFR-005", "trial_id": DUPIXENT_TRIAL, "standard": CDISCStandard.SDTM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=22), "dataset_name": "DM", "rule_id": "SD0003", "severity": ValidationSeverity.INFO, "message": "SUBJID contains leading zeros - acceptable per study convention", "variable": "SUBJID", "record_count": 150, "status": "closed", "resolution": "Documented as acceptable per study convention", "resolved_by": "Lisa Wang", "resolved_date": now - timedelta(days=20)},
            {"id": "CFR-006", "trial_id": DUPIXENT_TRIAL, "standard": CDISCStandard.SDTM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=22), "dataset_name": "QS", "rule_id": "SD0084", "severity": ValidationSeverity.ERROR, "message": "QSORRES missing for 23 EASI records", "variable": "QSORRES", "record_count": 23, "status": "open", "resolution": None, "resolved_by": None, "resolved_date": None},
            {"id": "CFR-007", "trial_id": DUPIXENT_TRIAL, "standard": CDISCStandard.SDTM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=22), "dataset_name": "EX", "rule_id": "SD0045", "severity": ValidationSeverity.WARNING, "message": "EXDOSE inconsistencies between IRT and CRF for 8 subjects", "variable": "EXDOSE", "record_count": 8, "status": "open", "resolution": None, "resolved_by": None, "resolved_date": None},
            {"id": "CFR-008", "trial_id": DUPIXENT_TRIAL, "standard": CDISCStandard.ADAM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=18), "dataset_name": "ADEASI", "rule_id": "AD0033", "severity": ValidationSeverity.ERROR, "message": "ANL01FL derivation logic does not match SAP", "variable": "ANL01FL", "record_count": 0, "status": "open", "resolution": None, "resolved_by": None, "resolved_date": None},
            {"id": "CFR-009", "trial_id": LIBTAYO_TRIAL, "standard": CDISCStandard.SDTM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=15), "dataset_name": "RS", "rule_id": "SD0090", "severity": ValidationSeverity.ERROR, "message": "RSORRES uses non-standard response values for 5 records", "variable": "RSORRES", "record_count": 5, "status": "open", "resolution": None, "resolved_by": None, "resolved_date": None},
            {"id": "CFR-010", "trial_id": LIBTAYO_TRIAL, "standard": CDISCStandard.SDTM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=15), "dataset_name": "TU", "rule_id": "SD0095", "severity": ValidationSeverity.WARNING, "message": "TULOC values inconsistent with TUTESTCD for 3 records", "variable": "TULOC", "record_count": 3, "status": "open", "resolution": None, "resolved_by": None, "resolved_date": None},
            {"id": "CFR-011", "trial_id": LIBTAYO_TRIAL, "standard": CDISCStandard.SDTM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=15), "dataset_name": "DM", "rule_id": "SD0020", "severity": ValidationSeverity.ERROR, "message": "RFSTDTC missing for 2 subjects who received treatment", "variable": "RFSTDTC", "record_count": 2, "status": "open", "resolution": None, "resolved_by": None, "resolved_date": None},
            {"id": "CFR-012", "trial_id": LIBTAYO_TRIAL, "standard": CDISCStandard.ADAM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=12), "dataset_name": "ADRS", "rule_id": "AD0050", "severity": ValidationSeverity.ERROR, "message": "PARAM values do not use CDISC controlled terminology", "variable": "PARAM", "record_count": 0, "status": "open", "resolution": None, "resolved_by": None, "resolved_date": None},
            {"id": "CFR-013", "trial_id": EYLEA_TRIAL, "standard": CDISCStandard.SDTM, "validation_tool": "OpenCDISC Validator", "validation_date": now - timedelta(days=35), "dataset_name": "CM", "rule_id": "SD0040", "severity": ValidationSeverity.NOTICE, "message": "CMTRT free-text values could be mapped to WHO Drug dictionary", "variable": "CMTRT", "record_count": 85, "status": "closed", "resolution": "WHO Drug coding completed", "resolved_by": "Sarah Chen", "resolved_date": now - timedelta(days=30)},
            {"id": "CFR-014", "trial_id": DUPIXENT_TRIAL, "standard": CDISCStandard.SDTM, "validation_tool": "OpenCDISC Validator", "validation_date": now - timedelta(days=30), "dataset_name": "VS", "rule_id": "SD0060", "severity": ValidationSeverity.INFO, "message": "VSPOS not populated for seated vital signs", "variable": "VSPOS", "record_count": 200, "status": "closed", "resolution": "VSPOS populated per protocol specification", "resolved_by": "David Park", "resolved_date": now - timedelta(days=27)},
            {"id": "CFR-015", "trial_id": LIBTAYO_TRIAL, "standard": CDISCStandard.ADAM, "validation_tool": "Pinnacle 21 Enterprise", "validation_date": now - timedelta(days=10), "dataset_name": "ADTTE", "rule_id": "AD0055", "severity": ValidationSeverity.WARNING, "message": "CNSR derivation does not account for lost to follow-up", "variable": "CNSR", "record_count": 0, "status": "open", "resolution": None, "resolved_by": None, "resolved_date": None},
        ]

        for c in conformance_data:
            self._conformance_results[c["id"]] = ConformanceResult(**c)

    # ------------------------------------------------------------------
    # SDTM Domain Management
    # ------------------------------------------------------------------

    def list_sdtm_domains(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[SDTMDomain]:
        """List SDTM domains with optional trial filter."""
        with self._lock:
            result = list(self._sdtm_domains.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]

        return sorted(result, key=lambda d: d.id)

    def get_sdtm_domain(self, domain_id: str) -> SDTMDomain | None:
        """Get a single SDTM domain by ID."""
        with self._lock:
            return self._sdtm_domains.get(domain_id)

    def create_sdtm_domain(self, payload: SDTMDomainCreate) -> SDTMDomain:
        """Create a new SDTM domain."""
        domain_id = f"SDTM-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        domain = SDTMDomain(
            id=domain_id,
            trial_id=payload.trial_id,
            domain_code=payload.domain_code,
            domain_name=payload.domain_name,
            domain_class=payload.domain_class,
            sdtm_version=payload.sdtm_version,
            description=payload.description,
            key_variables=payload.key_variables,
            programmer=payload.programmer,
            created_at=now,
        )
        with self._lock:
            self._sdtm_domains[domain_id] = domain
        logger.info("Created SDTM domain %s: %s", domain_id, payload.domain_code)
        return domain

    def update_sdtm_domain(
        self, domain_id: str, payload: SDTMDomainUpdate
    ) -> SDTMDomain | None:
        """Update an existing SDTM domain."""
        with self._lock:
            existing = self._sdtm_domains.get(domain_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SDTMDomain(**data)
            self._sdtm_domains[domain_id] = updated
        return updated

    def delete_sdtm_domain(self, domain_id: str) -> bool:
        """Delete an SDTM domain. Returns True if deleted."""
        with self._lock:
            if domain_id in self._sdtm_domains:
                del self._sdtm_domains[domain_id]
                return True
            return False

    # ------------------------------------------------------------------
    # ADaM Dataset Management
    # ------------------------------------------------------------------

    def list_adam_datasets(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[ADaMDataset]:
        """List ADaM datasets with optional trial filter."""
        with self._lock:
            result = list(self._adam_datasets.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]

        return sorted(result, key=lambda d: d.id)

    def get_adam_dataset(self, dataset_id: str) -> ADaMDataset | None:
        """Get a single ADaM dataset by ID."""
        with self._lock:
            return self._adam_datasets.get(dataset_id)

    def create_adam_dataset(self, payload: ADaMDatasetCreate) -> ADaMDataset:
        """Create a new ADaM dataset."""
        dataset_id = f"ADAM-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        dataset = ADaMDataset(
            id=dataset_id,
            trial_id=payload.trial_id,
            dataset_name=payload.dataset_name,
            dataset_label=payload.dataset_label,
            adam_version=payload.adam_version,
            source_domains=payload.source_domains,
            programmer=payload.programmer,
            analysis_purpose=payload.analysis_purpose,
            created_at=now,
        )
        with self._lock:
            self._adam_datasets[dataset_id] = dataset
        logger.info("Created ADaM dataset %s: %s", dataset_id, payload.dataset_name)
        return dataset

    def update_adam_dataset(
        self, dataset_id: str, payload: ADaMDatasetUpdate
    ) -> ADaMDataset | None:
        """Update an existing ADaM dataset."""
        with self._lock:
            existing = self._adam_datasets.get(dataset_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ADaMDataset(**data)
            self._adam_datasets[dataset_id] = updated
        return updated

    def delete_adam_dataset(self, dataset_id: str) -> bool:
        """Delete an ADaM dataset. Returns True if deleted."""
        with self._lock:
            if dataset_id in self._adam_datasets:
                del self._adam_datasets[dataset_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Controlled Term Management
    # ------------------------------------------------------------------

    def list_controlled_terms(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[ControlledTerm]:
        """List controlled terms with optional trial filter."""
        with self._lock:
            result = list(self._controlled_terms.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]

        return sorted(result, key=lambda t: t.id)

    def get_controlled_term(self, term_id: str) -> ControlledTerm | None:
        """Get a single controlled term by ID."""
        with self._lock:
            return self._controlled_terms.get(term_id)

    def create_controlled_term(self, payload: ControlledTermCreate) -> ControlledTerm:
        """Create a new controlled term."""
        term_id = f"CT-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        term = ControlledTerm(
            id=term_id,
            trial_id=payload.trial_id,
            codelist_code=payload.codelist_code,
            codelist_name=payload.codelist_name,
            term_code=payload.term_code,
            term_value=payload.term_value,
            decoded_value=payload.decoded_value,
            ct_version=payload.ct_version,
            standard=payload.standard,
            extensible=payload.extensible,
            created_at=now,
        )
        with self._lock:
            self._controlled_terms[term_id] = term
        logger.info("Created controlled term %s: %s", term_id, payload.term_value)
        return term

    def delete_controlled_term(self, term_id: str) -> bool:
        """Delete a controlled term. Returns True if deleted."""
        with self._lock:
            if term_id in self._controlled_terms:
                del self._controlled_terms[term_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Define XML Management
    # ------------------------------------------------------------------

    def list_define_xmls(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[DefineXML]:
        """List Define XMLs with optional trial filter."""
        with self._lock:
            result = list(self._define_xmls.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]

        return sorted(result, key=lambda d: d.id)

    def get_define_xml(self, define_id: str) -> DefineXML | None:
        """Get a single Define XML by ID."""
        with self._lock:
            return self._define_xmls.get(define_id)

    def create_define_xml(self, payload: DefineXMLCreate) -> DefineXML:
        """Create a new Define XML."""
        define_id = f"DEF-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        define = DefineXML(
            id=define_id,
            trial_id=payload.trial_id,
            standard=payload.standard,
            version=payload.version,
            file_name=payload.file_name,
            author=payload.author,
            created_at=now,
        )
        with self._lock:
            self._define_xmls[define_id] = define
        logger.info("Created Define XML %s: %s", define_id, payload.file_name)
        return define

    def update_define_xml(
        self, define_id: str, payload: DefineXMLUpdate
    ) -> DefineXML | None:
        """Update an existing Define XML."""
        with self._lock:
            existing = self._define_xmls.get(define_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DefineXML(**data)
            self._define_xmls[define_id] = updated
        return updated

    def delete_define_xml(self, define_id: str) -> bool:
        """Delete a Define XML. Returns True if deleted."""
        with self._lock:
            if define_id in self._define_xmls:
                del self._define_xmls[define_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Conformance Result Management
    # ------------------------------------------------------------------

    def list_conformance_results(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[ConformanceResult]:
        """List conformance results with optional trial filter."""
        with self._lock:
            result = list(self._conformance_results.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.id)

    def get_conformance_result(self, result_id: str) -> ConformanceResult | None:
        """Get a single conformance result by ID."""
        with self._lock:
            return self._conformance_results.get(result_id)

    def create_conformance_result(self, payload: ConformanceResultCreate) -> ConformanceResult:
        """Create a new conformance result."""
        result_id = f"CFR-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        result = ConformanceResult(
            id=result_id,
            trial_id=payload.trial_id,
            standard=payload.standard,
            validation_tool=payload.validation_tool,
            validation_date=now,
            dataset_name=payload.dataset_name,
            rule_id=payload.rule_id,
            severity=payload.severity,
            message=payload.message,
            variable=payload.variable,
            record_count=payload.record_count,
        )
        with self._lock:
            self._conformance_results[result_id] = result
        logger.info("Created conformance result %s: %s", result_id, payload.rule_id)
        return result

    def update_conformance_result(
        self, result_id: str, payload: ConformanceResultUpdate
    ) -> ConformanceResult | None:
        """Update an existing conformance result."""
        with self._lock:
            existing = self._conformance_results.get(result_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set resolved_date when resolution is provided
            if "resolution" in updates and updates["resolution"] is not None:
                if existing.resolved_date is None:
                    updates["resolved_date"] = datetime.now(timezone.utc)
            data.update(updates)
            updated = ConformanceResult(**data)
            self._conformance_results[result_id] = updated
        return updated

    def delete_conformance_result(self, result_id: str) -> bool:
        """Delete a conformance result. Returns True if deleted."""
        with self._lock:
            if result_id in self._conformance_results:
                del self._conformance_results[result_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> CDISCMetrics:
        """Compute aggregated CDISC standards metrics."""
        with self._lock:
            domains = list(self._sdtm_domains.values())
            adam_ds = list(self._adam_datasets.values())
            terms = list(self._controlled_terms.values())
            defines = list(self._define_xmls.values())
            conformance = list(self._conformance_results.values())

        if trial_id is not None:
            domains = [d for d in domains if d.trial_id == trial_id]
            adam_ds = [d for d in adam_ds if d.trial_id == trial_id]
            terms = [t for t in terms if t.trial_id == trial_id]
            defines = [d for d in defines if d.trial_id == trial_id]
            conformance = [r for r in conformance if r.trial_id == trial_id]

        # Domains by class
        domains_by_class: dict[str, int] = {}
        for d in domains:
            key = d.domain_class.value
            domains_by_class[key] = domains_by_class.get(key, 0) + 1

        # Domains by status
        domains_by_status: dict[str, int] = {}
        for d in domains:
            key = d.status.value
            domains_by_status[key] = domains_by_status.get(key, 0) + 1

        # SDTM mapping percentage
        total_vars = sum(d.total_variables for d in domains)
        mapped_vars = sum(d.mapped_variables for d in domains)
        sdtm_mapping_pct = round(mapped_vars / total_vars * 100.0, 1) if total_vars > 0 else 0.0

        # ADaM by status
        adam_by_status: dict[str, int] = {}
        for d in adam_ds:
            key = d.status.value
            adam_by_status[key] = adam_by_status.get(key, 0) + 1

        # Custom terms count
        custom_terms = sum(1 for t in terms if t.custom)

        # Validated define XMLs
        validated_defines = sum(1 for d in defines if d.validated)

        # Conformance by severity
        results_by_severity: dict[str, int] = {}
        for r in conformance:
            key = r.severity.value
            results_by_severity[key] = results_by_severity.get(key, 0) + 1

        # Open errors
        open_errors = sum(
            1 for r in conformance
            if r.severity == ValidationSeverity.ERROR and r.status == "open"
        )

        return CDISCMetrics(
            total_sdtm_domains=len(domains),
            domains_by_class=domains_by_class,
            domains_by_status=domains_by_status,
            sdtm_mapping_pct=sdtm_mapping_pct,
            total_adam_datasets=len(adam_ds),
            adam_by_status=adam_by_status,
            total_controlled_terms=len(terms),
            custom_terms=custom_terms,
            total_define_xmls=len(defines),
            validated_define_xmls=validated_defines,
            total_conformance_results=len(conformance),
            results_by_severity=results_by_severity,
            open_errors=open_errors,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: CDISCStandardsService | None = None
_instance_lock = threading.Lock()


def get_cdisc_standards_service() -> CDISCStandardsService:
    """Return the singleton CDISCStandardsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CDISCStandardsService()
    return _instance


def reset_cdisc_standards_service() -> CDISCStandardsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = CDISCStandardsService()
    return _instance
