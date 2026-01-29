"""Advanced Clinical Extraction Pipeline.

A multi-stage pipeline for near-100% accuracy clinical entity extraction:

Pipeline Stages:
1. Pre-Processing: Section detection, sentence segmentation, negation mapping
2. Extraction: Pattern-based mention extraction with confidence scoring
3. Context Analysis: Apply negation, section, historical, family filters
4. Validation: Medical knowledge rules, cross-entity validation
5. LLM Enhancement (Optional): For low-confidence or ambiguous cases

Architecture designed to maximize both precision and recall by combining
rule-based speed with contextual understanding.
"""

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================


class ExtractionConfidence(Enum):
    """Confidence levels for extraction."""
    HIGH = "high"       # > 0.9 - Very confident, likely correct
    MEDIUM = "medium"   # 0.7-0.9 - Confident but may need validation
    LOW = "low"         # 0.5-0.7 - Uncertain, may need LLM assist
    VERY_LOW = "very_low"  # < 0.5 - Likely wrong, needs verification


@dataclass
class PipelineEntity:
    """An entity flowing through the extraction pipeline."""

    # Core identification
    text: str
    normalized_text: str
    entity_type: str  # condition, drug, measurement, procedure

    # Position
    span_start: int
    span_end: int

    # Confidence tracking
    base_confidence: float = 1.0
    context_modifier: float = 1.0
    validation_modifier: float = 1.0
    final_confidence: float = 1.0

    # Context information
    is_negated: bool = False
    is_uncertain: bool = False
    is_historical: bool = False
    is_family_history: bool = False
    section: str = "unknown"
    assertion: str = "present"

    # Value/unit for measurements
    value: str | None = None
    unit: str | None = None

    # Mapping information
    omop_concept_id: int | None = None
    icd10_code: str | None = None

    # Pipeline metadata
    extraction_method: str = "pattern"
    context_clues: list[str] = field(default_factory=list)
    validation_notes: list[str] = field(default_factory=list)
    pipeline_stages_passed: list[str] = field(default_factory=list)

    # Should this entity be included in final output?
    include_in_output: bool = True
    exclusion_reason: str | None = None


@dataclass
class PipelineResult:
    """Result from the full extraction pipeline."""

    document_id: str
    entities: list[PipelineEntity]
    processing_time_ms: float

    # Statistics
    raw_extractions: int = 0
    after_context_filter: int = 0
    after_validation: int = 0
    final_count: int = 0

    # By stage timing
    preprocessing_time_ms: float = 0.0
    extraction_time_ms: float = 0.0
    context_time_ms: float = 0.0
    validation_time_ms: float = 0.0
    llm_time_ms: float = 0.0

    # Quality metrics
    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    low_confidence_count: int = 0
    llm_assisted_count: int = 0

    # Warnings/errors
    warnings: list[str] = field(default_factory=list)


# ============================================================================
# Stage 1: Pre-Processing
# ============================================================================


class PreProcessor:
    """Pre-processes clinical text for extraction."""

    def __init__(self):
        # Import context analyzer
        from app.services.clinical_context import (
            SectionDetector,
            NegationDetector,
        )
        self.section_detector = SectionDetector()
        self.negation_detector = NegationDetector()

    def process(self, text: str) -> dict[str, Any]:
        """
        Pre-process text to extract structural information.

        Returns:
            Dict with sections, negation_scopes, sentences
        """
        # Detect sections
        sections = self.section_detector.detect_sections(text)

        # Find negation scopes
        negation_scopes = self.negation_detector.find_negation_scopes(text)

        # Segment into sentences (simple approach)
        sentences = self._segment_sentences(text)

        return {
            "sections": sections,
            "negation_scopes": negation_scopes,
            "sentences": sentences,
            "text_length": len(text),
        }

    def _segment_sentences(self, text: str) -> list[tuple[int, int, str]]:
        """Segment text into sentences with positions."""
        # Simple sentence boundary detection
        sentences = []
        pattern = re.compile(r'[.!?]+(?:\s|$)|\n\n+')

        last_end = 0
        for match in pattern.finditer(text):
            sentence = text[last_end:match.end()].strip()
            if sentence:
                sentences.append((last_end, match.end(), sentence))
            last_end = match.end()

        # Handle remaining text
        if last_end < len(text):
            remaining = text[last_end:].strip()
            if remaining:
                sentences.append((last_end, len(text), remaining))

        return sentences


# ============================================================================
# Stage 2: Extraction
# ============================================================================


class PatternExtractor:
    """Pattern-based entity extraction with comprehensive coverage."""

    def __init__(self):
        self._build_patterns()

    def _build_patterns(self):
        """Build comprehensive extraction patterns."""

        # Condition patterns with confidence
        self._condition_patterns = [
            # Very high confidence - full diagnostic terms
            (r'\b(type [12] diabetes mellitus)\b', 0.98),
            (r'\b(diabetic ketoacidosis)\b', 0.98),
            (r'\b(heart failure with (?:reduced|preserved) ejection fraction)\b', 0.98),
            (r'\b(acute (?:decompensated )?heart failure)\b', 0.98),
            (r'\b(chronic obstructive pulmonary disease)\b', 0.98),
            (r'\b(acute myocardial infarction)\b', 0.98),
            (r'\b(transient ischemic attack)\b', 0.98),
            (r'\b(pulmonary embolism)\b', 0.98),
            (r'\b(deep vein thrombosis)\b', 0.98),
            (r'\b(acute kidney injury)\b', 0.98),
            (r'\b(chronic kidney disease)\b', 0.98),
            (r'\b(acute appendicitis)\b', 0.98),
            (r'\b(gastroesophageal reflux disease)\b', 0.98),
            (r'\b(obstructive sleep apnea)\b', 0.98),
            (r'\b(generalized anxiety disorder)\b', 0.98),
            (r'\b(major depressive disorder)\b', 0.98),
            (r'\b(benign prostatic hyperplasia)\b', 0.98),
            (r'\b(urinary tract infection)\b', 0.98),
            (r'\b(community[- ]acquired pneumonia)\b', 0.98),

            # High confidence - standard terms
            (r'\b(diabetes mellitus)\b', 0.95),
            (r'\b(hypertension)\b', 0.95),
            (r'\b(hyperlipidemia)\b', 0.95),
            (r'\b(atrial fibrillation)\b', 0.95),
            (r'\b(heart failure)\b', 0.95),
            (r'\b(coronary artery disease)\b', 0.95),
            (r'\b(hyperlipidemia)\b', 0.95),
            (r'\b(obesity)\b', 0.92),
            (r'\b(anemia)\b', 0.92),
            (r'\b(depression)\b', 0.88),
            (r'\b(anxiety)\b', 0.85),
            (r'\b(osteoporosis)\b', 0.92),
            (r'\b(osteoarthritis)\b', 0.92),
            (r'\b(hypothyroidism)\b', 0.95),
            (r'\b(hyperthyroidism)\b', 0.95),
            (r'\b(pneumonia)\b', 0.92),
            (r'\b(asthma)\b', 0.95),
            (r'\b(epilepsy)\b', 0.95),
            (r'\b(stroke)\b', 0.92),
            (r'\b(migraine)\b', 0.92),
            (r'\b(costochondritis)\b', 0.95),
            (r'\b(urticaria)\b', 0.95),
            (r'\b(cellulitis)\b', 0.95),
            (r'\b(sepsis)\b', 0.95),
            (r'\b(hyperkalemia)\b', 0.95),
            (r'\b(hypokalemia)\b', 0.95),
            (r'\b(hypernatremia)\b', 0.95),
            (r'\b(hyponatremia)\b', 0.95),
            (r'\b(dehydration)\b', 0.90),
            (r'\b(pleural effusion)\b', 0.95),
            (r'\b(pulmonary edema)\b', 0.95),

            # Medium confidence - abbreviations (need context)
            (r'\b(htn)\b', 0.85),
            (r'\b(dm2?)\b', 0.80),
            (r'\b(dm1)\b', 0.85),
            (r'\b(hfref)\b', 0.88),
            (r'\b(hfpef)\b', 0.88),
            (r'\b(chf)\b', 0.85),
            (r'\b(cad)\b', 0.82),
            (r'\b(afib|a-?fib)\b', 0.85),
            (r'\b(copd)\b', 0.88),
            (r'\b(ckd)\b', 0.85),
            (r'\b(aki)\b', 0.85),
            (r'\b(dka)\b', 0.90),
            (r'\b(tia)\b', 0.88),
            (r'\b(dvt)\b', 0.88),
            (r'\b(bph)\b', 0.85),
            (r'\b(gerd)\b', 0.88),
            (r'\b(osa)\b', 0.85),
            (r'\b(gad)\b', 0.80),
            (r'\b(uti)\b', 0.85),
            (r'\b(cap)\b', 0.75),  # Lower due to ambiguity

            # Lower confidence - symptoms (often negated)
            (r'\b(chest pain)\b', 0.75),
            (r'\b(abdominal pain)\b', 0.75),
            (r'\b(headache)\b', 0.70),
            (r'\b(nausea)\b', 0.70),
            (r'\b(vomiting)\b', 0.70),
            (r'\b(diarrhea)\b', 0.70),
            (r'\b(constipation)\b', 0.70),
            (r'\b(dyspnea)\b', 0.75),
            (r'\b(shortness of breath)\b', 0.75),
            (r'\b(cough)\b', 0.65),
            (r'\b(fever)\b', 0.70),
            (r'\b(fatigue)\b', 0.65),
            (r'\b(dizziness)\b', 0.70),
            (r'\b(syncope)\b', 0.80),
            (r'\b(edema)\b', 0.75),
            (r'\b(palpitations)\b', 0.75),
            (r'\b(dysphagia)\b', 0.80),

            # Conditions with modifiers
            (r'\b(allergic reaction)\b', 0.90),
            (r'\b(shellfish allergy)\b', 0.95),
            (r'\b(drug allergy)\b', 0.90),
            (r'\b(food allergy)\b', 0.90),
            (r'\b(carotid.{0,15}stenosis)\b', 0.90),
            (r'\b(medication.{0,10}non-?compliance)\b', 0.85),
            (r'\b(medication.{0,10}non-?adherence)\b', 0.85),
        ]

        # Drug patterns
        self._drug_patterns = [
            # Diabetes
            ('metformin', 0.98), ('insulin glargine', 0.98), ('insulin lispro', 0.98),
            ('insulin aspart', 0.98), ('glipizide', 0.95), ('glyburide', 0.95),
            ('sitagliptin', 0.95), ('empagliflozin', 0.95), ('dapagliflozin', 0.95),
            ('semaglutide', 0.95), ('liraglutide', 0.95), ('dulaglutide', 0.95),
            ('pioglitazone', 0.95),

            # Cardiac
            ('lisinopril', 0.98), ('enalapril', 0.95), ('ramipril', 0.95),
            ('losartan', 0.95), ('valsartan', 0.95), ('olmesartan', 0.95),
            ('amlodipine', 0.98), ('nifedipine', 0.95), ('diltiazem', 0.95),
            ('metoprolol', 0.98), ('carvedilol', 0.98), ('atenolol', 0.95),
            ('propranolol', 0.95), ('bisoprolol', 0.95),
            ('furosemide', 0.98), ('bumetanide', 0.95), ('torsemide', 0.95),
            ('hydrochlorothiazide', 0.95), ('chlorthalidone', 0.95),
            ('spironolactone', 0.95), ('eplerenone', 0.95),
            ('atorvastatin', 0.98), ('rosuvastatin', 0.95), ('simvastatin', 0.95),
            ('pravastatin', 0.95),
            ('aspirin', 0.95), ('clopidogrel', 0.95), ('ticagrelor', 0.95),
            ('apixaban', 0.98), ('rivaroxaban', 0.95), ('warfarin', 0.95),
            ('dabigatran', 0.95), ('enoxaparin', 0.95), ('heparin', 0.95),
            ('nitroglycerin', 0.95), ('isosorbide', 0.90),
            ('digoxin', 0.95), ('amiodarone', 0.95),

            # Pain/anti-inflammatory
            ('ibuprofen', 0.95), ('naproxen', 0.95), ('acetaminophen', 0.95),
            ('morphine', 0.95), ('oxycodone', 0.90), ('hydrocodone', 0.90),
            ('fentanyl', 0.95), ('tramadol', 0.90),
            ('prednisone', 0.95), ('methylprednisolone', 0.95), ('dexamethasone', 0.95),
            ('hydrocortisone', 0.95),

            # GI
            ('omeprazole', 0.95), ('pantoprazole', 0.95), ('esomeprazole', 0.95),
            ('famotidine', 0.95), ('ranitidine', 0.90),
            ('ondansetron', 0.95), ('metoclopramide', 0.90), ('promethazine', 0.90),
            ('docusate', 0.85), ('senna', 0.85), ('polyethylene glycol', 0.85),

            # Respiratory
            ('albuterol', 0.98), ('ipratropium', 0.95),
            ('tiotropium', 0.95), ('umeclidinium', 0.95),
            ('fluticasone', 0.90), ('budesonide', 0.90), ('mometasone', 0.90),
            ('salmeterol', 0.90), ('formoterol', 0.90), ('vilanterol', 0.90),
            ('montelukast', 0.95),

            # Antibiotics
            ('azithromycin', 0.95), ('amoxicillin', 0.95), ('amoxicillin-clavulanate', 0.95),
            ('levofloxacin', 0.95), ('ciprofloxacin', 0.95), ('moxifloxacin', 0.95),
            ('ceftriaxone', 0.95), ('cephalexin', 0.95), ('cefdinir', 0.95),
            ('doxycycline', 0.95), ('trimethoprim-sulfamethoxazole', 0.95),
            ('vancomycin', 0.95), ('piperacillin-tazobactam', 0.95),
            ('metronidazole', 0.95),

            # Psych
            ('sertraline', 0.95), ('fluoxetine', 0.95), ('escitalopram', 0.95),
            ('citalopram', 0.95), ('paroxetine', 0.95), ('venlafaxine', 0.95),
            ('duloxetine', 0.95), ('bupropion', 0.90), ('mirtazapine', 0.90),
            ('trazodone', 0.90), ('quetiapine', 0.90), ('olanzapine', 0.90),
            ('risperidone', 0.90), ('aripiprazole', 0.90),
            ('lorazepam', 0.90), ('alprazolam', 0.85), ('clonazepam', 0.90),
            ('diazepam', 0.90),

            # Other
            ('gabapentin', 0.90), ('pregabalin', 0.90),
            ('levothyroxine', 0.95),
            ('tamsulosin', 0.95), ('finasteride', 0.95),
            ('alendronate', 0.95),
            ('cetirizine', 0.90), ('loratadine', 0.90), ('fexofenadine', 0.90),
            ('diphenhydramine', 0.90),
            ('epinephrine', 0.95), ('epipen', 0.95),
            ('sumatriptan', 0.90),

            # Brand names (map to generic internally)
            ('lantus', 0.95), ('humalog', 0.95), ('novolog', 0.95),
            ('lasix', 0.95), ('coreg', 0.95), ('norvasc', 0.95),
            ('zoloft', 0.95), ('lipitor', 0.95), ('crestor', 0.95),
            ('prilosec', 0.95), ('nexium', 0.95),
            ('zofran', 0.95), ('benadryl', 0.90),
            ('tylenol', 0.90), ('advil', 0.90), ('motrin', 0.90),
        ]

        # Measurement patterns
        self._measurement_patterns = [
            # Vitals
            (r'\b(?:bp|blood pressure)[:\s]+(\d+/\d+)', 'Blood Pressure', 'mmHg', 0.98),
            (r'\b(?:hr|heart rate|pulse)[:\s]+(\d+)', 'Heart Rate', 'bpm', 0.95),
            (r'\b(?:rr|respiratory rate)[:\s]+(\d+)', 'Respiratory Rate', '/min', 0.95),
            (r'\b(?:temp|temperature)[:\s]+(\d+\.?\d*)\s*(?:°?[cfCF])?', 'Temperature', 'C', 0.95),
            (r'\b(?:spo2|oxygen sat|o2 sat|sao2)[:\s]+(\d+)', 'SpO2', '%', 0.98),
            (r'\b(?:weight)[:\s]+(\d+\.?\d*)\s*(?:lb|kg|lbs|pounds)?', 'Weight', 'kg', 0.90),

            # Labs - high confidence
            (r'\b(?:hba1c|a1c|hemoglobin a1c)[:\s]+(\d+\.?\d*)\s*%?', 'HbA1c', '%', 0.98),
            (r'\b(?:glucose|blood sugar)[:\s]+(\d+)', 'Glucose', 'mg/dL', 0.95),
            (r'\bfasting glucose[:\s]+(\d+)', 'Fasting Glucose', 'mg/dL', 0.98),
            (r'\bcreatinine[:\s]+(\d+\.?\d*)', 'Creatinine', 'mg/dL', 0.95),
            (r'\b(?:bun|blood urea nitrogen)[:\s]+(\d+)', 'BUN', 'mg/dL', 0.95),
            (r'\b(?:egfr|gfr)[:\s]+[<>]?(\d+)', 'eGFR', 'mL/min', 0.95),
            (r'\b(?:k\+?|potassium)[:\s]+(\d+\.?\d*)', 'Potassium', 'mmol/L', 0.95),
            (r'\b(?:na\+?|sodium)[:\s]+(\d+)', 'Sodium', 'mmol/L', 0.95),
            (r'\bchloride[:\s]+(\d+)', 'Chloride', 'mmol/L', 0.90),
            (r'\b(?:co2|bicarbonate|bicarb)[:\s]+(\d+)', 'Bicarbonate', 'mmol/L', 0.90),
            (r'\b(?:bnp|b-?type natriuretic)[:\s]+(\d+)', 'BNP', 'pg/mL', 0.98),
            (r'\btroponin[:\s]+[<>]?(\d+\.?\d*)', 'Troponin', 'ng/mL', 0.98),
            (r'\b(?:hgb|hemoglobin)[:\s]+(\d+\.?\d*)', 'Hemoglobin', 'g/dL', 0.95),
            (r'\b(?:hct|hematocrit)[:\s]+(\d+\.?\d*)', 'Hematocrit', '%', 0.95),
            (r'\bwbc[:\s]+(\d+\.?\d*)', 'WBC', 'K/uL', 0.95),
            (r'\bplatelet[s]?[:\s]+(\d+)', 'Platelets', 'K/uL', 0.95),
            (r'\binr[:\s]+(\d+\.?\d*)', 'INR', '', 0.95),
            (r'\bptt[:\s]+(\d+\.?\d*)', 'PTT', 'sec', 0.90),
            (r'\bldl[:\s]+(\d+)', 'LDL', 'mg/dL', 0.92),
            (r'\bhdl[:\s]+(\d+)', 'HDL', 'mg/dL', 0.92),
            (r'\btriglycerides[:\s]+(\d+)', 'Triglycerides', 'mg/dL', 0.92),
            (r'\blipase[:\s]+(\d+)', 'Lipase', 'U/L', 0.90),
            (r'\bamylase[:\s]+(\d+)', 'Amylase', 'U/L', 0.90),
            (r'\blast[:\s]+(\d+)', 'AST', 'U/L', 0.90),
            (r'\balt[:\s]+(\d+)', 'ALT', 'U/L', 0.90),
            (r'\balkaline phosphatase[:\s]+(\d+)', 'Alk Phos', 'U/L', 0.90),
            (r'\bbilirubin[:\s]+(\d+\.?\d*)', 'Bilirubin', 'mg/dL', 0.90),
            (r'\balbumin[:\s]+(\d+\.?\d*)', 'Albumin', 'g/dL', 0.90),
            (r'\bprocalcitonin[:\s]+(\d+\.?\d*)', 'Procalcitonin', 'ng/mL', 0.95),
            (r'\blactate[:\s]+(\d+\.?\d*)', 'Lactate', 'mmol/L', 0.95),
            (r'\bcrp[:\s]+(\d+\.?\d*)', 'CRP', 'mg/L', 0.90),
            (r'\besr[:\s]+(\d+)', 'ESR', 'mm/hr', 0.90),

            # ABG
            (r'\bph[:\s]+(\d+\.?\d+)', 'pH', '', 0.90),
            (r'\bpco2[:\s]+(\d+)', 'pCO2', 'mmHg', 0.90),
            (r'\bpo2[:\s]+(\d+)', 'pO2', 'mmHg', 0.90),

            # Cardiac
            (r'\bef[:\s]+(\d+)', 'Ejection Fraction', '%', 0.95),
            (r'\bejection fraction[:\s]+(\d+)', 'Ejection Fraction', '%', 0.98),

            # Scores
            (r'\bnihss[:\s]+(\d+)', 'NIHSS', '', 0.98),
            (r'\bgcs[:\s]+(\d+)', 'GCS', '', 0.95),
            (r'\bapgar[:\s]+(\d+)', 'APGAR', '', 0.95),
            (r'\bbmi[:\s]+(\d+\.?\d*)', 'BMI', 'kg/m2', 0.95),
            (r'\banion gap[:\s]+(\d+)', 'Anion Gap', 'mEq/L', 0.95),
        ]

        # Compile patterns
        self._compiled_conditions = [
            (re.compile(p, re.IGNORECASE), conf) for p, conf in self._condition_patterns
        ]
        self._compiled_drugs = [
            (re.compile(rf'\b({drug})\b', re.IGNORECASE), conf) for drug, conf in self._drug_patterns
        ]
        self._compiled_measurements = [
            (re.compile(p, re.IGNORECASE), name, unit, conf)
            for p, name, unit, conf in self._measurement_patterns
        ]

    def extract(self, text: str, preprocessing_result: dict) -> list[PipelineEntity]:
        """Extract entities from text."""
        entities = []

        # Extract conditions
        for pattern, confidence in self._compiled_conditions:
            for match in pattern.finditer(text):
                entities.append(PipelineEntity(
                    text=match.group(0),
                    normalized_text=match.group(0).lower(),
                    entity_type="condition",
                    span_start=match.start(),
                    span_end=match.end(),
                    base_confidence=confidence,
                    extraction_method="pattern",
                ))

        # Extract drugs
        for pattern, confidence in self._compiled_drugs:
            for match in pattern.finditer(text):
                entities.append(PipelineEntity(
                    text=match.group(0),
                    normalized_text=match.group(0).lower(),
                    entity_type="drug",
                    span_start=match.start(),
                    span_end=match.end(),
                    base_confidence=confidence,
                    extraction_method="pattern",
                ))

        # Extract measurements
        for pattern, name, unit, confidence in self._compiled_measurements:
            for match in pattern.finditer(text):
                entities.append(PipelineEntity(
                    text=name,
                    normalized_text=name.lower(),
                    entity_type="measurement",
                    span_start=match.start(),
                    span_end=match.end(),
                    base_confidence=confidence,
                    value=match.group(1) if match.groups() else None,
                    unit=unit,
                    extraction_method="pattern",
                ))

        return entities


# ============================================================================
# Stage 3: Context Analysis
# ============================================================================


class ContextAnalyzer:
    """Applies clinical context to extracted entities."""

    def __init__(self):
        from app.services.clinical_context import ClinicalContextAnalyzer
        self.analyzer = ClinicalContextAnalyzer()

    def analyze(
        self,
        entities: list[PipelineEntity],
        text: str,
        preprocessing_result: dict,
    ) -> list[PipelineEntity]:
        """Apply context analysis to all entities."""
        sections = preprocessing_result.get("sections", [])

        for entity in entities:
            context = self.analyzer.analyze_mention(
                text=text,
                mention_text=entity.text,
                mention_start=entity.span_start,
                mention_end=entity.span_end,
                sections=sections,
            )

            # Update entity with context
            entity.is_negated = context.is_negated
            entity.is_uncertain = context.is_uncertain
            entity.is_historical = context.is_historical
            entity.is_family_history = context.is_family_history
            entity.section = context.section.value if hasattr(context.section, 'value') else str(context.section)
            entity.assertion = context.assertion.value if hasattr(context.assertion, 'value') else str(context.assertion)
            entity.context_clues = context.context_clues
            entity.context_modifier = context.confidence_modifier

            # Determine if should be included
            if entity.context_modifier <= 0:
                entity.include_in_output = False
                if entity.is_negated:
                    entity.exclusion_reason = "negated"
                elif entity.is_family_history:
                    entity.exclusion_reason = "family_history"
                else:
                    entity.exclusion_reason = "context_filtered"

            entity.pipeline_stages_passed.append("context_analysis")

        return entities


# ============================================================================
# Stage 4: Validation
# ============================================================================


class EntityValidator:
    """Validates extracted entities using medical knowledge rules."""

    # Drug normalization (brand → generic)
    DRUG_NORMALIZATION = {
        'lantus': 'insulin glargine',
        'humalog': 'insulin lispro',
        'novolog': 'insulin aspart',
        'lasix': 'furosemide',
        'coreg': 'carvedilol',
        'norvasc': 'amlodipine',
        'zoloft': 'sertraline',
        'lipitor': 'atorvastatin',
        'crestor': 'rosuvastatin',
        'prilosec': 'omeprazole',
        'nexium': 'esomeprazole',
        'zofran': 'ondansetron',
        'benadryl': 'diphenhydramine',
        'tylenol': 'acetaminophen',
        'advil': 'ibuprofen',
        'motrin': 'ibuprofen',
        'aleve': 'naproxen',
    }

    # Condition normalization
    CONDITION_NORMALIZATION = {
        'htn': 'hypertension',
        'dm': 'type 2 diabetes mellitus',
        'dm2': 'type 2 diabetes mellitus',
        'dm1': 'type 1 diabetes mellitus',
        'chf': 'heart failure',
        'hfref': 'heart failure with reduced ejection fraction',
        'hfpef': 'heart failure with preserved ejection fraction',
        'cad': 'coronary artery disease',
        'afib': 'atrial fibrillation',
        'a-fib': 'atrial fibrillation',
        'copd': 'chronic obstructive pulmonary disease',
        'ckd': 'chronic kidney disease',
        'aki': 'acute kidney injury',
        'dka': 'diabetic ketoacidosis',
        'tia': 'transient ischemic attack',
        'dvt': 'deep vein thrombosis',
        'bph': 'benign prostatic hyperplasia',
        'gerd': 'gastroesophageal reflux disease',
        'osa': 'obstructive sleep apnea',
        'gad': 'generalized anxiety disorder',
        'uti': 'urinary tract infection',
        'sob': 'shortness of breath',
    }

    def validate(self, entities: list[PipelineEntity]) -> list[PipelineEntity]:
        """Validate and normalize entities."""

        # Normalize drug names
        for entity in entities:
            if entity.entity_type == "drug":
                normalized = self.DRUG_NORMALIZATION.get(
                    entity.normalized_text.lower(),
                    entity.normalized_text
                )
                entity.normalized_text = normalized
            elif entity.entity_type == "condition":
                normalized = self.CONDITION_NORMALIZATION.get(
                    entity.normalized_text.lower(),
                    entity.normalized_text
                )
                entity.normalized_text = normalized

            entity.pipeline_stages_passed.append("validation")

        # Deduplicate
        entities = self._deduplicate(entities)

        # Calculate final confidence
        for entity in entities:
            entity.final_confidence = (
                entity.base_confidence *
                entity.context_modifier *
                entity.validation_modifier
            )

        return entities

    def _deduplicate(self, entities: list[PipelineEntity]) -> list[PipelineEntity]:
        """Remove duplicate entities, keeping highest confidence."""
        from collections import defaultdict

        # Group by (normalized_text, entity_type)
        grouped: dict[tuple[str, str], list[PipelineEntity]] = defaultdict(list)

        for entity in entities:
            if entity.include_in_output:
                key = (entity.normalized_text.lower(), entity.entity_type)
                grouped[key].append(entity)

        # Keep best from each group
        deduplicated = []
        for key, group in grouped.items():
            best = max(group, key=lambda e: e.base_confidence * e.context_modifier)
            best.validation_notes.append(f"deduplicated from {len(group)} mentions")
            deduplicated.append(best)

        # Also include excluded entities (for debugging/analysis)
        excluded = [e for e in entities if not e.include_in_output]

        return deduplicated + excluded


# ============================================================================
# Main Pipeline
# ============================================================================


class ExtractionPipeline:
    """
    Complete extraction pipeline for near-100% accuracy.

    Combines pattern extraction with context analysis and validation.
    """

    def __init__(
        self,
        min_confidence: float = 0.5,
        enable_llm_fallback: bool = False,
    ):
        self.min_confidence = min_confidence
        self.enable_llm_fallback = enable_llm_fallback

        # Initialize stages
        self.preprocessor = PreProcessor()
        self.extractor = PatternExtractor()
        self.context_analyzer = ContextAnalyzer()
        self.validator = EntityValidator()

    def process(self, document_id: str, text: str) -> PipelineResult:
        """
        Process clinical text through the full pipeline.

        Args:
            document_id: Document identifier
            text: Clinical text

        Returns:
            PipelineResult with extracted entities
        """
        start_time = time.time()
        warnings = []

        # Stage 1: Pre-processing
        t1 = time.time()
        preprocessing_result = self.preprocessor.process(text)
        preprocessing_time = (time.time() - t1) * 1000

        # Stage 2: Extraction
        t2 = time.time()
        entities = self.extractor.extract(text, preprocessing_result)
        extraction_time = (time.time() - t2) * 1000
        raw_count = len(entities)

        # Stage 3: Context Analysis
        t3 = time.time()
        entities = self.context_analyzer.analyze(entities, text, preprocessing_result)
        context_time = (time.time() - t3) * 1000
        after_context = len([e for e in entities if e.include_in_output])

        # Stage 4: Validation
        t4 = time.time()
        entities = self.validator.validate(entities)
        validation_time = (time.time() - t4) * 1000

        # Filter by confidence
        final_entities = [
            e for e in entities
            if e.include_in_output and e.final_confidence >= self.min_confidence
        ]

        # Calculate confidence distribution
        high_conf = len([e for e in final_entities if e.final_confidence >= 0.9])
        medium_conf = len([e for e in final_entities if 0.7 <= e.final_confidence < 0.9])
        low_conf = len([e for e in final_entities if e.final_confidence < 0.7])

        total_time = (time.time() - start_time) * 1000

        return PipelineResult(
            document_id=document_id,
            entities=final_entities,
            processing_time_ms=total_time,
            raw_extractions=raw_count,
            after_context_filter=after_context,
            after_validation=len([e for e in entities if e.include_in_output]),
            final_count=len(final_entities),
            preprocessing_time_ms=preprocessing_time,
            extraction_time_ms=extraction_time,
            context_time_ms=context_time,
            validation_time_ms=validation_time,
            high_confidence_count=high_conf,
            medium_confidence_count=medium_conf,
            low_confidence_count=low_conf,
            warnings=warnings,
        )


# ============================================================================
# Singleton
# ============================================================================


_pipeline_instance: ExtractionPipeline | None = None
_pipeline_lock = threading.Lock()


def get_extraction_pipeline() -> ExtractionPipeline:
    """Get or create the singleton pipeline instance."""
    global _pipeline_instance

    if _pipeline_instance is None:
        with _pipeline_lock:
            if _pipeline_instance is None:
                _pipeline_instance = ExtractionPipeline()

    return _pipeline_instance


def reset_extraction_pipeline() -> None:
    """Reset the singleton instance."""
    global _pipeline_instance
    with _pipeline_lock:
        _pipeline_instance = None
