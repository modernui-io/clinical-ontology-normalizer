#!/usr/bin/env python3
"""
Generate comprehensive longitudinal clinical notes for a patient.

Creates a realistic clinical timeline with:
- Admission notes
- Progress notes (daily)
- Specialty consultations
- Discharge summaries
- Follow-up visits
- Lab reports
- Imaging reports
- Procedure notes

This generates enough variation to produce 1000+ unique entities.
"""

import json
import random
from datetime import datetime, timedelta

# Base patient data
PATIENT = {
    "id": "TEST12345",
    "name": "John Smith",
    "age": 64,
    "sex": "Male",
    "dob": "1961-04-12",
}

# Comprehensive condition list with variations
CONDITIONS = [
    # Cardiac
    ("HFrEF", "Heart failure with reduced ejection fraction", ["EF 25%", "EF 28%", "EF 30%"]),
    ("Atrial fibrillation", "Atrial fibrillation", ["persistent", "paroxysmal", "with RVR"]),
    ("CAD", "Coronary artery disease", ["3-vessel", "s/p CABG", "s/p PCI"]),
    ("Mitral regurgitation", "Mitral regurgitation", ["moderate", "mild-moderate", "moderate-severe"]),
    ("Tricuspid regurgitation", "Tricuspid regurgitation", ["mild", "moderate"]),
    ("Pulmonary hypertension", "Pulmonary hypertension", ["Group 2", "secondary to HF"]),
    ("Left ventricular hypertrophy", "LVH", ["concentric", "eccentric"]),
    ("Diastolic dysfunction", "Diastolic dysfunction", ["Grade I", "Grade II"]),

    # Renal
    ("CKD Stage 4", "Chronic kidney disease stage 4", ["eGFR 20-25", "eGFR 22"]),
    ("Diabetic nephropathy", "Diabetic nephropathy", ["with albuminuria", "A3 category"]),
    ("Hypertensive nephrosclerosis", "Hypertensive nephrosclerosis", []),
    ("Secondary hyperparathyroidism", "Secondary hyperparathyroidism", ["PTH elevated"]),
    ("Metabolic acidosis", "Metabolic acidosis", ["chronic", "compensated"]),
    ("Hyperphosphatemia", "Hyperphosphatemia", []),
    ("Hypocalcemia", "Hypocalcemia", ["mild"]),

    # Metabolic/Endocrine
    ("Type 2 diabetes", "Type 2 diabetes mellitus", ["with complications", "insulin-requiring"]),
    ("Diabetic neuropathy", "Diabetic peripheral neuropathy", ["bilateral feet", "sensory"]),
    ("Diabetic retinopathy", "Diabetic retinopathy", ["non-proliferative", "mild"]),
    ("Hyperlipidemia", "Hyperlipidemia", ["on statin", "mixed"]),
    ("Obesity", "Obesity", ["Class I", "BMI 30-35"]),
    ("Vitamin D deficiency", "Vitamin D deficiency", ["25-OH-D low"]),
    ("Hypothyroidism", "Hypothyroidism", ["subclinical", "on levothyroxine"]),

    # Pulmonary
    ("OSA", "Obstructive sleep apnea", ["on CPAP", "moderate-severe"]),
    ("Pulmonary edema", "Pulmonary edema", ["cardiogenic", "mild"]),
    ("Pleural effusion", "Pleural effusion", ["bilateral", "small", "moderate"]),
    ("Dyspnea", "Dyspnea", ["on exertion", "at rest"]),

    # Hematologic
    ("Anemia", "Anemia", ["chronic disease", "normocytic", "Hgb 10-11"]),
    ("Iron deficiency", "Iron deficiency", ["functional", "TSAT low"]),
    ("Thrombocytopenia", "Thrombocytopenia", ["mild", "drug-induced"]),

    # Other
    ("Hypertension", "Essential hypertension", ["controlled", "stage 2"]),
    ("GERD", "Gastroesophageal reflux disease", ["on PPI"]),
    ("Chronic pain", "Chronic pain", ["low back", "knee OA"]),
    ("Osteoarthritis", "Osteoarthritis", ["knees", "hands"]),
    ("Gout", "Gout", ["controlled", "on allopurinol"]),
    ("BPH", "Benign prostatic hyperplasia", ["on tamsulosin"]),
    ("Depression", "Depression", ["on SSRI", "mild"]),
    ("Anxiety", "Anxiety disorder", ["generalized"]),
    ("Insomnia", "Insomnia", ["chronic"]),
]

# Comprehensive medication list
MEDICATIONS = [
    # Cardiac
    ("Carvedilol", "25 mg", "PO BID", "Beta-blocker"),
    ("Metoprolol succinate", "100 mg", "PO daily", "Beta-blocker"),
    ("Lisinopril", "20 mg", "PO daily", "ACE inhibitor"),
    ("Losartan", "50 mg", "PO daily", "ARB"),
    ("Sacubitril-valsartan", "49-51 mg", "PO BID", "ARNI"),
    ("Furosemide", "40 mg", "PO BID", "Loop diuretic"),
    ("Bumetanide", "1 mg", "PO BID", "Loop diuretic"),
    ("Torsemide", "20 mg", "PO daily", "Loop diuretic"),
    ("Spironolactone", "25 mg", "PO daily", "MRA"),
    ("Eplerenone", "25 mg", "PO daily", "MRA"),
    ("Digoxin", "0.125 mg", "PO daily", "Cardiac glycoside"),
    ("Apixaban", "5 mg", "PO BID", "Anticoagulant"),
    ("Rivaroxaban", "20 mg", "PO daily", "Anticoagulant"),
    ("Warfarin", "5 mg", "PO daily", "Anticoagulant"),
    ("Aspirin", "81 mg", "PO daily", "Antiplatelet"),
    ("Clopidogrel", "75 mg", "PO daily", "Antiplatelet"),
    ("Atorvastatin", "80 mg", "PO QHS", "Statin"),
    ("Rosuvastatin", "20 mg", "PO daily", "Statin"),
    ("Isosorbide mononitrate", "30 mg", "PO daily", "Nitrate"),
    ("Hydralazine", "25 mg", "PO TID", "Vasodilator"),
    ("Amlodipine", "5 mg", "PO daily", "CCB"),
    ("Diltiazem", "180 mg", "PO daily", "CCB"),

    # Diabetes
    ("Metformin", "500 mg", "PO BID", "Biguanide"),
    ("Insulin glargine", "20 units", "SC QHS", "Long-acting insulin"),
    ("Insulin lispro", "5 units", "SC with meals", "Rapid-acting insulin"),
    ("Empagliflozin", "10 mg", "PO daily", "SGLT2 inhibitor"),
    ("Semaglutide", "0.5 mg", "SC weekly", "GLP-1 agonist"),
    ("Sitagliptin", "50 mg", "PO daily", "DPP-4 inhibitor"),

    # Renal/Electrolytes
    ("Sevelamer", "800 mg", "PO TID with meals", "Phosphate binder"),
    ("Calcitriol", "0.25 mcg", "PO daily", "Vitamin D"),
    ("Ergocalciferol", "50000 IU", "PO weekly", "Vitamin D2"),
    ("Ferrous sulfate", "325 mg", "PO daily", "Iron supplement"),
    ("Iron sucrose", "200 mg", "IV", "IV iron"),
    ("Epoetin alfa", "4000 units", "SC weekly", "ESA"),
    ("Sodium bicarbonate", "650 mg", "PO TID", "Alkalinizing agent"),
    ("Calcium acetate", "667 mg", "PO TID with meals", "Phosphate binder"),

    # Other
    ("Gabapentin", "300 mg", "PO TID", "Neuropathic pain"),
    ("Omeprazole", "20 mg", "PO daily", "PPI"),
    ("Tamsulosin", "0.4 mg", "PO QHS", "Alpha-blocker"),
    ("Allopurinol", "100 mg", "PO daily", "Uric acid lowering"),
    ("Sertraline", "50 mg", "PO daily", "SSRI"),
    ("Trazodone", "50 mg", "PO QHS", "Sleep aid"),
    ("Levothyroxine", "50 mcg", "PO daily", "Thyroid hormone"),
    ("Acetaminophen", "650 mg", "PO Q6H PRN", "Analgesic"),
    ("Docusate", "100 mg", "PO BID", "Stool softener"),
    ("Sennosides", "8.6 mg", "PO QHS PRN", "Laxative"),
]

# Lab panels with values and ranges
LAB_PANELS = {
    "CBC": [
        ("WBC", "6.8", "4.5-11.0", "K/uL"),
        ("RBC", "3.8", "4.5-5.5", "M/uL"),
        ("Hemoglobin", "10.2", "14.0-18.0", "g/dL"),
        ("Hematocrit", "31", "42-52", "%"),
        ("MCV", "82", "80-100", "fL"),
        ("Platelets", "185", "150-400", "K/uL"),
    ],
    "BMP": [
        ("Sodium", "138", "136-145", "mEq/L"),
        ("Potassium", "4.8", "3.5-5.0", "mEq/L"),
        ("Chloride", "102", "98-106", "mEq/L"),
        ("CO2", "22", "23-29", "mEq/L"),
        ("BUN", "52", "7-20", "mg/dL"),
        ("Creatinine", "2.8", "0.7-1.3", "mg/dL"),
        ("Glucose", "126", "70-100", "mg/dL"),
        ("Calcium", "8.8", "8.5-10.5", "mg/dL"),
    ],
    "Renal": [
        ("eGFR", "22", ">60", "mL/min/1.73m2"),
        ("BUN/Creatinine ratio", "18.6", "10-20", ""),
        ("Urine albumin", "850", "<30", "mg/g Cr"),
        ("Urine protein", "1.2", "<0.15", "g/24hr"),
    ],
    "Hepatic": [
        ("AST", "28", "10-40", "U/L"),
        ("ALT", "32", "7-56", "U/L"),
        ("Alkaline phosphatase", "95", "44-147", "U/L"),
        ("Total bilirubin", "0.8", "0.1-1.2", "mg/dL"),
        ("Albumin", "3.4", "3.5-5.0", "g/dL"),
    ],
    "Cardiac": [
        ("BNP", "850", "<100", "pg/mL"),
        ("Troponin I", "<0.03", "<0.04", "ng/mL"),
        ("CK-MB", "2.1", "<5.0", "ng/mL"),
    ],
    "Lipids": [
        ("Total cholesterol", "165", "<200", "mg/dL"),
        ("LDL", "72", "<100", "mg/dL"),
        ("HDL", "38", ">40", "mg/dL"),
        ("Triglycerides", "178", "<150", "mg/dL"),
    ],
    "Diabetes": [
        ("HbA1c", "7.4", "<7.0", "%"),
        ("Fasting glucose", "126", "70-100", "mg/dL"),
        ("C-peptide", "2.1", "0.8-3.1", "ng/mL"),
    ],
    "Thyroid": [
        ("TSH", "2.8", "0.4-4.0", "mIU/L"),
        ("Free T4", "1.1", "0.8-1.8", "ng/dL"),
    ],
    "Iron studies": [
        ("Iron", "55", "60-170", "mcg/dL"),
        ("TIBC", "320", "250-370", "mcg/dL"),
        ("Ferritin", "150", "20-200", "ng/mL"),
        ("Transferrin saturation", "17", "20-50", "%"),
    ],
    "Bone/Mineral": [
        ("Phosphorus", "5.2", "2.5-4.5", "mg/dL"),
        ("PTH", "185", "15-65", "pg/mL"),
        ("Vitamin D, 25-OH", "22", "30-100", "ng/mL"),
        ("Magnesium", "1.8", "1.7-2.2", "mg/dL"),
    ],
    "Coagulation": [
        ("PT", "12.5", "11-13.5", "seconds"),
        ("INR", "1.1", "0.8-1.2", ""),
        ("PTT", "32", "25-35", "seconds"),
    ],
}

# Vital sign variations
VITAL_SIGNS = [
    ("Blood pressure", ["128/78", "134/82", "122/76", "140/88", "118/72"], "mmHg"),
    ("Heart rate", ["72", "68", "78", "84", "66"], "bpm"),
    ("Temperature", ["98.2", "98.6", "99.1", "97.8"], "F"),
    ("Respiratory rate", ["16", "18", "20", "14"], "/min"),
    ("SpO2", ["96", "94", "97", "95", "98"], "%"),
    ("Weight", ["95", "94.5", "96", "93", "92.5"], "kg"),
    ("BMI", ["29.1", "28.9", "29.4", "28.5"], "kg/m2"),
]

# Procedures
PROCEDURES = [
    ("Echocardiogram", "Transthoracic echocardiography", ["LVEF 25%", "LVEF 28%", "moderate MR"]),
    ("ECG", "12-lead electrocardiogram", ["AFib", "NSR", "LAD"]),
    ("Cardiac catheterization", "Coronary angiography", ["3-vessel CAD", "patent grafts"]),
    ("CABG", "Coronary artery bypass grafting", ["x3 vessels", "LIMA to LAD"]),
    ("Stress test", "Pharmacologic stress test", ["negative for ischemia", "mildly positive"]),
    ("Holter monitor", "24-hour ambulatory ECG", ["AFib burden 40%", "rare PVCs"]),
    ("Chest X-ray", "Chest radiograph", ["cardiomegaly", "pulmonary edema", "clear"]),
    ("CT chest", "CT thorax", ["small effusions", "no PE"]),
    ("Renal ultrasound", "Kidney ultrasound", ["bilateral small kidneys", "no hydronephrosis"]),
    ("AV fistula creation", "Arteriovenous fistula surgery", ["left forearm"]),
    ("Dialysis catheter", "Hemodialysis catheter placement", ["right IJ"]),
    ("Eye exam", "Dilated fundoscopic exam", ["mild NPDR", "no DME"]),
    ("Nerve conduction study", "EMG/NCS", ["sensory polyneuropathy"]),
    ("Sleep study", "Polysomnography", ["AHI 28", "moderate OSA"]),
]

# Physical exam findings
EXAM_FINDINGS = [
    # General
    ("General appearance", ["alert and oriented", "no acute distress", "comfortable", "mild distress"]),

    # HEENT
    ("Conjunctivae", ["pale", "normal"]),
    ("JVP", ["8 cm", "10 cm", "elevated", "normal"]),

    # Cardiac
    ("Heart rhythm", ["irregularly irregular", "regular"]),
    ("Heart sounds", ["S1 S2 normal", "S3 present", "S4 present"]),
    ("Murmur", ["II/VI systolic at apex", "III/VI holosystolic", "no murmur"]),

    # Pulmonary
    ("Breath sounds", ["clear", "bibasilar crackles", "decreased at bases", "rales bilateral"]),

    # Abdomen
    ("Abdomen", ["soft, non-tender", "distended", "hepatomegaly"]),

    # Extremities
    ("Edema", ["2+ bilateral LE", "1+ pedal", "trace edema", "no edema"]),
    ("Pulses", ["1+ bilateral", "2+ bilateral", "diminished pedal"]),

    # Neuro
    ("Sensation", ["diminished bilateral feet", "intact", "decreased light touch"]),
    ("Reflexes", ["1+ bilateral", "2+ bilateral", "absent ankle jerks"]),
]


def generate_admission_note(date, conditions, meds):
    """Generate an admission H&P note."""
    selected_conditions = random.sample(conditions, min(8, len(conditions)))
    selected_meds = random.sample(meds, min(12, len(meds)))

    note = f"""
ADMISSION NOTE - {date.strftime('%m/%d/%Y')}

CHIEF COMPLAINT: Shortness of breath, lower extremity swelling

HISTORY OF PRESENT ILLNESS:
{PATIENT['age']}-year-old {PATIENT['sex'].lower()} with history of {', '.join([c[0] for c in selected_conditions[:4]])}
presenting with worsening dyspnea on exertion and bilateral lower extremity edema x 3 days.
Patient reports orthopnea, requiring 3 pillows to sleep. Denies chest pain, palpitations, or syncope.
Reports medication compliance. Weight has increased 5 lbs over the past week.

PAST MEDICAL HISTORY:
{chr(10).join(['- ' + c[0] + (' (' + random.choice(c[2]) + ')' if c[2] else '') for c in selected_conditions])}

PAST SURGICAL HISTORY:
- CABG x3 (2019)
- Appendectomy (1995)

MEDICATIONS ON ADMISSION:
{chr(10).join(['- ' + m[0] + ' ' + m[1] + ' ' + m[2] for m in selected_meds])}

ALLERGIES: Penicillin (rash), Sulfa (hives)

SOCIAL HISTORY:
- Former smoker (30 pack-years, quit 10 years ago)
- Occasional alcohol
- Retired accountant
- Lives with wife

FAMILY HISTORY:
- Father: MI at age 58, deceased
- Mother: Type 2 diabetes, hypertension
- Brother: Coronary artery disease

REVIEW OF SYSTEMS:
Constitutional: Fatigue, no fever
Cardiovascular: Dyspnea, orthopnea, PND, edema; denies chest pain
Respiratory: Dyspnea; denies cough, hemoptysis
GI: No nausea, vomiting, or abdominal pain
GU: Nocturia x3; no dysuria
Neuro: Numbness bilateral feet; no weakness
Psych: Mild depression; no SI

VITAL SIGNS:
BP {random.choice(['142/88', '138/84', '128/78'])} mmHg
HR {random.choice(['78', '84', '72'])} bpm (irregular)
Temp 98.4 F
RR {random.choice(['18', '20', '16'])} /min
SpO2 {random.choice(['94', '93', '95'])}% on RA
Weight 97 kg (baseline 92 kg)

PHYSICAL EXAMINATION:
General: Alert, mild respiratory distress
HEENT: NCAT, conjunctivae pale, JVP elevated to 12 cm
Cardiovascular: Irregularly irregular rhythm, III/VI holosystolic murmur at apex
Pulmonary: Bibasilar crackles, no wheezes
Abdomen: Soft, non-tender, no hepatomegaly
Extremities: 3+ bilateral pitting edema to knees, warm
Neuro: Alert and oriented x3, diminished sensation bilateral feet
Skin: No rashes

LABORATORY DATA:
Na 136, K 5.1, Cl 100, CO2 20, BUN 58, Cr 3.0, Glucose 142
WBC 7.2, Hgb 9.8, Hct 30, Plt 175
BNP 1250, Troponin <0.03
PT 13.2, INR 1.1

ECG: Atrial fibrillation with RVR (rate 108), LAD, LAFB, old anterolateral infarct

CXR: Cardiomegaly, bilateral pleural effusions, pulmonary vascular congestion

ASSESSMENT AND PLAN:

1. Acute on chronic systolic heart failure exacerbation (HFrEF, EF 25%)
   - IV furosemide 80 mg BID
   - Daily weights, strict I/O
   - Fluid restriction 1.5L/day
   - Sodium restriction <2g/day
   - Continue carvedilol, lisinopril, spironolactone
   - Echo in AM

2. Atrial fibrillation with RVR
   - Rate control with IV diltiazem
   - Continue anticoagulation (apixaban)
   - Consider cardioversion if persistent

3. CKD Stage 4 (baseline Cr 2.8)
   - AKI superimposed (Cr 3.0)
   - Hold metformin
   - Avoid nephrotoxins
   - Renal diet

4. Type 2 diabetes
   - Sliding scale insulin
   - Hold metformin for AKI
   - Continue basal insulin at reduced dose

5. Anemia of chronic disease
   - Hgb 9.8, baseline ~10
   - Check iron studies, reticulocyte count

6. DVT prophylaxis: On therapeutic anticoagulation

Admitting to telemetry floor.
"""
    return note


def generate_progress_note(date, day_number, conditions, meds):
    """Generate a daily progress note."""
    selected_conditions = random.sample(conditions, min(5, len(conditions)))

    note = f"""
PROGRESS NOTE - Hospital Day #{day_number} - {date.strftime('%m/%d/%Y')}

SUBJECTIVE:
Patient reports {random.choice(['improved breathing', 'mild dyspnea with ambulation', 'feeling better'])}.
{random.choice(['Slept well last night.', 'Some difficulty sleeping due to nocturia.', 'Required PRN trazodone for sleep.'])}
{random.choice(['Appetite improved.', 'Eating 50% of meals.', 'Poor appetite.'])}
{random.choice(['Denies chest pain.', 'No chest discomfort.'])}
{random.choice(['No palpitations.', 'Occasional palpitations.'])}

OBJECTIVE:
Vitals: BP {random.choice(['128/76', '132/80', '124/74'])} | HR {random.choice(['72', '68', '78'])} | T 98.2 | RR {random.choice(['16', '18'])} | SpO2 {random.choice(['95', '96', '97'])}% RA
Weight: {random.choice(['95', '94', '93', '92'])} kg ({random.choice(['-1 kg', '-2 kg', '-0.5 kg'])} from yesterday)
I/O: {random.choice(['2100/2800', '1800/2500', '2000/3000'])} mL

Physical Exam:
- General: {random.choice(['Comfortable', 'No acute distress', 'Resting comfortably'])}
- CV: {random.choice(['Irregularly irregular', 'Regular rhythm'])}, {random.choice(['II/VI systolic murmur', 'soft systolic murmur'])}
- Lungs: {random.choice(['Bibasilar crackles improved', 'Clear to auscultation', 'Faint crackles bilateral bases'])}
- Ext: {random.choice(['1+ bilateral LE edema', '2+ bilateral LE edema improved from 3+', 'trace pedal edema'])}

Labs ({date.strftime('%m/%d')}):
Na {random.choice(['138', '140', '136'])}, K {random.choice(['4.5', '4.8', '4.2'])}, Cr {random.choice(['2.7', '2.6', '2.8'])} (trending {random.choice(['down', 'stable'])})
BNP {random.choice(['950', '850', '1050'])} (down from {random.choice(['1250', '1100'])})
Hgb {random.choice(['10.0', '9.8', '10.2'])}

ASSESSMENT/PLAN:

1. HFrEF exacerbation - Improving
   - Continue IV diuresis, transition to PO furosemide 60 mg BID today
   - Net negative goal 1-1.5L/day
   - Daily weights continue
   - Echo yesterday showed EF {random.choice(['25%', '28%', '30%'])}

2. Atrial fibrillation - Rate controlled
   - HR 70s on carvedilol
   - Continue apixaban

3. CKD Stage 4 with AKI - Improving
   - Cr improving to {random.choice(['2.7', '2.6'])}
   - Continue to hold metformin

4. Type 2 diabetes - Controlled
   - Sugars 120-180 on current regimen
   - Continue basal-bolus insulin

5. Anemia - Stable
   - Iron studies pending
   - Continue ferrous sulfate

Disposition: Continue current management. Target discharge in {random.choice(['1-2 days', '2-3 days'])} if diuresis goals met.
"""
    return note


def generate_discharge_summary(admit_date, discharge_date, conditions, meds):
    """Generate a discharge summary."""
    los = (discharge_date - admit_date).days
    selected_meds = random.sample(meds, min(15, len(meds)))

    note = f"""
DISCHARGE SUMMARY

PATIENT: {PATIENT['name']}
MRN: {PATIENT['id']}
ADMIT DATE: {admit_date.strftime('%m/%d/%Y')}
DISCHARGE DATE: {discharge_date.strftime('%m/%d/%Y')}
LENGTH OF STAY: {los} days
ATTENDING: Dr. Smith, Cardiology

PRINCIPAL DIAGNOSIS:
Acute on chronic systolic heart failure exacerbation

SECONDARY DIAGNOSES:
- Heart failure with reduced ejection fraction (HFrEF), EF 28%
- Atrial fibrillation, persistent
- Coronary artery disease, s/p CABG x3 (2019)
- Chronic kidney disease, stage 4, eGFR 22
- Type 2 diabetes mellitus with diabetic nephropathy
- Hypertension
- Hyperlipidemia
- Obstructive sleep apnea on CPAP
- Anemia of chronic disease
- Peripheral neuropathy

HOSPITAL COURSE:

The patient is a {PATIENT['age']}-year-old male with the above medical history who presented with
worsening dyspnea on exertion, orthopnea, and bilateral lower extremity edema.

On admission, he was found to be in decompensated heart failure with elevated BNP (1250),
pulmonary congestion on CXR, and volume overload on exam. He was also noted to have AKI
with creatinine elevated to 3.0 from baseline of 2.8.

Hospital course:
- Aggressive IV diuresis with furosemide achieved 8 kg weight loss
- Echocardiogram showed LVEF 28%, moderate MR, elevated RVSP
- AKI resolved with diuresis
- Rate controlled AF on carvedilol
- Diabetes managed with insulin
- Hemoglobin stable around 10

He responded well to diuresis with resolution of symptoms, improved oxygenation,
and return of creatinine to baseline.

DISCHARGE MEDICATIONS:
{chr(10).join(['- ' + m[0] + ' ' + m[1] + ' ' + m[2] for m in selected_meds])}

ALLERGIES: Penicillin (rash), Sulfonamides (hives)

DISCHARGE CONDITION: Stable, improved

DISCHARGE INSTRUCTIONS:
1. Daily weights - call if gain >3 lbs
2. Fluid restriction 1.5L/day
3. Low sodium diet (<2g/day)
4. CPAP every night
5. Follow up appointments as scheduled
6. Return to ED for worsening shortness of breath, chest pain, fever

FOLLOW-UP:
- Cardiology: Dr. Jones, 1 week
- Nephrology: Dr. Brown, 2 weeks
- PCP: Dr. Wilson, 1 week
- Lab work (BMP, CBC) in 3 days

DISCHARGE VITALS:
BP 124/74 mmHg, HR 68 bpm, SpO2 97% on RA, Weight 89 kg
"""
    return note


def generate_specialty_consult(date, specialty, conditions):
    """Generate a specialty consultation note."""

    consults = {
        "Nephrology": f"""
NEPHROLOGY CONSULTATION - {date.strftime('%m/%d/%Y')}

REASON FOR CONSULTATION: CKD stage 4 management, AKI

HISTORY:
{PATIENT['age']}M with CKD stage 4 (baseline Cr 2.5-2.8), HFrEF, T2DM with nephropathy, HTN.
Admitted with heart failure exacerbation, found to have AKI with Cr 3.0.

RENAL HISTORY:
- CKD attributed to diabetic nephropathy and hypertensive nephrosclerosis
- Baseline Cr 2.5-2.8, eGFR 20-25
- Urine albumin/creatinine ratio 850 mg/g (A3 category)
- GFR declining ~3-4 mL/min/year
- Not yet on dialysis

CURRENT LABS:
Cr {random.choice(['2.8', '2.7', '2.9'])}, BUN 52, eGFR 22
K 4.8, Phos 5.2, Ca 8.8
PTH 185, Vitamin D 22
Hgb 10.2, Ferritin 150, TSAT 17%

URINALYSIS: 2+ protein, bland sediment

ASSESSMENT:
1. CKD stage 4 G4 A3 - mixed diabetic/hypertensive etiology
   - AKI resolved (likely cardiorenal)
   - Progressive, approaching ESRD

2. Secondary hyperparathyroidism
   - PTH 185, elevated
   - Phosphorus elevated
   - Vitamin D insufficient

3. Anemia of CKD
   - Functional iron deficiency (low TSAT)
   - May need ESA soon

RECOMMENDATIONS:
1. Continue ACEi - renal protective despite CKD4
2. Add calcitriol 0.25 mcg daily
3. Increase ergocalciferol to 50,000 IU weekly x8 weeks
4. Start sevelamer 800 mg TID with meals
5. IV iron x3 doses then reassess
6. Initiate dialysis education
7. Schedule AV fistula creation (left arm preferred)
8. Renal diet counseling - low phosphorus, potassium watch
9. Follow-up in 2 weeks

Will continue to follow.
""",
        "Cardiology": f"""
CARDIOLOGY CONSULTATION - {date.strftime('%m/%d/%Y')}

REASON FOR CONSULTATION: Heart failure management

HPI:
{PATIENT['age']}M with HFrEF (EF 25-28%), CAD s/p CABG, AFib, HTN, DM2 admitted with
acute decompensated heart failure. Presented with progressive dyspnea, orthopnea, and
bilateral LE edema x 1 week. Reports dietary indiscretion and missed diuretic doses.

CARDIAC HISTORY:
- HFrEF diagnosed 2018, EF 25-28%
- CAD: 3-vessel disease, s/p CABG x3 (2019) - LIMA to LAD, SVG to OM, SVG to RCA
- Atrial fibrillation, persistent since 2020
- ICD considered but deferred due to patient preference

ECHO TODAY:
- LVEF 28% (improved from 25%)
- Moderate mitral regurgitation
- Mild tricuspid regurgitation
- RVSP 45 mmHg
- No pericardial effusion

ECG: Atrial fibrillation, rate 72, LAD, LAFB, old anterior infarct

MEDICATIONS:
- Carvedilol 25 mg BID
- Sacubitril-valsartan 49/51 mg BID (switched from lisinopril)
- Spironolactone 25 mg daily
- Furosemide 60 mg BID (increased)
- Apixaban 5 mg BID
- Atorvastatin 80 mg QHS

ASSESSMENT:
1. HFrEF, EF 28% - GDMT optimized
2. CAD s/p CABG - stable
3. AFib - well rate-controlled, anticoagulated

RECOMMENDATIONS:
1. Continue ARNI (transitioned from ACEi)
2. Continue beta-blocker at current dose
3. Continue MRA
4. Diuretics as needed for euvolemia
5. Consider CRT-D evaluation given EF <35%, LBBB
6. Cardiac rehab referral
7. Follow-up in clinic 2 weeks

Thank you for this consultation.
""",
        "Endocrinology": f"""
ENDOCRINOLOGY CONSULTATION - {date.strftime('%m/%d/%Y')}

REASON FOR CONSULTATION: Diabetes management in setting of CKD

HPI:
{PATIENT['age']}M with T2DM x 15 years complicated by nephropathy (CKD4), neuropathy.
Also with HFrEF, CAD. Admitted for HF exacerbation. A1c 7.4%.

DIABETES HISTORY:
- Dx 2011, initially on metformin
- Added basal insulin 2018
- Complications: nephropathy (CKD4), neuropathy (bilateral feet)
- Last dilated eye exam: mild NPDR

CURRENT REGIMEN:
- Metformin 500 mg BID (on hold for AKI)
- Glargine 20 units QHS
- Lispro sliding scale

HOME GLUCOSE LOG (per patient):
- Fasting: 110-140
- Pre-dinner: 120-160

TODAY'S LABS:
HbA1c 7.4%, Fasting glucose 126, C-peptide 2.1

PHYSICAL EXAM:
BMI 29.1
Foot exam: Diminished monofilament sensation bilateral feet
Pedal pulses: 1+ bilateral

ASSESSMENT:
1. T2DM, moderately controlled, A1c 7.4%
   - At goal given comorbidities (HFrEF, CKD4)
   - Multiple complications

2. Diabetic nephropathy, CKD stage 4
   - On ACEi

3. Diabetic peripheral neuropathy
   - On gabapentin

RECOMMENDATIONS:
1. Discontinue metformin permanently given eGFR <25
2. Increase glargine to 24 units QHS
3. Continue mealtime sliding scale
4. Consider GLP-1 agonist (dulaglutide) - beneficial for CV and renal
5. Gabapentin 300 mg TID for neuropathy
6. Annual dilated eye exam - due
7. Monofilament testing q visit
8. Podiatry referral for foot care
9. Follow-up in 4-6 weeks

Will continue to follow.
"""
    }

    return consults.get(specialty, "Consultation note not available.")


def generate_lab_report(date, panels):
    """Generate a lab report."""
    selected_panels = random.sample(list(panels.keys()), min(4, len(panels)))

    note = f"""
LABORATORY REPORT - {date.strftime('%m/%d/%Y %H:%M')}

PATIENT: {PATIENT['name']}
MRN: {PATIENT['id']}

"""
    for panel in selected_panels:
        note += f"\n{panel.upper()}:\n"
        for test_name, value, ref_range, unit in panels[panel]:
            # Add some random variation
            try:
                base_val = float(value)
                varied_val = base_val * random.uniform(0.95, 1.05)
                if '.' in value:
                    display_val = f"{varied_val:.1f}"
                else:
                    display_val = str(int(varied_val))
            except:
                display_val = value

            # Determine if high/low
            flag = ""
            try:
                if '-' in ref_range:
                    low, high = ref_range.split('-')
                    if float(display_val) < float(low):
                        flag = " [LOW]"
                    elif float(display_val) > float(high):
                        flag = " [HIGH]"
                elif '>' in ref_range:
                    threshold = float(ref_range.replace('>', ''))
                    if float(display_val) < threshold:
                        flag = " [LOW]"
                elif '<' in ref_range:
                    threshold = float(ref_range.replace('<', ''))
                    if float(display_val) > threshold:
                        flag = " [HIGH]"
            except:
                pass

            note += f"  {test_name}: {display_val} {unit} (ref: {ref_range}){flag}\n"

    return note


def generate_imaging_report(date, imaging_type):
    """Generate an imaging report."""

    reports = {
        "Echo": f"""
ECHOCARDIOGRAM REPORT - {date.strftime('%m/%d/%Y')}

INDICATION: Heart failure, assess LV function

TECHNIQUE: Complete 2D and Doppler transthoracic echocardiogram

FINDINGS:

LEFT VENTRICLE:
- LV size: Moderately dilated (LVEDV 180 mL, LVESV 130 mL)
- LV systolic function: Severely reduced
- LVEF: {random.choice(['25%', '28%', '30%'])} (Simpson's biplane)
- Regional wall motion: Global hypokinesis, akinesis of anterior wall
- LV mass: Increased (LVH)

RIGHT VENTRICLE:
- RV size: Mildly dilated
- RV systolic function: Mildly reduced
- TAPSE: 16 mm

ATRIA:
- Left atrium: Moderately dilated (LA volume index 42 mL/m2)
- Right atrium: Mildly dilated

VALVES:
- Mitral valve: Moderate mitral regurgitation (MR), functional
- Aortic valve: Sclerotic, no stenosis, trace AR
- Tricuspid valve: Mild tricuspid regurgitation
- Pulmonic valve: Normal

PULMONARY PRESSURES:
- RVSP: {random.choice(['42', '45', '48'])} mmHg (mildly elevated)

PERICARDIUM: No effusion

IVC: Dilated (2.2 cm), <50% collapse with inspiration

IMPRESSION:
1. Severely reduced LV systolic function, LVEF {random.choice(['25%', '28%', '30%'])}
2. Moderate mitral regurgitation, functional
3. Mild tricuspid regurgitation
4. Mildly elevated pulmonary pressures
5. Dilated IVC suggesting elevated RA pressure
""",
        "CXR": f"""
CHEST RADIOGRAPH - {date.strftime('%m/%d/%Y')}

INDICATION: Shortness of breath, heart failure

TECHNIQUE: PA and lateral chest radiographs

COMPARISON: {(date - timedelta(days=random.randint(30, 90))).strftime('%m/%d/%Y')}

FINDINGS:

LUNGS:
- {random.choice(['Bilateral interstitial edema', 'Mild pulmonary vascular congestion', 'Improved pulmonary edema'])}
- {random.choice(['Small bilateral pleural effusions', 'Trace bilateral pleural effusions', 'No pleural effusion'])}
- No focal consolidation
- No pneumothorax

HEART:
- Cardiomegaly (cardiothoracic ratio 0.58)
- {random.choice(['Stable', 'Unchanged', 'Mildly improved'])} compared to prior

MEDIASTINUM:
- No mediastinal widening
- Sternotomy wires intact
- Median sternotomy changes noted

BONES:
- Degenerative changes thoracic spine
- No acute osseous abnormality

IMPRESSION:
1. Cardiomegaly, stable
2. {random.choice(['Mild pulmonary vascular congestion', 'Improved pulmonary edema', 'Residual interstitial edema'])}
3. {random.choice(['Small bilateral pleural effusions', 'Trace effusions, improved'])}
4. Post-CABG changes
"""
    }

    return reports.get(imaging_type, "Report not available.")


def generate_all_notes(patient_id):
    """Generate a comprehensive set of clinical notes."""
    notes = []

    # Start date for the hospitalization
    base_date = datetime(2026, 1, 10)

    # Admission note
    notes.append(generate_admission_note(base_date, CONDITIONS, MEDICATIONS))

    # Daily progress notes (5 days)
    for day in range(1, 6):
        notes.append(generate_progress_note(
            base_date + timedelta(days=day),
            day,
            CONDITIONS,
            MEDICATIONS
        ))

    # Specialty consults
    notes.append(generate_specialty_consult(base_date + timedelta(days=1), "Nephrology", CONDITIONS))
    notes.append(generate_specialty_consult(base_date + timedelta(days=1), "Cardiology", CONDITIONS))
    notes.append(generate_specialty_consult(base_date + timedelta(days=2), "Endocrinology", CONDITIONS))

    # Discharge summary
    notes.append(generate_discharge_summary(
        base_date,
        base_date + timedelta(days=5),
        CONDITIONS,
        MEDICATIONS
    ))

    # Lab reports (multiple over hospitalization)
    for day in [0, 1, 2, 3, 5]:
        notes.append(generate_lab_report(base_date + timedelta(days=day), LAB_PANELS))

    # Imaging reports
    notes.append(generate_imaging_report(base_date + timedelta(days=1), "Echo"))
    notes.append(generate_imaging_report(base_date, "CXR"))
    notes.append(generate_imaging_report(base_date + timedelta(days=3), "CXR"))

    # Prior outpatient notes (to simulate longitudinal record)
    for months_back in [1, 3, 6]:
        prior_date = base_date - timedelta(days=30*months_back)
        notes.append(f"""
OUTPATIENT CARDIOLOGY NOTE - {prior_date.strftime('%m/%d/%Y')}

{PATIENT['age']}M with HFrEF (EF 25-28%), AFib, CAD s/p CABG, CKD4, T2DM here for routine follow-up.

SUBJECTIVE:
Patient reports NYHA Class II-III symptoms. DOE with 1-2 blocks walking.
{random.choice(['Denies PND or orthopnea.', 'Occasional 2-pillow orthopnea.'])}
{random.choice(['Weight stable.', 'Weight up 2 lbs.'])}
{random.choice(['Compliant with medications.', 'Admits missing occasional diuretic doses.'])}
Using CPAP nightly.

VITALS: BP {random.choice(['128/78', '132/82', '126/76'])} | HR {random.choice(['68', '72', '74'])} | SpO2 {random.choice(['96', '97'])}% | Wt {random.choice(['92', '93', '94'])} kg

EXAM:
- JVP: {random.choice(['8 cm', '10 cm'])}
- Lungs: {random.choice(['Clear', 'Faint bibasilar crackles'])}
- Cardiac: Irregular, {random.choice(['II/VI', 'III/VI'])} systolic murmur
- Ext: {random.choice(['Trace pedal edema', '1+ bilateral LE edema', 'No edema'])}

LABS: Cr {random.choice(['2.6', '2.7', '2.8'])}, K {random.choice(['4.5', '4.7', '4.9'])}, BNP {random.choice(['650', '720', '800'])}

ASSESSMENT/PLAN:
1. HFrEF - Stable, continue GDMT
2. AFib - Well controlled, continue anticoagulation
3. CKD4 - Stable, continue to follow with nephrology

Follow-up 3 months.
""")

    # Prior nephrology notes
    notes.append(f"""
NEPHROLOGY OUTPATIENT NOTE - {(base_date - timedelta(days=60)).strftime('%m/%d/%Y')}

CKD Stage 4 (G4 A3), Diabetic Nephropathy

{PATIENT['age']}M with progressive CKD attributed to diabetic nephropathy and hypertensive
nephrosclerosis. eGFR declining ~3-4 mL/min/year.

CURRENT LABS:
Cr 2.7, eGFR 24, BUN 48
K 4.6, Phos 4.8, Ca 8.9
PTH 165, Vitamin D 25
Hgb 10.4, Ferritin 180, TSAT 20%
Urine alb/cr 820 mg/g

ASSESSMENT:
1. CKD Stage 4 - Progressing, approaching ESRD
2. Secondary hyperparathyroidism - PTH improving on calcitriol
3. Anemia of CKD - Stable on iron

PLAN:
1. Continue ACEi for renal protection
2. Continue calcitriol, phosphate binder
3. Check AV fistula maturation
4. Dialysis education ongoing
5. Follow-up 2 months

Estimated dialysis initiation: 6-12 months
""")

    # Prior endocrine notes
    notes.append(f"""
ENDOCRINOLOGY OUTPATIENT NOTE - {(base_date - timedelta(days=90)).strftime('%m/%d/%Y')}

Type 2 Diabetes Mellitus

{PATIENT['age']}M with T2DM x 15 years, complicated by nephropathy (CKD4), neuropathy.

DIABETES REVIEW:
- A1c: 7.6% (previous 7.8%)
- Home glucoses: Fasting 110-140, Pre-dinner 130-170
- Hypoglycemia: None reported

CURRENT REGIMEN:
- Metformin 500 mg BID
- Glargine 18 units QHS
- PRN lispro sliding scale

COMPLICATIONS:
- Nephropathy: CKD Stage 4
- Neuropathy: Bilateral feet, on gabapentin
- Retinopathy: Mild NPDR, stable

EXAM:
- BMI 29.4
- Foot exam: Diminished sensation, calluses
- Pedal pulses present

PLAN:
1. Increase glargine to 20 units
2. Continue metformin (watch with declining eGFR)
3. Gabapentin 300 mg TID for neuropathy
4. Annual eye exam due
5. Follow-up 3 months
""")

    return notes


if __name__ == "__main__":
    notes = generate_all_notes("TEST12345")

    print(f"Generated {len(notes)} clinical notes")

    # Save to file
    output_file = "generated_clinical_notes.json"
    with open(output_file, 'w') as f:
        json.dump(notes, f, indent=2)

    print(f"Notes saved to {output_file}")

    # Print sample
    print("\n" + "="*50)
    print("Sample note (first admission note):")
    print("="*50)
    print(notes[0][:2000] + "...")
