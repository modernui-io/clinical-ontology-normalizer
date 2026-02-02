"""Entity extraction logic for clinical NLP.

This module contains:
- Entity extraction patterns (diagnoses, symptoms, medications, procedures, etc.)
- Extraction methods for each entity type
- Clinical abbreviations lookup
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from .nlp_entity_normalizers import (
    AssertionStatus,
    ClinicalSection,
    EntitySpan,
    EntityType,
    NormalizedCode,
    NormalizationVocabulary,
    SectionSpan,
    LATERALITY_PATTERNS,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Fixture paths for clinical terminology data
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures"
CLINICAL_ABBREVIATIONS_FILE = FIXTURES_DIR / "clinical_abbreviations.json"
LOINC_MEASUREMENTS_FILE = FIXTURES_DIR / "loinc_measurements.json"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class ExtractedEntity:
    """A clinical entity extracted from text."""

    id: str
    entity_type: EntityType
    text: str
    normalized_text: str
    span: EntitySpan
    section: ClinicalSection
    assertion: AssertionStatus
    confidence: float
    normalized_codes: list[NormalizedCode] = field(default_factory=list)

    # Entity-specific fields
    value: str | None = None
    unit: str | None = None
    reference_range: str | None = None
    laterality: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    route: str | None = None
    duration: str | None = None

    # Negation information
    negation_trigger: str | None = None
    negation_scope_start: int | None = None
    negation_scope_end: int | None = None

    # Allergy-specific fields
    reaction_type: str | None = None
    reaction_severity: str | None = None
    allergen_category: str | None = None

    # Social history-specific fields
    social_history_category: str | None = None  # smoking, alcohol, drugs
    social_history_status: str | None = None  # current_smoker, former_smoker, etc.
    quantity: str | None = None  # pack-years, drinks per week, etc.


# ============================================================================
# Diagnosis/Problem patterns
# ============================================================================

DIAGNOSIS_PATTERNS = [
    # Common conditions - all use (?:...) non-capturing groups with \b on both sides
    (r"\b(?:(?:type\s*[12]?\s*)?diabet(?:es|ic)(?:\s+mellitus)?(?:\s+(?:with|without)\s+\w+)?)\b", "Diabetes"),
    (r"\b(?:hypertension|htn|high\s+blood\s+pressure)\b", "Hypertension"),
    (r"\b(?:(?:congestive\s+)?heart\s+failure|chf|hfref|hfpef)\b", "Heart Failure"),
    (r"\b(?:coronary\s+artery\s+disease|cad)\b", "Coronary Artery Disease"),
    (r"\b(?:atrial\s+fibrillation|afib|a\.?\s*fib)\b", "Atrial Fibrillation"),
    (r"\b(?:chronic\s+(?:kidney|renal)\s+disease|ckd)\s+(?:stage\s+)?(?:5|v|five)\b", "CKD Stage 5"),
    (r"\b(?:chronic\s+(?:kidney|renal)\s+disease|ckd)\s+(?:stage\s+)?(?:4|iv|four)\b", "CKD Stage 4"),
    (r"\b(?:chronic\s+(?:kidney|renal)\s+disease|ckd)\s+(?:stage\s+)?(?:3b?|iii|three)\b", "CKD Stage 3"),
    (r"\b(?:chronic\s+(?:kidney|renal)\s+disease|ckd)\s+(?:stage\s+)?(?:2|ii|two)\b", "CKD Stage 2"),
    (r"\b(?:chronic\s+(?:kidney|renal)\s+disease|ckd)\s+(?:stage\s+)?(?:1|i|one)\b", "CKD Stage 1"),
    (r"\b(?:esrd|eskd|end[\s-]?stage\s+(?:kidney|renal)\s+disease)\b", "End Stage Renal Disease"),
    (r"\b(?:chronic\s+(?:kidney|renal)\s+disease|ckd)\b", "Chronic Kidney Disease"),
    (r"\b(?:copd|chronic\s+obstructive\s+pulmonary\s+disease)\b", "COPD"),
    (r"\basthma\b", "Asthma"),
    (r"\bpneumonia\b", "Pneumonia"),
    (r"\b(?:stroke|cva|cerebrovascular\s+accident)\b", "Stroke"),
    (r"\b(?:mi|myocardial\s+infarction|heart\s+attack)\b", "Myocardial Infarction"),
    (r"\b(?:depression|major\s+depressive\s+disorder|mdd)\b", "Depression"),
    (r"\banxiety(?:\s+disorder)?\b", "Anxiety"),
    (r"\b(?:hyperlipidemia|dyslipidemia|high\s+cholesterol)\b", "Hyperlipidemia"),
    (r"\bhypothyroidism\b", "Hypothyroidism"),
    (r"\bhyperthyroidism\b", "Hyperthyroidism"),
    (r"\b(?:gerd|gastroesophageal\s+reflux)\b", "GERD"),
    (r"\b(?:osteoarthritis|oa)\b", "Osteoarthritis"),
    (r"\b(?:rheumatoid\s+arthritis)\b", "Rheumatoid Arthritis"),
    (r"\bobesity\b", "Obesity"),
    (r"\b(?:sleep\s+apnea|osa|obstructive\s+sleep\s+apnea)\b", "Sleep Apnea"),
    (r"\b(?:dvt|deep\s+vein\s+thrombosis)\b", "Deep Vein Thrombosis"),
    (r"\b(?:pulmonary\s+embolism|pe)\b", "Pulmonary Embolism"),
    (r"\b(?:uti|urinary\s+tract\s+infection)\b", "Urinary Tract Infection"),
    (r"\bsepsis\b", "Sepsis"),
    (r"\b(?:cancer|malignancy|carcinoma|neoplasm)\b", "Cancer"),
    (r"\b(?:iron\s+deficiency\s+anemia|iron\s+deficiency\s+anaemia|ida)\b", "Iron Deficiency Anemia"),
    (r"\b(?:hemorrhagic\s+anemia|blood\s+loss\s+anemia|acute\s+blood\s+loss\s+anemia)\b", "Hemorrhagic Anemia"),
    (r"\banemia\b", "Anemia"),
    (r"\b(?:viral\s+)?gastroenteritis\b", "Gastroenteritis"),
    (r"\b(?:syncope|fainting|fainted|passed\s+out|loss\s+of\s+consciousness)\b", "Syncope"),
    (r"\bdehydration\b", "Dehydration"),
    (r"\b(?:volume\s+depletion|hypovolemia)\b", "Volume Depletion"),
    (r"\b(?:orthostatic\s+hypotension|orthostatic\s+syncope|postural\s+hypotension)\b", "Orthostatic Hypotension"),
    (r"\bhypotension\b", "Hypotension"),
    # Neurological conditions
    (r"\b(?:peripheral\s+neuropathy|diabetic\s+neuropathy|neuropathy)\b", "Peripheral Neuropathy"),
    (r"\b(?:autonomic\s+neuropathy)\b", "Autonomic Neuropathy"),
    (r"\b(?:dementia|alzheimer(?:'?s)?(?:\s+disease)?)\b", "Dementia"),
    (r"\b(?:parkinson(?:'?s)?(?:\s+disease)?)\b", "Parkinson Disease"),
    (r"\b(?:multiple\s+sclerosis|ms)\b", "Multiple Sclerosis"),
    (r"\b(?:epilepsy|seizure\s+disorder)\b", "Epilepsy"),
    (r"\b(?:migraine(?:s)?)\b", "Migraine"),
    # Vascular conditions
    (r"\b(?:peripheral\s+(?:arterial|artery|vascular)\s+disease|pad|pvd)\b", "Peripheral Arterial Disease"),
    (r"\b(?:aortic\s+aneurysm|aaa)\b", "Aortic Aneurysm"),
    (r"\b(?:carotid\s+(?:stenosis|disease))\b", "Carotid Stenosis"),
    (r"\b(?:claudication|intermittent\s+claudication)\b", "Claudication"),
    (r"\b(?:varicose\s+veins)\b", "Varicose Veins"),
    (r"\b(?:chronic\s+venous\s+insufficiency|cvi)\b", "Chronic Venous Insufficiency"),
    # Infectious diseases
    (r"\b(?:osteomyelitis)\b", "Osteomyelitis"),
    (r"\b(?:cellulitis)\b", "Cellulitis"),
    (r"\b(?:abscess)\b", "Abscess"),
    (r"\b(?:bacteremia)\b", "Bacteremia"),
    (r"\b(?:endocarditis)\b", "Endocarditis"),
    (r"\b(?:meningitis)\b", "Meningitis"),
    (r"\b(?:encephalitis)\b", "Encephalitis"),
    (r"\b(?:wound\s+infection|infected\s+wound)\b", "Wound Infection"),
    (r"\b(?:diabetic\s+foot\s+infection|foot\s+infection)\b", "Diabetic Foot Infection"),
    (r"\b(?:skin\s+(?:and\s+)?soft\s+tissue\s+infection|ssti)\b", "Skin and Soft Tissue Infection"),
    (r"\b(?:necrotizing\s+fasciitis)\b", "Necrotizing Fasciitis"),
    (r"\b(?:gangrene)\b", "Gangrene"),
    (r"\b(?:covid(?:-?19)?|sars-cov-2|coronavirus)\b", "COVID-19"),
    (r"\b(?:influenza|flu)\b", "Influenza"),
    (r"\b(?:hepatitis\s*[abc]?)\b", "Hepatitis"),
    (r"\b(?:hiv|aids|human\s+immunodeficiency\s+virus)\b", "HIV"),
    # Diabetic complications
    (r"\b(?:diabetic\s+ketoacidosis|dka)\b", "Diabetic Ketoacidosis"),
    (r"\b(?:hyperglycemia|high\s+(?:blood\s+)?(?:sugar|glucose))\b", "Hyperglycemia"),
    (r"\b(?:hypoglycemia|low\s+(?:blood\s+)?(?:sugar|glucose))\b", "Hypoglycemia"),
    (r"\b(?:diabetic\s+retinopathy|retinopathy)\b", "Diabetic Retinopathy"),
    (r"\b(?:diabetic\s+nephropathy|nephropathy)\b", "Diabetic Nephropathy"),
    (r"\b(?:foot\s+ulcer|diabetic\s+(?:foot\s+)?ulcer|plantar\s+ulcer)\b", "Foot Ulcer"),
    (r"\b(?:hyperosmolar\s+(?:hyperglycemic\s+)?(?:state|syndrome)|hhs)\b", "Hyperosmolar Hyperglycemic State"),
    # Skin/wound conditions
    (r"\b(?:pressure\s+(?:ulcer|sore|injury)|decubitus(?:\s+ulcer)?|bedsore)\b", "Pressure Ulcer"),
    (r"\b(?:venous\s+(?:stasis\s+)?ulcer|venous\s+ulcer)\b", "Venous Ulcer"),
    (r"\b(?:arterial\s+ulcer)\b", "Arterial Ulcer"),
    (r"\b(?:skin\s+tear)\b", "Skin Tear"),
    (r"\b(?:dermatitis)\b", "Dermatitis"),
    (r"\b(?:eczema)\b", "Eczema"),
    (r"\b(?:psoriasis)\b", "Psoriasis"),
    # Renal conditions
    (r"\b(?:acute\s+kidney\s+injury|aki|acute\s+renal\s+failure|arf)\b", "Acute Kidney Injury"),
    (r"\b(?:end[\s-]?stage\s+(?:renal|kidney)\s+disease|esrd|eskd)\b", "End Stage Renal Disease"),
    (r"\b(?:nephrolithiasis|kidney\s+stone(?:s)?|renal\s+calcul(?:i|us))\b", "Kidney Stones"),
    (r"\b(?:hydronephrosis)\b", "Hydronephrosis"),
    (r"\b(?:pyelonephritis)\b", "Pyelonephritis"),
    (r"\b(?:glomerulonephritis)\b", "Glomerulonephritis"),
    # Hepatic/GI conditions
    (r"\b(?:cirrhosis|liver\s+cirrhosis)\b", "Cirrhosis"),
    (r"\b(?:fatty\s+liver|nafld|nash|hepatic\s+steatosis)\b", "Fatty Liver Disease"),
    (r"\b(?:liver\s+disease|hepatic\s+disease|chronic\s+liver\s+disease|cld)\b", "Liver Disease"),
    (r"\b(?:pancreatitis)\b", "Pancreatitis"),
    (r"\b(?:cholecystitis)\b", "Cholecystitis"),
    (r"\b(?:cholelithiasis|gallstone(?:s)?)\b", "Cholelithiasis"),
    (r"\b(?:appendicitis)\b", "Appendicitis"),
    (r"\b(?:perforated\s+appendix|ruptured\s+appendix)\b", "Perforated Appendicitis"),
    (r"\b(?:diverticulitis)\b", "Diverticulitis"),
    (r"\b(?:diverticulosis)\b", "Diverticulosis"),
    (r"\b(?:crohn(?:'?s)?(?:\s+disease)?)\b", "Crohn Disease"),
    (r"\b(?:ulcerative\s+colitis)\b", "Ulcerative Colitis"),
    (r"\b(?:irritable\s+bowel\s+syndrome|ibs)\b", "Irritable Bowel Syndrome"),
    (r"\b(?:upper\s+gi\s+bleed(?:ing)?|ugib)\b", "Upper GI Bleeding"),
    (r"\b(?:lower\s+gi\s+bleed(?:ing)?|lgib)\b", "Lower GI Bleeding"),
    (r"\b(?:gi\s+bleed(?:ing)?|gastrointestinal\s+(?:bleed(?:ing)?|hemorrhage))\b", "GI Bleeding"),
    (r"\b(?:peptic\s+ulcer(?:\s+disease)?|pud)\b", "Peptic Ulcer Disease"),
    (r"\b(?:gastric\s+ulcer)\b", "Gastric Ulcer"),
    (r"\b(?:duodenal\s+ulcer)\b", "Duodenal Ulcer"),
    (r"\b(?:bowel\s+obstruction|intestinal\s+obstruction|sbo|lbo)\b", "Bowel Obstruction"),
    (r"\b(?:ileus)\b", "Ileus"),
    (r"\b(?:ascites)\b", "Ascites"),
    (r"\b(?:hepatic\s+encephalopathy)\b", "Hepatic Encephalopathy"),
    # Hematologic conditions
    (r"\b(?:thrombocytopenia)\b", "Thrombocytopenia"),
    (r"\b(?:leukocytosis)\b", "Leukocytosis"),
    (r"\b(?:leukopenia|neutropenia)\b", "Leukopenia"),
    (r"\b(?:pancytopenia)\b", "Pancytopenia"),
    (r"\b(?:coagulopathy)\b", "Coagulopathy"),
    (r"\b(?:dic|disseminated\s+intravascular\s+coagulation)\b", "DIC"),
    # Sickle cell disease and complications
    (r"\b(?:sickle\s+cell\s+(?:disease|anemia|anaemia)|scd|hbss|hbs[\s-]?disease)\b", "Sickle Cell Disease"),
    (r"\b(?:sickle\s+cell\s+trait|hbas|sickle\s+trait)\b", "Sickle Cell Trait"),
    (r"\b(?:vaso[\s-]?occlusive\s+(?:crisis|episode|pain\s+crisis)|voc|sickle\s+(?:cell\s+)?(?:pain\s+)?crisis)\b", "Vaso-occlusive Crisis"),
    (r"\b(?:acute\s+chest\s+syndrome)\b", "Acute Chest Syndrome"),
    (r"\b(?:avascular\s+necrosis|osteonecrosis|avn|aseptic\s+necrosis)\b", "Avascular Necrosis"),
    (r"\b(?:hemolytic\s+anemia|haemolytic\s+anaemia|hemolysis)\b", "Hemolytic Anemia"),
    (r"\b(?:aplastic\s+crisis|aplastic\s+anemia)\b", "Aplastic Crisis"),
    (r"\b(?:splenic\s+sequestration(?:\s+crisis)?)\b", "Splenic Sequestration"),
    (r"\b(?:priapism)\b", "Priapism"),
    (r"\b(?:iron\s+overload|hemochromatosis|hemosiderosis)\b", "Iron Overload"),
    (r"\b(?:chronic\s+pain\s+syndrome)\b", "Chronic Pain Syndrome"),
    (r"\b(?:leg\s+ulcer(?:s)?|sickle\s+cell\s+ulcer(?:s)?)\b", "Leg Ulcers"),
    (r"\b(?:stroke|cerebrovascular\s+accident|cva)\b", "Stroke"),
    (r"\b(?:pulmonary\s+hypertension|pah|phtn)\b", "Pulmonary Hypertension"),
    (r"\b(?:retinopathy|proliferative\s+retinopathy)\b", "Retinopathy"),
    # Electrolyte/metabolic disorders
    (r"\b(?:hyponatremia|low\s+sodium)\b", "Hyponatremia"),
    (r"\b(?:hypernatremia|high\s+sodium)\b", "Hypernatremia"),
    (r"\b(?:hypokalemia|low\s+potassium)\b", "Hypokalemia"),
    (r"\b(?:hyperkalemia|high\s+potassium)\b", "Hyperkalemia"),
    (r"\b(?:hypocalcemia|low\s+calcium)\b", "Hypocalcemia"),
    (r"\b(?:hypercalcemia|high\s+calcium)\b", "Hypercalcemia"),
    (r"\b(?:hypomagnesemia|low\s+magnesium)\b", "Hypomagnesemia"),
    (r"\b(?:metabolic\s+acidosis)\b", "Metabolic Acidosis"),
    (r"\b(?:metabolic\s+alkalosis)\b", "Metabolic Alkalosis"),
    (r"\b(?:respiratory\s+acidosis)\b", "Respiratory Acidosis"),
    (r"\b(?:respiratory\s+alkalosis)\b", "Respiratory Alkalosis"),
    (r"\b(?:lactic\s+acidosis)\b", "Lactic Acidosis"),
    # Cardiac conditions
    (r"\b(?:acute\s+coronary\s+syndrome|acs)\b", "Acute Coronary Syndrome"),
    (r"\b(?:unstable\s+angina|ua)\b", "Unstable Angina"),
    (r"\b(?:stable\s+angina|angina\s+pectoris)\b", "Stable Angina"),
    (r"\b(?:ischemia|ischaemia|myocardial\s+ischemia)\b", "Ischemia"),
    (r"\b(?:demand\s+ischemia)\b", "Demand Ischemia"),
    (r"\b(?:nstemi|non[\s-]?st[\s-]?elevation\s+mi)\b", "NSTEMI"),
    (r"\b(?:stemi|st[\s-]?elevation\s+mi)\b", "STEMI"),
    (r"\b(?:cardiomyopathy)\b", "Cardiomyopathy"),
    (r"\b(?:pericarditis)\b", "Pericarditis"),
    (r"\b(?:pericardial\s+effusion)\b", "Pericardial Effusion"),
    (r"\b(?:cardiac\s+tamponade|tamponade)\b", "Cardiac Tamponade"),
    (r"\b(?:aortic\s+stenosis|as)\b", "Aortic Stenosis"),
    (r"\b(?:aortic\s+regurgitation|ar|aortic\s+insufficiency)\b", "Aortic Regurgitation"),
    (r"\b(?:mitral\s+stenosis|ms)\b", "Mitral Stenosis"),
    (r"\b(?:mitral\s+regurgitation|mr|mitral\s+insufficiency)\b", "Mitral Regurgitation"),
    (r"\b(?:atrial\s+flutter)\b", "Atrial Flutter"),
    (r"\b(?:ventricular\s+tachycardia|vtach|vt)\b", "Ventricular Tachycardia"),
    (r"\b(?:ventricular\s+fibrillation|vfib|vf)\b", "Ventricular Fibrillation"),
    (r"\b(?:bradycardia)\b", "Bradycardia"),
    (r"\b(?:tachycardia)\b", "Tachycardia"),
    (r"\b(?:heart\s+block|av\s+block)\b", "Heart Block"),
    (r"\b(?:sick\s+sinus\s+syndrome)\b", "Sick Sinus Syndrome"),
    # Pulmonary conditions
    (r"\b(?:pulmonary\s+edema|flash\s+pulmonary\s+edema)\b", "Pulmonary Edema"),
    (r"\b(?:pleural\s+effusion)\b", "Pleural Effusion"),
    (r"\b(?:pneumothorax)\b", "Pneumothorax"),
    (r"\b(?:hemothorax)\b", "Hemothorax"),
    (r"\b(?:ards|acute\s+respiratory\s+distress\s+syndrome)\b", "ARDS"),
    (r"\b(?:respiratory\s+failure)\b", "Respiratory Failure"),
    (r"\b(?:pulmonary\s+fibrosis|ipf)\b", "Pulmonary Fibrosis"),
    (r"\b(?:bronchitis)\b", "Bronchitis"),
    (r"\b(?:bronchiectasis)\b", "Bronchiectasis"),
    (r"\b(?:lung\s+cancer)\b", "Lung Cancer"),
    # Musculoskeletal
    (r"\b(?:fracture)\b", "Fracture"),
    (r"\b(?:osteoporosis)\b", "Osteoporosis"),
    (r"\b(?:gout)\b", "Gout"),
    (r"\b(?:fibromyalgia)\b", "Fibromyalgia"),
    (r"\b(?:lupus|sle|systemic\s+lupus\s+erythematosus)\b", "Systemic Lupus Erythematosus"),
    (r"\b(?:spondylosis)\b", "Spondylosis"),
    (r"\b(?:spinal\s+stenosis)\b", "Spinal Stenosis"),
    (r"\b(?:disc\s+herniation|herniated\s+disc)\b", "Disc Herniation"),
    (r"\b(?:rotator\s+cuff\s+(?:tear|injury))\b", "Rotator Cuff Tear"),
    # Psychiatric
    (r"\b(?:bipolar\s+disorder)\b", "Bipolar Disorder"),
    (r"\b(?:schizophrenia)\b", "Schizophrenia"),
    (r"\b(?:ptsd|post[\s-]?traumatic\s+stress\s+disorder)\b", "PTSD"),
    (r"\b(?:ocd|obsessive[\s-]?compulsive\s+disorder)\b", "OCD"),
    (r"\b(?:adhd|attention\s+deficit)\b", "ADHD"),
    (r"\b(?:substance\s+(?:abuse|use\s+disorder)|sud)\b", "Substance Use Disorder"),
    (r"\b(?:alcohol(?:ism|\s+use\s+disorder|\s+abuse)?)\b", "Alcohol Use Disorder"),
    (r"\b(?:opioid\s+(?:use\s+disorder|abuse|dependence))\b", "Opioid Use Disorder"),
    # Other
    (r"\b(?:shock)\b", "Shock"),
    (r"\b(?:septic\s+shock)\b", "Septic Shock"),
    (r"\b(?:cardiogenic\s+shock)\b", "Cardiogenic Shock"),
    (r"\b(?:hypovolemic\s+shock)\b", "Hypovolemic Shock"),
    (r"\b(?:anaphylaxis|anaphylactic\s+shock)\b", "Anaphylaxis"),
    (r"\b(?:allergic\s+reaction)\b", "Allergic Reaction"),
    # Note: NKDA and drug allergy patterns moved to ALLERGY_PATTERNS
    (r"\b(?:hypothermia)\b", "Hypothermia"),
    (r"\b(?:hyperthermia|heat\s+stroke)\b", "Hyperthermia"),
    (r"\b(?:malnutrition)\b", "Malnutrition"),
    (r"\b(?:failure\s+to\s+thrive)\b", "Failure to Thrive"),
    (r"\b(?:altered\s+mental\s+status|ams)\b", "Altered Mental Status"),
    (r"\b(?:encephalopathy)\b", "Encephalopathy"),
    (r"\b(?:delirium)\b", "Delirium"),
    (r"\b(?:coma)\b", "Coma"),
    (r"\b(?:benign\s+prostatic\s+hyperplasia|bph)\b", "Benign Prostatic Hyperplasia"),
    (r"\b(?:urinary\s+retention)\b", "Urinary Retention"),
    (r"\b(?:chronic\s+pain)\b", "Chronic Pain"),
    (r"\b(?:neuropathic\s+pain)\b", "Neuropathic Pain"),
    (r"\b(?:falls?|fall\s+risk|recurrent\s+falls)\b", "Fall Risk"),
    (r"\b(?:frailty)\b", "Frailty"),
    (r"\b(?:cachexia)\b", "Cachexia"),
]


# ============================================================================
# Symptom patterns
# ============================================================================

SYMPTOM_PATTERNS = [
    (r"\b(?:fever|febrile)\b", "Fever"),
    (r"\bcough(?:ing)?\b", "Cough"),
    (r"\b(?:shortness\s+of\s+breath|sob|dyspnea)\b", "Shortness of Breath"),
    (r"\bchest\s+pain\b", "Chest Pain"),
    (r"\b(?:abdominal\s+pain|stomach\s+ache)\b", "Abdominal Pain"),
    (r"\b(?:headache|cephalgia)\b", "Headache"),
    (r"\bnausea\b", "Nausea"),
    (r"\b(?:vomiting|emesis)\b", "Vomiting"),
    (r"\b(?:diarrhea|diarrhoea)\b", "Diarrhea"),
    (r"\bconstipation\b", "Constipation"),
    (r"\b(?:fatigue[d]?|tiredness|tired)\b", "Fatigue"),
    (r"\b(?:dizziness|vertigo|dizzy)\b", "Dizziness"),
    (r"\b(?:lightheaded(?:ness)?|light[\s-]?headed(?:ness)?)\b", "Lightheadedness"),
    (r"\btunnel\s+vision\b", "Tunnel Vision"),
    (r"\b(?:pre[\s-]?syncope|presyncope|near\s+syncope|near\s+fainting)\b", "Presyncope"),
    (r"\b(?:blurred\s+vision|blurry\s+vision|vision\s+changes?)\b", "Vision Changes"),
    (r"\bpalpitations\b", "Palpitations"),
    (r"\b(?:edema|swelling)\b", "Edema"),
    (r"\brash\b", "Rash"),
    (r"\b(?:itching|pruritus)\b", "Itching"),
    (r"\bweight\s+(?:loss|gain)\b", "Weight Change"),
    (r"\binsomnia\b", "Insomnia"),
    (r"\b(?:joint\s+pain|arthralgia)\b", "Joint Pain"),
    (r"\bback\s+pain\b", "Back Pain"),
    (r"\bneck\s+pain\b", "Neck Pain"),
    (r"\bweakness\b", "Weakness"),
    (r"\b(?:numbness|paresthesia)\b", "Numbness"),
    (r"\bconfusion\b", "Confusion"),
    (r"\b(?:loss\s+of\s+consciousness|loc|passed\s+out|passing\s+out|faint(?:ed|ing)?)\b", "Loss of Consciousness"),
    (r"\b(?:seizure[\s-]?like\s+activity|convulsion)\b", "Seizure-like Activity"),
    (r"\btongue\s+bite\b", "Tongue Bite"),
    (r"\bincontinence\b", "Incontinence"),
    (r"\b(?:post[\s-]?ictal\s+confusion|post[\s-]?ictal)\b", "Post-ictal State"),
    (r"\b(?:poor\s+)?(?:oral|po)\s+intake\b", "Poor Oral Intake"),
    # Additional symptoms from clinical notes
    (r"\b(?:chills?|rigor(?:s)?)\b", "Chills"),
    (r"\b(?:purulent\s+)?drainage\b", "Drainage"),
    (r"\berythema\b", "Erythema"),
    (r"\bwarmth\b", "Warmth"),
    (r"\b(?:foul\s+)?odor\b", "Foul Odor"),
    (r"\b(?:sore\s+throat|pharyngitis)\b", "Sore Throat"),
    (r"\b(?:runny\s+nose|rhinorrhea)\b", "Rhinorrhea"),
    (r"\b(?:nasal\s+congestion|congestion)\b", "Nasal Congestion"),
    (r"\b(?:wheezing|wheeze)\b", "Wheezing"),
    (r"\bstridor\b", "Stridor"),
    (r"\b(?:chest\s+tightness)\b", "Chest Tightness"),
    (r"\b(?:hemoptysis|coughing\s+(?:up\s+)?blood)\b", "Hemoptysis"),
    (r"\b(?:hematemesis|vomiting\s+blood|bloody\s+vomit|coffee[\s-]?ground\s+(?:emesis|vomit))\b", "Hematemesis"),
    (r"\b(?:melena|black\s+(?:tarry\s+)?stool(?:s)?)\b", "Melena"),
    (r"\b(?:hematochezia|blood(?:y)?\s+stool(?:s)?|rectal\s+bleed(?:ing)?)\b", "Hematochezia"),
    (r"\b(?:brbpr|bright\s+red\s+blood\s+per\s+rectum)\b", "Bright Red Blood Per Rectum"),
    (r"\b(?:hematuria|blood(?:y)?\s+urine)\b", "Hematuria"),
    (r"\b(?:dysuria|painful\s+urination)\b", "Dysuria"),
    (r"\b(?:urinary\s+)?frequency\b", "Urinary Frequency"),
    (r"\b(?:urinary\s+)?urgency\b", "Urinary Urgency"),
    (r"\blethargy\b", "Lethargy"),
    (r"\bmalaise\b", "Malaise"),
    (r"\b(?:night\s+sweats)\b", "Night Sweats"),
    (r"\b(?:anorexia|loss\s+of\s+appetite|decreased\s+appetite)\b", "Anorexia"),
    (r"\b(?:polydipsia|excessive\s+thirst)\b", "Polydipsia"),
    (r"\b(?:polyuria|frequent\s+urination)\b", "Polyuria"),
    (r"\b(?:polyphagia|excessive\s+hunger)\b", "Polyphagia"),
    (r"\b(?:diplopia|double\s+vision)\b", "Diplopia"),
    (r"\b(?:photophobia|light\s+sensitivity)\b", "Photophobia"),
    (r"\b(?:tinnitus|ringing\s+in\s+(?:the\s+)?ears?)\b", "Tinnitus"),
    (r"\b(?:hearing\s+loss)\b", "Hearing Loss"),
    (r"\b(?:tremor(?:s)?)\b", "Tremor"),
    (r"\bataxia\b", "Ataxia"),
    (r"\bdysarthria\b", "Dysarthria"),
    (r"\b(?:dysphagia|difficulty\s+swallowing)\b", "Dysphagia"),
    (r"\b(?:odynophagia|painful\s+swallowing)\b", "Odynophagia"),
    (r"\bhiccups?\b", "Hiccups"),
    (r"\b(?:abdominal\s+)?distension\b", "Abdominal Distension"),
    (r"\b(?:flank\s+pain)\b", "Flank Pain"),
    (r"\b(?:tenderness)\b", "Tenderness"),
    (r"\b(?:discomfort)\b", "Discomfort"),
    (r"\b(?:guarding)\b", "Guarding"),
    (r"\b(?:rebound\s+tenderness|rebound)\b", "Rebound Tenderness"),
    (r"\b(?:jaundice|icterus|yellow\s+skin)\b", "Jaundice"),
    (r"\b(?:cyanosis|blue\s+(?:skin|lips))\b", "Cyanosis"),
    (r"\b(?:pallor|pale)\b", "Pallor"),
    (r"\b(?:petechiae)\b", "Petechiae"),
    (r"\b(?:purpura)\b", "Purpura"),
    (r"\b(?:ecchymosis|bruising)\b", "Ecchymosis"),
    (r"\b(?:hives|urticaria)\b", "Urticaria"),
    (r"\b(?:angioedema)\b", "Angioedema"),
    (r"\b(?:clubbing)\b", "Clubbing"),
    (r"\b(?:crepitus)\b", "Crepitus"),
    (r"\b(?:muscle\s+(?:ache|pain)|myalgia)\b", "Myalgia"),
    (r"\b(?:bone\s+pain)\b", "Bone Pain"),
    (r"\b(?:radicular\s+pain|radiculopathy)\b", "Radicular Pain"),
    (r"\b(?:sciatica)\b", "Sciatica"),
    (r"\b(?:stiffness)\b", "Stiffness"),
    (r"\b(?:morning\s+stiffness)\b", "Morning Stiffness"),
    (r"\b(?:limited\s+(?:range\s+of\s+)?motion|rom)\b", "Limited Range of Motion"),
    (r"\b(?:focal\s+neurological\s+deficit(?:s)?|focal\s+neuro\s+deficit)\b", "Focal Neurological Deficit"),
    (r"\b(?:aphasia)\b", "Aphasia"),
    (r"\b(?:facial\s+droop(?:ing)?)\b", "Facial Droop"),
    (r"\b(?:hemiparesis|hemiplegia)\b", "Hemiparesis"),
    (r"\b(?:quadriparesis|quadriplegia)\b", "Quadriparesis"),
    (r"\b(?:paraparesis|paraplegia)\b", "Paraparesis"),
    (r"\b(?:foot\s+drop)\b", "Foot Drop"),
    (r"\b(?:wrist\s+drop)\b", "Wrist Drop"),
    (r"\b(?:hyperreflexia)\b", "Hyperreflexia"),
    (r"\b(?:hyporeflexia|areflexia)\b", "Hyporeflexia"),
    (r"\b(?:clonus)\b", "Clonus"),
    (r"\b(?:babinski(?:\s+sign)?|upgoing\s+toes?)\b", "Babinski Sign"),
    # Emergency/critical symptoms
    (r"\b(?:unresponsive|unresponsiveness)\b", "Unresponsive"),
    (r"\b(?:apnea|apneic|apnoea|apnoeic)\b", "Apnea"),
    (r"\b(?:nauseated|feeling\s+sick)\b", "Nauseated"),
    (r"\b(?:diaphoretic|sweating|sweaty)\b", "Diaphoresis"),
    (r"\b(?:irritable|irritability)\b", "Irritability"),
    (r"\b(?:restless(?:ness)?|agitated|agitation)\b", "Restlessness"),
    (r"\b(?:altered\s+mental\s+status|ams)\b", "Altered Mental Status"),
    (r"\b(?:decreased\s+(?:loc|level\s+of\s+consciousness))\b", "Decreased Level of Consciousness"),
    (r"\b(?:obtunded)\b", "Obtunded"),
    (r"\b(?:somnolent|somnolence)\b", "Somnolence"),
    (r"\b(?:stupor(?:ous)?)\b", "Stupor"),
    (r"\b(?:comatose|coma)\b", "Coma"),
    (r"\b(?:bradypnea|bradypneic)\b", "Bradypnea"),
    (r"\b(?:tachypnea|tachypneic)\b", "Tachypnea"),
    (r"\b(?:hypoxic|hypoxia)\b", "Hypoxia"),
    (r"\b(?:cyanotic)\b", "Cyanotic"),
    (r"\b(?:respiratory\s+distress)\b", "Respiratory Distress"),
    (r"\b(?:respiratory\s+depression)\b", "Respiratory Depression"),
    (r"\b(?:tachycardic)\b", "Tachycardia"),
    (r"\b(?:irregularly\s+irregular)\b", "Irregularly Irregular Rhythm"),
    (r"\b(?:regularly\s+irregular)\b", "Regularly Irregular Rhythm"),
    (r"\b(?:bradycardic)\b", "Bradycardia"),
    (r"\b(?:hypotensive)\b", "Hypotension"),
    (r"\b(?:hypertensive)\b", "Hypertension"),
    (r"\b(?:trauma(?:tic)?)\b", "Trauma"),
    (r"\b(?:self[\s-]?harm)\b", "Self-harm"),
    (r"\b(?:overdose|od)\b", "Overdose"),
    (r"\b(?:intoxicated|intoxication)\b", "Intoxication"),
    (r"\b(?:withdrawal)\b", "Withdrawal"),
    (r"\b(?:seizing|convulsing)\b", "Active Seizure"),
    (r"\b(?:bleeding|hemorrhage|hemorrhaging)\b", "Bleeding"),
    (r"\b(?:pain(?:ful)?)\b", "Pain"),
    (r"\b(?:anxious|anxiety)\b", "Anxiety"),
    (r"\b(?:depressed)\b", "Depressed Mood"),
    (r"\b(?:suicidal(?:\s+ideation)?|si)\b", "Suicidal Ideation"),
    (r"\b(?:homicidal(?:\s+ideation)?|hi)\b", "Homicidal Ideation"),
]


# ============================================================================
# Medication patterns
# ============================================================================

MEDICATION_PATTERNS = [
    # Diabetes medications
    r"\b(metformin|glucophage)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|g)))?(?:\s+(daily|bid|tid|qid|qd|prn))?",
    r"\b(insulin\s+glargine|lantus|basaglar)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?(?:\s+(nightly|daily|qhs))?",
    r"\b(insulin\s+lispro|humalog)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?(?:\s+(with\s+meals|ac|tid))?",
    r"\b(insulin\s+aspart|novolog)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?(?:\s+(with\s+meals|ac|tid))?",
    r"\b(insulin\s+regular|regular\s+insulin|humulin\s+r|novolin\s+r)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
    r"\b(insulin\s+nph|nph\s+insulin|humulin\s+n)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
    r"\b(insulin\s+detemir|levemir)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
    r"\b(insulin\s+degludec|tresiba)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
    r"\b(insulin(?:\s+(?:glargine|lispro|aspart|regular|nph|detemir|degludec))?)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
    r"\b(glipizide|glucotrol)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(glyburide|diabeta|micronase)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(glimepiride|amaryl)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(sitagliptin|januvia)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(empagliflozin|jardiance)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(canagliflozin|invokana)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(dapagliflozin|farxiga)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(semaglutide|ozempic|wegovy|rybelsus)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(weekly|daily))?",
    r"\b(liraglutide|victoza|saxenda)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(pioglitazone|actos)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    # Cardiovascular medications
    r"\b(lisinopril|prinivil|zestril)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|qd))?",
    r"\b(atorvastatin|lipitor)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qd|qhs))?",
    r"\b(amlodipine|norvasc)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qd))?",
    r"\b(aspirin|asa)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qd))?",
    r"\b(warfarin|coumadin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qd))?",
    r"\b(furosemide|lasix)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(carvedilol|coreg)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
    r"\b(metoprolol(?:\s+(?:tartrate|succinate))?)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(clopidogrel|plavix)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(rosuvastatin|crestor)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(simvastatin|zocor)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qhs))?",
    r"\b(pravastatin|pravachol)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(losartan|cozaar)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(valsartan|diovan)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(hydrochlorothiazide|hctz|microzide)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(spironolactone|aldactone)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(diltiazem|cardizem|tiazac)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|tid))?",
    r"\b(verapamil|calan|isoptin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|tid))?",
    r"\b(atenolol|tenormin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(propranolol|inderal)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|tid))?",
    r"\b(bisoprolol|zebeta)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(digoxin|lanoxin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|mcg)))?(?:\s+(daily))?",
    r"\b(amiodarone|cordarone|pacerone)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(isosorbide(?:\s+(?:mononitrate|dinitrate))?|imdur|isordil)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
    r"\b(nitroglycerin|nitro|ntg)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|mcg)))?",
    r"\b(hydralazine|apresoline)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|qid))?",
    r"\b(clonidine|catapres)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|tid))?",
    r"\b(prazosin|minipress)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|tid))?",
    r"\b(doxazosin|cardura)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(apixaban|eliquis)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
    r"\b(rivaroxaban|xarelto)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(dabigatran|pradaxa)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
    r"\b(enoxaparin|lovenox)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|q12h))?",
    r"\b(heparin)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
    # GI medications
    r"\b(omeprazole|prilosec)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|qd))?",
    r"\b(pantoprazole|protonix)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(esomeprazole|nexium)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(lansoprazole|prevacid)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(famotidine|pepcid)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(ranitidine|zantac)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(sucralfate|carafate)\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg)))?(?:\s+(qid|tid))?",
    r"\b(ondansetron|zofran)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
    r"\b(metoclopramide|reglan)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(qid|tid|prn))?",
    r"\b(promethazine|phenergan)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
    r"\b(docusate|colace)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(polyethylene\s+glycol|miralax|peg)\s*(?:(\d+(?:\.\d+)?\s*(?:g|ml)))?(?:\s+(daily))?",
    r"\b(lactulose)\s*(?:(\d+(?:\.\d+)?\s*(?:ml|g)))?(?:\s+(daily|bid|tid|qid))?",
    # Pain/Neurologic medications
    r"\b(nsaid(?:s)?)\b",
    r"\b(ppi(?:s)?)\b",
    r"\b(anticoagula(?:tion|nt)(?:s)?)\b",
    r"\b(acetaminophen|tylenol)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
    r"\b(ibuprofen|advil|motrin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn|tid))?",
    r"\b(naproxen|aleve|naprosyn)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|prn))?",
    r"\b(hydrocodone|norco|vicodin)\s*(?:(\d+(?:[\/\-]\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
    r"\b(oxycodone|oxycontin|roxicodone|percocet)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
    r"\b(morphine|ms\s+contin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
    r"\b(fentanyl|duragesic)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg|mcg/h)))?",
    r"\b(hydromorphone|dilaudid)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
    r"\b(tramadol|ultram)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn|tid|qid))?",
    r"\b(gabapentin|neurontin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|bid|qhs))?",
    r"\b(pregabalin|lyrica)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|tid))?",
    r"\b(duloxetine|cymbalta)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(amitriptyline|elavil)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(qhs|daily))?",
    r"\b(cyclobenzaprine|flexeril)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|prn))?",
    r"\b(baclofen|lioresal)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|qid))?",
    r"\b(tizanidine|zanaflex)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|tid|prn))?",
    # Thyroid
    r"\b(levothyroxine|synthroid|levoxyl)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg|mg)))?(?:\s+(daily))?",
    # Respiratory
    r"\b(albuterol|proventil|ventolin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|puffs?)))?(?:\s+(q\d+h|prn))?",
    r"\b(ipratropium|atrovent)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg|puffs?)))?(?:\s+(q\d+h|qid))?",
    r"\b(budesonide|pulmicort)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?(?:\s+(bid|daily))?",
    r"\b(fluticasone|flovent|flonase)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?(?:\s+(bid|daily))?",
    r"\b(montelukast|singulair)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qhs))?",
    r"\b(prednisone)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|taper))?",
    r"\b(methylprednisolone|solu-?medrol)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
    r"\b(dexamethasone|decadron)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|q\d+h))?",
    # Psychiatric
    r"\b(sertraline|zoloft)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(fluoxetine|prozac)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(escitalopram|lexapro)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(citalopram|celexa)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(paroxetine|paxil)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(venlafaxine|effexor)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(bupropion|wellbutrin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(mirtazapine|remeron)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(qhs|daily))?",
    r"\b(trazodone|desyrel)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(qhs|prn))?",
    r"\b(quetiapine|seroquel)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|qhs))?",
    r"\b(risperidone|risperdal)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(olanzapine|zyprexa)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qhs))?",
    r"\b(aripiprazole|abilify)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(haloperidol|haldol)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|prn))?",
    r"\b(lorazepam|ativan)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn|tid))?",
    r"\b(alprazolam|xanax)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|prn))?",
    r"\b(clonazepam|klonopin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|tid))?",
    r"\b(diazepam|valium)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|tid|prn))?",
    r"\b(zolpidem|ambien)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(qhs|prn))?",
    # Antibiotics
    r"\b(vancomycin|vanc)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|g)))?(?:\s+(?:iv|po|q\d+h))?",
    r"\b(piperacillin[\s/-]?tazobactam|pip[\s/-]?tazo?|zosyn)\s*(?:(\d+(?:\.\d+)?\s*(?:g)))?(?:\s+(?:iv|q\d+h))?",
    r"\b(ceftriaxone|rocephin)\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg)))?(?:\s+(?:iv|im|daily))?",
    r"\b(cefepime|maxipime)\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg)))?(?:\s+(?:iv|q\d+h))?",
    r"\b(cefazolin|ancef|kefzol)\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg)))?(?:\s+(?:iv|q\d+h))?",
    r"\b(cephalexin|keflex)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(qid|tid|bid))?",
    r"\b(cefdinir|omnicef)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(amoxicillin|amoxil)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|bid))?",
    r"\b(amoxicillin[\s/-]?clavulanate|augmentin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|tid))?",
    r"\b(ampicillin[\s/-]?sulbactam|unasyn)\s*(?:(\d+(?:\.\d+)?\s*(?:g)))?(?:\s+(?:iv|q\d+h))?",
    r"\b(azithromycin|zithromax|z[\s-]?pack)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(ciprofloxacin|cipro)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|daily))?",
    r"\b(levofloxacin|levaquin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(moxifloxacin|avelox)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(metronidazole|flagyl)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|bid|q\d+h))?",
    r"\b(doxycycline|vibramycin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|daily))?",
    r"\b(trimethoprim[\s/-]?sulfamethoxazole|tmp[\s/-]?smx|bactrim|septra)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
    r"\b(nitrofurantoin|macrobid|macrodantin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|qid))?",
    r"\b(clindamycin|cleocin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|qid|q\d+h))?",
    r"\b(meropenem|merrem)\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg)))?(?:\s+(?:iv|q\d+h))?",
    r"\b(ertapenem|invanz)\s*(?:(\d+(?:\.\d+)?\s*(?:g)))?(?:\s+(?:iv|daily))?",
    r"\b(imipenem[\s/-]?cilastatin|primaxin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|q\d+h))?",
    r"\b(linezolid|zyvox)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|po|bid))?",
    r"\b(daptomycin|cubicin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|daily))?",
    r"\b(gentamicin|garamycin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|q\d+h))?",
    r"\b(tobramycin|tobrex)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|q\d+h))?",
    r"\b(fluconazole|diflucan)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(micafungin|mycamine)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|daily))?",
    r"\b(caspofungin|cancidas)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|daily))?",
    r"\b(voriconazole|vfend)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
    r"\b(acyclovir|valacyclovir|zovirax|valtrex)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|tid))?",
    r"\b(oseltamivir|tamiflu)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
    # IV Fluids
    r"\b(iv\s+fluids?|intravenous\s+fluids?|ivf)\b",
    r"\b(normal\s+saline|ns|0\.9%?\s*(?:saline|nacl)|0\.9\s*ns)\b",
    r"\b(lactated\s+ringer(?:'?s)?|lr|ringer(?:'?s)?\s+lactate)\b",
    r"\b(d5(?:w|\s*1/2\s*ns|ns)?|dextrose\s+5%?)\b",
    r"\b(half\s+normal\s+saline|1/2\s*ns|0\.45%?\s*(?:saline|nacl))\b",
    r"\b(plasmalyte)\b",
    r"\b(albumin)\s*(?:(\d+(?:\.\d+)?\s*(?:%|g)))?",
    # Miscellaneous
    r"\b(potassium\s+chloride|kcl|k-?dur)\s*(?:(\d+(?:\.\d+)?\s*(?:meq|mg)))?",
    r"\b(magnesium(?:\s+(?:sulfate|oxide|chloride))?|mag\s+(?:sulfate|ox))\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg|meq)))?",
    r"\b(calcium(?:\s+(?:carbonate|gluconate|chloride))?|tums)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|g)))?",
    r"\b(sodium\s+bicarbonate|bicarb|nahco3)\s*(?:(\d+(?:\.\d+)?\s*(?:meq|mg)))?",
    r"\b(thiamine|vitamin\s+b1)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
    r"\b(folic\s+acid|folate)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
    r"\b(multivitamin|mvi)\s*(?:\s+(daily))?",
    r"\b(vitamin\s+d|cholecalciferol|ergocalciferol)\s*(?:(\d+(?:\.\d+)?\s*(?:iu|units?|mcg)))?",
    r"\b(iron(?:\s+(?:sulfate|gluconate))?|ferrous\s+(?:sulfate|gluconate))\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
    r"\b(epoetin|procrit|epogen|epo)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
    r"\b(darbepoetin|aranesp)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?",
    r"\b(filgrastim|neupogen|g-?csf)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?",
    # Sickle cell disease medications
    r"\b(hydroxyurea|hydrea|droxia|siklos)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(l[\s-]?glutamine|endari)\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg)))?(?:\s+(bid|daily))?",
    r"\b(voxelotor|oxbryta)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(crizanlizumab|adakveo)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
    r"\b(deferasirox|exjade|jadenu)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(deferoxamine|desferal)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|g)))?",
    r"\b(deferiprone|ferriprox)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid))?",
    r"\b(penicillin\s+v(?:k)?|pen\s*vk|veetids)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|daily))?",
    r"\b(allopurinol|zyloprim)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(colchicine|colcrys)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(tamsulosin|flomax)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(finasteride|proscar|propecia)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(sildenafil|viagra|revatio)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(prn|tid))?",
    r"\b(naloxone|narcan)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
    r"\b(flumazenil|romazicon)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
    r"\b(diphenhydramine|benadryl)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
    r"\b(hydroxyzine|vistaril|atarax)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn|tid))?",
    r"\b(cetirizine|zyrtec)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(loratadine|claritin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
    r"\b(fexofenadine|allegra)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
    r"\b(epinephrine|epipen|adrenaline)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|ml)))?",
    r"\b(norepinephrine|levophed|norepi)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?",
    r"\b(vasopressin|pitressin)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
    r"\b(dopamine)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?",
    r"\b(dobutamine)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?",
    r"\b(phenylephrine|neosynephrine)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg|mg)))?",
]


# ============================================================================
# Procedure patterns
# ============================================================================

PROCEDURE_PATTERNS = [
    # Cardiac procedures
    (r"\b(?:coronary\s+)?angiography|cath(?:eterization)?\b", "Cardiac Catheterization"),
    (r"\b(?:coronary\s+)?angioplasty|pci|ptca\b", "Coronary Angioplasty"),
    (r"\bcabg|coronary\s+(?:artery\s+)?bypass(?:\s+graft(?:ing)?)?\b", "CABG"),
    (r"\b(?:pacemaker|pacer|ppm)(?:\s+(?:implant(?:ation)?|insertion|placement))?\b", "Pacemaker Implantation"),
    (r"\b(?:icd|defibrillator)(?:\s+(?:implant(?:ation)?|insertion|placement))?\b", "ICD Implantation"),
    (r"\b(?:ablation)\b", "Cardiac Ablation"),
    (r"\b(?:cardioversion)\b", "Cardioversion"),
    (r"\b(?:echocardiogram|echo|tte|tee)\b", "Echocardiogram"),
    (r"\b(?:stress\s+test|exercise\s+tolerance\s+test|ett|treadmill\s+test)\b", "Stress Test"),
    # GI procedures
    (r"\bcolonoscopy\b", "Colonoscopy"),
    (r"\b(?:endoscopy|egd|esophagogastroduodenoscopy)\b", "Endoscopy"),
    (r"\bappendectomy\b", "Appendectomy"),
    (r"\bcholecystectomy\b", "Cholecystectomy"),
    (r"\b(?:paracentesis)\b", "Paracentesis"),
    (r"\b(?:thoracentesis)\b", "Thoracentesis"),
    (r"\b(?:ercp)\b", "ERCP"),
    # Surgical procedures
    (r"\bhysterectomy\b", "Hysterectomy"),
    (r"\b(?:c[\s-]?section|cesarean(?:\s+section)?)\b", "Cesarean Section"),
    (r"\b(?:joint\s+replacement|arthroplasty)\b", "Joint Replacement"),
    (r"\b(?:knee\s+replacement|tka)\b", "Total Knee Arthroplasty"),
    (r"\b(?:hip\s+replacement|tha)\b", "Total Hip Arthroplasty"),
    (r"\blaminectomy\b", "Laminectomy"),
    (r"\bspinal\s+fusion\b", "Spinal Fusion"),
    (r"\b(?:amputation)\b", "Amputation"),
    (r"\b(?:debridement)\b", "Debridement"),
    (r"\b(?:i\s*&\s*d|incision\s+and\s+drainage|incision\s+&\s+drainage)\b", "Incision and Drainage"),
    (r"\b(?:wound\s+care)\b", "Wound Care"),
    (r"\b(?:skin\s+graft(?:ing)?)\b", "Skin Grafting"),
    (r"\b(?:laparotomy|exploratory\s+laparotomy)\b", "Laparotomy"),
    (r"\b(?:laparoscopy|laparoscopic)\b", "Laparoscopy"),
    (r"\b(?:hernia\s+repair|herniorrhaphy)\b", "Hernia Repair"),
    (r"\b(?:mastectomy)\b", "Mastectomy"),
    (r"\b(?:thyroidectomy)\b", "Thyroidectomy"),
    (r"\b(?:nephrectomy)\b", "Nephrectomy"),
    (r"\b(?:prostatectomy)\b", "Prostatectomy"),
    (r"\b(?:tracheostomy|trach)\b", "Tracheostomy"),
    # Medical procedures
    (r"\b(?:dialysis|hemodialysis|hd|peritoneal\s+dialysis|pd)\b", "Dialysis"),
    (r"\b(?:chemotherapy|chemo)\b", "Chemotherapy"),
    (r"\b(?:radiation(?:\s+therapy)?|radiotherapy|xrt)\b", "Radiation Therapy"),
    (r"\b(?:surgery|surgical\s+(?:procedure|intervention))\b", "Surgery"),
    (r"\b(?:biopsy)\b", "Biopsy"),
    (r"\b(?:transfusion|blood\s+transfusion|prbc(?:s)?|ffp)\b", "Transfusion"),
    (r"\b(?:intubation)\b", "Intubation"),
    (r"\b(?:extubation)\b", "Extubation"),
    (r"\b(?:ventilation|mechanical\s+ventilation)\b", "Mechanical Ventilation"),
    (r"\b(?:cpr|cardiopulmonary\s+resuscitation)\b", "CPR"),
    (r"\b(?:lumbar\s+puncture|lp|spinal\s+tap)\b", "Lumbar Puncture"),
    (r"\b(?:central\s+line|central\s+venous\s+catheter|cvc|picc(?:\s+line)?)\b", "Central Line Insertion"),
    (r"\b(?:arterial\s+line|a[\s-]?line)\b", "Arterial Line"),
    (r"\b(?:foley(?:\s+catheter)?|urinary\s+catheter(?:ization)?)\b", "Urinary Catheterization"),
    (r"\b(?:ng\s+tube|nasogastric\s+tube)\b", "NG Tube Placement"),
    (r"\b(?:feeding\s+tube|peg(?:\s+tube)?|g[\s-]?tube)\b", "Feeding Tube Placement"),
    (r"\b(?:chest\s+tube|thoracostomy)\b", "Chest Tube Insertion"),
    # Imaging procedures/studies
    (r"\b(?:x[\s-]?ray|xray|radiograph)\b", "X-Ray"),
    (r"\b(?:ct(?:\s+scan)?|cat\s+scan|computed\s+tomography)\b", "CT Scan"),
    (r"\b(?:mri|magnetic\s+resonance\s+imaging)\b", "MRI"),
    (r"\b(?:ultrasound|us|sonogram|sonography)\b", "Ultrasound"),
    (r"\b(?:pet(?:\s+scan)?|positron\s+emission\s+tomography)\b", "PET Scan"),
    (r"\b(?:nuclear\s+(?:medicine\s+)?(?:study|scan)|bone\s+scan)\b", "Nuclear Medicine Scan"),
    (r"\b(?:angiogram)\b", "Angiogram"),
    (r"\b(?:venogram)\b", "Venogram"),
    (r"\b(?:doppler(?:\s+(?:ultrasound|study))?)\b", "Doppler Study"),
    (r"\b(?:ekg|ecg|electrocardiogram)\b", "EKG"),
    (r"\b(?:eeg|electroencephalogram)\b", "EEG"),
    (r"\b(?:emg|electromyography|nerve\s+conduction\s+study|ncs)\b", "EMG/NCS"),
    # Lab draws/cultures
    (r"\b(?:blood\s+cultur(?:e|es)?)\b", "Blood Culture"),
    (r"\b(?:urine\s+cultur(?:e|es)?|ucx)\b", "Urine Culture"),
    (r"\b(?:wound\s+cultur(?:e|es)?)\b", "Wound Culture"),
    (r"\b(?:sputum\s+cultur(?:e|es)?)\b", "Sputum Culture"),
    (r"\b(?:csf\s+(?:cultur(?:e|es)?|analysis))\b", "CSF Analysis"),
    (r"\b(?:stool\s+(?:cultur(?:e|es)?|(?:studies|sample)))\b", "Stool Culture"),
    (r"\b(?:blood\s+(?:draw|work)|labs|laboratory)\b", "Laboratory Testing"),
    (r"\b(?:type\s+and\s+(?:screen|crossmatch)|t&s|t\s*&\s*s|crossmatch)\b", "Type and Screen"),
    (r"\b(?:urinalysis|ua)\b", "Urinalysis"),
    (r"\b(?:cbc|complete\s+blood\s+count)\b", "CBC"),
    (r"\b(?:bmp|basic\s+metabolic\s+panel)\b", "BMP"),
    (r"\b(?:cmp|comprehensive\s+metabolic\s+panel)\b", "CMP"),
    (r"\b(?:lipid\s+panel)\b", "Lipid Panel"),
    (r"\b(?:coagulation\s+(?:panel|studies)|pt/inr|ptt)\b", "Coagulation Studies"),
    (r"\b(?:abg|arterial\s+blood\s+gas)\b", "ABG"),
    (r"\b(?:vbg|venous\s+blood\s+gas)\b", "VBG"),
    (r"\b(?:troponin)\b", "Troponin"),
    (r"\b(?:bnp|brain\s+natriuretic\s+peptide)\b", "BNP"),
    (r"\b(?:d[\s-]?dimer)\b", "D-Dimer"),
    (r"\b(?:crp|c[\s-]?reactive\s+protein)\b", "CRP"),
    (r"\b(?:esr|sed\s+rate|sedimentation\s+rate)\b", "ESR"),
    (r"\b(?:lactate|lactic\s+acid)\b", "Lactate"),
    (r"\b(?:procalcitonin|pct)\b", "Procalcitonin"),
    # Consults
    (r"\b(?:consult(?:ation)?)\b", "Consultation"),
    (r"\b(?:podiatry(?:\s+consult)?)\b", "Podiatry Consult"),
    (r"\b(?:ortho(?:pedic)?(?:s)?(?:\s+consult)?)\b", "Orthopedic Consult"),
    (r"\b(?:cardiology(?:\s+consult)?)\b", "Cardiology Consult"),
    (r"\b(?:nephrology(?:\s+consult)?)\b", "Nephrology Consult"),
    (r"\b(?:pulmonology(?:\s+consult)?)\b", "Pulmonology Consult"),
    (r"\b(?:gi(?:\s+consult)?|gastroenterology(?:\s+consult)?)\b", "GI Consult"),
    (r"\b(?:neurology(?:\s+consult)?)\b", "Neurology Consult"),
    (r"\b(?:infectious\s+disease(?:s)?(?:\s+consult)?|id\s+consult)\b", "Infectious Disease Consult"),
    (r"\b(?:surgery(?:\s+consult)?|surgical\s+consult)\b", "Surgery Consult"),
    (r"\b(?:vascular(?:\s+surgery)?(?:\s+consult)?)\b", "Vascular Surgery Consult"),
    (r"\b(?:palliative\s+care(?:\s+consult)?)\b", "Palliative Care Consult"),
    (r"\b(?:social\s+work(?:\s+consult)?|sw\s+consult)\b", "Social Work Consult"),
    (r"\b(?:physical\s+therapy|pt(?:\s+consult)?)\b", "Physical Therapy"),
    (r"\b(?:occupational\s+therapy|ot(?:\s+consult)?)\b", "Occupational Therapy"),
    (r"\b(?:speech\s+(?:language\s+)?therapy|slp|st)\b", "Speech Therapy"),
    (r"\b(?:nutrition(?:\s+consult)?|dietitian(?:\s+consult)?|rd\s+consult)\b", "Nutrition Consult"),
    (r"\b(?:case\s+management|cm\s+consult)\b", "Case Management"),
    (r"\b(?:wound\s+care(?:\s+consult)?)\b", "Wound Care Consult"),
    # Resuscitation and critical care
    (r"\b(?:resuscitation|resuscitate(?:d)?|fluid\s+resuscitation|volume\s+resuscitation)\b", "Resuscitation"),
    (r"\b(?:icu|intensive\s+care(?:\s+unit)?|micu|sicu|ccu|cvicu)\b", "ICU Admission"),
    (r"\b(?:stepdown|step[\s-]?down(?:\s+unit)?|progressive\s+care(?:\s+unit)?|pcu)\b", "Stepdown Unit"),
    (r"\b(?:large[\s-]?bore\s+(?:iv|peripheral|access)|(?:2|two)\s+large[\s-]?bore\s+(?:ivs?|access))\b", "Large Bore IV Access"),
    (r"\b(?:peripheral\s+iv|piv)\b", "Peripheral IV"),
    # Discharge/disposition
    (r"\b(?:admit(?:ted)?|admission)\b", "Admission"),
    (r"\b(?:discharge(?:d)?)\b", "Discharge"),
    (r"\b(?:transfer(?:red)?)\b", "Transfer"),
]


# ============================================================================
# Vital sign patterns
# ============================================================================

VITAL_SIGN_PATTERNS = [
    # Blood pressure
    (
        r"(?:blood\s+pressure|bp)\s*[:\s]*(\d{2,3})\s*/\s*(\d{2,3})\s*(?:mm\s*hg)?",
        "blood_pressure",
    ),
    # Heart rate
    (
        r"(?:heart\s+rate|hr|pulse)\s*[:\s]*(\d{2,3})\s*(?:bpm|beats?\s*(?:per\s*)?(?:min(?:ute)?)?)?",
        "heart_rate",
    ),
    # Temperature
    (
        r"(?:temperature|temp)\s*[:\s]*([\d.]+)\s*(?:\u00b0?\s*)?([FCfc])?",
        "temperature",
    ),
    # Respiratory rate
    (
        r"(?:respiratory\s+rate|resp(?:iratory)?\s+rate|rr|respirations?)\s*[:\s]*(\d{1,2})\s*(?:/\s*min)?",
        "respiratory_rate",
    ),
    # Oxygen saturation
    (
        r"(?:spo2|o2\s*sat(?:uration)?|oxygen\s+saturation|sat)\s*[:\s]*(\d{2,3})\s*%?",
        "oxygen_saturation",
    ),
    # Weight
    (
        r"(?:weight|wt)\s*[:\s]*([\d.]+)\s*(kg|lbs?|pounds?|kilograms?)?",
        "weight",
    ),
    # Height
    (
        r"(?:height|ht)\s*[:\s]*(?:(\d+)\s*[\'\']\s*(\d+)\s*[\"\"]?|([\d.]+)\s*(?:cm|in(?:ches)?|m(?:eters?)?)?)",
        "height",
    ),
    # BMI
    (
        r"(?:bmi|body\s+mass\s+index)\s*[:\s]*([\d.]+)",
        "bmi",
    ),
]


# ============================================================================
# Lab result patterns (partial - see original file for complete list)
# ============================================================================

LAB_RESULT_PATTERNS = [
    # CBC
    (r"\b(?:wbc|white\s+blood\s+cell(?:s)?(?:\s+count)?)\s*:?\s*([\d.]+)\s*(k/ul|k/\u00b5l|x10\^?9/l|\u00d710\^?9/l)?", "wbc", "K/uL", "4.5-11.0"),
    (r"\b(?:hemoglobin|hgb|hb)\s*:?\s*([\d.]+)\s*(g/dl|g/l)?", "hemoglobin", "g/dL", "12-17"),
    (r"\b(?:hematocrit|hct)\s*:?\s*([\d.]+)\s*%?", "hematocrit", "%", "36-48"),
    (r"\b(?:platelet(?:s)?|plt)\s*:?\s*([\d.]+)\s*(k/ul|k/\u00b5l|x10\^?9/l)?", "platelets", "K/uL", "150-400"),
    # Metabolic panel
    (r"\b(?:glucose|blood\s+sugar|bs|fbs|fasting\s+glucose)\s*:?\s*([\d.]+)\s*(mg/dl|mmol/l)?", "glucose", "mg/dL", "70-100"),
    (r"\b(?:sodium|na)\s*[:\-=]?\s*([\d.]+)\s*(meq/l|mmol/l)?", "sodium", "mEq/L", "136-145"),
    (r"\b(?:potassium|k)\s*[:\-=]?\s*([\d.]+)\s*(meq/l|mmol/l)?", "potassium", "mEq/L", "3.5-5.0"),
    (r"\b(?:chloride|cl)\s*[:\-=]?\s*([\d.]+)\s*(meq/l|mmol/l)?", "chloride", "mEq/L", "98-106"),
    (r"\b(?:co2|bicarbonate|bicarb|hco3)\s*[:\-=]?\s*([\d.]+)\s*(meq/l|mmol/l)?", "co2", "mEq/L", "22-29"),
    (r"\b(?:bun|blood\s+urea\s+nitrogen)\s*[:\-=]?\s*([\d.]+)\s*(mg/dl)?", "bun", "mg/dL", "7-20"),
    (r"\b(?:creatinine|cr)\s*[:\-=]?\s*([\d.]+)\s*(mg/dl)?", "creatinine", "mg/dL", "0.7-1.3"),
    (r"\b(?:egfr|gfr|estimated\s+gfr)\s*:?\s*([\d.]+)\s*(ml/min)?", "egfr", "mL/min", ">60"),
    # Liver function
    (r"\b(?:ast|sgot|aspartate\s+(?:amino)?transaminase)\s*:?\s*([\d.]+)\s*(u/l|iu/l)?", "ast", "U/L", "10-40"),
    (r"\b(?:alt|sgpt|alanine\s+(?:amino)?transaminase)\s*:?\s*([\d.]+)\s*(u/l|iu/l)?", "alt", "U/L", "7-56"),
    # Cardiac markers
    (r"\b(?:troponin(?:\s+[it])?|tn[it])\s*:?\s*([\d.]+)\s*(ng/ml|ng/l)?", "troponin", "ng/mL", "<0.04"),
    (r"\b(?:bnp|b[\s-]?type\s+natriuretic\s+peptide)\s*:?\s*([\d.]+)\s*(pg/ml)?", "bnp", "pg/mL", "<100"),
    # Coagulation
    (r"\b(?:inr|international\s+normalized\s+ratio)\s*:?\s*([\d.]+)", "inr", "", "0.9-1.1"),
    (r"\b(?:pt|prothrombin\s+time)\s*:?\s*([\d.]+)\s*(sec(?:onds)?)?", "pt", "sec", "11-13.5"),
    # Inflammatory markers
    (r"\b(?:crp|c[\s-]?reactive\s+protein)\s*:?\s*([\d.]+)\s*(mg/l|mg/dl)?", "crp", "mg/L", "<10"),
    (r"\b(?:lactate|lactic\s+acid)\s*:?\s*([\d.]+)\s*(mmol/l|mg/dl)?", "lactate", "mmol/L", "<2.0"),
    # Diabetes
    (r"\b(?:hba1c|hemoglobin\s+a1c|a1c|glycated\s+hemoglobin)\s*:?\s*([\d.]+)\s*%?", "hba1c", "%", "<5.7"),
]


# ============================================================================
# Allergy patterns
# ============================================================================

# Allergy patterns: (pattern, normalized_name, allergen_category)
ALLERGY_PATTERNS = [
    # No Known Allergies variants
    (r"\b(?:nkda|no\s+known\s+drug\s+allergies?)\b", "No Known Drug Allergies", "none"),
    (r"\b(?:nka|no\s+known\s+allergies?)\b", "No Known Allergies", "none"),
    (r"\b(?:nkfa|no\s+known\s+food\s+allergies?)\b", "No Known Food Allergies", "none"),
    # Drug allergies - Antibiotics
    (r"\b(?:penicillin|pcn)\s*(?:allergy|allergic)?\b", "Penicillin", "drug"),
    (r"\b(?:allergic\s+to\s+)?(?:penicillin|pcn)\b", "Penicillin", "drug"),
    (r"\b(?:amoxicillin|amox)\s*(?:allergy|allergic)?\b", "Amoxicillin", "drug"),
    (r"\b(?:allergic\s+to\s+)?(?:amoxicillin|amox)\b", "Amoxicillin", "drug"),
    (r"\b(?:ampicillin)\s*(?:allergy|allergic)?\b", "Ampicillin", "drug"),
    (r"\b(?:sulfa|sulfonamide(?:s)?|sulfon?amide(?:s)?|bactrim|septra|tmp[\s-]?smx)\s*(?:allergy|allergic)?\b", "Sulfonamides", "drug"),
    (r"\b(?:allergic\s+to\s+)?(?:sulfa|sulfonamide(?:s)?|bactrim|septra)\b", "Sulfonamides", "drug"),
    (r"\b(?:cephalosporin(?:s)?|cefazolin|ancef|keflex|cephalexin|ceftriaxone|rocephin)\s*(?:allergy|allergic)?\b", "Cephalosporins", "drug"),
    (r"\b(?:fluoroquinolone(?:s)?|cipro(?:floxacin)?|levaquin|levofloxacin|moxifloxacin|avelox)\s*(?:allergy|allergic)?\b", "Fluoroquinolones", "drug"),
    (r"\b(?:macrolide(?:s)?|azithromycin|z[\s-]?pack|zithromax|erythromycin|clarithromycin|biaxin)\s*(?:allergy|allergic)?\b", "Macrolides", "drug"),
    (r"\b(?:tetracycline(?:s)?|doxycycline|minocycline)\s*(?:allergy|allergic)?\b", "Tetracyclines", "drug"),
    (r"\b(?:vancomycin|vanco)\s*(?:allergy|allergic)?\b", "Vancomycin", "drug"),
    (r"\b(?:clindamycin|cleocin)\s*(?:allergy|allergic)?\b", "Clindamycin", "drug"),
    (r"\b(?:metronidazole|flagyl)\s*(?:allergy|allergic)?\b", "Metronidazole", "drug"),
    (r"\b(?:nitrofurantoin|macrobid)\s*(?:allergy|allergic)?\b", "Nitrofurantoin", "drug"),
    # Drug allergies - Pain medications
    (r"\b(?:aspirin|asa)\s*(?:allergy|allergic)?\b", "Aspirin", "drug"),
    (r"\b(?:allergic\s+to\s+)?(?:aspirin|asa)\b", "Aspirin", "drug"),
    (r"\b(?:nsaid(?:s)?|ibuprofen|advil|motrin|naproxen|aleve|celebrex|celecoxib)\s*(?:allergy|allergic)?\b", "NSAIDs", "drug"),
    (r"\b(?:allergic\s+to\s+)?(?:nsaid(?:s)?|ibuprofen|naproxen)\b", "NSAIDs", "drug"),
    (r"\b(?:codeine)\s*(?:allergy|allergic)?\b", "Codeine", "drug"),
    (r"\b(?:morphine)\s*(?:allergy|allergic)?\b", "Morphine", "drug"),
    (r"\b(?:hydrocodone|vicodin|norco)\s*(?:allergy|allergic)?\b", "Hydrocodone", "drug"),
    (r"\b(?:oxycodone|percocet|oxycontin)\s*(?:allergy|allergic)?\b", "Oxycodone", "drug"),
    (r"\b(?:tramadol|ultram)\s*(?:allergy|allergic)?\b", "Tramadol", "drug"),
    (r"\b(?:fentanyl)\s*(?:allergy|allergic)?\b", "Fentanyl", "drug"),
    (r"\b(?:meperidine|demerol)\s*(?:allergy|allergic)?\b", "Meperidine", "drug"),
    # Drug allergies - Cardiovascular
    (r"\b(?:ace[\s-]?inhibitor(?:s)?|lisinopril|enalapril|ramipril|captopril)\s*(?:allergy|allergic)?\b", "ACE Inhibitors", "drug"),
    (r"\b(?:beta[\s-]?blocker(?:s)?|metoprolol|atenolol|propranolol|carvedilol)\s*(?:allergy|allergic)?\b", "Beta Blockers", "drug"),
    (r"\b(?:statin(?:s)?|atorvastatin|lipitor|simvastatin|zocor|rosuvastatin|crestor|pravastatin)\s*(?:allergy|allergic)?\b", "Statins", "drug"),
    # Drug allergies - Other
    (r"\b(?:heparin)\s*(?:allergy|allergic)?\b", "Heparin", "drug"),
    (r"\b(?:warfarin|coumadin)\s*(?:allergy|allergic)?\b", "Warfarin", "drug"),
    (r"\b(?:metformin|glucophage)\s*(?:allergy|allergic)?\b", "Metformin", "drug"),
    (r"\b(?:gabapentin|neurontin)\s*(?:allergy|allergic)?\b", "Gabapentin", "drug"),
    (r"\b(?:pregabalin|lyrica)\s*(?:allergy|allergic)?\b", "Pregabalin", "drug"),
    (r"\b(?:phenytoin|dilantin)\s*(?:allergy|allergic)?\b", "Phenytoin", "drug"),
    (r"\b(?:carbamazepine|tegretol)\s*(?:allergy|allergic)?\b", "Carbamazepine", "drug"),
    (r"\b(?:lamotrigine|lamictal)\s*(?:allergy|allergic)?\b", "Lamotrigine", "drug"),
    (r"\b(?:allopurinol|zyloprim)\s*(?:allergy|allergic)?\b", "Allopurinol", "drug"),
    # Food allergies
    (r"\b(?:peanut(?:s)?)\s*(?:allergy|allergic)?\b", "Peanuts", "food"),
    (r"\b(?:allergic\s+to\s+)?(?:peanut(?:s)?)\b", "Peanuts", "food"),
    (r"\b(?:tree\s+nut(?:s)?|almond(?:s)?|walnut(?:s)?|cashew(?:s)?|pistachio(?:s)?|hazelnut(?:s)?|pecan(?:s)?)\s*(?:allergy|allergic)?\b", "Tree Nuts", "food"),
    (r"\b(?:shellfish|shrimp|lobster|crab|scallop(?:s)?|clam(?:s)?|mussel(?:s)?|oyster(?:s)?)\s*(?:allergy|allergic)?\b", "Shellfish", "food"),
    (r"\b(?:allergic\s+to\s+)?(?:shellfish|shrimp|lobster|crab)\b", "Shellfish", "food"),
    (r"\b(?:fish)\s*(?:allergy|allergic)?\b", "Fish", "food"),
    (r"\b(?:egg(?:s)?)\s*(?:allergy|allergic)?\b", "Eggs", "food"),
    (r"\b(?:allergic\s+to\s+)?(?:egg(?:s)?)\b", "Eggs", "food"),
    (r"\b(?:milk|dairy|lactose)\s*(?:allergy|allergic|intoleran(?:t|ce))?\b", "Dairy/Milk", "food"),
    (r"\b(?:wheat|gluten)\s*(?:allergy|allergic|intoleran(?:t|ce)|sensitiv(?:e|ity))?\b", "Wheat/Gluten", "food"),
    (r"\b(?:soy(?:bean)?(?:s)?)\s*(?:allergy|allergic)?\b", "Soy", "food"),
    (r"\b(?:sesame)\s*(?:allergy|allergic)?\b", "Sesame", "food"),
    # Environmental allergies
    (r"\b(?:latex)\s*(?:allergy|allergic)?\b", "Latex", "environmental"),
    (r"\b(?:allergic\s+to\s+)?(?:latex)\b", "Latex", "environmental"),
    (r"\b(?:contrast(?:\s+dye)?|iodine(?:d)?\s+contrast|iodinated\s+contrast|iv\s+contrast)\s*(?:allergy|allergic)?\b", "Contrast Dye", "environmental"),
    (r"\b(?:allergic\s+to\s+)?(?:contrast(?:\s+dye)?|iodine\s+contrast)\b", "Contrast Dye", "environmental"),
    (r"\b(?:iodine)\s*(?:allergy|allergic)?\b", "Iodine", "environmental"),
    (r"\b(?:adhesive(?:s)?|tape|bandage(?:s)?)\s*(?:allergy|allergic)?\b", "Adhesives", "environmental"),
    (r"\b(?:bee(?:\s+sting)?|wasp(?:\s+sting)?|insect(?:\s+sting)?|hymenoptera)\s*(?:allergy|allergic)?\b", "Insect Stings", "environmental"),
    (r"\b(?:pollen|hay\s+fever|seasonal\s+allerg(?:y|ies))\b", "Pollen", "environmental"),
    (r"\b(?:dust(?:\s+mite)?(?:s)?)\s*(?:allergy|allergic)?\b", "Dust Mites", "environmental"),
    (r"\b(?:pet\s+dander|cat(?:s)?|dog(?:s)?)\s*(?:allergy|allergic)?\b", "Pet Dander", "environmental"),
    (r"\b(?:mold|mould)\s*(?:allergy|allergic)?\b", "Mold", "environmental"),
    (r"\b(?:nickel)\s*(?:allergy|allergic)?\b", "Nickel", "environmental"),
]

# Reaction type patterns - used to capture reaction severity/type
ALLERGY_REACTION_PATTERNS = [
    (r"\b(?:anaphylaxis|anaphylactic(?:\s+(?:shock|reaction))?)\b", "anaphylaxis", "severe"),
    (r"\b(?:rash|skin\s+rash|maculopapular\s+rash)\b", "rash", "moderate"),
    (r"\b(?:hives|urticaria)\b", "hives", "moderate"),
    (r"\b(?:angioedema|swelling|facial\s+swelling|tongue\s+swelling|lip\s+swelling)\b", "angioedema", "severe"),
    (r"\b(?:shortness\s+of\s+breath|sob|dyspnea|difficulty\s+breathing|throat\s+(?:swelling|tightness|closing))\b", "respiratory", "severe"),
    (r"\b(?:itching|pruritus|itchy)\b", "itching", "mild"),
    (r"\b(?:nausea|vomiting|gi\s+upset|stomach\s+upset|diarrhea)\b", "gi_upset", "mild"),
    (r"\b(?:stevens[\s-]?johnson(?:\s+syndrome)?|sjs|toxic\s+epidermal\s+necrolysis|ten)\b", "sjs_ten", "severe"),
    (r"\b(?:drug\s+reaction|adverse\s+reaction|hypersensitivity)\b", "drug_reaction", "moderate"),
]


# ============================================================================
# Anatomical location patterns
# ============================================================================

ANATOMICAL_PATTERNS = [
    # Lateralized body parts
    (r"\b(left|right|bilateral)\s+(arm|leg|hand|foot|eye|ear|lung|kidney|breast|shoulder|hip|knee|ankle|wrist|elbow)\b", None),
    # Body regions with modifiers
    (r"\b(upper|lower|mid)\s+(extremity|extremities|lobe|quadrant|back|abdomen|chest|leg|arm)\b", None),
    (r"\b(anterior|posterior|lateral|medial|proximal|distal|dorsal|ventral|cranial|caudal)\s+\w+\b", None),
    # Major body regions
    (r"\b(head|neck|chest|thorax|abdomen|pelvis|back|spine|trunk|groin|axilla|flank)\b", None),
    # Major organs
    (r"\b(heart|lungs?|liver|kidneys?|brain|stomach|spleen|pancreas|bladder|uterus|prostate|thyroid|adrenal(?:s)?)\b", None),
    (r"\b(gallbladder|appendix|ovary|ovaries|testicle|testes|testis)\b", None),
    # GI tract
    (r"\b(esophagus|duodenum|jejunum|ileum|cecum|colon|rectum|anus|sigmoid)\b", None),
    (r"\b(small\s+bowel|small\s+intestine|large\s+bowel|large\s+intestine)\b", None),
    (r"\b(ascending|descending|transverse|sigmoid)\s+colon\b", None),
    # Cardiovascular structures
    (r"\b(aorta|vena\s+cava|pulmonary\s+artery|pulmonary\s+vein|coronary\s+artery|carotid(?:\s+artery)?)\b", None),
    (r"\b(femoral|radial|brachial|subclavian|iliac|mesenteric|renal)\s+(artery|vein)\b", None),
    (r"\b(left|right)\s+(atrium|ventricle)\b", None),
    (r"\b(mitral|aortic|tricuspid|pulmonic)\s+valve\b", None),
    (r"\b(lad|lcx|rca|lca|lmca)\b", None),
    # Musculoskeletal
    (r"\b(shoulder|elbow|wrist|hip|knee|ankle|mcp|pip|dip|mtp|si|tmj|ac)\s*(joint)?\b", None),
    (r"\b(c\d|t\d|l\d|s\d)(?:-[ctls]\d)?\b", None),
    (r"\b(cervical|thoracic|lumbar|sacral|coccygeal)\s*(spine|vertebra(?:e)?)\b", None),
    # Bones
    (r"\b(femur|tibia|fibula|humerus|radius|ulna|clavicle|scapula|pelvis|patella)\b", None),
    (r"\b(rib(?:s)?|sternum|vertebra(?:e)?|skull|mandible|maxilla)\b", None),
    # Neurological
    (r"\b(frontal|parietal|temporal|occipital)\s*(lobe)?\b", None),
    (r"\b(cerebellum|brainstem|thalamus|hypothalamus|hippocampus|basal\s+ganglia)\b", None),
    (r"\b(spinal\s+cord|sciatic\s+nerve|brachial\s+plexus|cauda\s+equina)\b", None),
    # Respiratory
    (r"\b(trachea|bronchus|bronchi|bronchioles?|alveoli|pleura)\b", None),
    (r"\b(pharynx|larynx|nasopharynx|oropharynx)\b", None),
    # Lung lobes
    (r"\b(lul|rul|lll|rll|rml)\b", None),
    (r"\b(left|right)\s+(upper|lower|middle)\s+lobe\b", None),
    # Abdominal quadrants
    (r"\b(ruq|luq|rlq|llq|epigastric|periumbilical|suprapubic)\b", None),
    (r"\b(right|left)\s+(upper|lower)\s+quadrant\b", None),
]


# ============================================================================
# Temporal expression patterns
# ============================================================================

TEMPORAL_PATTERNS = [
    (r"\b(\d+)\s*(days?|weeks?|months?|years?)\s+(ago|prior)\b", "relative_past"),
    (r"\b(since|for)\s+(\d+)\s*(days?|weeks?|months?|years?)\b", "duration"),
    (r"\b(yesterday|today|tomorrow)\b", "relative_day"),
    (r"\b(morning|afternoon|evening|night|overnight)\b", "time_of_day"),
    (r"\b(daily|weekly|monthly|yearly|annually)\b", "frequency"),
    (r"\b(chronic|acute|subacute|intermittent|persistent)\b", "temporal_quality"),
    (r"\b(onset|started|began|developed)\s+(\d+)\s*(days?|weeks?|months?|years?)\s+ago\b", "onset"),
    (r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b", "date"),
]


# ============================================================================
# Social History Patterns
# ============================================================================

# Social history patterns for smoking, alcohol, and drug use
# NOTE: More specific patterns MUST come FIRST to avoid shorter patterns matching first
SOCIAL_HISTORY_PATTERNS: dict[str, list[tuple[str, str, AssertionStatus]]] = {
    "smoking": [
        # Former smoker (MUST come before generic smoker patterns)
        (r"\bformer\s+smok(?:er|ing)\b", "former_smoker", AssertionStatus.HISTORICAL),
        (r"\bex[\s-]?smok(?:er|ing)\b", "former_smoker", AssertionStatus.HISTORICAL),
        (r"\bprevious(?:ly)?\s+smok(?:er|ed|ing)\b", "former_smoker", AssertionStatus.HISTORICAL),
        (r"\bused\s+to\s+smoke\b", "former_smoker", AssertionStatus.HISTORICAL),
        (r"\bsmoked\s+(?:in\s+the\s+)?past\b", "former_smoker", AssertionStatus.HISTORICAL),
        (r"\bhistory\s+of\s+(?:tobacco|smoking|cigarette)\s+(?:use|abuse)\b", "former_smoker", AssertionStatus.HISTORICAL),
        (r"\bquit\s+(?:smoking|tobacco|cigarettes?)\b", "former_smoker", AssertionStatus.HISTORICAL),
        (r"\b(?:stopped|discontinued|ceased)\s+(?:smoking|tobacco|cigarettes?)\b", "former_smoker", AssertionStatus.HISTORICAL),
        # Never smoker (MUST come before generic smoker patterns)
        (r"\bnever\s+smok(?:er|ed|ing)\b", "never_smoker", AssertionStatus.ABSENT),
        (r"\bnon[\s-]?smok(?:er|ing)\b", "never_smoker", AssertionStatus.ABSENT),
        (r"\bno\s+(?:tobacco|smoking|cigarette)\s*(?:use|history)?\b", "never_smoker", AssertionStatus.ABSENT),
        (r"\bdeni(?:es|ed)\s+(?:tobacco|smoking|cigarettes?)\b", "never_smoker", AssertionStatus.ABSENT),
        (r"\blifetime\s+non[\s-]?smok(?:er|ing)\b", "never_smoker", AssertionStatus.ABSENT),
        # Current smoker (explicit modifier patterns)
        (r"\bcurrent(?:ly)?\s+smok(?:er|es|ing)\b", "current_smoker", AssertionStatus.PRESENT),
        (r"\bactive(?:ly)?\s+smok(?:er|es|ing)\b", "current_smoker", AssertionStatus.PRESENT),
        (r"\b(?:tobacco|cigarette)(?:\s+use(?:r)?)\b", "current_smoker", AssertionStatus.PRESENT),
        (r"\bppd\b", "current_smoker", AssertionStatus.PRESENT),  # packs per day
        (r"\b(?:\d+)\s*(?:pack(?:s)?|ppd)\s*(?:per\s+)?(?:day|daily)\b", "current_smoker", AssertionStatus.PRESENT),
        # Generic smoker (last resort - when no modifier present)
        (r"\bsmok(?:er|es|ing)\b", "current_smoker", AssertionStatus.PRESENT),
        # Pack-years (smoking quantification)
        (r"\b(\d+(?:\.\d+)?)\s*pack[\s-]?years?\b", "pack_years", AssertionStatus.PRESENT),
        # Quit duration
        (r"\bquit\s+(\d+)\s+(years?|months?|weeks?|days?)\s+ago\b", "quit_duration", AssertionStatus.HISTORICAL),
        (r"\b(?:stopped|discontinued|ceased)\s+(\d+)\s+(years?|months?|weeks?|days?)\s+ago\b", "quit_duration", AssertionStatus.HISTORICAL),
        (r"\b(?:tobacco|smoke)[\s-]?free\s+(?:for\s+)?(\d+)\s+(years?|months?)\b", "quit_duration", AssertionStatus.HISTORICAL),
    ],
    "alcohol": [
        # Current use
        (r"\b(?:social(?:ly)?)\s*drink(?:er|s|ing)?\b", "social_drinker", AssertionStatus.PRESENT),
        (r"\b(?:occasional(?:ly)?)\s*drink(?:er|s|ing)?\b", "occasional_drinker", AssertionStatus.PRESENT),
        (r"\bdrinks?\s+(?:alcohol|socially|occasionally)\b", "current_drinker", AssertionStatus.PRESENT),
        (r"\balcohol\s+use\b", "current_drinker", AssertionStatus.PRESENT),
        (r"\bcurrent(?:ly)?\s+drink(?:er|s|ing)\b", "current_drinker", AssertionStatus.PRESENT),
        (r"\bmoderate\s+(?:alcohol\s+)?(?:use|intake|consumption|drinker)\b", "moderate_drinker", AssertionStatus.PRESENT),
        (r"\brare(?:ly)?\s+(?:drinks?|alcohol)\b", "rare_drinker", AssertionStatus.PRESENT),
        # Heavy use
        (r"\bheavy\s+drink(?:er|ing)\b", "heavy_drinker", AssertionStatus.PRESENT),
        (r"\balcohol(?:ic|ism)\b", "alcoholism", AssertionStatus.PRESENT),
        (r"\betoh\s+(?:abuse|dependence)\b", "alcohol_abuse", AssertionStatus.PRESENT),
        (r"\balcohol\s+(?:abuse|dependence|use\s+disorder|addiction)\b", "alcohol_abuse", AssertionStatus.PRESENT),
        (r"\baud\b", "alcohol_use_disorder", AssertionStatus.PRESENT),  # Alcohol Use Disorder
        (r"\bbinge\s+drink(?:er|ing)\b", "binge_drinker", AssertionStatus.PRESENT),
        (r"\bexcessive\s+(?:alcohol\s+)?(?:use|intake|consumption|drinking)\b", "excessive_drinker", AssertionStatus.PRESENT),
        # Denies alcohol
        (r"\bdeni(?:es|ed)\s+(?:alcohol|etoh|drinking)\b", "denies_alcohol", AssertionStatus.ABSENT),
        (r"\bno\s+alcohol(?:\s+use)?\b", "denies_alcohol", AssertionStatus.ABSENT),
        (r"\bnon[\s-]?drink(?:er|ing)\b", "denies_alcohol", AssertionStatus.ABSENT),
        (r"\bdoes\s+not\s+drink\b", "denies_alcohol", AssertionStatus.ABSENT),
        (r"\babstains?\s+(?:from\s+)?alcohol\b", "abstains_alcohol", AssertionStatus.ABSENT),
        (r"\bteetotal(?:er|ing)?\b", "abstains_alcohol", AssertionStatus.ABSENT),
        # Former drinker
        (r"\bformer\s+(?:alcohol(?:ic)?|drinker|heavy\s+drinker)\b", "former_drinker", AssertionStatus.HISTORICAL),
        (r"\bquit\s+(?:drinking|alcohol)\b", "former_drinker", AssertionStatus.HISTORICAL),
        (r"\bsober\s+(?:for\s+)?(\d+)\s+(years?|months?)\b", "former_drinker", AssertionStatus.HISTORICAL),
        (r"\bin\s+recovery\b", "former_drinker", AssertionStatus.HISTORICAL),
        (r"\bhistory\s+of\s+(?:alcohol(?:ism)?|etoh)\s*(?:abuse|dependence)?\b", "former_drinker", AssertionStatus.HISTORICAL),
        # Quantity patterns
        (r"\b(\d+(?:-\d+)?)\s*drinks?\s*per\s*(day|week|month|night|occasion)\b", "alcohol_quantity", AssertionStatus.PRESENT),
        (r"\b(\d+(?:-\d+)?)\s*(?:beers?|glasses?|drinks?)\s*(?:per\s*)?(daily|weekly|nightly)\b", "alcohol_quantity", AssertionStatus.PRESENT),
        (r"\b(\d+(?:-\d+)?)\s*drinks?\s*/\s*(day|week|wk|d|w)\b", "alcohol_quantity", AssertionStatus.PRESENT),
    ],
    "drugs": [
        # Denies (MUST come first to catch "denies illicit drug use" before "illicit drug use")
        (r"\bdeni(?:es|ed)\s+(?:illicit\s+)?(?:drugs?|substances?)(?:\s+use)?\b", "denies_drugs", AssertionStatus.ABSENT),
        (r"\bdeni(?:es|ed)\s+(?:recreational\s+)?(?:drugs?|substances?)(?:\s+use)?\b", "denies_drugs", AssertionStatus.ABSENT),
        (r"\bdeni(?:es|ed)\s+(?:iv|injection)\s+(?:drugs?|substances?)(?:\s+use)?\b", "denies_drugs", AssertionStatus.ABSENT),
        (r"\bno\s+(?:illicit|recreational)?\s*(?:drugs?|substances?)\s+use\b", "denies_drugs", AssertionStatus.ABSENT),
        (r"\bdeni(?:es|ed)\s+(?:marijuana|cannabis|cocaine|heroin|meth(?:amphetamine)?|opioids?)\b", "denies_drugs", AssertionStatus.ABSENT),
        (r"\bno\s+(?:marijuana|cannabis|cocaine|heroin|meth(?:amphetamine)?|opioids?)\b", "denies_drugs", AssertionStatus.ABSENT),
        (r"\bdoes\s+not\s+use\s+(?:drugs?|substances?)\b", "denies_drugs", AssertionStatus.ABSENT),
        # History (MUST come before current use patterns)
        (r"\bhistory\s+of\s+(?:substance|drug)\s+(?:abuse|use|dependence)\b", "history_drug_use", AssertionStatus.HISTORICAL),
        (r"\bhistory\s+of\s+iv\s+drug\s+use\b", "history_iv_drug_use", AssertionStatus.HISTORICAL),
        (r"\bformer\s+(?:iv\s+)?drug\s+use(?:r)?\b", "former_drug_use", AssertionStatus.HISTORICAL),
        (r"\bpast\s+(?:illicit|recreational)?\s*(?:drug|substance)\s+use\b", "former_drug_use", AssertionStatus.HISTORICAL),
        (r"\bprevious(?:ly)?\s+(?:used|using)\s+(?:drugs?|substances?)\b", "former_drug_use", AssertionStatus.HISTORICAL),
        (r"\b(?:clean|sober)\s+(?:from\s+drugs?\s+)?(?:for\s+)?(\d+)\s+(years?|months?)\b", "drug_free_duration", AssertionStatus.HISTORICAL),
        (r"\bin\s+(?:drug\s+)?recovery\b", "in_recovery", AssertionStatus.HISTORICAL),
        (r"\brecovering\s+addict\b", "recovering_addict", AssertionStatus.HISTORICAL),
        (r"\bsubstance\s+use\s+disorder\s+(?:in\s+)?remission\b", "sud_remission", AssertionStatus.HISTORICAL),
        # Current use
        (r"\bmarijuana\s+use\b", "marijuana_use", AssertionStatus.PRESENT),
        (r"\bcannabis\s+use\b", "cannabis_use", AssertionStatus.PRESENT),
        (r"\bthc\s+(?:use|positive)\b", "thc_use", AssertionStatus.PRESENT),
        (r"\bcocaine\s+use\b", "cocaine_use", AssertionStatus.PRESENT),
        (r"\bopioid\s+use\b", "opioid_use", AssertionStatus.PRESENT),
        (r"\bheroin\s+use\b", "heroin_use", AssertionStatus.PRESENT),
        (r"\bmethamphetamine\s+use\b", "methamphetamine_use", AssertionStatus.PRESENT),
        (r"\bmeth\s+use\b", "methamphetamine_use", AssertionStatus.PRESENT),
        (r"\bamphetamine\s+use\b", "amphetamine_use", AssertionStatus.PRESENT),
        (r"\bbenzo(?:diazepine)?\s+(?:abuse|misuse)\b", "benzodiazepine_abuse", AssertionStatus.PRESENT),
        (r"\billicit\s+(?:drug|substance)\s+use\b", "illicit_drug_use", AssertionStatus.PRESENT),
        (r"\brecreational\s+(?:drug|substance)\s+use\b", "recreational_drug_use", AssertionStatus.PRESENT),
        (r"\bivdu\b", "iv_drug_use", AssertionStatus.PRESENT),  # IV drug use
        (r"\biv\s+drug\s+use(?:r)?\b", "iv_drug_use", AssertionStatus.PRESENT),
        (r"\bintravenous\s+drug\s+use(?:r)?\b", "iv_drug_use", AssertionStatus.PRESENT),
        (r"\binjection\s+drug\s+use(?:r)?\b", "iv_drug_use", AssertionStatus.PRESENT),
        (r"\b(?:uses?|using)\s+(?:marijuana|cannabis|cocaine|heroin|meth(?:amphetamine)?|opioids?)\b", "drug_use", AssertionStatus.PRESENT),
    ],
}


# ============================================================================
# Extractor Mixin Class
# ============================================================================


class ExtractorMixin:
    """Mixin providing entity extraction methods."""

    # These will be set by the main class
    _clinical_abbreviations: dict
    _loinc_codes: dict
    _abbreviations_loaded: bool

    def _load_clinical_abbreviations(self) -> None:
        """Load clinical abbreviations from fixture file."""
        if self._abbreviations_loaded:
            return

        # Load clinical abbreviations with OMOP concept IDs
        if CLINICAL_ABBREVIATIONS_FILE.exists():
            try:
                with open(CLINICAL_ABBREVIATIONS_FILE) as f:
                    data = json.load(f)
                    for term in data.get("terms", []):
                        name = term.get("name", "").lower()
                        self._clinical_abbreviations[name] = term
                        # Also index by synonyms
                        for syn in term.get("synonyms", []):
                            self._clinical_abbreviations[syn.lower()] = term
                logger.info(
                    f"Loaded {len(data.get('terms', []))} clinical abbreviations"
                )
            except Exception as e:
                logger.warning(f"Could not load clinical abbreviations: {e}")

        # Load LOINC measurements
        if LOINC_MEASUREMENTS_FILE.exists():
            try:
                with open(LOINC_MEASUREMENTS_FILE) as f:
                    data = json.load(f)
                    for concept in data.get("concepts", []):
                        code = concept.get("concept_code", "")
                        name = concept.get("concept_name", "").lower()
                        self._loinc_codes[name] = concept
                        self._loinc_codes[code] = concept
                        # Also index by synonyms
                        for syn in concept.get("synonyms", []):
                            if isinstance(syn, str):
                                self._loinc_codes[syn.lower()] = concept
                logger.info(f"Loaded {len(data.get('concepts', []))} LOINC codes")
            except Exception as e:
                logger.warning(f"Could not load LOINC measurements: {e}")

        self._abbreviations_loaded = True

    def _extract_diagnoses_and_symptoms(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract diagnosis and symptom entities."""
        entities: list[ExtractedEntity] = []
        text_lower = text.lower()

        # Extract diagnoses
        for pattern, normalized_name in DIAGNOSIS_PATTERNS:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)
                confidence = self._calculate_confidence(
                    match.group(0), normalized_name, section, EntityType.DIAGNOSIS
                )

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.DIAGNOSIS,
                    text=span.text,
                    normalized_text=normalized_name,
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=confidence,
                )
                entities.append(entity)

        # Extract symptoms
        for pattern, normalized_name in SYMPTOM_PATTERNS:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)
                confidence = self._calculate_confidence(
                    match.group(0), normalized_name, section, EntityType.SYMPTOM
                )

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.SYMPTOM,
                    text=span.text,
                    normalized_text=normalized_name,
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=confidence,
                )
                entities.append(entity)

        return entities

    def _extract_medications(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract medication entities with dosage, frequency, and route."""
        entities: list[ExtractedEntity] = []

        for pattern in MEDICATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                drug_name = match.group(1)
                dosage = match.group(2) if match.lastindex >= 2 else None
                frequency = match.group(3) if match.lastindex >= 3 else None

                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                # Higher confidence in Medications section
                confidence = 0.85 if section == ClinicalSection.MEDICATIONS else 0.75

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.MEDICATION,
                    text=span.text,
                    normalized_text=drug_name.title(),
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=confidence,
                    dosage=dosage,
                    frequency=frequency,
                )
                entities.append(entity)

        return entities

    def _extract_procedures(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract procedure entities."""
        entities: list[ExtractedEntity] = []
        text_lower = text.lower()

        for pattern, normalized_name in PROCEDURE_PATTERNS:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                # Higher confidence for PSH section
                confidence = 0.85 if section == ClinicalSection.PAST_SURGICAL_HISTORY else 0.75

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.PROCEDURE,
                    text=span.text,
                    normalized_text=normalized_name,
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=confidence,
                )
                entities.append(entity)

        return entities

    def _extract_vital_signs(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract vital sign entities with values and units."""
        entities: list[ExtractedEntity] = []

        for pattern, vital_name in VITAL_SIGN_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                # Extract value based on vital type
                value = None
                unit = None

                if vital_name == "blood_pressure":
                    value = f"{match.group(1)}/{match.group(2)}"
                    unit = "mmHg"
                elif vital_name == "heart_rate":
                    value = match.group(1)
                    unit = "bpm"
                elif vital_name == "temperature":
                    value = match.group(1)
                    unit = match.group(2).upper() if match.group(2) else "F"
                elif vital_name == "respiratory_rate":
                    value = match.group(1)
                    unit = "/min"
                elif vital_name == "oxygen_saturation":
                    value = match.group(1)
                    unit = "%"
                elif vital_name == "weight":
                    value = match.group(1)
                    unit = match.group(2) if match.lastindex >= 2 and match.group(2) else "kg"
                elif vital_name == "bmi":
                    value = match.group(1)
                    unit = "kg/m2"

                # Higher confidence in Vitals section
                confidence = 0.9 if section == ClinicalSection.VITAL_SIGNS else 0.8

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.VITAL_SIGN,
                    text=span.text,
                    normalized_text=vital_name.replace("_", " ").title(),
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=confidence,
                    value=value,
                    unit=unit,
                )
                entities.append(entity)

        return entities

    def _extract_lab_results(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract lab result entities with values, units, and reference ranges."""
        entities: list[ExtractedEntity] = []

        for pattern, lab_name, default_unit, ref_range in LAB_RESULT_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                value = match.group(1)
                unit = match.group(2) if match.lastindex >= 2 and match.group(2) else default_unit

                # Higher confidence in Labs section
                confidence = 0.9 if section == ClinicalSection.LABS else 0.8

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.LAB_RESULT,
                    text=span.text,
                    normalized_text=lab_name.upper(),
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=confidence,
                    value=value,
                    unit=unit,
                    reference_range=ref_range,
                )
                entities.append(entity)

        return entities

    def _extract_anatomical_locations(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract anatomical location entities with laterality."""
        entities: list[ExtractedEntity] = []

        for pattern, _ in ANATOMICAL_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                # Detect laterality
                laterality = None
                for lat_pattern, lat_value in LATERALITY_PATTERNS:
                    if re.search(lat_pattern, span.text, re.IGNORECASE):
                        laterality = lat_value
                        break

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.ANATOMICAL_LOCATION,
                    text=span.text,
                    normalized_text=span.text.title(),
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=0.75,
                    laterality=laterality,
                )
                entities.append(entity)

        return entities

    def _extract_temporal_expressions(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract temporal expression entities."""
        entities: list[ExtractedEntity] = []

        for pattern, temporal_type in TEMPORAL_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.TEMPORAL,
                    text=span.text,
                    normalized_text=temporal_type,
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=0.85,
                )
                entities.append(entity)

        return entities

    def _extract_allergies(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract allergy entities with reaction type and severity.

        Extracts drug allergies, food allergies, and environmental allergies.
        Also captures reaction types (rash, anaphylaxis, etc.) when mentioned.
        """
        entities: list[ExtractedEntity] = []
        text_lower = text.lower()

        # Track matched spans to avoid duplicates
        matched_spans: set[tuple[int, int]] = set()

        for pattern, normalized_name, allergen_category in ALLERGY_PATTERNS:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                # Skip if this span overlaps with an existing match
                span_key = (match.start(), match.end())
                overlaps = False
                for existing_start, existing_end in matched_spans:
                    if not (match.end() <= existing_start or match.start() >= existing_end):
                        overlaps = True
                        break
                if overlaps:
                    continue

                matched_spans.add(span_key)

                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start():match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                # Higher confidence in Allergies section
                confidence = 0.90 if section == ClinicalSection.ALLERGIES else 0.80

                # Look for reaction type in surrounding context
                # Limit to 30 chars or stop at sentence/phrase boundaries
                context_start = max(0, match.start() - 30)
                context_end = min(len(text_lower), match.end() + 40)

                # Find sentence/phrase boundaries to limit context
                # Stop at period, semicolon, or newline
                before_text = text_lower[context_start:match.start()]
                after_text = text_lower[match.end():context_end]

                # Trim context at phrase boundaries
                for sep in ['. ', '; ', '\n', '|']:
                    if sep in before_text:
                        before_text = before_text.split(sep)[-1]
                    if sep in after_text:
                        after_text = after_text.split(sep)[0]

                context = before_text + text_lower[match.start():match.end()] + after_text

                reaction_type = None
                reaction_severity = None

                # Search for reaction patterns in the context
                # First, check for negation words that might negate reactions
                negation_match = re.search(r'\b(?:no|not|without|denies|denied)\s+', context)

                for reaction_pattern, reaction_name, severity in ALLERGY_REACTION_PATTERNS:
                    reaction_match = re.search(reaction_pattern, context, re.IGNORECASE)
                    if reaction_match:
                        # Check if this reaction is negated (negation word appears before reaction)
                        if negation_match and negation_match.end() <= reaction_match.start():
                            # This reaction is negated, skip it
                            continue
                        reaction_type = reaction_name
                        reaction_severity = severity
                        # Prefer more severe reactions if multiple found
                        if severity == "severe":
                            break

                # For "no known allergies" variants, set assertion to ABSENT
                assertion = AssertionStatus.PRESENT
                if allergen_category == "none":
                    assertion = AssertionStatus.ABSENT

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.ALLERGY,
                    text=span.text,
                    normalized_text=normalized_name,
                    span=span,
                    section=section,
                    assertion=assertion,
                    confidence=confidence,
                    reaction_type=reaction_type,
                    reaction_severity=reaction_severity,
                    allergen_category=allergen_category,
                )
                entities.append(entity)

        return entities

    def _extract_social_history(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract social history entities (smoking, alcohol, drugs).

        Extracts structured information about:
        - Smoking status (current, former, never) with pack-years and quit duration
        - Alcohol use status with quantity
        - Drug use status (current, former, denies)

        Args:
            text: The clinical text to process.
            sections: List of detected clinical sections.

        Returns:
            List of ExtractedEntity objects for social history items.
        """
        entities: list[ExtractedEntity] = []
        text_lower = text.lower()
        matched_spans: set[tuple[int, int]] = set()

        # Process each social history category
        for category, patterns in SOCIAL_HISTORY_PATTERNS.items():
            for pattern, status, default_assertion in patterns:
                for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                    # Check for overlapping spans
                    span_start = match.start()
                    span_end = match.end()
                    overlap = False
                    for existing_start, existing_end in matched_spans:
                        if not (span_end <= existing_start or span_start >= existing_end):
                            overlap = True
                            break

                    if overlap:
                        continue

                    matched_spans.add((span_start, span_end))

                    span = EntitySpan(
                        start=span_start,
                        end=span_end,
                        text=text[span_start:span_end],
                    )
                    section = self._get_section_at_offset(span_start, sections)

                    # Higher confidence in Social History section
                    confidence = 0.90 if section == ClinicalSection.SOCIAL_HISTORY else 0.75

                    # Extract quantity information if present
                    quantity = None
                    if status == "pack_years":
                        # Extract numeric value for pack-years
                        qty_match = re.search(r"(\d+(?:\.\d+)?)", match.group(0))
                        if qty_match:
                            quantity = f"{qty_match.group(1)} pack-years"
                    elif status == "quit_duration" or status == "drug_free_duration":
                        # Extract duration value
                        if match.lastindex and match.lastindex >= 2:
                            quantity = f"{match.group(1)} {match.group(2)} ago"
                    elif status == "alcohol_quantity":
                        # Extract drinks per period
                        if match.lastindex and match.lastindex >= 1:
                            quantity = match.group(0)

                    # Build normalized text based on category and status
                    if category == "smoking":
                        if status == "current_smoker":
                            normalized_text = "Current Smoker"
                        elif status == "former_smoker":
                            normalized_text = "Former Smoker"
                        elif status == "never_smoker":
                            normalized_text = "Never Smoker"
                        elif status == "pack_years":
                            normalized_text = f"Tobacco Use - {quantity}" if quantity else "Tobacco Use"
                        elif status == "quit_duration":
                            normalized_text = f"Former Smoker - Quit {quantity}" if quantity else "Former Smoker"
                        else:
                            normalized_text = f"Tobacco: {status.replace('_', ' ').title()}"
                    elif category == "alcohol":
                        if status in ("social_drinker", "occasional_drinker", "moderate_drinker", "rare_drinker", "current_drinker"):
                            normalized_text = status.replace("_", " ").title()
                        elif status in ("heavy_drinker", "binge_drinker", "excessive_drinker"):
                            normalized_text = status.replace("_", " ").title()
                        elif status in ("alcoholism", "alcohol_abuse", "alcohol_use_disorder"):
                            normalized_text = "Alcohol Use Disorder"
                        elif status in ("denies_alcohol", "abstains_alcohol"):
                            normalized_text = "Denies Alcohol Use"
                        elif status == "former_drinker":
                            normalized_text = "Former Alcohol Use"
                        elif status == "alcohol_quantity":
                            normalized_text = f"Alcohol Use - {quantity}" if quantity else "Alcohol Use"
                        else:
                            normalized_text = f"Alcohol: {status.replace('_', ' ').title()}"
                    else:  # drugs
                        if status == "denies_drugs":
                            normalized_text = "Denies Illicit Drug Use"
                        elif status == "history_drug_use":
                            normalized_text = "History of Substance Use"
                        elif status == "history_iv_drug_use":
                            normalized_text = "History of IV Drug Use"
                        elif status == "former_drug_use":
                            normalized_text = "Former Drug Use"
                        elif status in ("in_recovery", "recovering_addict", "sud_remission"):
                            normalized_text = "Substance Use Disorder - In Recovery"
                        elif status == "drug_free_duration":
                            normalized_text = f"Substance Use - Clean {quantity}" if quantity else "Substance Use - In Recovery"
                        elif status == "iv_drug_use":
                            normalized_text = "IV Drug Use"
                        elif status == "illicit_drug_use":
                            normalized_text = "Illicit Drug Use"
                        elif status == "recreational_drug_use":
                            normalized_text = "Recreational Drug Use"
                        elif "_use" in status:
                            # marijuana_use -> Marijuana Use
                            substance = status.replace("_use", "").replace("_", " ").title()
                            normalized_text = f"{substance} Use"
                        else:
                            normalized_text = f"Substance Use: {status.replace('_', ' ').title()}"

                    entity = ExtractedEntity(
                        id=str(uuid4()),
                        entity_type=EntityType.SOCIAL_HISTORY,
                        text=span.text,
                        normalized_text=normalized_text,
                        span=span,
                        section=section,
                        assertion=default_assertion,
                        confidence=confidence,
                        social_history_category=category,
                        social_history_status=status,
                        quantity=quantity,
                    )
                    entities.append(entity)

        return entities

    def _extract_from_clinical_abbreviations(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract entities using the clinical abbreviations dictionary."""
        self._load_clinical_abbreviations()
        entities: list[ExtractedEntity] = []
        text_lower = text.lower()

        # Build a set of already-matched spans to avoid duplicates
        matched_spans: set[tuple[int, int]] = set()

        # Domain to EntityType mapping
        domain_to_entity_type = {
            "Condition": EntityType.DIAGNOSIS,
            "Observation": EntityType.SYMPTOM,
            "Drug": EntityType.MEDICATION,
            "Procedure": EntityType.PROCEDURE,
            "Measurement": EntityType.LAB_RESULT,
            "Device": EntityType.PROCEDURE,
        }

        # Sort abbreviations by length (longest first)
        sorted_abbrevs = sorted(
            self._clinical_abbreviations.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )

        # Context-dependent abbreviations
        context_exclusions = {
            "ra": (r"(?:spo2|o2\s*sat|saturation|sat).*?(?:on|%)\s*ra\b|\bra\s*(?:room\s*air)", "room air"),
            "pe": (r"\brule\s+out\s+pe\b|\bpe\s+protocol\b|\bpe\s+study\b|\bno\s+pe\b|\bcta\s+pe\b", "pulmonary embolism"),
            "pt": (r"\binr|coag|anticoag|warfarin|pt/inr\b", "prothrombin time"),
        }

        for abbrev_key, term_data in sorted_abbrevs:
            if len(abbrev_key) < 2:
                continue

            pattern = r'\b' + re.escape(abbrev_key) + r'\b'

            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                # Check context exclusions
                if abbrev_key in context_exclusions:
                    exclusion_pattern, _ = context_exclusions[abbrev_key]
                    context_start = max(0, match.start() - 50)
                    context_end = min(len(text_lower), match.end() + 50)
                    context = text_lower[context_start:context_end]
                    if re.search(exclusion_pattern, context, re.IGNORECASE):
                        continue

                span_key = (match.start(), match.end())

                # Check overlap
                overlaps = False
                for existing_start, existing_end in matched_spans:
                    if not (match.end() <= existing_start or match.start() >= existing_end):
                        overlaps = True
                        break

                if overlaps:
                    continue

                matched_spans.add(span_key)

                domain = term_data.get("domain", "Condition")
                entity_type = domain_to_entity_type.get(domain, EntityType.DIAGNOSIS)

                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start():match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                omop_id = term_data.get("omop_concept_id")
                base_confidence = 0.90 if omop_id else 0.80

                # Section boost
                section_boost = 0.0
                if section in (ClinicalSection.ASSESSMENT, ClinicalSection.HPI, ClinicalSection.PAST_MEDICAL_HISTORY):
                    if entity_type == EntityType.DIAGNOSIS:
                        section_boost = 0.05
                elif section == ClinicalSection.MEDICATIONS:
                    if entity_type == EntityType.MEDICATION:
                        section_boost = 0.05
                elif section in (ClinicalSection.LABS, ClinicalSection.VITAL_SIGNS):
                    if entity_type == EntityType.LAB_RESULT:
                        section_boost = 0.05

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=entity_type,
                    text=span.text,
                    normalized_text=term_data.get("name", abbrev_key),
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=min(0.95, base_confidence + section_boost),
                )

                if omop_id:
                    entity.normalized_codes.append(
                        NormalizedCode(
                            code=str(omop_id),
                            display=term_data.get("name", abbrev_key),
                            system=NormalizationVocabulary.SNOMED_CT,
                            confidence=0.95,
                            is_preferred=True,
                        )
                    )

                entities.append(entity)

        return entities
