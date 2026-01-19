"""Clinical Note Generation Service.

AI-powered service for generating clinical documentation:
- SOAP notes (Subjective, Objective, Assessment, Plan)
- H&P (History and Physical) notes
- Progress notes
- Discharge summaries
- Procedure notes

Features:
- Structured prompts for each note type
- Clinical terminology enforcement
- HIPAA-compliant generation (no hallucinated PHI)
- Template-based customization
- Singleton pattern for efficient resource usage
"""

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from app.services.llm_service import (
    LLMProvider,
    LLMService,
    get_llm_service,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Types
# ============================================================================


class NoteType(str, Enum):
    """Types of clinical notes that can be generated."""

    SOAP = "soap"  # Subjective, Objective, Assessment, Plan
    HP = "hp"  # History and Physical
    PROGRESS = "progress"  # Progress Note
    DISCHARGE = "discharge"  # Discharge Summary
    PROCEDURE = "procedure"  # Procedure Note
    CONSULTATION = "consultation"  # Consultation Note
    OPERATIVE = "operative"  # Operative Note


class NoteStatus(str, Enum):
    """Status of a generated note."""

    DRAFT = "draft"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    NEEDS_REVIEW = "needs_review"


class SectionStatus(str, Enum):
    """Status of a note section."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    GENERATED = "generated"
    USER_PROVIDED = "user_provided"


class ConfidenceLevel(str, Enum):
    """Confidence level in generated content."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ============================================================================
# Data Classes - Input Models
# ============================================================================


@dataclass
class PatientData:
    """Patient demographic and clinical data for note generation."""

    # Demographics (use placeholders for HIPAA compliance)
    age: int | None = None
    sex: str | None = None  # M, F, Other

    # Clinical history
    chief_complaint: str | None = None
    history_present_illness: str | None = None
    past_medical_history: list[str] = field(default_factory=list)
    past_surgical_history: list[str] = field(default_factory=list)
    medications: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)
    social_history: str | None = None
    family_history: str | None = None
    review_of_systems: dict[str, str] = field(default_factory=dict)

    # Vital signs
    vitals: dict[str, Any] = field(default_factory=dict)


@dataclass
class EncounterData:
    """Encounter-specific data for note generation."""

    encounter_type: str  # inpatient, outpatient, emergency, etc.
    encounter_date: str | None = None  # ISO format date
    provider_type: str | None = None  # MD, DO, NP, PA, etc.
    location: str | None = None  # clinic, hospital, ER, etc.

    # Exam and findings
    physical_exam: dict[str, str] = field(default_factory=dict)
    lab_results: dict[str, Any] = field(default_factory=dict)
    imaging_results: dict[str, str] = field(default_factory=dict)

    # Assessment and plan
    diagnoses: list[str] = field(default_factory=list)
    icd10_codes: list[str] = field(default_factory=list)
    procedures_performed: list[str] = field(default_factory=list)
    cpt_codes: list[str] = field(default_factory=list)
    plan_items: list[str] = field(default_factory=list)

    # Additional context
    interval_history: str | None = None
    hospital_course: str | None = None
    follow_up: list[str] = field(default_factory=list)

    # For procedures
    procedure_name: str | None = None
    procedure_indication: str | None = None
    procedure_findings: str | None = None
    procedure_complications: str | None = None
    estimated_blood_loss: str | None = None
    specimens: list[str] = field(default_factory=list)


@dataclass
class NoteTemplate:
    """Template for clinical note generation."""

    template_id: str
    note_type: NoteType
    name: str
    description: str
    sections: list["NoteSectionTemplate"]
    default_prompts: dict[str, str] = field(default_factory=dict)
    formatting: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NoteSectionTemplate:
    """Template for a section within a note."""

    name: str
    key: str  # Unique identifier for the section
    required: bool = True
    order: int = 0
    prompt_template: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    subsections: list[str] = field(default_factory=list)


@dataclass
class NoteGenerationRequest:
    """Request to generate a clinical note."""

    note_type: NoteType
    patient_data: PatientData
    encounter_data: EncounterData
    template_id: str | None = None
    custom_instructions: str | None = None
    include_codes: bool = True
    provider: LLMProvider | None = None
    model: str | None = None


# ============================================================================
# Data Classes - Output Models
# ============================================================================


@dataclass
class NoteSection:
    """A section within a generated clinical note."""

    name: str
    key: str
    content: str
    required: bool = True
    order: int = 0
    status: SectionStatus = SectionStatus.GENERATED
    word_count: int = 0
    subsections: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class NoteValidationResult:
    """Result of validating a clinical note."""

    is_valid: bool
    completeness_score: float  # 0.0 to 1.0
    missing_sections: list[str] = field(default_factory=list)
    incomplete_sections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class GeneratedNote:
    """A generated clinical note."""

    note_id: str
    note_type: NoteType
    content: str  # Full formatted note text
    sections: list[NoteSection]
    status: NoteStatus
    confidence: ConfidenceLevel

    # Metadata
    generated_at: str
    template_id: str | None = None
    model_used: str = ""

    # Usage metrics
    token_usage: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0

    # Validation
    validation: NoteValidationResult | None = None

    # Additional info
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NoteEnhancementResult:
    """Result of enhancing a partial note."""

    enhanced_content: str
    original_content: str
    sections_enhanced: list[str]
    sections_added: list[str]
    confidence: ConfidenceLevel
    token_usage: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)


# ============================================================================
# Prompt Templates
# ============================================================================

HIPAA_COMPLIANCE_INSTRUCTIONS = """
CRITICAL HIPAA COMPLIANCE INSTRUCTIONS:
1. NEVER invent or hallucinate specific patient identifiers (names, dates of birth, SSN, MRN)
2. Use provided clinical data ONLY - do not add symptoms, findings, or diagnoses not in the input
3. Use placeholders like [PATIENT NAME], [DATE], [MRN] for any required identifiers
4. Focus on clinical content structure and medical terminology
5. If information is missing, explicitly note it as "[Not documented]" or similar
6. Do not fabricate lab values, vital signs, or test results not provided in the input
"""

SOAP_NOTE_SYSTEM_PROMPT = f"""You are a clinical documentation specialist AI assistant. Generate a SOAP note following standard medical documentation practices.

{HIPAA_COMPLIANCE_INSTRUCTIONS}

SOAP Note Structure:
- SUBJECTIVE: Patient's reported symptoms, history, and complaints
- OBJECTIVE: Observable findings, vital signs, physical exam, lab results
- ASSESSMENT: Clinical diagnosis/impression based on S and O
- PLAN: Treatment plan, medications, follow-up, patient education

Use professional medical terminology and standard abbreviations appropriately.
Format the note clearly with labeled sections."""

SOAP_NOTE_USER_PROMPT = """Generate a SOAP note based on the following clinical information:

Patient Information:
- Age/Sex: {age_sex}
- Chief Complaint: {chief_complaint}

History of Present Illness:
{hpi}

Past Medical History:
{pmh}

Medications:
{medications}

Allergies:
{allergies}

Vital Signs:
{vitals}

Physical Exam Findings:
{physical_exam}

Laboratory Results:
{labs}

Imaging Results:
{imaging}

Assessment/Diagnoses:
{diagnoses}

Plan Items:
{plan}

{custom_instructions}

Generate a complete SOAP note:"""

HP_NOTE_SYSTEM_PROMPT = f"""You are a clinical documentation specialist AI assistant. Generate a comprehensive History and Physical (H&P) note following standard medical documentation practices.

{HIPAA_COMPLIANCE_INSTRUCTIONS}

H&P Note Structure:
1. CHIEF COMPLAINT (CC): Brief statement of why patient is being seen
2. HISTORY OF PRESENT ILLNESS (HPI): Detailed narrative of the current problem
3. PAST MEDICAL HISTORY (PMH): Prior medical conditions
4. PAST SURGICAL HISTORY (PSH): Prior surgeries and procedures
5. MEDICATIONS: Current medications with doses
6. ALLERGIES: Drug and other allergies with reactions
7. FAMILY HISTORY (FH): Relevant family medical history
8. SOCIAL HISTORY (SH): Tobacco, alcohol, drugs, occupation, living situation
9. REVIEW OF SYSTEMS (ROS): Systematic review by organ system
10. PHYSICAL EXAMINATION: Comprehensive or focused exam findings
11. LABORATORY/IMAGING: Relevant results
12. ASSESSMENT: Clinical impression and differential diagnosis
13. PLAN: Treatment plan and disposition

Use professional medical terminology and standard abbreviations appropriately."""

HP_NOTE_USER_PROMPT = """Generate a comprehensive History and Physical note based on the following clinical information:

Patient Demographics:
- Age/Sex: {age_sex}

Chief Complaint:
{chief_complaint}

History of Present Illness:
{hpi}

Past Medical History:
{pmh}

Past Surgical History:
{psh}

Medications:
{medications}

Allergies:
{allergies}

Family History:
{family_history}

Social History:
{social_history}

Review of Systems:
{ros}

Vital Signs:
{vitals}

Physical Examination:
{physical_exam}

Laboratory Results:
{labs}

Imaging Results:
{imaging}

Assessment/Diagnoses:
{diagnoses}

Plan:
{plan}

{custom_instructions}

Generate a complete H&P note:"""

PROGRESS_NOTE_SYSTEM_PROMPT = f"""You are a clinical documentation specialist AI assistant. Generate a progress note for ongoing patient care.

{HIPAA_COMPLIANCE_INSTRUCTIONS}

Progress Note Structure:
1. INTERVAL HISTORY: Changes since last visit/note
2. CURRENT SYMPTOMS: Present complaints and status
3. VITAL SIGNS: Current vitals
4. PHYSICAL EXAMINATION: Relevant focused exam
5. LABORATORY/IMAGING: New results since last encounter
6. ASSESSMENT: Current clinical status and response to treatment
7. PLAN: Continuation, changes, or new treatments

Use professional medical terminology. Focus on changes from baseline and current clinical status."""

PROGRESS_NOTE_USER_PROMPT = """Generate a progress note based on the following clinical information:

Patient: {age_sex}
Encounter Date: {encounter_date}
Location: {location}

Interval History:
{interval_history}

Current Symptoms/Chief Complaint:
{chief_complaint}

Vital Signs:
{vitals}

Physical Examination:
{physical_exam}

New Laboratory Results:
{labs}

New Imaging Results:
{imaging}

Current Medications:
{medications}

Assessment/Diagnoses:
{diagnoses}

Plan:
{plan}

{custom_instructions}

Generate a progress note:"""

DISCHARGE_SUMMARY_SYSTEM_PROMPT = f"""You are a clinical documentation specialist AI assistant. Generate a comprehensive discharge summary for hospital discharge.

{HIPAA_COMPLIANCE_INSTRUCTIONS}

Discharge Summary Structure:
1. ADMISSION DATE / DISCHARGE DATE
2. ADMITTING DIAGNOSIS
3. DISCHARGE DIAGNOSES (primary and secondary)
4. HOSPITAL COURSE: Brief narrative of hospitalization
5. PROCEDURES PERFORMED: List with dates
6. DISCHARGE MEDICATIONS: Complete list with instructions
7. DISCHARGE CONDITION: Patient's status at discharge
8. FOLLOW-UP APPOINTMENTS
9. DISCHARGE INSTRUCTIONS: Activity, diet, wound care, warning signs
10. PENDING TESTS/RESULTS

Ensure critical information for continuity of care is clearly documented."""

DISCHARGE_SUMMARY_USER_PROMPT = """Generate a discharge summary based on the following clinical information:

Patient: {age_sex}
Admission Date: {admission_date}
Discharge Date: {discharge_date}
Encounter Type: {encounter_type}

Admitting Diagnosis:
{admitting_diagnosis}

Hospital Course:
{hospital_course}

Procedures Performed:
{procedures}

Discharge Diagnoses:
{diagnoses}

Discharge Medications:
{medications}

Follow-up Appointments:
{follow_up}

Discharge Instructions:
{instructions}

{custom_instructions}

Generate a comprehensive discharge summary:"""

PROCEDURE_NOTE_SYSTEM_PROMPT = f"""You are a clinical documentation specialist AI assistant. Generate a procedure note documenting a medical procedure.

{HIPAA_COMPLIANCE_INSTRUCTIONS}

Procedure Note Structure:
1. PROCEDURE: Name and date
2. INDICATION: Reason for procedure
3. CONSENT: Documentation of informed consent
4. ANESTHESIA: Type used
5. DESCRIPTION: Step-by-step procedure details
6. FINDINGS: What was found/observed
7. SPECIMENS: Any specimens obtained
8. ESTIMATED BLOOD LOSS
9. COMPLICATIONS: Any complications or "None"
10. DISPOSITION: Post-procedure status and plan

Document the procedure with sufficient detail for medical-legal purposes."""

PROCEDURE_NOTE_USER_PROMPT = """Generate a procedure note based on the following information:

Patient: {age_sex}
Date: {procedure_date}

Procedure:
{procedure_name}

Indication:
{indication}

Anesthesia:
{anesthesia}

Procedure Description:
{procedure_description}

Findings:
{findings}

Specimens:
{specimens}

Estimated Blood Loss:
{ebl}

Complications:
{complications}

Disposition:
{disposition}

{custom_instructions}

Generate a complete procedure note:"""

NOTE_ENHANCEMENT_SYSTEM_PROMPT = f"""You are a clinical documentation specialist AI assistant. Your task is to enhance and complete partial clinical notes.

{HIPAA_COMPLIANCE_INSTRUCTIONS}

Guidelines for enhancement:
1. Identify missing or incomplete sections
2. Complete sections using provided clinical data
3. Maintain consistency with existing content
4. Use standard medical terminology
5. Do not contradict information already documented
6. Mark any assumptions clearly as "[Inferred from context]"
"""

NOTE_VALIDATION_PROMPT = """Analyze the following clinical note for completeness and documentation quality:

Note Type: {note_type}
Note Content:
---
{note_content}
---

Evaluate:
1. Are all required sections present?
2. Is each section adequately documented?
3. Are there any inconsistencies?
4. What critical information might be missing?
5. Are there any potential compliance issues?

Provide a structured assessment:"""


# ============================================================================
# Default Templates
# ============================================================================


def get_default_templates() -> dict[str, NoteTemplate]:
    """Get default note templates for each note type."""
    templates = {}

    # SOAP Note Template
    templates["soap_standard"] = NoteTemplate(
        template_id="soap_standard",
        note_type=NoteType.SOAP,
        name="Standard SOAP Note",
        description="Standard SOAP format for outpatient encounters",
        sections=[
            NoteSectionTemplate(
                name="Subjective",
                key="subjective",
                required=True,
                order=1,
                subsections=["chief_complaint", "hpi", "ros"]
            ),
            NoteSectionTemplate(
                name="Objective",
                key="objective",
                required=True,
                order=2,
                subsections=["vitals", "physical_exam", "labs", "imaging"]
            ),
            NoteSectionTemplate(
                name="Assessment",
                key="assessment",
                required=True,
                order=3,
                subsections=["diagnoses"]
            ),
            NoteSectionTemplate(
                name="Plan",
                key="plan",
                required=True,
                order=4,
                subsections=["treatment", "medications", "follow_up"]
            ),
        ]
    )

    # H&P Template
    templates["hp_comprehensive"] = NoteTemplate(
        template_id="hp_comprehensive",
        note_type=NoteType.HP,
        name="Comprehensive History and Physical",
        description="Full H&P for admissions or new patient evaluations",
        sections=[
            NoteSectionTemplate(name="Chief Complaint", key="cc", required=True, order=1),
            NoteSectionTemplate(name="History of Present Illness", key="hpi", required=True, order=2),
            NoteSectionTemplate(name="Past Medical History", key="pmh", required=True, order=3),
            NoteSectionTemplate(name="Past Surgical History", key="psh", required=False, order=4),
            NoteSectionTemplate(name="Medications", key="medications", required=True, order=5),
            NoteSectionTemplate(name="Allergies", key="allergies", required=True, order=6),
            NoteSectionTemplate(name="Family History", key="fh", required=False, order=7),
            NoteSectionTemplate(name="Social History", key="sh", required=True, order=8),
            NoteSectionTemplate(name="Review of Systems", key="ros", required=True, order=9),
            NoteSectionTemplate(name="Physical Examination", key="pe", required=True, order=10),
            NoteSectionTemplate(name="Labs/Imaging", key="results", required=False, order=11),
            NoteSectionTemplate(name="Assessment", key="assessment", required=True, order=12),
            NoteSectionTemplate(name="Plan", key="plan", required=True, order=13),
        ]
    )

    # Progress Note Template
    templates["progress_daily"] = NoteTemplate(
        template_id="progress_daily",
        note_type=NoteType.PROGRESS,
        name="Daily Progress Note",
        description="Daily progress note for inpatient care",
        sections=[
            NoteSectionTemplate(name="Interval History", key="interval", required=True, order=1),
            NoteSectionTemplate(name="Current Symptoms", key="symptoms", required=True, order=2),
            NoteSectionTemplate(name="Vital Signs", key="vitals", required=True, order=3),
            NoteSectionTemplate(name="Physical Exam", key="exam", required=True, order=4),
            NoteSectionTemplate(name="Labs/Studies", key="results", required=False, order=5),
            NoteSectionTemplate(name="Assessment", key="assessment", required=True, order=6),
            NoteSectionTemplate(name="Plan", key="plan", required=True, order=7),
        ]
    )

    # Discharge Summary Template
    templates["discharge_standard"] = NoteTemplate(
        template_id="discharge_standard",
        note_type=NoteType.DISCHARGE,
        name="Standard Discharge Summary",
        description="Comprehensive discharge summary for hospital discharge",
        sections=[
            NoteSectionTemplate(name="Admission/Discharge Dates", key="dates", required=True, order=1),
            NoteSectionTemplate(name="Discharge Diagnoses", key="diagnoses", required=True, order=2),
            NoteSectionTemplate(name="Hospital Course", key="course", required=True, order=3),
            NoteSectionTemplate(name="Procedures", key="procedures", required=False, order=4),
            NoteSectionTemplate(name="Discharge Medications", key="medications", required=True, order=5),
            NoteSectionTemplate(name="Discharge Condition", key="condition", required=True, order=6),
            NoteSectionTemplate(name="Follow-up", key="follow_up", required=True, order=7),
            NoteSectionTemplate(name="Discharge Instructions", key="instructions", required=True, order=8),
        ]
    )

    # Procedure Note Template
    templates["procedure_standard"] = NoteTemplate(
        template_id="procedure_standard",
        note_type=NoteType.PROCEDURE,
        name="Standard Procedure Note",
        description="Documentation for medical procedures",
        sections=[
            NoteSectionTemplate(name="Procedure", key="procedure", required=True, order=1),
            NoteSectionTemplate(name="Indication", key="indication", required=True, order=2),
            NoteSectionTemplate(name="Consent", key="consent", required=True, order=3),
            NoteSectionTemplate(name="Anesthesia", key="anesthesia", required=False, order=4),
            NoteSectionTemplate(name="Description", key="description", required=True, order=5),
            NoteSectionTemplate(name="Findings", key="findings", required=True, order=6),
            NoteSectionTemplate(name="Specimens", key="specimens", required=False, order=7),
            NoteSectionTemplate(name="EBL", key="ebl", required=False, order=8),
            NoteSectionTemplate(name="Complications", key="complications", required=True, order=9),
            NoteSectionTemplate(name="Disposition", key="disposition", required=True, order=10),
        ]
    )

    return templates


# ============================================================================
# Main Service Class
# ============================================================================


class ClinicalNoteGeneratorService:
    """AI-powered clinical note generation service.

    Generates structured clinical documentation using LLMs with:
    - HIPAA-compliant prompting (no hallucinated PHI)
    - Template-based customization
    - Multiple note type support
    - Validation and enhancement capabilities
    """

    def __init__(self, llm_service: LLMService | None = None):
        """Initialize the note generator service.

        Args:
            llm_service: LLM service to use. If None, uses singleton.
        """
        self._llm_service = llm_service or get_llm_service()
        self._templates = get_default_templates()

        # Metrics
        self._total_notes_generated = 0
        self._total_tokens = 0
        self._total_cost = 0.0

        logger.info("ClinicalNoteGeneratorService initialized")

    # ========================================================================
    # Public Methods - Note Generation
    # ========================================================================

    async def generate_note(
        self,
        request: NoteGenerationRequest,
    ) -> GeneratedNote:
        """Generate a clinical note based on the request.

        Args:
            request: Note generation request with patient and encounter data.

        Returns:
            GeneratedNote with complete note content and sections.
        """
        note_id = str(uuid4())
        start_time = datetime.now()

        # Get template
        template = self._get_template(request.note_type, request.template_id)

        # Route to specific generator based on note type
        if request.note_type == NoteType.SOAP:
            result = await self._generate_soap_note(request, template)
        elif request.note_type == NoteType.HP:
            result = await self._generate_hp_note(request, template)
        elif request.note_type == NoteType.PROGRESS:
            result = await self._generate_progress_note(request, template)
        elif request.note_type == NoteType.DISCHARGE:
            result = await self._generate_discharge_summary(request, template)
        elif request.note_type == NoteType.PROCEDURE:
            result = await self._generate_procedure_note(request, template)
        else:
            raise ValueError(f"Unsupported note type: {request.note_type}")

        # Parse sections from generated content
        sections = self._parse_sections(result["content"], template)

        # Validate the note
        validation = self._validate_note(sections, template)

        # Determine confidence and status
        confidence = self._calculate_confidence(validation, result)
        status = self._determine_status(validation, confidence)

        # Update metrics
        self._total_notes_generated += 1
        self._total_tokens += result.get("token_usage", 0)
        self._total_cost += result.get("cost_usd", 0.0)

        return GeneratedNote(
            note_id=note_id,
            note_type=request.note_type,
            content=result["content"],
            sections=sections,
            status=status,
            confidence=confidence,
            generated_at=start_time.isoformat(),
            template_id=template.template_id if template else None,
            model_used=result.get("model", ""),
            token_usage=result.get("token_usage", 0),
            cost_usd=result.get("cost_usd", 0.0),
            latency_ms=result.get("latency_ms", 0.0),
            validation=validation,
            warnings=result.get("warnings", []),
            metadata={
                "patient_age_sex": self._format_age_sex(request.patient_data),
                "encounter_type": request.encounter_data.encounter_type,
            }
        )

    async def generate_soap_note(
        self,
        patient_data: PatientData,
        encounter_data: EncounterData,
        template_id: str | None = None,
        provider: LLMProvider | None = None,
        model: str | None = None,
    ) -> GeneratedNote:
        """Generate a SOAP note.

        Convenience method for SOAP note generation.
        """
        request = NoteGenerationRequest(
            note_type=NoteType.SOAP,
            patient_data=patient_data,
            encounter_data=encounter_data,
            template_id=template_id,
            provider=provider,
            model=model,
        )
        return await self.generate_note(request)

    async def generate_hp_note(
        self,
        patient_data: PatientData,
        encounter_data: EncounterData,
        template_id: str | None = None,
        provider: LLMProvider | None = None,
        model: str | None = None,
    ) -> GeneratedNote:
        """Generate a History and Physical note.

        Convenience method for H&P note generation.
        """
        request = NoteGenerationRequest(
            note_type=NoteType.HP,
            patient_data=patient_data,
            encounter_data=encounter_data,
            template_id=template_id,
            provider=provider,
            model=model,
        )
        return await self.generate_note(request)

    async def generate_progress_note(
        self,
        patient_data: PatientData,
        encounter_data: EncounterData,
        template_id: str | None = None,
        provider: LLMProvider | None = None,
        model: str | None = None,
    ) -> GeneratedNote:
        """Generate a progress note.

        Convenience method for progress note generation.
        """
        request = NoteGenerationRequest(
            note_type=NoteType.PROGRESS,
            patient_data=patient_data,
            encounter_data=encounter_data,
            template_id=template_id,
            provider=provider,
            model=model,
        )
        return await self.generate_note(request)

    async def generate_discharge_summary(
        self,
        patient_data: PatientData,
        encounter_data: EncounterData,
        template_id: str | None = None,
        provider: LLMProvider | None = None,
        model: str | None = None,
    ) -> GeneratedNote:
        """Generate a discharge summary.

        Convenience method for discharge summary generation.
        """
        request = NoteGenerationRequest(
            note_type=NoteType.DISCHARGE,
            patient_data=patient_data,
            encounter_data=encounter_data,
            template_id=template_id,
            provider=provider,
            model=model,
        )
        return await self.generate_note(request)

    async def generate_procedure_note(
        self,
        patient_data: PatientData,
        encounter_data: EncounterData,
        template_id: str | None = None,
        provider: LLMProvider | None = None,
        model: str | None = None,
    ) -> GeneratedNote:
        """Generate a procedure note.

        Convenience method for procedure note generation.
        """
        request = NoteGenerationRequest(
            note_type=NoteType.PROCEDURE,
            patient_data=patient_data,
            encounter_data=encounter_data,
            template_id=template_id,
            provider=provider,
            model=model,
        )
        return await self.generate_note(request)

    # ========================================================================
    # Public Methods - Enhancement and Validation
    # ========================================================================

    async def enhance_note(
        self,
        partial_content: str,
        note_type: NoteType,
        patient_data: PatientData | None = None,
        encounter_data: EncounterData | None = None,
        provider: LLMProvider | None = None,
        model: str | None = None,
    ) -> NoteEnhancementResult:
        """Enhance or complete a partial clinical note.

        Args:
            partial_content: Existing partial note content.
            note_type: Type of note being enhanced.
            patient_data: Optional additional patient data.
            encounter_data: Optional additional encounter data.
            provider: LLM provider to use.
            model: LLM model to use.

        Returns:
            NoteEnhancementResult with enhanced content.
        """
        template = self._get_template(note_type, None)

        # Build enhancement prompt
        additional_context = ""
        if patient_data:
            additional_context += f"\n\nPatient Information:\n{self._format_patient_context(patient_data)}"
        if encounter_data:
            additional_context += f"\n\nEncounter Information:\n{self._format_encounter_context(encounter_data)}"

        prompt = f"""Enhance and complete the following partial clinical note.

Note Type: {note_type.value.upper()}

Existing Content:
---
{partial_content}
---
{additional_context}

Required sections for this note type:
{self._format_required_sections(template)}

Instructions:
1. Identify incomplete or missing sections
2. Complete any partial sections using available data
3. Add missing required sections with appropriate placeholders
4. Maintain consistency with existing content
5. Mark inferred content clearly

Provide the enhanced complete note:"""

        try:
            response = await self._llm_service.generate(
                prompt=prompt,
                system_prompt=NOTE_ENHANCEMENT_SYSTEM_PROMPT,
                model=model,
                provider=provider,
                temperature=0.3,
            )

            # Parse to identify what was enhanced
            sections_enhanced, sections_added = self._identify_enhancements(
                partial_content,
                response.content,
                template
            )

            # Determine confidence
            confidence = ConfidenceLevel.MEDIUM
            if len(sections_added) == 0 and len(sections_enhanced) <= 2:
                confidence = ConfidenceLevel.HIGH
            elif len(sections_added) > 3:
                confidence = ConfidenceLevel.LOW

            return NoteEnhancementResult(
                enhanced_content=response.content,
                original_content=partial_content,
                sections_enhanced=sections_enhanced,
                sections_added=sections_added,
                confidence=confidence,
                token_usage=response.token_usage.total_tokens,
                cost_usd=response.cost_estimate.total_cost,
                latency_ms=response.latency_ms,
            )

        except Exception as e:
            logger.error(f"Note enhancement failed: {e}")
            return NoteEnhancementResult(
                enhanced_content=partial_content,
                original_content=partial_content,
                sections_enhanced=[],
                sections_added=[],
                confidence=ConfidenceLevel.LOW,
                warnings=[f"Enhancement failed: {str(e)}"],
            )

    async def validate_note(
        self,
        content: str,
        note_type: NoteType,
        provider: LLMProvider | None = None,
        model: str | None = None,
    ) -> NoteValidationResult:
        """Validate a clinical note for completeness and quality.

        Args:
            content: Note content to validate.
            note_type: Type of note being validated.
            provider: LLM provider to use.
            model: LLM model to use.

        Returns:
            NoteValidationResult with validation details.
        """
        template = self._get_template(note_type, None)

        # Parse sections from content
        sections = self._parse_sections(content, template)

        # Basic validation
        validation = self._validate_note(sections, template)

        # Optional: Use LLM for deeper validation
        try:
            prompt = NOTE_VALIDATION_PROMPT.format(
                note_type=note_type.value.upper(),
                note_content=content[:5000],  # Truncate for API limits
            )

            response = await self._llm_service.generate(
                prompt=prompt,
                system_prompt="You are a clinical documentation quality reviewer.",
                model=model,
                provider=provider,
                temperature=0.2,
                max_tokens=500,
            )

            # Parse LLM suggestions and add to validation
            llm_suggestions = self._parse_validation_suggestions(response.content)
            validation.suggestions.extend(llm_suggestions)

        except Exception as e:
            logger.warning(f"LLM validation enhancement failed: {e}")

        return validation

    # ========================================================================
    # Public Methods - Templates
    # ========================================================================

    def get_templates(self, note_type: NoteType | None = None) -> list[NoteTemplate]:
        """Get available note templates.

        Args:
            note_type: Optional filter by note type.

        Returns:
            List of available templates.
        """
        templates = list(self._templates.values())
        if note_type:
            templates = [t for t in templates if t.note_type == note_type]
        return templates

    def get_template(self, template_id: str) -> NoteTemplate | None:
        """Get a specific template by ID.

        Args:
            template_id: Template identifier.

        Returns:
            NoteTemplate if found, None otherwise.
        """
        return self._templates.get(template_id)

    def register_template(self, template: NoteTemplate) -> None:
        """Register a custom template.

        Args:
            template: Template to register.
        """
        self._templates[template.template_id] = template
        logger.info(f"Registered custom template: {template.template_id}")

    # ========================================================================
    # Private Methods - Note Generation
    # ========================================================================

    async def _generate_soap_note(
        self,
        request: NoteGenerationRequest,
        template: NoteTemplate | None,
    ) -> dict[str, Any]:
        """Generate SOAP note content."""
        patient = request.patient_data
        encounter = request.encounter_data

        prompt = SOAP_NOTE_USER_PROMPT.format(
            age_sex=self._format_age_sex(patient),
            chief_complaint=patient.chief_complaint or "[Not documented]",
            hpi=patient.history_present_illness or "[Not documented]",
            pmh=self._format_list(patient.past_medical_history) or "[None reported]",
            medications=self._format_list(patient.medications) or "[None]",
            allergies=self._format_list(patient.allergies) or "NKDA",
            vitals=self._format_vitals(patient.vitals),
            physical_exam=self._format_dict(encounter.physical_exam) or "[Not documented]",
            labs=self._format_labs(encounter.lab_results),
            imaging=self._format_dict(encounter.imaging_results) or "[None]",
            diagnoses=self._format_diagnoses(encounter.diagnoses, encounter.icd10_codes),
            plan=self._format_list(encounter.plan_items) or "[To be determined]",
            custom_instructions=request.custom_instructions or "",
        )

        return await self._call_llm(
            prompt=prompt,
            system_prompt=SOAP_NOTE_SYSTEM_PROMPT,
            provider=request.provider,
            model=request.model,
        )

    async def _generate_hp_note(
        self,
        request: NoteGenerationRequest,
        template: NoteTemplate | None,
    ) -> dict[str, Any]:
        """Generate History and Physical note content."""
        patient = request.patient_data
        encounter = request.encounter_data

        prompt = HP_NOTE_USER_PROMPT.format(
            age_sex=self._format_age_sex(patient),
            chief_complaint=patient.chief_complaint or "[Not documented]",
            hpi=patient.history_present_illness or "[Not documented]",
            pmh=self._format_list(patient.past_medical_history) or "[None reported]",
            psh=self._format_list(patient.past_surgical_history) or "[None reported]",
            medications=self._format_list(patient.medications) or "[None]",
            allergies=self._format_list(patient.allergies) or "NKDA",
            family_history=patient.family_history or "[Not documented]",
            social_history=patient.social_history or "[Not documented]",
            ros=self._format_ros(patient.review_of_systems),
            vitals=self._format_vitals(patient.vitals),
            physical_exam=self._format_dict(encounter.physical_exam) or "[Not documented]",
            labs=self._format_labs(encounter.lab_results),
            imaging=self._format_dict(encounter.imaging_results) or "[None]",
            diagnoses=self._format_diagnoses(encounter.diagnoses, encounter.icd10_codes),
            plan=self._format_list(encounter.plan_items) or "[To be determined]",
            custom_instructions=request.custom_instructions or "",
        )

        return await self._call_llm(
            prompt=prompt,
            system_prompt=HP_NOTE_SYSTEM_PROMPT,
            provider=request.provider,
            model=request.model,
        )

    async def _generate_progress_note(
        self,
        request: NoteGenerationRequest,
        template: NoteTemplate | None,
    ) -> dict[str, Any]:
        """Generate progress note content."""
        patient = request.patient_data
        encounter = request.encounter_data

        prompt = PROGRESS_NOTE_USER_PROMPT.format(
            age_sex=self._format_age_sex(patient),
            encounter_date=encounter.encounter_date or "[Date]",
            location=encounter.location or "[Location]",
            interval_history=encounter.interval_history or "[Document interval changes]",
            chief_complaint=patient.chief_complaint or "[Current status]",
            vitals=self._format_vitals(patient.vitals),
            physical_exam=self._format_dict(encounter.physical_exam) or "[Focused exam]",
            labs=self._format_labs(encounter.lab_results),
            imaging=self._format_dict(encounter.imaging_results) or "[None new]",
            medications=self._format_list(patient.medications) or "[Current meds]",
            diagnoses=self._format_diagnoses(encounter.diagnoses, encounter.icd10_codes),
            plan=self._format_list(encounter.plan_items) or "[Continue current management]",
            custom_instructions=request.custom_instructions or "",
        )

        return await self._call_llm(
            prompt=prompt,
            system_prompt=PROGRESS_NOTE_SYSTEM_PROMPT,
            provider=request.provider,
            model=request.model,
        )

    async def _generate_discharge_summary(
        self,
        request: NoteGenerationRequest,
        template: NoteTemplate | None,
    ) -> dict[str, Any]:
        """Generate discharge summary content."""
        patient = request.patient_data
        encounter = request.encounter_data

        # Determine admission diagnosis (first diagnosis or chief complaint)
        admitting_dx = encounter.diagnoses[0] if encounter.diagnoses else patient.chief_complaint or "[Admitting diagnosis]"

        prompt = DISCHARGE_SUMMARY_USER_PROMPT.format(
            age_sex=self._format_age_sex(patient),
            admission_date="[Admission Date]",
            discharge_date=encounter.encounter_date or "[Discharge Date]",
            encounter_type=encounter.encounter_type,
            admitting_diagnosis=admitting_dx,
            hospital_course=encounter.hospital_course or "[Document hospital course]",
            procedures=self._format_list(encounter.procedures_performed) or "[None]",
            diagnoses=self._format_diagnoses(encounter.diagnoses, encounter.icd10_codes),
            medications=self._format_list(patient.medications) or "[Discharge medications]",
            follow_up=self._format_list(encounter.follow_up) or "[Follow-up appointments]",
            instructions="[Discharge instructions, activity restrictions, warning signs]",
            custom_instructions=request.custom_instructions or "",
        )

        return await self._call_llm(
            prompt=prompt,
            system_prompt=DISCHARGE_SUMMARY_SYSTEM_PROMPT,
            provider=request.provider,
            model=request.model,
        )

    async def _generate_procedure_note(
        self,
        request: NoteGenerationRequest,
        template: NoteTemplate | None,
    ) -> dict[str, Any]:
        """Generate procedure note content."""
        patient = request.patient_data
        encounter = request.encounter_data

        prompt = PROCEDURE_NOTE_USER_PROMPT.format(
            age_sex=self._format_age_sex(patient),
            procedure_date=encounter.encounter_date or "[Date]",
            procedure_name=encounter.procedure_name or "[Procedure name]",
            indication=encounter.procedure_indication or "[Indication]",
            anesthesia="[Type of anesthesia]",
            procedure_description="[Detailed procedure description]",
            findings=encounter.procedure_findings or "[Findings]",
            specimens=self._format_list(encounter.specimens) or "None",
            ebl=encounter.estimated_blood_loss or "Minimal",
            complications=encounter.procedure_complications or "None",
            disposition="[Post-procedure status and plan]",
            custom_instructions=request.custom_instructions or "",
        )

        return await self._call_llm(
            prompt=prompt,
            system_prompt=PROCEDURE_NOTE_SYSTEM_PROMPT,
            provider=request.provider,
            model=request.model,
        )

    # ========================================================================
    # Private Methods - LLM Interaction
    # ========================================================================

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: str,
        provider: LLMProvider | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Call LLM and return structured result."""
        try:
            response = await self._llm_service.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                provider=provider,
                temperature=0.3,
            )

            return {
                "content": response.content,
                "model": response.model,
                "token_usage": response.token_usage.total_tokens,
                "cost_usd": response.cost_estimate.total_cost,
                "latency_ms": response.latency_ms,
                "warnings": [],
            }

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {
                "content": f"Error generating note: {str(e)}",
                "model": "error",
                "token_usage": 0,
                "cost_usd": 0.0,
                "latency_ms": 0.0,
                "warnings": [f"Generation error: {str(e)}"],
            }

    # ========================================================================
    # Private Methods - Formatting Helpers
    # ========================================================================

    def _format_age_sex(self, patient: PatientData) -> str:
        """Format patient age and sex."""
        parts = []
        if patient.age:
            parts.append(f"{patient.age} year-old")
        if patient.sex:
            sex_map = {"M": "male", "F": "female"}
            parts.append(sex_map.get(patient.sex, patient.sex))
        return " ".join(parts) if parts else "[Age/Sex not specified]"

    def _format_list(self, items: list[str] | None) -> str:
        """Format a list of items."""
        if not items:
            return ""
        return "\n".join(f"- {item}" for item in items)

    def _format_dict(self, data: dict[str, Any] | None) -> str:
        """Format a dictionary as text."""
        if not data:
            return ""
        lines = []
        for key, value in data.items():
            key_formatted = key.replace("_", " ").title()
            lines.append(f"- {key_formatted}: {value}")
        return "\n".join(lines)

    def _format_vitals(self, vitals: dict[str, Any]) -> str:
        """Format vital signs."""
        if not vitals:
            return "[Vital signs not documented]"

        vital_labels = {
            "bp": "Blood Pressure",
            "hr": "Heart Rate",
            "rr": "Respiratory Rate",
            "temp": "Temperature",
            "spo2": "SpO2",
            "weight": "Weight",
            "height": "Height",
            "bmi": "BMI",
        }

        lines = []
        for key, value in vitals.items():
            label = vital_labels.get(key.lower(), key.replace("_", " ").title())
            lines.append(f"- {label}: {value}")
        return "\n".join(lines)

    def _format_labs(self, labs: dict[str, Any]) -> str:
        """Format laboratory results."""
        if not labs:
            return "[No labs documented]"

        lines = []
        for test, value in labs.items():
            test_formatted = test.replace("_", " ").upper()
            if isinstance(value, dict):
                # Handle complex lab results with components
                lines.append(f"{test_formatted}:")
                for component, result in value.items():
                    lines.append(f"  - {component}: {result}")
            else:
                lines.append(f"- {test_formatted}: {value}")
        return "\n".join(lines)

    def _format_ros(self, ros: dict[str, str]) -> str:
        """Format review of systems."""
        if not ros:
            return "[ROS not documented]"

        lines = []
        for system, findings in ros.items():
            system_formatted = system.replace("_", " ").title()
            lines.append(f"- {system_formatted}: {findings}")
        return "\n".join(lines)

    def _format_diagnoses(
        self,
        diagnoses: list[str],
        icd10_codes: list[str] | None = None,
    ) -> str:
        """Format diagnoses with optional ICD-10 codes."""
        if not diagnoses:
            return "[Diagnoses not documented]"

        lines = []
        for i, dx in enumerate(diagnoses):
            code = icd10_codes[i] if icd10_codes and i < len(icd10_codes) else ""
            if code:
                lines.append(f"{i+1}. {dx} ({code})")
            else:
                lines.append(f"{i+1}. {dx}")
        return "\n".join(lines)

    def _format_patient_context(self, patient: PatientData) -> str:
        """Format patient data for context."""
        parts = []
        if patient.age or patient.sex:
            parts.append(f"Demographics: {self._format_age_sex(patient)}")
        if patient.chief_complaint:
            parts.append(f"Chief Complaint: {patient.chief_complaint}")
        if patient.past_medical_history:
            parts.append(f"PMH: {', '.join(patient.past_medical_history)}")
        if patient.medications:
            parts.append(f"Medications: {', '.join(patient.medications)}")
        return "\n".join(parts)

    def _format_encounter_context(self, encounter: EncounterData) -> str:
        """Format encounter data for context."""
        parts = []
        if encounter.diagnoses:
            parts.append(f"Diagnoses: {', '.join(encounter.diagnoses)}")
        if encounter.physical_exam:
            parts.append(f"Exam: {self._format_dict(encounter.physical_exam)}")
        return "\n".join(parts)

    def _format_required_sections(self, template: NoteTemplate | None) -> str:
        """Format list of required sections for a template."""
        if not template:
            return "Standard sections for this note type"

        required = [s.name for s in template.sections if s.required]
        optional = [s.name for s in template.sections if not s.required]

        result = "Required: " + ", ".join(required)
        if optional:
            result += "\nOptional: " + ", ".join(optional)
        return result

    # ========================================================================
    # Private Methods - Parsing and Validation
    # ========================================================================

    def _get_template(
        self,
        note_type: NoteType,
        template_id: str | None,
    ) -> NoteTemplate | None:
        """Get the appropriate template for note generation."""
        if template_id and template_id in self._templates:
            return self._templates[template_id]

        # Find default template for note type
        default_map = {
            NoteType.SOAP: "soap_standard",
            NoteType.HP: "hp_comprehensive",
            NoteType.PROGRESS: "progress_daily",
            NoteType.DISCHARGE: "discharge_standard",
            NoteType.PROCEDURE: "procedure_standard",
        }

        default_id = default_map.get(note_type)
        return self._templates.get(default_id) if default_id else None

    def _parse_sections(
        self,
        content: str,
        template: NoteTemplate | None,
    ) -> list[NoteSection]:
        """Parse content into structured sections."""
        sections = []

        if not template:
            # Return single section with full content
            return [NoteSection(
                name="Content",
                key="content",
                content=content,
                required=True,
                order=1,
                status=SectionStatus.GENERATED,
                word_count=len(content.split()),
            )]

        # Try to identify sections based on template
        remaining_content = content

        for section_template in sorted(template.sections, key=lambda s: s.order):
            section_content = self._extract_section(
                remaining_content,
                section_template.name,
                section_template.key,
            )

            status = SectionStatus.GENERATED if section_content else SectionStatus.MISSING
            if section_content and "[Not documented]" in section_content:
                status = SectionStatus.PARTIAL

            sections.append(NoteSection(
                name=section_template.name,
                key=section_template.key,
                content=section_content or "",
                required=section_template.required,
                order=section_template.order,
                status=status,
                word_count=len(section_content.split()) if section_content else 0,
            ))

        return sections

    def _extract_section(
        self,
        content: str,
        section_name: str,
        section_key: str,
    ) -> str:
        """Extract a specific section from note content."""
        # Try various patterns to find section
        patterns = [
            # All caps with colon
            rf"(?:{section_name.upper()}|{section_key.upper()})[\s:]+(.+?)(?=\n[A-Z]{{2,}}[\s:]|\Z)",
            # Title case with colon
            rf"(?:{section_name}|{section_key})[\s:]+(.+?)(?=\n[A-Z][a-z]+[\s:]|\Z)",
            # Numbered section
            rf"\d+\.\s*{section_name}[\s:]+(.+?)(?=\n\d+\.|\Z)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        return ""

    def _validate_note(
        self,
        sections: list[NoteSection],
        template: NoteTemplate | None,
    ) -> NoteValidationResult:
        """Validate note sections against template requirements."""
        missing = []
        incomplete = []
        warnings = []
        suggestions = []

        if not template:
            # Basic validation without template
            total_words = sum(s.word_count for s in sections)
            if total_words < 50:
                warnings.append("Note appears very brief")
                suggestions.append("Consider adding more clinical detail")

            return NoteValidationResult(
                is_valid=True,
                completeness_score=1.0 if total_words >= 50 else 0.5,
                warnings=warnings,
                suggestions=suggestions,
            )

        # Validate against template
        section_map = {s.key: s for s in sections}
        required_count = 0
        complete_required = 0

        for section_template in template.sections:
            section = section_map.get(section_template.key)

            if section_template.required:
                required_count += 1

                if not section or section.status == SectionStatus.MISSING:
                    missing.append(section_template.name)
                elif section.status == SectionStatus.PARTIAL:
                    incomplete.append(section_template.name)
                    complete_required += 0.5
                else:
                    complete_required += 1

        completeness = complete_required / required_count if required_count > 0 else 1.0

        if missing:
            warnings.append(f"Missing required sections: {', '.join(missing)}")
            suggestions.append("Complete all required sections before finalizing")

        if incomplete:
            warnings.append(f"Incomplete sections: {', '.join(incomplete)}")
            suggestions.append("Review and complete partial sections")

        return NoteValidationResult(
            is_valid=len(missing) == 0,
            completeness_score=round(completeness, 2),
            missing_sections=missing,
            incomplete_sections=incomplete,
            warnings=warnings,
            suggestions=suggestions,
        )

    def _calculate_confidence(
        self,
        validation: NoteValidationResult,
        result: dict[str, Any],
    ) -> ConfidenceLevel:
        """Calculate confidence level for generated note."""
        if validation.completeness_score >= 0.9 and not result.get("warnings"):
            return ConfidenceLevel.HIGH
        elif validation.completeness_score >= 0.7:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _determine_status(
        self,
        validation: NoteValidationResult,
        confidence: ConfidenceLevel,
    ) -> NoteStatus:
        """Determine note status based on validation."""
        if not validation.is_valid:
            return NoteStatus.INCOMPLETE
        elif validation.incomplete_sections:
            return NoteStatus.NEEDS_REVIEW
        elif confidence == ConfidenceLevel.LOW:
            return NoteStatus.NEEDS_REVIEW
        elif confidence == ConfidenceLevel.MEDIUM:
            return NoteStatus.DRAFT
        else:
            return NoteStatus.COMPLETE

    def _identify_enhancements(
        self,
        original: str,
        enhanced: str,
        template: NoteTemplate | None,
    ) -> tuple[list[str], list[str]]:
        """Identify what sections were enhanced or added."""
        enhanced_sections = []
        added_sections = []

        if not template:
            return enhanced_sections, added_sections

        original_lower = original.lower()
        enhanced_lower = enhanced.lower()

        for section in template.sections:
            section_name_lower = section.name.lower()

            # Check if section was in original
            in_original = section_name_lower in original_lower or section.key in original_lower
            in_enhanced = section_name_lower in enhanced_lower or section.key in enhanced_lower

            if in_enhanced and not in_original:
                added_sections.append(section.name)
            elif in_original and in_enhanced:
                # Section existed but may have been enhanced
                # Simple heuristic: check if content after section header increased
                original_content = self._extract_section(original, section.name, section.key)
                enhanced_content = self._extract_section(enhanced, section.name, section.key)

                if len(enhanced_content) > len(original_content) * 1.2:  # 20% increase
                    enhanced_sections.append(section.name)

        return enhanced_sections, added_sections

    def _parse_validation_suggestions(self, llm_response: str) -> list[str]:
        """Parse validation suggestions from LLM response."""
        suggestions = []

        # Look for numbered items or bullet points
        lines = llm_response.split("\n")
        for line in lines:
            line = line.strip()
            if line and (
                line.startswith("-") or
                line.startswith("*") or
                re.match(r"^\d+[.)]\s", line)
            ):
                # Clean up the line
                suggestion = re.sub(r"^[-*\d.)]+\s*", "", line).strip()
                if suggestion and len(suggestion) > 10:
                    suggestions.append(suggestion)

        return suggestions[:5]  # Limit to 5 suggestions

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "total_notes_generated": self._total_notes_generated,
            "total_tokens_used": self._total_tokens,
            "total_cost_usd": round(self._total_cost, 4),
            "available_templates": len(self._templates),
            "llm_service_stats": self._llm_service.get_stats(),
        }


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: ClinicalNoteGeneratorService | None = None
_service_lock = threading.Lock()


def get_note_generator_service() -> ClinicalNoteGeneratorService:
    """Get or create the singleton note generator service instance.

    Returns:
        ClinicalNoteGeneratorService singleton instance.
    """
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = ClinicalNoteGeneratorService()

    return _service_instance


def reset_note_generator_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None


# ============================================================================
# Patient Summary Generation
# ============================================================================

PATIENT_SUMMARY_SYSTEM_PROMPT = f"""You are a clinical documentation specialist AI assistant. Generate a concise patient summary based on the provided clinical facts.

{HIPAA_COMPLIANCE_INSTRUCTIONS}

Summary Guidelines:
1. Organize information by clinical relevance
2. Highlight active problems and current medications
3. Include recent encounters and significant findings
4. Use professional medical terminology
5. Keep the summary focused on clinically actionable information
6. Include relevant dates when available
7. Note any alerts or concerns that need attention

Format the summary in clear sections for easy reading.
"""

PATIENT_SUMMARY_USER_PROMPT = """Generate a concise patient summary based on the following clinical facts:

Patient Demographics:
{demographics}

Active Problems:
{problems}

Current Medications:
{medications}

Recent Visits/Encounters:
{encounters}

Recent Lab Results:
{labs}

Recent Vital Signs:
{vitals}

Allergies:
{allergies}

Focus Areas: {focus_areas}

Additional Context:
{additional_context}

Generate a concise, clinically useful patient summary:"""


@dataclass
class PatientFact:
    """A clinical fact about a patient."""

    fact_id: str
    fact_type: str  # problem, medication, lab, vital, allergy, encounter, etc.
    description: str
    code: str | None = None  # ICD-10, RxNorm, LOINC, etc.
    code_system: str | None = None
    value: str | None = None
    unit: str | None = None
    date: str | None = None
    status: str | None = None  # active, resolved, etc.
    source_document_id: str | None = None
    confidence: float = 1.0


@dataclass
class PatientSummaryRequest:
    """Request to generate a patient summary."""

    patient_id: str
    facts: list[PatientFact]
    focus_areas: list[str] = field(default_factory=list)  # problems, meds, visits, etc.
    max_length: int | None = None
    include_citations: bool = True
    provider: LLMProvider | None = None
    model: str | None = None


@dataclass
class FactCitation:
    """Citation linking summary text to source facts."""

    text_span: str  # The text in the summary
    fact_id: str  # ID of the source fact
    fact_type: str
    source_description: str


@dataclass
class PatientSummary:
    """Generated patient summary with citations."""

    summary_id: str
    patient_id: str
    content: str
    sections: dict[str, str]  # section_name -> content
    citations: list[FactCitation]
    generated_at: str
    focus_areas: list[str]
    fact_count: int
    model_used: str
    token_usage: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


@dataclass
class NoteHistoryEntry:
    """Entry in the note generation history."""

    note_id: str
    note_type: NoteType
    patient_id: str | None
    template_id: str | None
    status: NoteStatus
    generated_at: str
    model_used: str
    token_usage: int
    cost_usd: float
    preview: str  # First 200 chars of content


@dataclass
class CustomTemplateRequest:
    """Request to customize a note template."""

    base_template_id: str
    new_template_id: str
    name: str
    description: str | None = None
    sections_to_add: list[NoteSectionTemplate] = field(default_factory=list)
    sections_to_remove: list[str] = field(default_factory=list)  # section keys
    section_order: list[str] | None = None  # ordered list of section keys
    custom_prompts: dict[str, str] = field(default_factory=dict)  # section_key -> prompt


class PatientSummaryService:
    """Service for generating patient summaries from clinical facts."""

    def __init__(self, llm_service: LLMService | None = None):
        """Initialize the patient summary service."""
        self._llm_service = llm_service or get_llm_service()
        self._history: list[NoteHistoryEntry] = []
        self._max_history = 100
        logger.info("PatientSummaryService initialized")

    async def generate_summary(
        self,
        request: PatientSummaryRequest,
    ) -> PatientSummary:
        """Generate a patient summary from clinical facts.

        Args:
            request: Summary generation request with patient facts.

        Returns:
            PatientSummary with generated content and citations.
        """
        summary_id = str(uuid4())
        start_time = datetime.now()

        # Organize facts by type
        facts_by_type = self._organize_facts(request.facts)

        # Build prompt
        focus_str = ", ".join(request.focus_areas) if request.focus_areas else "all areas"

        prompt = PATIENT_SUMMARY_USER_PROMPT.format(
            demographics=self._format_demographics(facts_by_type.get("demographic", [])),
            problems=self._format_problems(facts_by_type.get("problem", [])),
            medications=self._format_medications(facts_by_type.get("medication", [])),
            encounters=self._format_encounters(facts_by_type.get("encounter", [])),
            labs=self._format_labs(facts_by_type.get("lab", [])),
            vitals=self._format_vitals_facts(facts_by_type.get("vital", [])),
            allergies=self._format_allergies(facts_by_type.get("allergy", [])),
            focus_areas=focus_str,
            additional_context=self._format_other_facts(facts_by_type),
        )

        try:
            response = await self._llm_service.generate(
                prompt=prompt,
                system_prompt=PATIENT_SUMMARY_SYSTEM_PROMPT,
                model=request.model,
                provider=request.provider,
                temperature=0.3,
                max_tokens=request.max_length or 2000,
            )

            # Parse sections from response
            sections = self._parse_summary_sections(response.content)

            # Generate citations if requested
            citations = []
            if request.include_citations:
                citations = self._generate_citations(response.content, request.facts)

            # Determine confidence
            confidence = ConfidenceLevel.HIGH if len(request.facts) >= 5 else (
                ConfidenceLevel.MEDIUM if len(request.facts) >= 2 else ConfidenceLevel.LOW
            )

            return PatientSummary(
                summary_id=summary_id,
                patient_id=request.patient_id,
                content=response.content,
                sections=sections,
                citations=citations,
                generated_at=start_time.isoformat(),
                focus_areas=request.focus_areas,
                fact_count=len(request.facts),
                model_used=response.model,
                token_usage=response.token_usage.total_tokens,
                cost_usd=response.cost_estimate.total_cost,
                latency_ms=response.latency_ms,
                confidence=confidence,
            )

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return PatientSummary(
                summary_id=summary_id,
                patient_id=request.patient_id,
                content=f"Error generating summary: {str(e)}",
                sections={},
                citations=[],
                generated_at=start_time.isoformat(),
                focus_areas=request.focus_areas,
                fact_count=len(request.facts),
                model_used="error",
                confidence=ConfidenceLevel.LOW,
            )

    def _organize_facts(self, facts: list[PatientFact]) -> dict[str, list[PatientFact]]:
        """Organize facts by type."""
        organized: dict[str, list[PatientFact]] = {}
        for fact in facts:
            fact_type = fact.fact_type.lower()
            if fact_type not in organized:
                organized[fact_type] = []
            organized[fact_type].append(fact)
        return organized

    def _format_demographics(self, facts: list[PatientFact]) -> str:
        """Format demographic facts."""
        if not facts:
            return "[Demographics not available]"
        lines = []
        for fact in facts:
            lines.append(f"- {fact.description}")
        return "\n".join(lines)

    def _format_problems(self, facts: list[PatientFact]) -> str:
        """Format problem/condition facts."""
        if not facts:
            return "[No problems documented]"
        lines = []
        for fact in sorted(facts, key=lambda f: f.status == "active", reverse=True):
            status = f" ({fact.status})" if fact.status else ""
            code = f" [{fact.code}]" if fact.code else ""
            date = f" - {fact.date}" if fact.date else ""
            lines.append(f"- {fact.description}{status}{code}{date}")
        return "\n".join(lines)

    def _format_medications(self, facts: list[PatientFact]) -> str:
        """Format medication facts."""
        if not facts:
            return "[No medications documented]"
        lines = []
        for fact in facts:
            dose = f" {fact.value} {fact.unit}" if fact.value else ""
            status = f" ({fact.status})" if fact.status else ""
            lines.append(f"- {fact.description}{dose}{status}")
        return "\n".join(lines)

    def _format_encounters(self, facts: list[PatientFact]) -> str:
        """Format encounter facts."""
        if not facts:
            return "[No recent encounters]"
        lines = []
        for fact in sorted(facts, key=lambda f: f.date or "", reverse=True)[:5]:
            date = f" ({fact.date})" if fact.date else ""
            lines.append(f"- {fact.description}{date}")
        return "\n".join(lines)

    def _format_labs(self, facts: list[PatientFact]) -> str:
        """Format lab result facts."""
        if not facts:
            return "[No recent labs]"
        lines = []
        for fact in sorted(facts, key=lambda f: f.date or "", reverse=True)[:10]:
            value = f": {fact.value}" if fact.value else ""
            unit = f" {fact.unit}" if fact.unit else ""
            date = f" ({fact.date})" if fact.date else ""
            lines.append(f"- {fact.description}{value}{unit}{date}")
        return "\n".join(lines)

    def _format_vitals_facts(self, facts: list[PatientFact]) -> str:
        """Format vital sign facts."""
        if not facts:
            return "[No recent vitals]"
        lines = []
        for fact in sorted(facts, key=lambda f: f.date or "", reverse=True)[:10]:
            value = f": {fact.value}" if fact.value else ""
            unit = f" {fact.unit}" if fact.unit else ""
            date = f" ({fact.date})" if fact.date else ""
            lines.append(f"- {fact.description}{value}{unit}{date}")
        return "\n".join(lines)

    def _format_allergies(self, facts: list[PatientFact]) -> str:
        """Format allergy facts."""
        if not facts:
            return "NKDA (No Known Drug Allergies)"
        lines = []
        for fact in facts:
            reaction = f" - {fact.value}" if fact.value else ""
            lines.append(f"- {fact.description}{reaction}")
        return "\n".join(lines)

    def _format_other_facts(self, facts_by_type: dict[str, list[PatientFact]]) -> str:
        """Format other fact types not covered above."""
        known_types = {"demographic", "problem", "medication", "encounter", "lab", "vital", "allergy"}
        other_facts = []
        for fact_type, facts in facts_by_type.items():
            if fact_type not in known_types:
                other_facts.extend(facts)

        if not other_facts:
            return "[No additional information]"

        lines = []
        for fact in other_facts:
            lines.append(f"- {fact.fact_type}: {fact.description}")
        return "\n".join(lines)

    def _parse_summary_sections(self, content: str) -> dict[str, str]:
        """Parse sections from summary content."""
        sections: dict[str, str] = {}

        # Try to identify common section headers
        section_patterns = [
            (r"(?:^|\n)(Active Problems|Problems|Diagnoses)[:\s]*\n(.+?)(?=\n[A-Z]|\Z)", "active_problems"),
            (r"(?:^|\n)(Medications|Current Medications)[:\s]*\n(.+?)(?=\n[A-Z]|\Z)", "medications"),
            (r"(?:^|\n)(Allergies)[:\s]*\n(.+?)(?=\n[A-Z]|\Z)", "allergies"),
            (r"(?:^|\n)(Recent Labs|Laboratory)[:\s]*\n(.+?)(?=\n[A-Z]|\Z)", "labs"),
            (r"(?:^|\n)(Vital Signs|Vitals)[:\s]*\n(.+?)(?=\n[A-Z]|\Z)", "vitals"),
            (r"(?:^|\n)(Recent Encounters|Visits)[:\s]*\n(.+?)(?=\n[A-Z]|\Z)", "encounters"),
            (r"(?:^|\n)(Clinical Summary|Summary|Overview)[:\s]*\n(.+?)(?=\n[A-Z]|\Z)", "summary"),
            (r"(?:^|\n)(Recommendations|Plan)[:\s]*\n(.+?)(?=\n[A-Z]|\Z)", "recommendations"),
        ]

        for pattern, key in section_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                sections[key] = match.group(2).strip()

        # If no sections found, put entire content as summary
        if not sections:
            sections["summary"] = content

        return sections

    def _generate_citations(
        self,
        content: str,
        facts: list[PatientFact],
    ) -> list[FactCitation]:
        """Generate citations linking summary text to source facts."""
        citations = []

        for fact in facts:
            # Simple matching - look for fact description in content
            desc_lower = fact.description.lower()
            content_lower = content.lower()

            if desc_lower in content_lower:
                # Find the actual text span (preserve case)
                idx = content_lower.find(desc_lower)
                text_span = content[idx:idx + len(fact.description)]

                citations.append(FactCitation(
                    text_span=text_span,
                    fact_id=fact.fact_id,
                    fact_type=fact.fact_type,
                    source_description=f"{fact.fact_type}: {fact.description}",
                ))
            elif fact.code and fact.code in content:
                citations.append(FactCitation(
                    text_span=fact.code,
                    fact_id=fact.fact_id,
                    fact_type=fact.fact_type,
                    source_description=f"{fact.fact_type}: {fact.description}",
                ))

        return citations


# Extended ClinicalNoteGeneratorService methods
def _add_history_entry(service: ClinicalNoteGeneratorService, note: GeneratedNote, patient_id: str | None = None) -> None:
    """Add an entry to the note generation history."""
    if not hasattr(service, '_history'):
        service._history = []

    entry = NoteHistoryEntry(
        note_id=note.note_id,
        note_type=note.note_type,
        patient_id=patient_id,
        template_id=note.template_id,
        status=note.status,
        generated_at=note.generated_at,
        model_used=note.model_used,
        token_usage=note.token_usage,
        cost_usd=note.cost_usd,
        preview=note.content[:200] + "..." if len(note.content) > 200 else note.content,
    )

    service._history.insert(0, entry)

    # Limit history size
    max_history = getattr(service, '_max_history', 100)
    if len(service._history) > max_history:
        service._history = service._history[:max_history]


def get_note_history(
    service: ClinicalNoteGeneratorService,
    limit: int = 50,
    note_type: NoteType | None = None,
    patient_id: str | None = None,
) -> list[NoteHistoryEntry]:
    """Get note generation history.

    Args:
        service: The note generator service.
        limit: Maximum entries to return.
        note_type: Filter by note type.
        patient_id: Filter by patient ID.

    Returns:
        List of history entries.
    """
    if not hasattr(service, '_history'):
        return []

    history = service._history

    if note_type:
        history = [h for h in history if h.note_type == note_type]

    if patient_id:
        history = [h for h in history if h.patient_id == patient_id]

    return history[:limit]


def customize_template(
    service: ClinicalNoteGeneratorService,
    request: CustomTemplateRequest,
) -> NoteTemplate:
    """Create a customized template based on an existing one.

    Args:
        service: The note generator service.
        request: Template customization request.

    Returns:
        The new customized template.

    Raises:
        ValueError: If base template not found.
    """
    # Get base template
    base = service.get_template(request.base_template_id)
    if not base:
        raise ValueError(f"Base template not found: {request.base_template_id}")

    # Start with base sections
    new_sections = [s for s in base.sections if s.key not in request.sections_to_remove]

    # Add new sections
    for section in request.sections_to_add:
        # Check if section key already exists
        existing_keys = {s.key for s in new_sections}
        if section.key not in existing_keys:
            new_sections.append(section)

    # Reorder if specified
    if request.section_order:
        ordered_sections = []
        key_to_section = {s.key: s for s in new_sections}
        for i, key in enumerate(request.section_order):
            if key in key_to_section:
                section = key_to_section[key]
                # Update order
                ordered_sections.append(NoteSectionTemplate(
                    name=section.name,
                    key=section.key,
                    required=section.required,
                    order=i + 1,
                    prompt_template=section.prompt_template,
                    min_length=section.min_length,
                    max_length=section.max_length,
                    subsections=section.subsections,
                ))
        # Add any sections not in the order list at the end
        for section in new_sections:
            if section.key not in request.section_order:
                ordered_sections.append(NoteSectionTemplate(
                    name=section.name,
                    key=section.key,
                    required=section.required,
                    order=len(ordered_sections) + 1,
                    prompt_template=section.prompt_template,
                    min_length=section.min_length,
                    max_length=section.max_length,
                    subsections=section.subsections,
                ))
        new_sections = ordered_sections

    # Create new template
    new_template = NoteTemplate(
        template_id=request.new_template_id,
        note_type=base.note_type,
        name=request.name,
        description=request.description or base.description,
        sections=new_sections,
        default_prompts={**base.default_prompts, **request.custom_prompts},
        formatting=base.formatting.copy(),
        metadata={
            "base_template": request.base_template_id,
            "customized": True,
        },
    )

    # Register the new template
    service.register_template(new_template)

    return new_template


# Singleton for patient summary service
_summary_service_instance: PatientSummaryService | None = None
_summary_service_lock = threading.Lock()


def get_patient_summary_service() -> PatientSummaryService:
    """Get or create the singleton patient summary service instance."""
    global _summary_service_instance

    if _summary_service_instance is None:
        with _summary_service_lock:
            if _summary_service_instance is None:
                _summary_service_instance = PatientSummaryService()

    return _summary_service_instance


def reset_patient_summary_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _summary_service_instance
    with _summary_service_lock:
        _summary_service_instance = None
