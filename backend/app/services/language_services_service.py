"""Language & Translation Services Management Service.

Manages document translations for global clinical trials: translation project
lifecycle, translation task assignment and tracking, linguistic validation with
forward-backward and cognitive debriefing methods, certified translator
management with qualification tracking, multilingual glossary maintenance,
and translation metrics.

Usage:
    from app.services.language_services_service import (
        get_language_services_service,
    )

    svc = get_language_services_service()
    projects = svc.list_projects()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.language_services import (
    CertificationLevel,
    CertifiedTranslator,
    CertifiedTranslatorCreate,
    CertifiedTranslatorUpdate,
    DocumentCategory,
    LanguageMetrics,
    LinguisticValidation,
    LinguisticValidationCreate,
    LinguisticValidationUpdate,
    ProjectProgress,
    TranslationCertification,
    TranslationGlossary,
    TranslationGlossaryCreate,
    TranslationGlossaryUpdate,
    TranslationProject,
    TranslationProjectCreate,
    TranslationProjectUpdate,
    TranslationStatus,
    TranslationSubmission,
    TranslationTask,
    TranslationTaskCreate,
    TranslationTaskUpdate,
    TranslatorAssignment,
    TranslatorStatus,
    ValidationMethod,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class LanguageServicesService:
    """In-memory Language & Translation Services engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._projects: dict[str, TranslationProject] = {}
        self._tasks: dict[str, TranslationTask] = {}
        self._validations: dict[str, LinguisticValidation] = {}
        self._translators: dict[str, CertifiedTranslator] = {}
        self._glossary: dict[str, TranslationGlossary] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic translation data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 6 Certified Translators ---
        translators_data = [
            {"id": "TRN-001", "name": "Marie Dupont", "email": "m.dupont@translationpro.com", "languages": ["en", "fr", "de"], "specializations": ["ophthalmology", "regulatory"], "certification_level": CertificationLevel.CERTIFIED, "certifying_body": "ATA - American Translators Association", "certification_expiry": now + timedelta(days=365), "status": TranslatorStatus.ACTIVE, "projects_completed": 24, "quality_rating": 4.8},
            {"id": "TRN-002", "name": "Kenji Tanaka", "email": "k.tanaka@lingualink.jp", "languages": ["en", "ja", "zh"], "specializations": ["oncology", "immunology"], "certification_level": CertificationLevel.SWORN, "certifying_body": "JAT - Japan Association of Translators", "certification_expiry": now + timedelta(days=540), "status": TranslatorStatus.ACTIVE, "projects_completed": 31, "quality_rating": 4.9},
            {"id": "TRN-003", "name": "Ana Garcia Lopez", "email": "a.garcia@medtranslate.es", "languages": ["en", "es", "pt"], "specializations": ["dermatology", "patient_diary"], "certification_level": CertificationLevel.CERTIFIED, "certifying_body": "CIOL - Chartered Institute of Linguists", "certification_expiry": now + timedelta(days=200), "status": TranslatorStatus.ACTIVE, "projects_completed": 18, "quality_rating": 4.6},
            {"id": "TRN-004", "name": "Hans Mueller", "email": "h.mueller@pharmatrans.de", "languages": ["en", "de", "nl"], "specializations": ["regulatory", "packaging"], "certification_level": CertificationLevel.NOTARIZED, "certifying_body": "BDU - German Federal Association of Interpreters and Translators", "certification_expiry": now + timedelta(days=730), "status": TranslatorStatus.ACTIVE, "projects_completed": 42, "quality_rating": 4.7},
            {"id": "TRN-005", "name": "Li Wei Chen", "email": "l.chen@globalmedtrans.cn", "languages": ["en", "zh", "ko"], "specializations": ["oncology", "questionnaire"], "certification_level": CertificationLevel.CERTIFIED, "certifying_body": "TAC - Translators Association of China", "certification_expiry": now + timedelta(days=400), "status": TranslatorStatus.ACTIVE, "projects_completed": 15, "quality_rating": 4.5},
            {"id": "TRN-006", "name": "Sofia Petrov", "email": "s.petrov@eurtrans.bg", "languages": ["en", "ru", "bg"], "specializations": ["ophthalmology", "icf"], "certification_level": CertificationLevel.STANDARD, "certifying_body": "UTR - Union of Translators of Russia", "certification_expiry": now - timedelta(days=30), "status": TranslatorStatus.INACTIVE, "projects_completed": 8, "quality_rating": 4.2},
        ]

        for t in translators_data:
            self._translators[t["id"]] = CertifiedTranslator(**t)

        # --- 4 Translation Projects ---
        projects_data = [
            {"id": "TPRJ-001", "trial_id": EYLEA_TRIAL, "project_name": "EYLEA HD Protocol Translation - Phase 3", "source_language": "en", "target_languages": ["fr", "de", "ja", "zh"], "document_category": DocumentCategory.PROTOCOL, "status": TranslationStatus.DELIVERED, "requested_date": now - timedelta(days=120), "due_date": now - timedelta(days=30), "completed_date": now - timedelta(days=35), "requestor": "Clinical Operations", "priority": "high"},
            {"id": "TPRJ-002", "trial_id": EYLEA_TRIAL, "project_name": "EYLEA HD Informed Consent Form - Multi-language", "source_language": "en", "target_languages": ["fr", "de", "ja", "es"], "document_category": DocumentCategory.ICF, "status": TranslationStatus.RECONCILED, "requested_date": now - timedelta(days=90), "due_date": now - timedelta(days=10), "completed_date": None, "requestor": "Regulatory Affairs", "priority": "urgent"},
            {"id": "TPRJ-003", "trial_id": DUPIXENT_TRIAL, "project_name": "Dupixent Patient Diary Translation", "source_language": "en", "target_languages": ["es", "pt", "de"], "document_category": DocumentCategory.PATIENT_DIARY, "status": TranslationStatus.IN_PROGRESS, "requested_date": now - timedelta(days=60), "due_date": now + timedelta(days=30), "completed_date": None, "requestor": "Patient Engagement", "priority": "normal"},
            {"id": "TPRJ-004", "trial_id": LIBTAYO_TRIAL, "project_name": "Libtayo Regulatory Submission Dossier", "source_language": "en", "target_languages": ["ja", "zh", "ko"], "document_category": DocumentCategory.REGULATORY_SUBMISSION, "status": TranslationStatus.REQUESTED, "requested_date": now - timedelta(days=10), "due_date": now + timedelta(days=90), "completed_date": None, "requestor": "Regulatory Affairs", "priority": "high"},
        ]

        for p in projects_data:
            self._projects[p["id"]] = TranslationProject(**p)

        # --- 12 Translation Tasks ---
        tasks_data = [
            # EYLEA Protocol tasks (TPRJ-001) - delivered
            {"id": "TTSK-001", "project_id": "TPRJ-001", "source_document": "EYLEA_HD_Protocol_v3.2.docx", "source_language": "en", "target_language": "fr", "status": TranslationStatus.DELIVERED, "translator_id": "TRN-001", "reviewer_id": "TRN-004", "word_count": 45000, "translated_text_reference": "EYLEA_HD_Protocol_v3.2_FR.docx", "back_translation_reference": "EYLEA_HD_Protocol_v3.2_FR_BT.docx", "reconciliation_notes": "Minor terminology adjustments in section 6.2", "started_date": now - timedelta(days=100), "completed_date": now - timedelta(days=40)},
            {"id": "TTSK-002", "project_id": "TPRJ-001", "source_document": "EYLEA_HD_Protocol_v3.2.docx", "source_language": "en", "target_language": "de", "status": TranslationStatus.DELIVERED, "translator_id": "TRN-004", "reviewer_id": "TRN-001", "word_count": 45000, "translated_text_reference": "EYLEA_HD_Protocol_v3.2_DE.docx", "back_translation_reference": "EYLEA_HD_Protocol_v3.2_DE_BT.docx", "reconciliation_notes": None, "started_date": now - timedelta(days=100), "completed_date": now - timedelta(days=38)},
            {"id": "TTSK-003", "project_id": "TPRJ-001", "source_document": "EYLEA_HD_Protocol_v3.2.docx", "source_language": "en", "target_language": "ja", "status": TranslationStatus.DELIVERED, "translator_id": "TRN-002", "reviewer_id": "TRN-005", "word_count": 45000, "translated_text_reference": "EYLEA_HD_Protocol_v3.2_JA.docx", "back_translation_reference": "EYLEA_HD_Protocol_v3.2_JA_BT.docx", "reconciliation_notes": "Cultural adaptation of informed consent language", "started_date": now - timedelta(days=95), "completed_date": now - timedelta(days=36)},

            # EYLEA ICF tasks (TPRJ-002) - reconciled
            {"id": "TTSK-004", "project_id": "TPRJ-002", "source_document": "EYLEA_HD_ICF_v2.1.docx", "source_language": "en", "target_language": "fr", "status": TranslationStatus.CERTIFIED, "translator_id": "TRN-001", "reviewer_id": "TRN-004", "word_count": 12000, "translated_text_reference": "EYLEA_HD_ICF_v2.1_FR.docx", "back_translation_reference": "EYLEA_HD_ICF_v2.1_FR_BT.docx", "reconciliation_notes": None, "started_date": now - timedelta(days=70), "completed_date": now - timedelta(days=20)},
            {"id": "TTSK-005", "project_id": "TPRJ-002", "source_document": "EYLEA_HD_ICF_v2.1.docx", "source_language": "en", "target_language": "de", "status": TranslationStatus.RECONCILED, "translator_id": "TRN-004", "reviewer_id": "TRN-001", "word_count": 12000, "translated_text_reference": "EYLEA_HD_ICF_v2.1_DE.docx", "back_translation_reference": "EYLEA_HD_ICF_v2.1_DE_BT.docx", "reconciliation_notes": "Resolved 3 discrepancies in eligibility criteria section", "started_date": now - timedelta(days=65), "completed_date": None},
            {"id": "TTSK-006", "project_id": "TPRJ-002", "source_document": "EYLEA_HD_ICF_v2.1.docx", "source_language": "en", "target_language": "ja", "status": TranslationStatus.BACK_TRANSLATED, "translator_id": "TRN-002", "reviewer_id": "TRN-005", "word_count": 12000, "translated_text_reference": "EYLEA_HD_ICF_v2.1_JA.docx", "back_translation_reference": "EYLEA_HD_ICF_v2.1_JA_BT.docx", "reconciliation_notes": None, "started_date": now - timedelta(days=60), "completed_date": None},
            {"id": "TTSK-007", "project_id": "TPRJ-002", "source_document": "EYLEA_HD_ICF_v2.1.docx", "source_language": "en", "target_language": "es", "status": TranslationStatus.TRANSLATED, "translator_id": "TRN-003", "reviewer_id": None, "word_count": 12000, "translated_text_reference": "EYLEA_HD_ICF_v2.1_ES.docx", "back_translation_reference": None, "reconciliation_notes": None, "started_date": now - timedelta(days=50), "completed_date": None},

            # Dupixent Patient Diary tasks (TPRJ-003) - in progress
            {"id": "TTSK-008", "project_id": "TPRJ-003", "source_document": "Dupixent_PatientDiary_v1.0.docx", "source_language": "en", "target_language": "es", "status": TranslationStatus.IN_PROGRESS, "translator_id": "TRN-003", "reviewer_id": None, "word_count": 5000, "translated_text_reference": None, "back_translation_reference": None, "reconciliation_notes": None, "started_date": now - timedelta(days=30), "completed_date": None},
            {"id": "TTSK-009", "project_id": "TPRJ-003", "source_document": "Dupixent_PatientDiary_v1.0.docx", "source_language": "en", "target_language": "pt", "status": TranslationStatus.IN_PROGRESS, "translator_id": "TRN-003", "reviewer_id": None, "word_count": 5000, "translated_text_reference": None, "back_translation_reference": None, "reconciliation_notes": None, "started_date": now - timedelta(days=25), "completed_date": None},
            {"id": "TTSK-010", "project_id": "TPRJ-003", "source_document": "Dupixent_PatientDiary_v1.0.docx", "source_language": "en", "target_language": "de", "status": TranslationStatus.REQUESTED, "translator_id": None, "reviewer_id": None, "word_count": 5000, "translated_text_reference": None, "back_translation_reference": None, "reconciliation_notes": None, "started_date": None, "completed_date": None},

            # Libtayo Regulatory tasks (TPRJ-004) - requested
            {"id": "TTSK-011", "project_id": "TPRJ-004", "source_document": "Libtayo_RegSub_Module2.5.docx", "source_language": "en", "target_language": "ja", "status": TranslationStatus.REQUESTED, "translator_id": None, "reviewer_id": None, "word_count": 80000, "translated_text_reference": None, "back_translation_reference": None, "reconciliation_notes": None, "started_date": None, "completed_date": None},
            {"id": "TTSK-012", "project_id": "TPRJ-004", "source_document": "Libtayo_RegSub_Module2.5.docx", "source_language": "en", "target_language": "zh", "status": TranslationStatus.REQUESTED, "translator_id": None, "reviewer_id": None, "word_count": 80000, "translated_text_reference": None, "back_translation_reference": None, "reconciliation_notes": None, "started_date": None, "completed_date": None},
        ]

        for t in tasks_data:
            self._tasks[t["id"]] = TranslationTask(**t)

        # --- 5 Linguistic Validations ---
        validations_data = [
            {"id": "LVAL-001", "task_id": "TTSK-001", "method": ValidationMethod.FORWARD_BACKWARD, "validation_date": now - timedelta(days=50), "validator": "Dr. Claire Beaumont", "cognitive_debriefing_participants": None, "issues_found": 3, "issues_resolved": 3, "conceptual_equivalence_score": 95.0, "cultural_appropriateness_score": 92.0, "readability_score": 88.0, "overall_pass": True, "notes": "All issues resolved. Translation approved for use."},
            {"id": "LVAL-002", "task_id": "TTSK-002", "method": ValidationMethod.FORWARD_BACKWARD, "validation_date": now - timedelta(days=48), "validator": "Prof. Klaus Schmidt", "cognitive_debriefing_participants": None, "issues_found": 1, "issues_resolved": 1, "conceptual_equivalence_score": 97.0, "cultural_appropriateness_score": 96.0, "readability_score": 93.0, "overall_pass": True, "notes": "High quality translation. Minor formatting issue resolved."},
            {"id": "LVAL-003", "task_id": "TTSK-003", "method": ValidationMethod.DUAL_FORWARD, "validation_date": now - timedelta(days=45), "validator": "Dr. Yuki Nakamura", "cognitive_debriefing_participants": None, "issues_found": 5, "issues_resolved": 5, "conceptual_equivalence_score": 91.0, "cultural_appropriateness_score": 89.0, "readability_score": 86.0, "overall_pass": True, "notes": "Cultural adaptations for Japanese regulatory requirements applied."},
            {"id": "LVAL-004", "task_id": "TTSK-004", "method": ValidationMethod.COGNITIVE_DEBRIEFING, "validation_date": now - timedelta(days=25), "validator": "Marie Dupont", "cognitive_debriefing_participants": 8, "issues_found": 2, "issues_resolved": 2, "conceptual_equivalence_score": 94.0, "cultural_appropriateness_score": 93.0, "readability_score": 90.0, "overall_pass": True, "notes": "Cognitive debriefing with 8 native French-speaking patients. All comprehension issues addressed."},
            {"id": "LVAL-005", "task_id": "TTSK-005", "method": ValidationMethod.HARMONIZATION, "validation_date": now - timedelta(days=15), "validator": "Prof. Klaus Schmidt", "cognitive_debriefing_participants": None, "issues_found": 4, "issues_resolved": 2, "conceptual_equivalence_score": 85.0, "cultural_appropriateness_score": 88.0, "readability_score": 82.0, "overall_pass": False, "notes": "Two unresolved issues in risk disclosure section. Re-translation required."},
        ]

        for v in validations_data:
            self._validations[v["id"]] = LinguisticValidation(**v)

        # --- 10 Glossary Entries ---
        glossary_data = [
            {"id": "GLOSS-001", "trial_id": EYLEA_TRIAL, "source_term": "Best-Corrected Visual Acuity", "source_language": "en", "translations": {"fr": "Acuite visuelle la mieux corrigee", "de": "Bestkorrigierte Sehscharfe", "ja": "Saiteishi ryokuryoku"}, "context": "Primary endpoint measurement in ophthalmology trials. BCVA measured using ETDRS chart.", "approved": True, "approved_by": "Dr. Sarah Ophtho"},
            {"id": "GLOSS-002", "trial_id": EYLEA_TRIAL, "source_term": "Intravitreal Injection", "source_language": "en", "translations": {"fr": "Injection intravitreenne", "de": "Intravitreale Injektion", "ja": "Shoritai nai chusha"}, "context": "Route of administration for EYLEA. Injection directly into the vitreous humor of the eye.", "approved": True, "approved_by": "Dr. Sarah Ophtho"},
            {"id": "GLOSS-003", "trial_id": EYLEA_TRIAL, "source_term": "Central Retinal Thickness", "source_language": "en", "translations": {"fr": "Epaisseur retinienne centrale", "de": "Zentrale Netzhautdicke"}, "context": "Secondary endpoint measured via OCT imaging.", "approved": True, "approved_by": "Dr. Sarah Ophtho"},
            {"id": "GLOSS-004", "trial_id": DUPIXENT_TRIAL, "source_term": "Eczema Area and Severity Index", "source_language": "en", "translations": {"es": "Indice de Area y Severidad del Eczema", "pt": "Indice de Area e Severidade do Eczema", "de": "Ekzem-Flachen- und Schweregrad-Index"}, "context": "EASI score. Primary efficacy endpoint for atopic dermatitis trials.", "approved": True, "approved_by": "Dr. Derm Lead"},
            {"id": "GLOSS-005", "trial_id": DUPIXENT_TRIAL, "source_term": "Investigator Global Assessment", "source_language": "en", "translations": {"es": "Evaluacion Global del Investigador", "pt": "Avaliacao Global do Investigador"}, "context": "IGA score on 0-4 scale. Co-primary endpoint.", "approved": True, "approved_by": "Dr. Derm Lead"},
            {"id": "GLOSS-006", "trial_id": DUPIXENT_TRIAL, "source_term": "Pruritus Numerical Rating Scale", "source_language": "en", "translations": {"es": "Escala Numerica de Valoracion del Prurito"}, "context": "Patient-reported outcome for itch severity (0-10 scale).", "approved": False, "approved_by": None},
            {"id": "GLOSS-007", "trial_id": LIBTAYO_TRIAL, "source_term": "Objective Response Rate", "source_language": "en", "translations": {"ja": "Kyakkanteki hano ritsu", "zh": "Keguan huanying lv"}, "context": "ORR per RECIST 1.1 criteria. Primary endpoint for oncology trials.", "approved": True, "approved_by": "Dr. Onco Lead"},
            {"id": "GLOSS-008", "trial_id": LIBTAYO_TRIAL, "source_term": "Progression-Free Survival", "source_language": "en", "translations": {"ja": "Musinkou seizonki", "zh": "Wujinzhan shengcunqi", "ko": "Mujinhaeng saengjongi"}, "context": "PFS measured from randomization to disease progression or death.", "approved": True, "approved_by": "Dr. Onco Lead"},
            {"id": "GLOSS-009", "trial_id": LIBTAYO_TRIAL, "source_term": "Immune-Related Adverse Event", "source_language": "en", "translations": {"ja": "Meneki kanren yukigaisho", "zh": "Mianyi xiangguan buliang shijian"}, "context": "irAE. Safety term specific to checkpoint inhibitor therapy.", "approved": True, "approved_by": "Dr. Safety Lead"},
            {"id": "GLOSS-010", "trial_id": LIBTAYO_TRIAL, "source_term": "Programmed Death-Ligand 1", "source_language": "en", "translations": {"ja": "Puroguramu shibo rigando 1", "zh": "Chengxuxing siwang peiti 1"}, "context": "PD-L1 biomarker expression. Used for patient stratification.", "approved": False, "approved_by": None},
        ]

        for g in glossary_data:
            self._glossary[g["id"]] = TranslationGlossary(**g)

    # ------------------------------------------------------------------
    # Translation Project Management
    # ------------------------------------------------------------------

    def list_projects(
        self,
        *,
        trial_id: str | None = None,
        status: TranslationStatus | None = None,
        document_category: DocumentCategory | None = None,
    ) -> list[TranslationProject]:
        """List translation projects with optional filters."""
        with self._lock:
            result = list(self._projects.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if status is not None:
            result = [p for p in result if p.status == status]
        if document_category is not None:
            result = [p for p in result if p.document_category == document_category]

        return sorted(result, key=lambda p: p.requested_date, reverse=True)

    def get_project(self, project_id: str) -> TranslationProject | None:
        """Get a single project by ID."""
        with self._lock:
            return self._projects.get(project_id)

    def create_project(self, payload: TranslationProjectCreate) -> TranslationProject:
        """Create a new translation project."""
        now = datetime.now(timezone.utc)
        project_id = f"TPRJ-{uuid4().hex[:8].upper()}"
        project = TranslationProject(
            id=project_id,
            trial_id=payload.trial_id,
            project_name=payload.project_name,
            source_language=payload.source_language,
            target_languages=payload.target_languages,
            document_category=payload.document_category,
            status=TranslationStatus.REQUESTED,
            requested_date=now,
            due_date=payload.due_date,
            completed_date=None,
            requestor=payload.requestor,
            priority=payload.priority,
        )
        with self._lock:
            self._projects[project_id] = project
        logger.info("Created translation project %s: %s", project_id, payload.project_name)
        return project

    def update_project(
        self, project_id: str, payload: TranslationProjectUpdate
    ) -> TranslationProject | None:
        """Update an existing translation project."""
        with self._lock:
            existing = self._projects.get(project_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TranslationProject(**data)
            self._projects[project_id] = updated
        return updated

    def delete_project(self, project_id: str) -> bool:
        """Delete a project. Returns True if deleted."""
        with self._lock:
            if project_id in self._projects:
                del self._projects[project_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Translation Task Management
    # ------------------------------------------------------------------

    def list_tasks(
        self,
        *,
        project_id: str | None = None,
        status: TranslationStatus | None = None,
        target_language: str | None = None,
        translator_id: str | None = None,
    ) -> list[TranslationTask]:
        """List translation tasks with optional filters."""
        with self._lock:
            result = list(self._tasks.values())

        if project_id is not None:
            result = [t for t in result if t.project_id == project_id]
        if status is not None:
            result = [t for t in result if t.status == status]
        if target_language is not None:
            result = [t for t in result if t.target_language == target_language]
        if translator_id is not None:
            result = [t for t in result if t.translator_id == translator_id]

        return sorted(result, key=lambda t: t.id)

    def get_task(self, task_id: str) -> TranslationTask | None:
        """Get a single task by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def create_task(self, payload: TranslationTaskCreate) -> TranslationTask:
        """Create a new translation task."""
        task_id = f"TTSK-{uuid4().hex[:8].upper()}"
        task = TranslationTask(
            id=task_id,
            project_id=payload.project_id,
            source_document=payload.source_document,
            source_language=payload.source_language,
            target_language=payload.target_language,
            status=TranslationStatus.REQUESTED,
            translator_id=None,
            reviewer_id=None,
            word_count=payload.word_count,
            translated_text_reference=None,
            back_translation_reference=None,
            reconciliation_notes=None,
            started_date=None,
            completed_date=None,
        )
        with self._lock:
            self._tasks[task_id] = task
        logger.info(
            "Created translation task %s: project=%s lang=%s->%s",
            task_id, payload.project_id, payload.source_language, payload.target_language,
        )
        return task

    def update_task(
        self, task_id: str, payload: TranslationTaskUpdate
    ) -> TranslationTask | None:
        """Update an existing translation task."""
        with self._lock:
            existing = self._tasks.get(task_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TranslationTask(**data)
            self._tasks[task_id] = updated
        return updated

    def delete_task(self, task_id: str) -> bool:
        """Delete a task. Returns True if deleted."""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Linguistic Validation Management
    # ------------------------------------------------------------------

    def list_validations(
        self,
        *,
        task_id: str | None = None,
        method: ValidationMethod | None = None,
    ) -> list[LinguisticValidation]:
        """List linguistic validations with optional filters."""
        with self._lock:
            result = list(self._validations.values())

        if task_id is not None:
            result = [v for v in result if v.task_id == task_id]
        if method is not None:
            result = [v for v in result if v.method == method]

        return sorted(result, key=lambda v: v.validation_date, reverse=True)

    def get_validation(self, validation_id: str) -> LinguisticValidation | None:
        """Get a single validation by ID."""
        with self._lock:
            return self._validations.get(validation_id)

    def create_validation(self, payload: LinguisticValidationCreate) -> LinguisticValidation:
        """Create a new linguistic validation record."""
        now = datetime.now(timezone.utc)
        validation_id = f"LVAL-{uuid4().hex[:8].upper()}"

        with self._lock:
            task = self._tasks.get(payload.task_id)
            if task is None:
                raise ValueError(f"Task '{payload.task_id}' not found")

        validation = LinguisticValidation(
            id=validation_id,
            task_id=payload.task_id,
            method=payload.method,
            validation_date=now,
            validator=payload.validator,
            cognitive_debriefing_participants=payload.cognitive_debriefing_participants,
            issues_found=payload.issues_found,
            issues_resolved=payload.issues_resolved,
            conceptual_equivalence_score=payload.conceptual_equivalence_score,
            cultural_appropriateness_score=payload.cultural_appropriateness_score,
            readability_score=payload.readability_score,
            overall_pass=payload.overall_pass,
            notes=payload.notes,
        )

        with self._lock:
            self._validations[validation_id] = validation

        logger.info(
            "Created linguistic validation %s: task=%s method=%s pass=%s",
            validation_id, payload.task_id, payload.method.value, payload.overall_pass,
        )
        return validation

    def update_validation(
        self, validation_id: str, payload: LinguisticValidationUpdate
    ) -> LinguisticValidation | None:
        """Update an existing linguistic validation."""
        with self._lock:
            existing = self._validations.get(validation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LinguisticValidation(**data)
            self._validations[validation_id] = updated
        return updated

    def delete_validation(self, validation_id: str) -> bool:
        """Delete a validation. Returns True if deleted."""
        with self._lock:
            if validation_id in self._validations:
                del self._validations[validation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Certified Translator Management
    # ------------------------------------------------------------------

    def list_translators(
        self,
        *,
        status: TranslatorStatus | None = None,
        language: str | None = None,
        certification_level: CertificationLevel | None = None,
    ) -> list[CertifiedTranslator]:
        """List certified translators with optional filters."""
        with self._lock:
            result = list(self._translators.values())

        if status is not None:
            result = [t for t in result if t.status == status]
        if language is not None:
            result = [t for t in result if language in t.languages]
        if certification_level is not None:
            result = [t for t in result if t.certification_level == certification_level]

        return sorted(result, key=lambda t: t.id)

    def get_translator(self, translator_id: str) -> CertifiedTranslator | None:
        """Get a single translator by ID."""
        with self._lock:
            return self._translators.get(translator_id)

    def create_translator(self, payload: CertifiedTranslatorCreate) -> CertifiedTranslator:
        """Register a new certified translator."""
        translator_id = f"TRN-{uuid4().hex[:8].upper()}"
        translator = CertifiedTranslator(
            id=translator_id,
            name=payload.name,
            email=payload.email,
            languages=payload.languages,
            specializations=payload.specializations,
            certification_level=payload.certification_level,
            certifying_body=payload.certifying_body,
            certification_expiry=payload.certification_expiry,
            status=TranslatorStatus.PENDING_QUALIFICATION,
            projects_completed=0,
            quality_rating=0.0,
        )
        with self._lock:
            self._translators[translator_id] = translator
        logger.info("Registered translator %s: %s", translator_id, payload.name)
        return translator

    def update_translator(
        self, translator_id: str, payload: CertifiedTranslatorUpdate
    ) -> CertifiedTranslator | None:
        """Update a certified translator."""
        with self._lock:
            existing = self._translators.get(translator_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CertifiedTranslator(**data)
            self._translators[translator_id] = updated
        return updated

    def delete_translator(self, translator_id: str) -> bool:
        """Delete a translator. Returns True if deleted."""
        with self._lock:
            if translator_id in self._translators:
                del self._translators[translator_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Translation Glossary Management
    # ------------------------------------------------------------------

    def list_glossary(
        self,
        *,
        trial_id: str | None = None,
        source_language: str | None = None,
        approved: bool | None = None,
    ) -> list[TranslationGlossary]:
        """List glossary entries with optional filters."""
        with self._lock:
            result = list(self._glossary.values())

        if trial_id is not None:
            result = [g for g in result if g.trial_id == trial_id]
        if source_language is not None:
            result = [g for g in result if g.source_language == source_language]
        if approved is not None:
            result = [g for g in result if g.approved == approved]

        return sorted(result, key=lambda g: g.id)

    def get_glossary_entry(self, entry_id: str) -> TranslationGlossary | None:
        """Get a single glossary entry by ID."""
        with self._lock:
            return self._glossary.get(entry_id)

    def create_glossary_entry(self, payload: TranslationGlossaryCreate) -> TranslationGlossary:
        """Create a new glossary entry."""
        entry_id = f"GLOSS-{uuid4().hex[:8].upper()}"
        entry = TranslationGlossary(
            id=entry_id,
            trial_id=payload.trial_id,
            source_term=payload.source_term,
            source_language=payload.source_language,
            translations=payload.translations,
            context=payload.context,
            approved=False,
            approved_by=None,
        )
        with self._lock:
            self._glossary[entry_id] = entry
        logger.info("Created glossary entry %s: %s", entry_id, payload.source_term)
        return entry

    def update_glossary_entry(
        self, entry_id: str, payload: TranslationGlossaryUpdate
    ) -> TranslationGlossary | None:
        """Update a glossary entry."""
        with self._lock:
            existing = self._glossary.get(entry_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TranslationGlossary(**data)
            self._glossary[entry_id] = updated
        return updated

    def delete_glossary_entry(self, entry_id: str) -> bool:
        """Delete a glossary entry. Returns True if deleted."""
        with self._lock:
            if entry_id in self._glossary:
                del self._glossary[entry_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Workflow Operations
    # ------------------------------------------------------------------

    def assign_translator(
        self, task_id: str, payload: TranslatorAssignment
    ) -> TranslationTask | None:
        """Assign a translator to a task and move to in_progress status."""
        now = datetime.now(timezone.utc)
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None

            translator = self._translators.get(payload.translator_id)
            if translator is None:
                raise ValueError(f"Translator '{payload.translator_id}' not found")

            data = task.model_dump()
            data["translator_id"] = payload.translator_id
            data["reviewer_id"] = payload.reviewer_id
            data["status"] = TranslationStatus.IN_PROGRESS
            data["started_date"] = now
            updated = TranslationTask(**data)
            self._tasks[task_id] = updated
        logger.info("Assigned translator %s to task %s", payload.translator_id, task_id)
        return updated

    def submit_translation(
        self, task_id: str, payload: TranslationSubmission
    ) -> TranslationTask | None:
        """Submit a completed translation for a task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None

            data = task.model_dump()
            data["translated_text_reference"] = payload.translated_text_reference
            if payload.back_translation_reference:
                data["back_translation_reference"] = payload.back_translation_reference
                data["status"] = TranslationStatus.BACK_TRANSLATED
            else:
                data["status"] = TranslationStatus.TRANSLATED
            if payload.reconciliation_notes:
                data["reconciliation_notes"] = payload.reconciliation_notes
            updated = TranslationTask(**data)
            self._tasks[task_id] = updated
        logger.info("Submitted translation for task %s", task_id)
        return updated

    def certify_translation(
        self, task_id: str, payload: TranslationCertification
    ) -> TranslationTask | None:
        """Certify a completed translation."""
        now = datetime.now(timezone.utc)
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None

            data = task.model_dump()
            data["status"] = TranslationStatus.CERTIFIED
            data["completed_date"] = now
            updated = TranslationTask(**data)
            self._tasks[task_id] = updated
        logger.info(
            "Certified translation for task %s by %s",
            task_id, payload.certified_by,
        )
        return updated

    # ------------------------------------------------------------------
    # Project Progress
    # ------------------------------------------------------------------

    def get_project_progress(self, project_id: str) -> ProjectProgress | None:
        """Get progress summary for a translation project."""
        with self._lock:
            project = self._projects.get(project_id)
            if project is None:
                return None
            tasks = [t for t in self._tasks.values() if t.project_id == project_id]
            validations = list(self._validations.values())

        total_tasks = len(tasks)
        completed_statuses = {TranslationStatus.CERTIFIED, TranslationStatus.DELIVERED}
        in_progress_statuses = {
            TranslationStatus.IN_PROGRESS,
            TranslationStatus.TRANSLATED,
            TranslationStatus.BACK_TRANSLATED,
            TranslationStatus.RECONCILED,
        }

        tasks_completed = sum(1 for t in tasks if t.status in completed_statuses)
        tasks_in_progress = sum(1 for t in tasks if t.status in in_progress_statuses)
        tasks_pending = sum(1 for t in tasks if t.status == TranslationStatus.REQUESTED)

        completion_pct = (tasks_completed / total_tasks * 100.0) if total_tasks > 0 else 0.0
        total_word_count = sum(t.word_count for t in tasks)

        languages_completed = [
            t.target_language for t in tasks if t.status in completed_statuses
        ]
        languages_pending = [
            t.target_language for t in tasks if t.status not in completed_statuses
        ]

        # Validations for tasks in this project
        task_ids = {t.id for t in tasks}
        project_validations = [v for v in validations if v.task_id in task_ids]
        validations_passed = sum(1 for v in project_validations if v.overall_pass)
        validations_failed = sum(1 for v in project_validations if not v.overall_pass)

        return ProjectProgress(
            project_id=project_id,
            project_name=project.project_name,
            status=project.status,
            total_tasks=total_tasks,
            tasks_completed=tasks_completed,
            tasks_in_progress=tasks_in_progress,
            tasks_pending=tasks_pending,
            completion_percentage=round(completion_pct, 1),
            total_word_count=total_word_count,
            languages_completed=languages_completed,
            languages_pending=languages_pending,
            validations_passed=validations_passed,
            validations_failed=validations_failed,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> LanguageMetrics:
        """Compute aggregated language services metrics."""
        with self._lock:
            projects = list(self._projects.values())
            tasks = list(self._tasks.values())
            translators = list(self._translators.values())
            validations = list(self._validations.values())
            glossary = list(self._glossary.values())

        if trial_id is not None:
            projects = [p for p in projects if p.trial_id == trial_id]
            project_ids = {p.id for p in projects}
            tasks = [t for t in tasks if t.project_id in project_ids]
            glossary = [g for g in glossary if g.trial_id == trial_id]

        # Projects by status
        projects_by_status: dict[str, int] = {}
        for p in projects:
            key = p.status.value
            projects_by_status[key] = projects_by_status.get(key, 0) + 1

        # Tasks by status
        tasks_by_status: dict[str, int] = {}
        for t in tasks:
            key = t.status.value
            tasks_by_status[key] = tasks_by_status.get(key, 0) + 1

        # Translator metrics
        active_translators = sum(1 for t in translators if t.status == TranslatorStatus.ACTIVE)

        # Validation metrics - filter by project tasks if trial_id specified
        if trial_id is not None:
            task_ids = {t.id for t in tasks}
            validations = [v for v in validations if v.task_id in task_ids]

        validations_passed = sum(1 for v in validations if v.overall_pass)
        validations_failed = sum(1 for v in validations if not v.overall_pass)

        # Average scores
        if validations:
            avg_conceptual = sum(v.conceptual_equivalence_score for v in validations) / len(validations)
            avg_cultural = sum(v.cultural_appropriateness_score for v in validations) / len(validations)
            avg_readability = sum(v.readability_score for v in validations) / len(validations)
        else:
            avg_conceptual = 0.0
            avg_cultural = 0.0
            avg_readability = 0.0

        # Glossary metrics
        approved_glossary = sum(1 for g in glossary if g.approved)

        # Word count
        total_word_count = sum(t.word_count for t in tasks)

        # Unique languages
        all_languages: set[str] = set()
        for t in tasks:
            all_languages.add(t.target_language)

        # Average translator rating
        rated_translators = [t for t in translators if t.quality_rating > 0]
        avg_rating = (
            sum(t.quality_rating for t in rated_translators) / len(rated_translators)
            if rated_translators
            else 0.0
        )

        return LanguageMetrics(
            total_projects=len(projects),
            projects_by_status=projects_by_status,
            total_tasks=len(tasks),
            tasks_by_status=tasks_by_status,
            total_translators=len(translators),
            active_translators=active_translators,
            total_validations=len(validations),
            validations_passed=validations_passed,
            validations_failed=validations_failed,
            avg_conceptual_equivalence=round(avg_conceptual, 1),
            avg_cultural_appropriateness=round(avg_cultural, 1),
            avg_readability=round(avg_readability, 1),
            total_glossary_entries=len(glossary),
            approved_glossary_entries=approved_glossary,
            total_word_count=total_word_count,
            languages_supported=sorted(all_languages),
            avg_translator_rating=round(avg_rating, 2),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: LanguageServicesService | None = None
_instance_lock = threading.Lock()


def get_language_services_service() -> LanguageServicesService:
    """Return the singleton LanguageServicesService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = LanguageServicesService()
    return _instance


def reset_language_services_service() -> LanguageServicesService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = LanguageServicesService()
    return _instance
