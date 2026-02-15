"""Synthetic Data Generation Toolkit (P3-016).

Generates deterministic synthetic clinical data for safer pre-production testing.
All synthetic records are clearly marked with "SYNTH-" prefixed IDs to prevent
confusion with real patient data.

Features:
- Deterministic generation via seed for reproducibility
- Multiple clinical note types (admission, progress, discharge, lab_report, consultation)
- Realistic but clearly synthetic patient demographics, conditions, medications, labs
- Batch corpus generation for load/integration testing
"""

from __future__ import annotations

import hashlib
import logging
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

SYNTH_PREFIX = "SYNTH-"


# ============================================================================
# Enums
# ============================================================================


class NoteType(str, Enum):
    """Types of synthetic clinical notes."""

    ADMISSION = "admission"
    PROGRESS = "progress"
    DISCHARGE = "discharge"
    LAB_REPORT = "lab_report"
    CONSULTATION = "consultation"


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class SyntheticLabResult:
    """A single synthetic lab result."""

    test_name: str
    value: float
    unit: str
    reference_range: str
    is_abnormal: bool = False


@dataclass
class SyntheticPatient:
    """A synthetic patient record. All IDs prefixed with SYNTH-."""

    patient_id: str
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: str  # ISO date
    sex: str
    conditions: list[str] = field(default_factory=list)
    medications: list[str] = field(default_factory=list)
    lab_results: list[SyntheticLabResult] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)


@dataclass
class SyntheticDocument:
    """A synthetic clinical document."""

    document_id: str
    patient_id: str
    note_type: NoteType
    title: str
    content: str
    author: str
    created_at: str  # ISO datetime


@dataclass
class SyntheticCorpus:
    """A batch of synthetic patients and their documents."""

    corpus_id: str
    patients: list[SyntheticPatient]
    documents: list[SyntheticDocument]
    seed: int
    generated_at: str


# ============================================================================
# Reference Data (realistic but synthetic)
# ============================================================================

_FIRST_NAMES_M = [
    "James", "Robert", "Michael", "William", "David",
    "Richard", "Joseph", "Thomas", "Charles", "Daniel",
    "Matthew", "Anthony", "Mark", "Donald", "Steven",
]

_FIRST_NAMES_F = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara",
    "Elizabeth", "Susan", "Jessica", "Sarah", "Karen",
    "Lisa", "Nancy", "Betty", "Margaret", "Sandra",
]

_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones",
    "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin",
]

_CONDITIONS = [
    "Essential hypertension",
    "Type 2 diabetes mellitus",
    "Major depressive disorder",
    "Generalized anxiety disorder",
    "Chronic obstructive pulmonary disease",
    "Asthma",
    "Osteoarthritis of knee",
    "Hyperlipidemia",
    "Gastroesophageal reflux disease",
    "Chronic kidney disease, stage 3",
    "Atrial fibrillation",
    "Heart failure with reduced ejection fraction",
    "Iron deficiency anemia",
    "Hypothyroidism",
    "Obesity",
]

_MEDICATIONS = [
    "Lisinopril 10mg daily",
    "Metformin 500mg twice daily",
    "Atorvastatin 40mg daily",
    "Amlodipine 5mg daily",
    "Metoprolol 25mg twice daily",
    "Omeprazole 20mg daily",
    "Sertraline 50mg daily",
    "Albuterol inhaler PRN",
    "Levothyroxine 50mcg daily",
    "Aspirin 81mg daily",
    "Furosemide 20mg daily",
    "Gabapentin 300mg three times daily",
    "Acetaminophen 500mg PRN",
    "Warfarin 5mg daily",
    "Hydrochlorothiazide 25mg daily",
]

_PROCEDURES = [
    "Complete blood count",
    "Comprehensive metabolic panel",
    "Chest X-ray",
    "Electrocardiogram",
    "Echocardiogram",
    "Colonoscopy",
    "CT scan of chest",
    "MRI of brain",
    "Upper endoscopy",
    "Spirometry",
]

_ALLERGIES = [
    "Penicillin (rash)",
    "Sulfa drugs (hives)",
    "Ibuprofen (GI upset)",
    "Latex (contact dermatitis)",
    "Codeine (nausea)",
    "No known drug allergies",
]

_LAB_TESTS = [
    ("Hemoglobin", "g/dL", 12.0, 17.5, 7.0, 20.0),
    ("White blood cell count", "K/uL", 4.5, 11.0, 2.0, 25.0),
    ("Platelet count", "K/uL", 150.0, 400.0, 50.0, 600.0),
    ("Sodium", "mEq/L", 136.0, 145.0, 120.0, 160.0),
    ("Potassium", "mEq/L", 3.5, 5.0, 2.5, 7.0),
    ("Creatinine", "mg/dL", 0.7, 1.3, 0.3, 5.0),
    ("BUN", "mg/dL", 7.0, 20.0, 3.0, 80.0),
    ("Glucose", "mg/dL", 70.0, 100.0, 40.0, 400.0),
    ("HbA1c", "%", 4.0, 5.6, 4.0, 14.0),
    ("TSH", "mIU/L", 0.4, 4.0, 0.01, 20.0),
]


# ============================================================================
# Generator Functions
# ============================================================================


def _make_rng(seed: int) -> random.Random:
    """Create a seeded Random instance."""
    return random.Random(seed)


def _synth_id(prefix: str, seed: int, index: int = 0) -> str:
    """Generate a deterministic SYNTH- prefixed ID."""
    raw = f"{prefix}-{seed}-{index}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:12].upper()
    return f"{SYNTH_PREFIX}{short_hash}"


def generate_synthetic_patient(seed: int) -> SyntheticPatient:
    """Generate a single deterministic synthetic patient.

    Args:
        seed: Seed for deterministic generation. Same seed always produces
              the same patient.

    Returns:
        SyntheticPatient with realistic but synthetic clinical data.
    """
    rng = _make_rng(seed)

    patient_id = _synth_id("PAT", seed)
    mrn = f"{SYNTH_PREFIX}{rng.randint(100000, 999999)}"

    sex = rng.choice(["M", "F"])
    if sex == "M":
        first_name = rng.choice(_FIRST_NAMES_M)
    else:
        first_name = rng.choice(_FIRST_NAMES_F)
    last_name = rng.choice(_LAST_NAMES)

    # Age between 18 and 90
    age = rng.randint(18, 90)
    dob = date.today() - timedelta(days=age * 365 + rng.randint(0, 364))

    # Pick 1-4 conditions
    n_conditions = rng.randint(1, 4)
    conditions = rng.sample(_CONDITIONS, min(n_conditions, len(_CONDITIONS)))

    # Pick 1-5 medications
    n_meds = rng.randint(1, 5)
    medications = rng.sample(_MEDICATIONS, min(n_meds, len(_MEDICATIONS)))

    # Generate 3-6 lab results
    n_labs = rng.randint(3, 6)
    lab_tests = rng.sample(_LAB_TESTS, min(n_labs, len(_LAB_TESTS)))
    lab_results = []
    for test_name, unit, ref_low, ref_high, abs_low, abs_high in lab_tests:
        value = round(rng.uniform(abs_low, abs_high), 1)
        is_abnormal = value < ref_low or value > ref_high
        lab_results.append(SyntheticLabResult(
            test_name=test_name,
            value=value,
            unit=unit,
            reference_range=f"{ref_low}-{ref_high}",
            is_abnormal=is_abnormal,
        ))

    # Pick 0-3 procedures
    n_procs = rng.randint(0, 3)
    procedures = rng.sample(_PROCEDURES, min(n_procs, len(_PROCEDURES)))

    # Pick 0-2 allergies
    n_allergies = rng.randint(0, 2)
    allergies = rng.sample(_ALLERGIES, min(n_allergies, len(_ALLERGIES)))

    patient = SyntheticPatient(
        patient_id=patient_id,
        mrn=mrn,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=dob.isoformat(),
        sex=sex,
        conditions=conditions,
        medications=medications,
        lab_results=lab_results,
        procedures=procedures,
        allergies=allergies,
    )

    logger.debug(f"Generated synthetic patient {patient_id} (seed={seed})")
    return patient


def generate_synthetic_document(
    patient_id: str,
    note_type: NoteType | str,
    seed: int,
) -> SyntheticDocument:
    """Generate a synthetic clinical document for a patient.

    Args:
        patient_id: The synthetic patient ID (should be SYNTH- prefixed).
        note_type: Type of clinical note to generate.
        seed: Seed for deterministic generation.

    Returns:
        SyntheticDocument with realistic clinical note content.
    """
    if isinstance(note_type, str):
        note_type = NoteType(note_type)

    rng = _make_rng(seed)
    doc_id = _synth_id("DOC", seed)

    author = f"Dr. {rng.choice(_LAST_NAMES)}"
    created_at = datetime.now(timezone.utc) - timedelta(
        days=rng.randint(0, 90),
        hours=rng.randint(0, 23),
    )

    content = _generate_note_content(rng, note_type, patient_id)
    title = _note_title(note_type)

    doc = SyntheticDocument(
        document_id=doc_id,
        patient_id=patient_id,
        note_type=note_type,
        title=title,
        content=content,
        author=author,
        created_at=created_at.isoformat(),
    )

    logger.debug(f"Generated synthetic document {doc_id} type={note_type.value}")
    return doc


def generate_synthetic_corpus(
    n_patients: int,
    notes_per_patient: int,
    seed: int,
) -> SyntheticCorpus:
    """Generate a batch of synthetic patients and documents.

    Args:
        n_patients: Number of synthetic patients to generate.
        notes_per_patient: Number of notes per patient.
        seed: Master seed for deterministic generation.

    Returns:
        SyntheticCorpus with all patients and documents.
    """
    rng = _make_rng(seed)
    corpus_id = _synth_id("CORPUS", seed)

    patients: list[SyntheticPatient] = []
    documents: list[SyntheticDocument] = []

    note_types_list = list(NoteType)

    for i in range(n_patients):
        patient_seed = seed + i + 1
        patient = generate_synthetic_patient(patient_seed)
        patients.append(patient)

        for j in range(notes_per_patient):
            doc_seed = seed + (i * 1000) + j + 1
            nt = note_types_list[rng.randint(0, len(note_types_list) - 1)]
            doc = generate_synthetic_document(patient.patient_id, nt, doc_seed)
            documents.append(doc)

    corpus = SyntheticCorpus(
        corpus_id=corpus_id,
        patients=patients,
        documents=documents,
        seed=seed,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    logger.info(
        f"Generated synthetic corpus {corpus_id}: "
        f"{n_patients} patients, {len(documents)} documents"
    )
    return corpus


# ============================================================================
# Private Helpers - Note Content Generation
# ============================================================================


def _note_title(note_type: NoteType) -> str:
    """Return a human-readable title for the note type."""
    titles = {
        NoteType.ADMISSION: "Admission Note",
        NoteType.PROGRESS: "Progress Note",
        NoteType.DISCHARGE: "Discharge Summary",
        NoteType.LAB_REPORT: "Laboratory Report",
        NoteType.CONSULTATION: "Consultation Note",
    }
    return titles.get(note_type, "Clinical Note")


def _generate_note_content(rng: random.Random, note_type: NoteType, patient_id: str) -> str:
    """Generate realistic note content based on type."""
    generators = {
        NoteType.ADMISSION: _gen_admission_note,
        NoteType.PROGRESS: _gen_progress_note,
        NoteType.DISCHARGE: _gen_discharge_note,
        NoteType.LAB_REPORT: _gen_lab_report,
        NoteType.CONSULTATION: _gen_consultation_note,
    }
    gen_fn = generators.get(note_type, _gen_progress_note)
    return gen_fn(rng, patient_id)


def _gen_admission_note(rng: random.Random, patient_id: str) -> str:
    cc = rng.choice([
        "chest pain",
        "shortness of breath",
        "abdominal pain",
        "altered mental status",
        "fever and chills",
    ])
    condition = rng.choice(_CONDITIONS)
    return (
        f"[SYNTHETIC DATA - {patient_id}]\n\n"
        f"ADMISSION NOTE\n\n"
        f"Chief Complaint: {cc}\n\n"
        f"History of Present Illness:\n"
        f"Patient presents with {cc} for the past {rng.randint(1, 7)} days. "
        f"Symptoms have been {rng.choice(['worsening', 'stable', 'intermittent'])}. "
        f"Patient has a history of {condition}.\n\n"
        f"Assessment and Plan:\n"
        f"1. {cc.capitalize()} - Admit for observation and workup.\n"
        f"2. {condition} - Continue current management.\n"
        f"3. Monitor vitals every 4 hours.\n"
    )


def _gen_progress_note(rng: random.Random, patient_id: str) -> str:
    day = rng.randint(1, 10)
    status = rng.choice(["improving", "stable", "unchanged"])
    return (
        f"[SYNTHETIC DATA - {patient_id}]\n\n"
        f"PROGRESS NOTE - Hospital Day {day}\n\n"
        f"Subjective: Patient reports feeling {status}. "
        f"Pain level {rng.randint(0, 8)}/10.\n\n"
        f"Objective:\n"
        f"  Vitals: T {rng.uniform(97.0, 100.4):.1f}F, "
        f"HR {rng.randint(60, 110)}, "
        f"BP {rng.randint(100, 160)}/{rng.randint(60, 95)}, "
        f"RR {rng.randint(12, 24)}, "
        f"SpO2 {rng.randint(92, 100)}%\n\n"
        f"Assessment: Patient is {status}.\n\n"
        f"Plan: Continue current management. "
        f"Reassess in {rng.choice(['4', '8', '12', '24'])} hours.\n"
    )


def _gen_discharge_note(rng: random.Random, patient_id: str) -> str:
    los = rng.randint(1, 14)
    condition = rng.choice(_CONDITIONS)
    med = rng.choice(_MEDICATIONS)
    return (
        f"[SYNTHETIC DATA - {patient_id}]\n\n"
        f"DISCHARGE SUMMARY\n\n"
        f"Length of Stay: {los} days\n\n"
        f"Discharge Diagnosis: {condition}\n\n"
        f"Hospital Course:\n"
        f"Patient was admitted for management of {condition}. "
        f"Treatment was initiated and patient showed improvement. "
        f"Patient is discharged in {rng.choice(['stable', 'improved', 'good'])} condition.\n\n"
        f"Discharge Medications:\n"
        f"  - {med}\n\n"
        f"Follow-up: {rng.choice(['PCP', 'Specialist'])} in {rng.randint(1, 4)} weeks.\n"
    )


def _gen_lab_report(rng: random.Random, patient_id: str) -> str:
    tests = rng.sample(_LAB_TESTS, min(4, len(_LAB_TESTS)))
    lines = [
        f"[SYNTHETIC DATA - {patient_id}]\n",
        "LABORATORY REPORT\n",
    ]
    for test_name, unit, ref_low, ref_high, abs_low, abs_high in tests:
        val = round(rng.uniform(abs_low, abs_high), 1)
        flag = " [H]" if val > ref_high else (" [L]" if val < ref_low else "")
        lines.append(f"  {test_name}: {val} {unit} (ref: {ref_low}-{ref_high}){flag}")
    return "\n".join(lines) + "\n"


def _gen_consultation_note(rng: random.Random, patient_id: str) -> str:
    specialty = rng.choice([
        "Cardiology", "Pulmonology", "Gastroenterology",
        "Endocrinology", "Nephrology", "Neurology",
    ])
    reason = rng.choice(_CONDITIONS)
    return (
        f"[SYNTHETIC DATA - {patient_id}]\n\n"
        f"CONSULTATION NOTE - {specialty}\n\n"
        f"Reason for Consultation: {reason}\n\n"
        f"History: Patient was referred for evaluation of {reason}. "
        f"Current management includes {rng.choice(_MEDICATIONS)}.\n\n"
        f"Assessment:\n"
        f"{reason} - {rng.choice(['well controlled', 'suboptimally controlled', 'newly diagnosed'])}.\n\n"
        f"Recommendations:\n"
        f"1. {rng.choice(['Continue current therapy', 'Adjust medication dosing', 'Order additional workup'])}.\n"
        f"2. Follow up in {rng.randint(2, 8)} weeks.\n"
    )
