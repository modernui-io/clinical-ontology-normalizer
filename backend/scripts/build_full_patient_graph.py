#!/usr/bin/env python3
"""
Build a comprehensive knowledge graph from NLP-extracted clinical entities.

This script:
1. Reads clinical notes from a file or generates synthetic ones
2. Extracts entities using the NLP service
3. Persists ALL extracted entities to the knowledge graph
4. Creates relationships between entities

This creates the full longitudinal patient graph that can be used for:
- Graph RAG (retrieval-augmented generation)
- LLM reasoning with provenance
- Clinical decision support

Usage:
    python scripts/build_full_patient_graph.py --patient-id TEST12345
"""

import argparse
import json
import re
import sys
import os
import uuid
from datetime import datetime, UTC
from collections import defaultdict

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import Json


# Sample clinical notes for the test patient (abbreviated versions)
# In production, these would come from EHR or the NLP workbench
SAMPLE_NOTES = [
    """
    HISTORY OF PRESENT ILLNESS:
    64-year-old male with history of HFrEF (EF 25%), atrial fibrillation, CAD s/p CABG,
    CKD stage 4, type 2 diabetes, hypertension, and OSA presents for routine follow-up.

    Patient reports mild dyspnea on exertion, 2-pillow orthopnea. Denies chest pain,
    palpitations, or syncope. Weight stable. Compliant with medications and CPAP.

    MEDICATIONS:
    Carvedilol 25 mg PO BID
    Lisinopril 20 mg PO daily
    Furosemide 40 mg PO BID
    Spironolactone 25 mg PO daily
    Apixaban 5 mg PO BID
    Metformin 500 mg PO BID
    Insulin glargine 20 units subcutaneous at bedtime
    Atorvastatin 80 mg PO at bedtime
    Aspirin 81 mg PO daily
    Ferrous sulfate 325 mg PO daily

    ALLERGIES: Penicillin - rash

    VITAL SIGNS:
    BP 128/78 mmHg, HR 72 bpm, Temp 98.2 F, SpO2 96% on RA, Weight 95 kg

    PHYSICAL EXAM:
    General: Alert, no acute distress
    Cardiac: Irregularly irregular, grade II/VI systolic murmur at apex
    Lungs: Bibasilar crackles
    Extremities: 2+ bilateral lower extremity edema, JVD present

    LABS:
    Hemoglobin 10.2 g/dL (Low), Hematocrit 31% (Low)
    BUN 52 mg/dL (High), Creatinine 2.8 mg/dL (High), eGFR 22
    Sodium 138, Potassium 4.8, Chloride 102, CO2 24
    BNP 850 pg/mL (High)
    HbA1c 7.4%

    ASSESSMENT AND PLAN:
    1. HFrEF - Continue guideline-directed medical therapy. Order echocardiogram.
    2. Atrial fibrillation - Continue anticoagulation with apixaban, rate controlled.
    3. CKD stage 4 - Avoid nephrotoxins, continue monitoring.
    4. Type 2 diabetes - A1c at goal, continue current regimen.
    5. Anemia - Likely anemia of chronic disease, continue iron supplementation.
    """,
    """
    CARDIOLOGY FOLLOW-UP NOTE

    Chief Complaint: Heart failure follow-up

    HPI: 64 yo male with HFrEF (EF 25%), AFib, CAD s/p 3-vessel CABG (2019), CKD4,
    T2DM, HTN returns for cardiac evaluation. Since last visit, patient notes
    improved exercise tolerance after diuretic adjustment. No chest pain or syncope.
    Denies PND. Still using CPAP nightly for OSA.

    Echo (today): LVEF 28%, moderate MR, mild TR, RVSP 45 mmHg
    Previous echo (3 months ago): LVEF 25%

    Cardiac Cath (2019): 3-vessel CAD, successful CABG x3

    Current Meds: Carvedilol 25mg BID, Lisinopril 20mg daily, Furosemide 40mg BID,
    Spironolactone 25mg daily, Apixaban 5mg BID, Atorvastatin 80mg QHS

    Vitals: BP 124/76, HR 68, O2 sat 97%

    Physical: JVP 8cm, bibasilar crackles improved, 1+ pedal edema (improved from 2+)

    Labs: BNP 720 (down from 850), Cr 2.7 (stable), K 4.6

    A/P:
    1. HFrEF - EF slightly improved to 28%. Continue GDMT. Consider CRT-D evaluation.
    2. AFib - Well rate-controlled on carvedilol. Continue anticoagulation.
    3. CAD s/p CABG - Stable, continue secondary prevention.
    4. CKD4 - Stable, monitor closely with diuretics.
    """,
    """
    NEPHROLOGY CONSULTATION

    Reason for consultation: CKD stage 4 management

    HPI: 64M with CKD stage 4 (baseline Cr 2.5-2.8, eGFR 20-25), HFrEF, T2DM, HTN.
    Referred for nephrology management and dialysis planning.

    Renal History:
    - CKD attributed to diabetic nephropathy and hypertensive nephrosclerosis
    - Urine albumin/creatinine ratio: 850 mg/g (A3)
    - No prior AKI episodes
    - No family history of kidney disease

    Current GFR trajectory: Declining ~3-4 mL/min/year

    Labs today:
    Creatinine 2.8, BUN 52, eGFR 22
    Potassium 4.8, Phosphorus 5.2, Calcium 8.8
    PTH 185 (elevated), Vitamin D 25 ng/mL (insufficient)
    Hemoglobin 10.2, Iron studies: Ferritin 150, TSAT 22%

    Assessment:
    1. CKD stage 4, G4 A3 - likely diabetic/hypertensive etiology
    2. Secondary hyperparathyroidism
    3. Anemia of CKD
    4. Hypovitaminosis D

    Plan:
    1. Continue ACEi (renal protective despite CKD4)
    2. Start calcitriol 0.25 mcg daily for secondary hyperparathyroidism
    3. Start ergocalciferol 50,000 IU weekly x8 weeks
    4. Continue iron supplementation, target ferritin >200
    5. Initiate dialysis education, plan AV fistula creation
    6. Renal diet counseling - low phosphorus, potassium monitoring
    """,
    """
    ENDOCRINOLOGY NOTE

    Type 2 Diabetes Management

    64M with T2DM x15 years, complicated by diabetic nephropathy (CKD4), peripheral
    neuropathy. Also has HFrEF, CAD, HTN.

    Diabetes History:
    - Dx 2011, initially on metformin monotherapy
    - Added glargine 2018 for poor control
    - Current regimen: Metformin 500mg BID (reduced dose for CKD), Glargine 20u QHS

    Home glucose log: Fasting 110-140, pre-dinner 120-160

    Complications:
    - Diabetic nephropathy (CKD4, albuminuria)
    - Peripheral neuropathy - bilateral feet, on gabapentin
    - No retinopathy on last eye exam

    Labs:
    HbA1c 7.4% (improved from 7.8%)
    Fasting glucose 126
    C-peptide 2.1 (adequate endogenous insulin)

    Physical:
    BMI 29.1
    Monofilament testing: diminished sensation bilateral feet
    Pedal pulses: 1+ bilaterally

    A/P:
    1. T2DM - A1c improved to 7.4%, at goal given comorbidities. Caution with
       metformin given CKD4 - consider discontinuation if eGFR <20.
    2. Diabetic neuropathy - Continue gabapentin 300mg TID
    3. Diabetic nephropathy - Continue ACEi, refer to nephrology (done)
    4. Screen for retinopathy - due for eye exam
    """,
]


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host='localhost',
        port=5432,
        database='clinical_ontology',
        user='alexstinard'
    )


def insert_node(cur, patient_id, node_type, label, properties, omop_concept_id=None):
    """Insert a node and return its ID."""
    node_id = str(uuid.uuid4())
    cur.execute(
        """INSERT INTO kg_nodes (id, patient_id, node_type, label, properties, omop_concept_id, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (node_id, patient_id, node_type, label, Json(properties), omop_concept_id, datetime.now(UTC))
    )
    return node_id


def insert_edge(cur, patient_id, source_id, target_id, edge_type, properties=None):
    """Insert an edge."""
    edge_id = str(uuid.uuid4())
    cur.execute(
        """INSERT INTO kg_edges (id, patient_id, source_node_id, target_node_id, edge_type, properties, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (edge_id, patient_id, source_id, target_id, edge_type, Json(properties or {}), datetime.now(UTC))
    )
    return edge_id


def extract_entities_from_note(note_text, note_index):
    """
    Extract clinical entities from a note using pattern matching.
    Returns list of extracted entities with their types and metadata.
    """
    entities = []

    # Diagnosis/Condition patterns - expanded for comprehensive notes
    condition_patterns = [
        # Cardiac conditions
        (r'HFrEF\s*\(?\s*EF\s*~?\s*(\d+)%?\)?', 'HFrEF', 'Heart failure with reduced ejection fraction'),
        (r'(?:acute\s*(?:on\s*chronic\s*)?)?(?:systolic\s*)?heart\s*failure(?:\s*exacerbation)?', 'Heart failure exacerbation', 'Acute decompensated heart failure'),
        (r'atrial fibrillation|AFib|AF\b', 'Atrial fibrillation', 'Atrial fibrillation'),
        (r'AFib\s*with\s*RVR', 'AFib with RVR', 'Atrial fibrillation with rapid ventricular response'),
        (r'CAD\s*s/p\s*CABG|coronary artery disease', 'CAD s/p CABG', 'Coronary artery disease status post CABG'),
        (r'3-vessel\s*(?:CAD|disease)', '3-vessel CAD', 'Three-vessel coronary artery disease'),
        (r'cardiomegaly', 'Cardiomegaly', 'Enlarged heart'),
        (r'old\s*(?:anterolateral\s*)?infarct', 'Old MI', 'Prior myocardial infarction'),
        (r'LAD\b', 'Left axis deviation', 'Left axis deviation on ECG'),
        (r'LAFB|left\s*anterior\s*fascicular\s*block', 'LAFB', 'Left anterior fascicular block'),
        (r'LVH|left\s*ventricular\s*hypertrophy', 'LVH', 'Left ventricular hypertrophy'),
        (r'mitral regurgitation|MR\b', 'Mitral regurgitation', 'Mitral valve regurgitation'),
        (r'tricuspid regurgitation|TR\b', 'Tricuspid regurgitation', 'Tricuspid valve regurgitation'),
        (r'systolic murmur', 'Systolic murmur', 'Heart murmur'),
        (r'holosystolic murmur', 'Holosystolic murmur', 'Holosystolic heart murmur'),

        # Renal conditions
        (r'CKD\s*(?:stage\s*)?4|CKD4', 'CKD Stage 4', 'Chronic kidney disease stage 4'),
        (r'CKD\s*(?:stage\s*)?G4\s*A3', 'CKD G4 A3', 'Chronic kidney disease G4 A3'),
        (r'AKI|acute\s*kidney\s*injury', 'AKI', 'Acute kidney injury'),
        (r'diabetic nephropathy', 'Diabetic nephropathy', 'Diabetic nephropathy'),
        (r'hypertensive\s*nephrosclerosis', 'Hypertensive nephrosclerosis', 'Hypertensive nephrosclerosis'),
        (r'ESRD', 'ESRD', 'End-stage renal disease'),
        (r'albuminuria', 'Albuminuria', 'Albumin in urine'),

        # Metabolic conditions
        (r'type\s*2\s*diabetes|T2DM|DM2', 'Type 2 diabetes', 'Type 2 diabetes mellitus'),
        (r'secondary hyperparathyroidism', 'Secondary hyperparathyroidism', 'Secondary hyperparathyroidism'),
        (r'hypovitaminosis D|vitamin\s*D\s*(?:deficiency|insufficient)', 'Vitamin D deficiency', 'Hypovitaminosis D'),
        (r'hypertension|HTN', 'Hypertension', 'Essential hypertension'),
        (r'hyperlipidemia', 'Hyperlipidemia', 'Elevated lipids'),

        # Pulmonary
        (r'OSA|obstructive sleep apnea', 'OSA', 'Obstructive sleep apnea'),
        (r'pulmonary\s*(?:vascular\s*)?congestion', 'Pulmonary congestion', 'Pulmonary vascular congestion'),
        (r'pulmonary\s*edema', 'Pulmonary edema', 'Pulmonary edema'),
        (r'bilateral\s*pleural\s*effusions?', 'Bilateral pleural effusions', 'Fluid around lungs'),
        (r'interstitial\s*edema', 'Interstitial edema', 'Interstitial pulmonary edema'),

        # Hematologic
        (r'anemia(?:\s*of\s*(?:chronic\s*disease|CKD))?', 'Anemia', 'Anemia'),
        (r'functional\s*iron\s*deficiency', 'Functional iron deficiency', 'Iron deficiency with normal ferritin'),

        # Neurological
        (r'peripheral neuropathy', 'Peripheral neuropathy', 'Diabetic peripheral neuropathy'),
        (r'diabetic\s*peripheral\s*neuropathy', 'Diabetic neuropathy', 'Diabetic peripheral neuropathy'),
        (r'diminished\s*(?:monofilament\s*)?sensation', 'Diminished sensation', 'Peripheral sensory loss'),

        # GI
        (r'GERD', 'GERD', 'Gastroesophageal reflux disease'),
        (r'gout', 'Gout', 'Gout'),

        # Symptoms and signs
        (r'dyspnea\s*(?:on\s*exertion)?|DOE', 'Dyspnea', 'Shortness of breath'),
        (r'orthopnea', 'Orthopnea', 'Difficulty breathing when lying flat'),
        (r'PND|paroxysmal\s*nocturnal\s*dyspnea', 'PND', 'Paroxysmal nocturnal dyspnea'),
        (r'(?:\d\+\s*)?(?:bilateral\s*)?(?:lower\s*extremity\s*|LE\s*|pedal\s*)?edema', 'Edema', 'Peripheral edema'),
        (r'JVD|jugular venous distension|JVP\s*elevated', 'JVD', 'Jugular venous distension'),
        (r'(?:bibasilar\s*)?crackles|rales', 'Pulmonary crackles', 'Lung crackles'),
        (r'fatigue', 'Fatigue', 'Fatigue'),
        (r'nocturia', 'Nocturia', 'Nighttime urination'),
        (r'palpitations', 'Palpitations', 'Heart palpitations'),
        (r'(?:mild\s*)?NPDR', 'NPDR', 'Non-proliferative diabetic retinopathy'),

        # Allergy-related
        (r'Penicillin\s*(?:allergy|-\s*rash|\(rash\))', 'Penicillin allergy', 'Penicillin allergy - rash'),
        (r'Sulfa(?:mides?)?\s*(?:allergy|-\s*hives|\(hives\))', 'Sulfa allergy', 'Sulfonamide allergy - hives'),
    ]

    # Medication patterns - expanded for comprehensive notes
    medication_patterns = [
        # Beta-blockers
        (r'Carvedilol\s*(\d+\s*mg)?', 'Carvedilol', 'Beta-blocker'),
        (r'Metoprolol\s*(?:succinate\s*)?(\d+\s*mg)?', 'Metoprolol', 'Beta-blocker'),

        # ACE inhibitors / ARBs / ARNI
        (r'Lisinopril\s*(\d+\s*mg)?', 'Lisinopril', 'ACE inhibitor'),
        (r'ACEi|ACE\s*inhibitor', 'ACE inhibitor', 'ACE inhibitor class'),
        (r'Sacubitril-valsartan\s*(\d+/\d+\s*mg)?', 'Sacubitril-valsartan', 'ARNI'),
        (r'ARNI', 'ARNI', 'Angiotensin receptor-neprilysin inhibitor'),

        # Diuretics
        (r'Furosemide\s*(\d+\s*mg)?', 'Furosemide', 'Loop diuretic'),
        (r'Bumetanide\s*(\d+\s*mg)?', 'Bumetanide', 'Loop diuretic'),
        (r'Spironolactone\s*(\d+\s*mg)?', 'Spironolactone', 'Aldosterone antagonist'),
        (r'MRA', 'MRA', 'Mineralocorticoid receptor antagonist'),

        # Anticoagulants / Antiplatelets
        (r'Apixaban\s*(\d+\s*mg)?', 'Apixaban', 'Anticoagulant'),
        (r'Rivaroxaban\s*(\d+\s*mg)?', 'Rivaroxaban', 'Anticoagulant'),
        (r'Aspirin\s*(\d+\s*mg)?', 'Aspirin', 'Antiplatelet'),
        (r'Clopidogrel\s*(\d+\s*mg)?', 'Clopidogrel', 'Antiplatelet'),

        # Diabetic medications
        (r'Metformin\s*(\d+\s*mg)?', 'Metformin', 'Oral hypoglycemic'),
        (r'(?:Insulin\s*)?[Gg]largine\s*(\d+\s*units?)?', 'Insulin glargine', 'Long-acting insulin'),
        (r'(?:Insulin\s*)?[Ll]ispro', 'Insulin lispro', 'Rapid-acting insulin'),
        (r'[Ss]liding\s*scale\s*insulin', 'Sliding scale insulin', 'Rapid-acting insulin PRN'),
        (r'Sitagliptin\s*(\d+\s*mg)?', 'Sitagliptin', 'DPP-4 inhibitor'),
        (r'Empagliflozin\s*(\d+\s*mg)?', 'Empagliflozin', 'SGLT2 inhibitor'),
        (r'[Dd]ulaglutide', 'Dulaglutide', 'GLP-1 agonist'),
        (r'GLP-1\s*agonist', 'GLP-1 agonist', 'GLP-1 agonist class'),

        # Statins / Lipid lowering
        (r'Atorvastatin\s*(\d+\s*mg)?', 'Atorvastatin', 'Statin'),
        (r'Rosuvastatin\s*(\d+\s*mg)?', 'Rosuvastatin', 'Statin'),

        # Cardiac
        (r'Digoxin\s*(\d+\.?\d*\s*mg)?', 'Digoxin', 'Cardiac glycoside'),
        (r'Diltiazem\s*(\d+\s*mg)?', 'Diltiazem', 'Calcium channel blocker'),
        (r'Amlodipine\s*(\d+\s*mg)?', 'Amlodipine', 'Calcium channel blocker'),
        (r'Isosorbide\s*mononitrate\s*(\d+\s*mg)?', 'Isosorbide mononitrate', 'Nitrate'),

        # Supplements / Vitamins
        (r'Ferrous sulfate\s*(\d+\s*mg)?', 'Ferrous sulfate', 'Iron supplement'),
        (r'IV\s*iron', 'IV iron', 'Intravenous iron'),
        (r'[Cc]alcitriol\s*(\d+\.?\d*\s*mcg)?', 'Calcitriol', 'Vitamin D analog'),
        (r'[Ee]rgocalciferol\s*(\d+\s*IU)?', 'Ergocalciferol', 'Vitamin D supplement'),

        # CKD-related
        (r'[Ss]evelamer\s*(\d+\s*mg)?', 'Sevelamer', 'Phosphate binder'),
        (r'ESA|erythropoietin', 'ESA', 'Erythropoietin-stimulating agent'),

        # Neuropathy / Pain
        (r'[Gg]abapentin\s*(\d+\s*mg)?', 'Gabapentin', 'Neuropathic pain medication'),
        (r'Acetaminophen\s*(\d+\s*mg)?', 'Acetaminophen', 'Analgesic'),

        # GI / Other
        (r'PPI|[Oo]meprazole|[Pp]antoprazole', 'PPI', 'Proton pump inhibitor'),
        (r'Docusate\s*(\d+\s*mg)?', 'Docusate', 'Stool softener'),
        (r'Sennosides?\s*(\d+\.?\d*\s*mg)?', 'Sennosides', 'Laxative'),
        (r'Tamsulosin\s*(\d+\.?\d*\s*mg)?', 'Tamsulosin', 'Alpha blocker'),
        (r'[Aa]llopurinol', 'Allopurinol', 'Uric acid lowering'),
        (r'Levothyroxine\s*(\d+\s*mcg)?', 'Levothyroxine', 'Thyroid hormone'),
        (r'Trazodone', 'Trazodone', 'Sleep medication'),

        # GDMT
        (r'GDMT', 'GDMT', 'Guideline-directed medical therapy'),
    ]

    # Lab result patterns - expanded for comprehensive notes
    lab_patterns = [
        # CBC
        (r'WBC[:\s]*(\d+\.?\d*)\s*K/uL', 'WBC', 'K/uL'),
        (r'RBC[:\s]*(\d+\.?\d*)\s*M/uL', 'RBC', 'M/uL'),
        (r'[Hh]emoglobin[:\s]*(\d+\.?\d*)\s*g/dL', 'Hemoglobin', 'g/dL'),
        (r'Hgb[:\s]*(\d+\.?\d*)', 'Hemoglobin', 'g/dL'),
        (r'[Hh]ematocrit[:\s]*(\d+\.?\d*)\s*%', 'Hematocrit', '%'),
        (r'Hct[:\s]*(\d+)', 'Hematocrit', '%'),
        (r'MCV[:\s]*(\d+)\s*fL', 'MCV', 'fL'),
        (r'[Pp]latelets?[:\s]*(\d+)\s*K/uL', 'Platelets', 'K/uL'),
        (r'Plt[:\s]*(\d+)', 'Platelets', 'K/uL'),

        # BMP / Electrolytes
        (r'[Ss]odium[:\s]*(\d+)\s*mEq/L', 'Sodium', 'mEq/L'),
        (r'Na[:\s]*(\d+)', 'Sodium', 'mEq/L'),
        (r'[Pp]otassium[:\s]*(\d+\.?\d*)\s*mEq/L', 'Potassium', 'mEq/L'),
        (r'K[:\s]*(\d+\.?\d*)', 'Potassium', 'mEq/L'),
        (r'[Cc]hloride[:\s]*(\d+)\s*mEq/L', 'Chloride', 'mEq/L'),
        (r'Cl[:\s]*(\d+)', 'Chloride', 'mEq/L'),
        (r'CO2[:\s]*(\d+)\s*mEq/L', 'CO2', 'mEq/L'),
        (r'BUN[:\s]*(\d+\.?\d*)\s*mg/dL', 'BUN', 'mg/dL'),
        (r'BUN[:\s]*(\d+)', 'BUN', 'mg/dL'),
        (r'[Cc]reatinine[:\s]*(\d+\.?\d*)\s*mg/dL', 'Creatinine', 'mg/dL'),
        (r'Cr[:\s]*(\d+\.?\d*)', 'Creatinine', 'mg/dL'),
        (r'[Gg]lucose[:\s]*(\d+)\s*mg/dL', 'Glucose', 'mg/dL'),
        (r'eGFR[:\s]*(\d+)', 'eGFR', 'mL/min/1.73m2'),

        # Calcium / Bone
        (r'[Cc]alcium[:\s]*(\d+\.?\d*)\s*mg/dL', 'Calcium', 'mg/dL'),
        (r'Ca[:\s]*(\d+\.?\d*)', 'Calcium', 'mg/dL'),
        (r'[Pp]hosphorus[:\s]*(\d+\.?\d*)\s*mg/dL', 'Phosphorus', 'mg/dL'),
        (r'[Pp]hos[:\s]*(\d+\.?\d*)', 'Phosphorus', 'mg/dL'),
        (r'PTH[:\s]*(\d+)\s*pg/mL', 'PTH', 'pg/mL'),
        (r'PTH[:\s]*(\d+)', 'PTH', 'pg/mL'),
        (r'[Vv]itamin\s*D[,\s]*25-?OH[:\s]*(\d+)\s*ng/mL', 'Vitamin D', 'ng/mL'),
        (r'[Vv]itamin\s*D[:\s]*(\d+)', 'Vitamin D', 'ng/mL'),
        (r'[Mm]agnesium[:\s]*(\d+\.?\d*)\s*mg/dL', 'Magnesium', 'mg/dL'),

        # Cardiac markers
        (r'BNP[:\s]*(\d+)\s*pg/mL', 'BNP', 'pg/mL'),
        (r'BNP[:\s]*(\d+)', 'BNP', 'pg/mL'),
        (r'[Tt]roponin\s*I?[:\s]*(<?\d*\.?\d+)\s*ng/mL', 'Troponin', 'ng/mL'),
        (r'[Tt]roponin[:\s]*(<?\d*\.?\d+)', 'Troponin', 'ng/mL'),
        (r'CK-MB[:\s]*(\d+\.?\d*)\s*ng/mL', 'CK-MB', 'ng/mL'),

        # Diabetes
        (r'HbA1c[:\s]*(\d+\.?\d*)\s*%', 'HbA1c', '%'),
        (r'A1c[:\s]*(\d+\.?\d*)%', 'HbA1c', '%'),
        (r'[Ff]asting\s*glucose[:\s]*(\d+)', 'Fasting glucose', 'mg/dL'),
        (r'[Cc]-peptide[:\s]*(\d+\.?\d*)', 'C-peptide', 'ng/mL'),

        # Iron studies
        (r'[Ff]erritin[:\s]*(\d+)\s*ng/mL', 'Ferritin', 'ng/mL'),
        (r'[Ff]erritin[:\s]*(\d+)', 'Ferritin', 'ng/mL'),
        (r'TSAT[:\s]*(\d+)\s*%', 'TSAT', '%'),
        (r'[Tt]ransferrin\s*saturation[:\s]*(\d+)\s*%', 'TSAT', '%'),
        (r'[Ii]ron[:\s]*(\d+)\s*mcg/dL', 'Iron', 'mcg/dL'),
        (r'TIBC[:\s]*(\d+)\s*mcg/dL', 'TIBC', 'mcg/dL'),

        # Renal
        (r'BUN/[Cc]reatinine\s*ratio[:\s]*(\d+\.?\d*)', 'BUN/Cr ratio', 'ratio'),
        (r'[Uu]rine\s*albumin[:\s]*(\d+)\s*mg/g', 'Urine albumin', 'mg/g Cr'),
        (r'[Uu]rine\s*protein[:\s]*(\d+\.?\d*)\s*g/24hr', 'Urine protein', 'g/24hr'),

        # Lipids
        (r'[Tt]otal\s*cholesterol[:\s]*(\d+)\s*mg/dL', 'Total cholesterol', 'mg/dL'),
        (r'LDL[:\s]*(\d+)\s*mg/dL', 'LDL', 'mg/dL'),
        (r'HDL[:\s]*(\d+)\s*mg/dL', 'HDL', 'mg/dL'),
        (r'[Tt]riglycerides[:\s]*(\d+)\s*mg/dL', 'Triglycerides', 'mg/dL'),

        # Coagulation
        (r'PT[:\s]*(\d+\.?\d*)\s*seconds', 'PT', 'seconds'),
        (r'INR[:\s]*(\d+\.?\d*)', 'INR', 'ratio'),
        (r'PTT[:\s]*(\d+)\s*seconds', 'PTT', 'seconds'),

        # Thyroid
        (r'TSH[:\s]*(\d+\.?\d*)\s*mIU/L', 'TSH', 'mIU/L'),
        (r'[Ff]ree\s*T4[:\s]*(\d+\.?\d*)\s*ng/dL', 'Free T4', 'ng/dL'),

        # Liver
        (r'AST[:\s]*(\d+)\s*U/L', 'AST', 'U/L'),
        (r'ALT[:\s]*(\d+)\s*U/L', 'ALT', 'U/L'),
        (r'[Aa]lkaline\s*phosphatase[:\s]*(\d+)\s*U/L', 'Alk Phos', 'U/L'),
        (r'[Tt]otal\s*bilirubin[:\s]*(\d+\.?\d*)\s*mg/dL', 'Total bilirubin', 'mg/dL'),
        (r'[Aa]lbumin[:\s]*(\d+\.?\d*)\s*g/dL', 'Albumin', 'g/dL'),

        # Echo findings
        (r'LVEF[:\s]*(\d+)\s*%', 'LVEF', '%'),
        (r'EF[:\s]*(\d+)%', 'LVEF', '%'),
        (r'RVSP[:\s]*(\d+)\s*mmHg', 'RVSP', 'mmHg'),
        (r'TAPSE[:\s]*(\d+)\s*mm', 'TAPSE', 'mm'),
        (r'LVEDV[:\s]*(\d+)\s*mL', 'LVEDV', 'mL'),
        (r'LVESV[:\s]*(\d+)\s*mL', 'LVESV', 'mL'),
        (r'LA\s*volume\s*index[:\s]*(\d+)\s*mL/m2', 'LA volume index', 'mL/m2'),
        (r'LV\s*mass', 'LV mass', 'Increased'),
    ]

    # Vital sign patterns - expanded
    vital_patterns = [
        (r'BP\s*(\d+/\d+)\s*mmHg', 'Blood pressure', 'mmHg'),
        (r'BP\s*(\d+/\d+)', 'Blood pressure', 'mmHg'),
        (r'HR\s*(\d+)\s*bpm', 'Heart rate', 'bpm'),
        (r'HR\s*(\d+)', 'Heart rate', 'bpm'),
        (r'[Tt]emp\s*(\d+\.?\d*)\s*F', 'Temperature', 'F'),
        (r'T\s*(\d+\.?\d*)', 'Temperature', 'F'),
        (r'SpO2\s*(\d+)\s*%', 'SpO2', '%'),
        (r'O2\s*sat\s*(\d+)%', 'SpO2', '%'),
        (r'RR\s*(\d+)\s*/min', 'Respiratory rate', '/min'),
        (r'RR\s*(\d+)', 'Respiratory rate', '/min'),
        (r'[Ww]eight[:\s]*(\d+)\s*kg', 'Weight', 'kg'),
        (r'Wt[:\s]*(\d+)\s*kg', 'Weight', 'kg'),
        (r'BMI\s*(\d+\.?\d*)', 'BMI', 'kg/m2'),
        (r'JVP\s*(\d+)\s*cm', 'JVP', 'cm'),
        (r'I/O[:\s]*(\d+/\d+)\s*mL', 'I/O', 'mL'),
    ]

    # Procedure patterns - expanded
    procedure_patterns = [
        # Cardiac procedures
        (r'CABG(?:\s*x\s*\d)?|coronary artery bypass', 'CABG', 'Coronary artery bypass grafting'),
        (r'LIMA\s*to\s*LAD', 'LIMA to LAD graft', 'Left internal mammary artery to LAD'),
        (r'SVG\s*to\s*OM', 'SVG to OM graft', 'Saphenous vein graft to obtuse marginal'),
        (r'SVG\s*to\s*RCA', 'SVG to RCA graft', 'Saphenous vein graft to RCA'),
        (r'[Ee]chocardiogram|[Ee]cho(?:cardiography)?', 'Echocardiogram', 'Cardiac ultrasound'),
        (r'transthoracic\s*echocardiogram|TTE', 'TTE', 'Transthoracic echocardiogram'),
        (r'[Cc]ardiac\s*[Cc]ath(?:eterization)?', 'Cardiac catheterization', 'Coronary angiography'),
        (r'CRT-D(?:\s*evaluation)?', 'CRT-D', 'Cardiac resynchronization therapy with defibrillator'),
        (r'ICD', 'ICD', 'Implantable cardioverter-defibrillator'),
        (r'[Cc]ardioversion', 'Cardioversion', 'Electrical cardioversion'),
        (r'[Cc]ardiac\s*rehab', 'Cardiac rehabilitation', 'Cardiac rehabilitation program'),

        # Pulmonary
        (r'CPAP(?:\s*therapy)?', 'CPAP', 'Continuous positive airway pressure'),

        # Renal
        (r'AV\s*fistula(?:\s*creation)?', 'AV fistula creation', 'Arteriovenous fistula for dialysis'),
        (r'[Dd]ialysis(?:\s*education)?', 'Dialysis', 'Renal replacement therapy'),

        # Imaging
        (r'[Cc]hest\s*(?:radiograph|X-?ray|[Xx]ray)|CXR', 'Chest X-ray', 'Chest radiograph'),
        (r'PA\s*and\s*lateral', 'PA and lateral CXR', 'Chest X-ray views'),
        (r'ECG|EKG', 'ECG', 'Electrocardiogram'),

        # Other procedures
        (r'[Mm]onofilament\s*testing', 'Monofilament testing', 'Peripheral neuropathy screening'),
        (r'[Dd]ilated\s*eye\s*exam', 'Dilated eye exam', 'Diabetic retinopathy screening'),
        (r'[Ss]ternotomy', 'Sternotomy', 'Median sternotomy'),
        (r'[Aa]ppendectomy', 'Appendectomy', 'Appendix removal'),
        (r'IV\s*diuresis', 'IV diuresis', 'Intravenous diuretic therapy'),
    ]

    # Social/Family history patterns
    social_patterns = [
        (r'[Ff]ormer\s*smoker\s*\(?\s*(\d+)\s*pack-?years?\)?', 'Former smoker', 'Tobacco use history'),
        (r'[Oo]ccasional\s*alcohol', 'Occasional alcohol', 'Social alcohol use'),
        (r'[Rr]etired', 'Retired', 'Retirement status'),
        (r'[Ff]ather:\s*MI', 'Family history - MI', 'Paternal MI'),
        (r'[Mm]other:\s*(?:Type\s*2\s*)?diabetes', 'Family history - DM', 'Maternal diabetes'),
        (r'[Bb]rother:\s*(?:coronary\s*artery\s*disease|CAD)', 'Family history - CAD', 'Sibling CAD'),
    ]

    # Care plan patterns
    plan_patterns = [
        (r'[Ff]luid\s*restriction\s*(\d+\.?\d*)\s*L/day', 'Fluid restriction', 'Fluid limit'),
        (r'[Ss]odium\s*restriction\s*<?(\d+)\s*g/day', 'Sodium restriction', 'Dietary sodium limit'),
        (r'[Rr]enal\s*diet', 'Renal diet', 'Dietary restriction for CKD'),
        (r'[Ll]ow\s*phosphorus', 'Low phosphorus diet', 'Dietary phosphorus limit'),
        (r'[Dd]aily\s*weights', 'Daily weights', 'Weight monitoring'),
        (r'[Ss]trict\s*I/O', 'Strict I/O', 'Intake/output monitoring'),
    ]

    # Extract conditions
    for pattern, name, description in condition_patterns:
        matches = re.finditer(pattern, note_text, re.IGNORECASE)
        for match in matches:
            entities.append({
                'type': 'condition',
                'name': name,
                'description': description,
                'source_note': note_index,
                'span': (match.start(), match.end()),
                'matched_text': match.group(0),
            })

    # Extract medications
    for pattern, name, description in medication_patterns:
        matches = re.finditer(pattern, note_text, re.IGNORECASE)
        for match in matches:
            dosage = match.group(1) if match.lastindex else None
            entities.append({
                'type': 'drug',
                'name': name,
                'description': description,
                'dosage': dosage,
                'source_note': note_index,
                'span': (match.start(), match.end()),
                'matched_text': match.group(0),
            })

    # Extract lab results
    for pattern, name, unit in lab_patterns:
        matches = re.finditer(pattern, note_text, re.IGNORECASE)
        for match in matches:
            value = match.group(1) if match.lastindex else None
            entities.append({
                'type': 'measurement',
                'name': name,
                'value': value,
                'unit': unit,
                'source_note': note_index,
                'span': (match.start(), match.end()),
                'matched_text': match.group(0),
            })

    # Extract vital signs
    for pattern, name, unit in vital_patterns:
        matches = re.finditer(pattern, note_text, re.IGNORECASE)
        for match in matches:
            value = match.group(1) if match.lastindex else None
            entities.append({
                'type': 'vital_sign',
                'name': name,
                'value': value,
                'unit': unit,
                'source_note': note_index,
                'span': (match.start(), match.end()),
                'matched_text': match.group(0),
            })

    # Extract procedures
    for pattern, name, description in procedure_patterns:
        matches = re.finditer(pattern, note_text, re.IGNORECASE)
        for match in matches:
            entities.append({
                'type': 'procedure',
                'name': name,
                'description': description,
                'source_note': note_index,
                'span': (match.start(), match.end()),
                'matched_text': match.group(0),
            })

    # Extract social/family history
    for pattern, name, description in social_patterns:
        matches = re.finditer(pattern, note_text, re.IGNORECASE)
        for match in matches:
            value = match.group(1) if match.lastindex else None
            entities.append({
                'type': 'observation',
                'name': name,
                'description': description,
                'value': value,
                'source_note': note_index,
                'span': (match.start(), match.end()),
                'matched_text': match.group(0),
            })

    # Extract care plan elements
    for pattern, name, description in plan_patterns:
        matches = re.finditer(pattern, note_text, re.IGNORECASE)
        for match in matches:
            value = match.group(1) if match.lastindex else None
            entities.append({
                'type': 'observation',
                'name': name,
                'description': description,
                'value': value,
                'source_note': note_index,
                'span': (match.start(), match.end()),
                'matched_text': match.group(0),
            })

    return entities


def extract_note_date(note_text, note_index):
    """Extract the date from a note header."""
    # Try various date patterns
    date_patterns = [
        r'(\d{2}/\d{2}/\d{4})',  # MM/DD/YYYY
        r'(\d{1,2}/\d{1,2}/\d{4})',  # M/D/YYYY
        r'Hospital Day #(\d+)',  # Hospital day number
    ]

    for pattern in date_patterns:
        match = re.search(pattern, note_text[:200])  # Only check header
        if match:
            return match.group(1)

    return f"Note_{note_index}"


def build_full_knowledge_graph(patient_id, notes):
    """Build a comprehensive knowledge graph from clinical notes."""

    print(f"Building comprehensive knowledge graph for patient {patient_id}...")
    print(f"Processing {len(notes)} clinical notes...")

    # Extract entities from all notes
    all_entities = []
    for i, note in enumerate(notes):
        note_date = extract_note_date(note, i)
        entities = extract_entities_from_note(note, i)

        # Add date context to temporal entities (measurements, vitals)
        for entity in entities:
            entity['note_date'] = note_date

        all_entities.extend(entities)
        print(f"  Note {i+1} ({note_date}): Extracted {len(entities)} entities")

    print(f"\nTotal entities extracted: {len(all_entities)}")

    # Count by type
    type_counts = defaultdict(int)
    for e in all_entities:
        type_counts[e['type']] += 1

    for t, c in sorted(type_counts.items()):
        print(f"  {t}: {c}")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Clear existing data for this patient
        cur.execute("DELETE FROM kg_edges WHERE patient_id = %s", (patient_id,))
        cur.execute("DELETE FROM kg_nodes WHERE patient_id = %s", (patient_id,))
        print("\nCleared existing graph data")

        nodes_created = 0
        edges_created = 0

        # Create patient node
        patient_node_id = insert_node(
            cur, patient_id, 'patient', f"Patient {patient_id}",
            {"age": 64, "sex": "Male", "dob": "1961-04-12"}
        )
        nodes_created += 1

        # Track unique entities - conditions/drugs by name, measurements by name+date+value
        entity_nodes = {}  # key -> node_id
        # Also track base concepts for measurements to create "latest value" relationships
        measurement_concepts = {}  # measurement_name -> list of (node_id, date, value)

        # Create nodes for all extracted entities
        for entity in all_entities:
            entity_type = entity['type']
            note_date = entity.get('note_date', 'unknown')

            # For measurements and vitals, include date and value in key for temporal tracking
            if entity_type in ('measurement', 'vital_sign'):
                value = entity.get('value', '')
                key = (entity_type, entity['name'], note_date, value)

                # Also track as a concept for relationship building
                concept_name = entity['name']
                if concept_name not in measurement_concepts:
                    measurement_concepts[concept_name] = []
            else:
                key = (entity_type, entity['name'])

            if key in entity_nodes:
                # Entity already exists with same key
                continue

            # Build properties based on entity type
            properties = {
                'source_notes': [entity['source_note']],
                'matched_text': entity['matched_text'],
                'extracted_date': note_date,
            }

            if 'description' in entity:
                properties['description'] = entity['description']
            if 'value' in entity and entity['value']:
                properties['value'] = entity['value']
            if 'unit' in entity and entity['unit']:
                properties['unit'] = entity['unit']
            if 'dosage' in entity and entity['dosage']:
                properties['dosage'] = entity['dosage']

            # Map entity type to graph node type
            node_type = entity_type
            if node_type == 'vital_sign':
                node_type = 'measurement'

            # Create label with temporal context for measurements
            if entity_type in ('measurement', 'vital_sign'):
                value = entity.get('value', '')
                label = f"{entity['name']} ({value} on {note_date})" if value else f"{entity['name']} ({note_date})"
            else:
                label = entity['name']

            node_id = insert_node(
                cur, patient_id, node_type, label, properties
            )
            entity_nodes[key] = node_id
            nodes_created += 1

            # Track temporal measurements
            if entity_type in ('measurement', 'vital_sign'):
                measurement_concepts[entity['name']].append({
                    'node_id': node_id,
                    'date': note_date,
                    'value': entity.get('value', ''),
                })

            # Create edge from patient to entity
            edge_type = f"has_{node_type}"
            if node_type == 'drug':
                edge_type = 'takes_drug'
            elif node_type == 'condition':
                edge_type = 'has_condition'

            insert_edge(cur, patient_id, patient_node_id, node_id, edge_type)
            edges_created += 1

        # Create treatment relationships (condition -> medication) - expanded
        treatment_mappings = [
            # Heart failure treatments
            ('HFrEF', ['Carvedilol', 'Metoprolol', 'Lisinopril', 'Sacubitril-valsartan', 'Furosemide', 'Bumetanide', 'Spironolactone', 'Digoxin']),
            ('Heart failure exacerbation', ['Furosemide', 'Bumetanide', 'IV diuresis']),

            # AFib treatments
            ('Atrial fibrillation', ['Apixaban', 'Rivaroxaban', 'Carvedilol', 'Metoprolol', 'Diltiazem', 'Digoxin']),
            ('AFib with RVR', ['Diltiazem', 'Metoprolol', 'Carvedilol']),

            # Diabetes treatments
            ('Type 2 diabetes', ['Metformin', 'Insulin glargine', 'Insulin lispro', 'Sitagliptin', 'Empagliflozin', 'Dulaglutide']),
            ('Diabetic neuropathy', ['Gabapentin']),

            # Cardiovascular
            ('Hypertension', ['Lisinopril', 'Carvedilol', 'Metoprolol', 'Amlodipine', 'Diltiazem']),
            ('CAD s/p CABG', ['Atorvastatin', 'Rosuvastatin', 'Aspirin', 'Clopidogrel']),
            ('3-vessel CAD', ['Atorvastatin', 'Aspirin', 'Clopidogrel']),

            # Renal
            ('CKD Stage 4', ['ACE inhibitor', 'Lisinopril', 'Sevelamer', 'Calcitriol']),
            ('CKD G4 A3', ['ACE inhibitor', 'Lisinopril', 'Sevelamer']),
            ('Secondary hyperparathyroidism', ['Calcitriol', 'Sevelamer']),
            ('Vitamin D deficiency', ['Ergocalciferol', 'Calcitriol']),

            # Hematologic
            ('Anemia', ['Ferrous sulfate', 'IV iron', 'ESA']),
            ('Functional iron deficiency', ['Ferrous sulfate', 'IV iron']),

            # Other
            ('Peripheral neuropathy', ['Gabapentin']),
            ('OSA', ['CPAP']),
            ('Gout', ['Allopurinol']),
            ('GERD', ['PPI']),
            ('Edema', ['Furosemide', 'Bumetanide', 'Spironolactone']),
        ]

        for condition_name, med_names in treatment_mappings:
            condition_key = ('condition', condition_name)
            if condition_key in entity_nodes:
                for med_name in med_names:
                    med_key = ('drug', med_name)
                    if med_key in entity_nodes:
                        insert_edge(
                            cur, patient_id,
                            entity_nodes[condition_key],
                            entity_nodes[med_key],
                            'condition_treated_by',
                            {'relationship': 'therapeutic'}
                        )
                        edges_created += 1

        # Create reverse drug-treats relationships
        for condition_name, med_names in treatment_mappings:
            condition_key = ('condition', condition_name)
            if condition_key in entity_nodes:
                for med_name in med_names:
                    med_key = ('drug', med_name)
                    if med_key in entity_nodes:
                        insert_edge(
                            cur, patient_id,
                            entity_nodes[med_key],
                            entity_nodes[condition_key],
                            'drug_treats',
                            {'relationship': 'therapeutic'}
                        )
                        edges_created += 1

        # Create condition-to-complication relationships (as observations)
        complication_mappings = [
            ('Type 2 diabetes', ['Diabetic nephropathy', 'Diabetic neuropathy', 'Peripheral neuropathy', 'NPDR', 'CKD Stage 4']),
            ('HFrEF', ['Dyspnea', 'Orthopnea', 'PND', 'Edema', 'Fatigue', 'Pulmonary congestion', 'Pulmonary edema']),
            ('CKD Stage 4', ['Secondary hyperparathyroidism', 'Anemia', 'AKI', 'Vitamin D deficiency']),
            ('Hypertension', ['Hypertensive nephrosclerosis', 'LVH']),
            ('CAD s/p CABG', ['Old MI']),
            ('Atrial fibrillation', ['AFib with RVR', 'Palpitations']),
        ]

        for primary_condition, complications in complication_mappings:
            primary_key = ('condition', primary_condition)
            if primary_key in entity_nodes:
                for complication in complications:
                    complication_key = ('condition', complication)
                    if complication_key in entity_nodes:
                        # Use has_observation to link related conditions
                        insert_edge(
                            cur, patient_id,
                            entity_nodes[primary_key],
                            entity_nodes[complication_key],
                            'has_observation',
                            {'relationship': 'complication_of'}
                        )
                        edges_created += 1

        # Note: Using valid edge types only (has_condition, takes_drug, has_measurement,
        # has_procedure, has_observation, condition_treated_by, drug_treats)
        # Additional semantic relationships are stored in edge properties

        # Commit all changes
        conn.commit()

        print(f"\n{'='*50}")
        print(f"KNOWLEDGE GRAPH BUILT SUCCESSFULLY")
        print(f"{'='*50}")
        print(f"Total nodes created: {nodes_created}")
        print(f"  - Unique entities: {len(entity_nodes)}")
        print(f"Total edges created: {edges_created}")
        print(f"\nNode breakdown by type:")

        node_type_counts = defaultdict(int)
        for key in entity_nodes.keys():
            # Key can be (type, name) or (type, name, date, value)
            entity_type = key[0]
            if entity_type == 'vital_sign':
                entity_type = 'measurement'
            node_type_counts[entity_type] += 1
        node_type_counts['patient'] = 1

        for t, c in sorted(node_type_counts.items()):
            print(f"  - {t}: {c}")

        print(f"\nView at: http://localhost:3000/patients/{patient_id}/graph")

        return {
            'nodes_created': nodes_created,
            'edges_created': edges_created,
            'entity_counts': dict(type_counts),
        }

    except Exception as e:
        conn.rollback()
        print(f"\nError building graph: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Build comprehensive patient knowledge graph")
    parser.add_argument('--patient-id', default='TEST12345', help='Patient identifier')
    parser.add_argument('--notes-file', help='JSON file with clinical notes')
    args = parser.parse_args()

    # Use sample notes or load from file
    if args.notes_file:
        with open(args.notes_file) as f:
            notes = json.load(f)
    else:
        notes = SAMPLE_NOTES

    # Build the graph
    result = build_full_knowledge_graph(args.patient_id, notes)

    print(f"\nDone! Graph built with {result['nodes_created']} nodes and {result['edges_created']} edges.")


if __name__ == "__main__":
    main()
