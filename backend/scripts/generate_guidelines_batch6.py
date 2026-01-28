#!/usr/bin/env python3
"""Batch 6: ~250 sections targeting underrepresented specialties.

Focuses on Psychiatry, Pediatrics, Surgery, Neurology, Anesthesiology,
Radiology, Orthopedics, Ophthalmology, Dermatology, Urology, ENT, OB/GYN.
"""

import json, os, hashlib

def _id(guideline, title):
    raw = f"{guideline}|{title}"
    h = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"b6-{h}"

# (guideline, society, year, title, text, grade, strength, conditions, meds, measurements, keywords)
SECTIONS = [
    # ══════════════════════════════════════════
    # PSYCHIATRY EXPANSION (~30)
    # ══════════════════════════════════════════
    ("APA Generalized Anxiety Disorder Guidelines", "APA", 2024,
     "GAD First-Line Pharmacotherapy",
     "SSRIs (sertraline, escitalopram) or SNRIs (duloxetine, venlafaxine) as first-line. Start low, titrate over 2-4 weeks. Assess response at 4-6 weeks. If partial response, optimize dose before switching. Buspirone as alternative or augmentation.",
     "A", "Strong", ["generalized anxiety disorder"], ["sertraline", "escitalopram", "duloxetine", "venlafaxine", "buspirone"], ["gad-7", "ham-a"], ["anxiety", "ssri", "snri", "gad"]),

    ("APA Generalized Anxiety Disorder Guidelines", "APA", 2024,
     "GAD Psychotherapy",
     "CBT is the first-line psychotherapy for GAD. Structured CBT over 12-16 sessions. Combination CBT + pharmacotherapy may be superior to either alone. Mindfulness-based stress reduction as adjunct. Acceptance and commitment therapy as alternative.",
     "A", "Strong", ["generalized anxiety disorder"], [], ["gad-7"], ["anxiety", "cbt", "psychotherapy"]),

    ("APA Panic Disorder Guidelines", "APA", 2024,
     "Panic Disorder Treatment",
     "SSRIs first-line pharmacotherapy (paroxetine, sertraline, fluoxetine FDA-approved). CBT with interoceptive exposure is first-line psychotherapy. Benzodiazepines only short-term for acute symptom relief; high risk of dependence. Avoid caffeine and stimulants.",
     "A", "Strong", ["panic disorder", "panic attacks"], ["paroxetine", "sertraline", "fluoxetine", "alprazolam", "clonazepam"], ["phq-9", "panic disorder severity scale"], ["panic disorder", "ssri", "cbt", "exposure therapy"]),

    ("APA Social Anxiety Disorder Guidelines", "APA", 2024,
     "Social Anxiety Disorder Pharmacotherapy",
     "SSRIs (paroxetine, sertraline) and venlafaxine XR are first-line. Phenelzine effective but dietary restrictions limit use. PRN beta-blockers (propranolol) for performance-only subtype. Duration of treatment at least 12 months after response.",
     "A", "Strong", ["social anxiety disorder", "social phobia"], ["paroxetine", "sertraline", "venlafaxine", "propranolol"], ["liebowitz social anxiety scale"], ["social anxiety", "ssri", "beta-blocker"]),

    ("VA/DoD PTSD Guidelines", "VA/DoD", 2023,
     "PTSD First-Line Treatment",
     "Trauma-focused psychotherapy recommended over pharmacotherapy as initial treatment: CPT, PE, or EMDR. If pharmacotherapy needed: sertraline or paroxetine (FDA-approved). Venlafaxine as alternative. Prazosin for trauma-related nightmares (alpha-1 antagonist). Avoid benzodiazepines.",
     "A", "Strong", ["ptsd", "post-traumatic stress disorder"], ["sertraline", "paroxetine", "venlafaxine", "prazosin"], ["pcl-5", "caps-5"], ["ptsd", "trauma", "cpt", "emdr", "prazosin"]),

    ("VA/DoD PTSD Guidelines", "VA/DoD", 2023,
     "PTSD Comorbidity Management",
     "Screen for comorbid depression, substance use, and TBI. Treat comorbid depression with SSRI (effective for both). Integrated treatment for co-occurring PTSD and substance use. Sleep disturbances common; CBT-I preferred over sedative-hypnotics. Chronic pain: avoid opioids; use duloxetine or gabapentin.",
     "B", "Strong", ["ptsd", "comorbid depression", "substance use disorder"], ["sertraline", "duloxetine", "gabapentin"], ["phq-9", "audit-c", "pcl-5"], ["ptsd", "comorbidity", "depression", "substance use"]),

    ("APA Schizophrenia Guidelines", "APA", 2024,
     "Schizophrenia First Episode",
     "Second-generation antipsychotics (SGAs) preferred for first episode: risperidone, aripiprazole, or paliperidone. Start at low doses and titrate slowly. CBT for psychosis as adjunct. Supported employment and education. Family psychoeducation. Continue treatment for at least 1-2 years after first episode.",
     "A", "Strong", ["schizophrenia", "first episode psychosis"], ["risperidone", "aripiprazole", "paliperidone"], ["panss", "bprs", "cgi"], ["schizophrenia", "first episode", "antipsychotic", "psychosis"]),

    ("APA Schizophrenia Guidelines", "APA", 2024,
     "Treatment-Resistant Schizophrenia",
     "Clozapine is the only evidence-based treatment for treatment-resistant schizophrenia (failure of 2 adequate antipsychotic trials). REMS program required: weekly WBC/ANC monitoring for 6 months, biweekly for 6 months, then monthly. Monitor for metabolic syndrome, seizures, myocarditis, and agranulocytosis.",
     "A", "Strong", ["treatment-resistant schizophrenia"], ["clozapine"], ["wbc", "anc", "fasting glucose", "lipid panel", "ecg"], ["clozapine", "treatment resistant", "agranulocytosis", "rems"]),

    ("APA Schizophrenia Guidelines", "APA", 2024,
     "Long-Acting Injectable Antipsychotics",
     "LAIs recommended for patients with poor adherence or patient preference. Paliperidone palmitate monthly or 3-monthly, aripiprazole lauroxil monthly or bimonthly. Overlap with oral formulation during initiation. Monitor injection site reactions. LAIs may reduce relapse and hospitalization rates.",
     "A", "Strong", ["schizophrenia", "medication adherence"], ["paliperidone palmitate", "aripiprazole lauroxil", "haloperidol decanoate"], ["panss"], ["long-acting injectable", "lai", "adherence", "schizophrenia"]),

    ("APA Bipolar Disorder Guidelines", "APA", 2024,
     "Bipolar Mania Acute Treatment",
     "Lithium or valproate as first-line mood stabilizers. Second-generation antipsychotics (quetiapine, aripiprazole, olanzapine) as alternatives or augmentation. Avoid antidepressant monotherapy. Combination therapy often needed. ECT for severe/refractory mania. Hold and taper off antidepressants.",
     "A", "Strong", ["bipolar disorder", "mania"], ["lithium", "valproate", "quetiapine", "aripiprazole", "olanzapine"], ["lithium level", "valproate level", "cbc", "metabolic panel"], ["bipolar", "mania", "lithium", "mood stabilizer"]),

    ("APA Bipolar Disorder Guidelines", "APA", 2024,
     "Bipolar Depression Treatment",
     "Quetiapine monotherapy or lurasidone + lithium/valproate as first-line. Lamotrigine for maintenance prevention of bipolar depression. Cariprazine approved for bipolar I depression. Avoid antidepressant monotherapy (risk of switch to mania). Lithium augmentation if partial response.",
     "A", "Strong", ["bipolar depression"], ["quetiapine", "lurasidone", "lamotrigine", "cariprazine", "lithium"], ["lithium level", "phq-9", "metabolic panel"], ["bipolar depression", "quetiapine", "lamotrigine"]),

    ("APA Bipolar Disorder Guidelines", "APA", 2024,
     "Bipolar Maintenance Therapy",
     "Lithium is gold standard for long-term maintenance: reduces relapse, suicide risk. Target trough 0.6-0.8 mEq/L. Monitor renal function, thyroid, calcium every 6 months. Valproate or lamotrigine as alternatives. SGAs (quetiapine, aripiprazole) for adjunctive maintenance.",
     "A", "Strong", ["bipolar disorder maintenance"], ["lithium", "valproate", "lamotrigine", "quetiapine"], ["lithium level", "tsh", "creatinine", "calcium"], ["bipolar", "maintenance", "lithium monitoring"]),

    ("APA Personality Disorders Guidelines", "APA", 2024,
     "Borderline Personality Disorder Treatment",
     "Dialectical behavior therapy (DBT) is the most evidence-based psychotherapy for BPD. Mentalization-based therapy (MBT) and schema-focused therapy as alternatives. No FDA-approved medications; symptom-targeted pharmacotherapy only. Low-dose antipsychotics or mood stabilizers for affective dysregulation. Avoid benzodiazepines and polypharmacy.",
     "A", "Strong", ["borderline personality disorder"], ["quetiapine", "lamotrigine", "topiramate"], ["phq-9", "borderline symptom list"], ["bpd", "dbt", "personality disorder"]),

    ("AASM Insomnia Guidelines", "AASM", 2024,
     "Chronic Insomnia First-Line Treatment",
     "CBT-I is first-line treatment for chronic insomnia (superior to pharmacotherapy long-term). Includes sleep restriction, stimulus control, cognitive restructuring, sleep hygiene, relaxation training. Digital CBT-I acceptable alternative. Pharmacotherapy when CBT-I unavailable or insufficient.",
     "A", "Strong", ["chronic insomnia", "insomnia disorder"], [], ["isi", "sleep diary", "actigraphy"], ["insomnia", "cbt-i", "sleep restriction"]),

    ("AASM Insomnia Guidelines", "AASM", 2024,
     "Insomnia Pharmacotherapy",
     "If pharmacotherapy needed: orexin receptor antagonists (suvorexant, lemborexant) preferred for sleep maintenance. Low-dose doxepin for sleep maintenance insomnia. Z-drugs (zolpidem, eszopiclone) for short-term use only. Avoid benzodiazepines in elderly. Melatonin limited evidence in adults.",
     "B", "Moderate", ["insomnia"], ["suvorexant", "lemborexant", "doxepin", "zolpidem", "eszopiclone"], ["isi", "sleep study"], ["insomnia", "orexin antagonist", "sleep medication"]),

    ("APA Delirium Guidelines", "APA", 2024,
     "Delirium Prevention and Management",
     "Non-pharmacologic prevention: reorientation, sleep-wake cycle preservation, mobilization, hydration, avoid deliriogenic medications (anticholinergics, benzodiazepines). No evidence for pharmacologic prophylaxis. Treat underlying cause. Haloperidol or quetiapine for severe agitation only. Avoid physical restraints.",
     "B", "Strong", ["delirium", "acute confusion"], ["haloperidol", "quetiapine"], ["cam", "cam-icu", "4at"], ["delirium", "confusion", "haloperidol", "prevention"]),

    ("APA ECT Guidelines", "APA", 2024,
     "Electroconvulsive Therapy Indications",
     "ECT for treatment-resistant depression (failed 2+ adequate trials), severe depression with psychotic features, catatonia, acute suicidality, and bipolar mania unresponsive to medications. Bilateral electrode placement more effective. Brief-pulse preferred. Continuation ECT or maintenance pharmacotherapy to prevent relapse.",
     "A", "Strong", ["treatment-resistant depression", "psychotic depression", "catatonia"], [], ["phq-9", "ham-d", "ecg"], ["ect", "treatment resistant depression", "electroconvulsive"]),

    ("APA Tardive Dyskinesia Guidelines", "APA", 2024,
     "Tardive Dyskinesia Management",
     "VMAT2 inhibitors (valbenazine, deutetrabenazine) are first-line treatment for TD. Reduce or switch causative antipsychotic if clinically feasible. Monitor with AIMS scale every 3-6 months. Clozapine has lowest risk of TD. Do not use anticholinergics for TD.",
     "A", "Strong", ["tardive dyskinesia"], ["valbenazine", "deutetrabenazine", "clozapine"], ["aims score"], ["tardive dyskinesia", "vmat2", "aims", "antipsychotic"]),

    # ══════════════════════════════════════════
    # PEDIATRICS EXPANSION (~30)
    # ══════════════════════════════════════════
    ("AAP Bright Futures Guidelines", "AAP", 2024,
     "Well-Child Visits Schedule",
     "Periodicity schedule: newborn, 3-5 days, 1/2/4/6/9/12/15/18/24/30 months, then annually 3-21 years. Each visit: growth parameters, developmental screening (ASQ at 9/18/30mo, M-CHAT at 18/24mo), anticipatory guidance, immunizations per ACIP schedule. Depression screening annually starting age 12.",
     "A", "Strong", ["pediatric preventive care", "well-child visit"], [], ["height", "weight", "head circumference", "bmi percentile"], ["well child", "bright futures", "developmental screening"]),

    ("AAP Bright Futures Guidelines", "AAP", 2024,
     "Developmental Screening",
     "Standardized developmental screening at 9, 18, and 30 months using validated tool (ASQ-3). Autism-specific screening with M-CHAT-R/F at 18 and 24 months. Refer to early intervention (Part C) for children <3 with developmental concerns. School district evaluation for children ≥3.",
     "A", "Strong", ["developmental delay", "autism spectrum disorder"], [], ["asq-3", "m-chat-r/f", "developmental milestones"], ["developmental screening", "autism screening", "early intervention"]),

    ("AAP Febrile Seizure Guidelines", "AAP", 2024,
     "Simple Febrile Seizure Management",
     "Simple febrile seizures (generalized, <15 min, single in 24h) in well-appearing children 6-60 months require no laboratory testing, neuroimaging, or EEG. Educate parents on benign prognosis (recurrence 30%, no increased epilepsy risk). Antipyretics do not prevent febrile seizures. LP if meningitis suspected clinically.",
     "A", "Strong", ["febrile seizure", "simple febrile seizure"], ["acetaminophen", "ibuprofen"], ["temperature"], ["febrile seizure", "pediatric seizure", "fever"]),

    ("AAP Croup Guidelines", "AAP", 2024,
     "Croup Management",
     "Dexamethasone 0.6 mg/kg PO/IM (single dose) for all croup severity levels. Nebulized epinephrine for moderate-severe croup (observe 2-4 hours after). Observation alone for mild croup after dexamethasone. Avoid cough/cold medications. Humidified air not proven effective. Consider alternative diagnosis if no improvement.",
     "A", "Strong", ["croup", "laryngotracheobronchitis"], ["dexamethasone", "racemic epinephrine"], ["westley croup score", "oxygen saturation"], ["croup", "stridor", "dexamethasone", "epinephrine"]),

    ("AAP Acute Otitis Media Guidelines", "AAP", 2024,
     "AOM Diagnosis and Treatment",
     "Diagnosis requires: MEE (bulging TM, limited mobility, otorrhea) + acute symptoms. High-dose amoxicillin (80-90 mg/kg/day) first-line. Observation option for mild AOM in children ≥2 years with unilateral, non-severe symptoms. Amoxicillin-clavulanate if no improvement in 48-72h or recent antibiotic use. Tympanostomy tubes for recurrent AOM (≥3 in 6 months or ≥4 in 12 months).",
     "A", "Strong", ["acute otitis media", "ear infection"], ["amoxicillin", "amoxicillin-clavulanate", "ceftriaxone"], ["tympanometry", "pneumatic otoscopy"], ["otitis media", "amoxicillin", "ear infection", "tympanostomy"]),

    ("AAP Pediatric UTI Guidelines", "AAP", 2024,
     "Pediatric UTI Diagnosis",
     "Catheterized or suprapubic urine specimen for children 2-24 months. Clean-catch acceptable for toilet-trained children. Diagnosis requires both pyuria and ≥50,000 CFU/mL on catheterized specimen. Renal/bladder ultrasound after first febrile UTI. VCUG if ultrasound abnormal or recurrent UTI.",
     "A", "Strong", ["pediatric urinary tract infection", "pediatric pyelonephritis"], ["cephalexin", "trimethoprim-sulfamethoxazole", "ceftriaxone"], ["urinalysis", "urine culture", "renal ultrasound", "vcug"], ["pediatric uti", "vesicoureteral reflux", "pyelonephritis"]),

    ("AAP Pediatric Obesity Guidelines", "AAP", 2024,
     "Pediatric Obesity Comprehensive Management",
     "BMI ≥95th percentile = obesity; ≥120% of 95th = severe obesity. Intensive health behavior and lifestyle treatment (IHBLT) with ≥26 contact hours as foundation for all. Pharmacotherapy (GLP-1 RA, phentermine-topiramate) for age ≥12 with obesity. Metabolic/bariatric surgery for age ≥13 with severe obesity (BMI ≥40 or ≥35 with comorbidity). Screen for comorbidities: prediabetes, dyslipidemia, NAFLD, hypertension.",
     "A", "Strong", ["pediatric obesity", "childhood obesity"], ["semaglutide", "liraglutide", "phentermine-topiramate"], ["bmi percentile", "fasting glucose", "lipid panel", "alt", "blood pressure"], ["pediatric obesity", "bariatric", "glp-1", "bmi"]),

    ("AAP ADHD Guidelines", "AAP", 2024,
     "ADHD Diagnosis and Management",
     "Diagnosis for ages 4-18 using DSM-5 criteria with input from multiple settings. Age 4-5: behavior therapy first-line; methylphenidate if therapy insufficient. Age 6-11: stimulant medication AND behavior therapy. Age 12-18: medication with/without therapy. FDA-approved: methylphenidate, amphetamine, atomoxetine, viloxazine, guanfacine ER, clonidine ER.",
     "A", "Strong", ["adhd", "attention deficit hyperactivity disorder"], ["methylphenidate", "amphetamine", "atomoxetine", "guanfacine", "viloxazine"], ["vanderbilt assessment", "conners rating scale", "height", "weight", "blood pressure"], ["adhd", "stimulant", "methylphenidate", "behavior therapy"]),

    ("AAP Neonatal Jaundice Guidelines", "AAP", 2024,
     "Neonatal Hyperbilirubinemia Management",
     "Universal bilirubin screening (transcutaneous or serum) before discharge. Plot on hour-specific nomogram. Phototherapy thresholds based on gestational age and neurotoxicity risk factors. Exchange transfusion for bilirubin approaching or exceeding critical threshold. Encourage frequent feeding (8-12x/day). Follow-up within 24-48h of discharge.",
     "A", "Strong", ["neonatal jaundice", "neonatal hyperbilirubinemia"], [], ["total bilirubin", "direct bilirubin", "reticulocyte count", "blood type"], ["jaundice", "phototherapy", "bilirubin", "newborn"]),

    ("AAP Neonatal Hypoglycemia Guidelines", "AAP", 2024,
     "Neonatal Hypoglycemia Screening",
     "Screen at-risk neonates: LGA, SGA, IDM, late preterm (34-36 weeks). Target glucose ≥45 mg/dL in first 4 hours, ≥50 after 4-24 hours, ≥60 after 24 hours. Initial management: early and frequent feeding. Dextrose gel 200 mg/kg buccal for glucose 25-45. IV dextrose for symptomatic or persistent hypoglycemia.",
     "A", "Strong", ["neonatal hypoglycemia"], ["dextrose gel"], ["point-of-care glucose", "serum glucose"], ["neonatal hypoglycemia", "glucose screening", "dextrose"]),

    ("AAP Gastroenteritis Guidelines", "AAP", 2024,
     "Pediatric Acute Gastroenteritis",
     "Oral rehydration therapy (ORT) with low-osmolality ORS is first-line for mild-moderate dehydration. Ondansetron (single dose) if vomiting prevents ORT. Early refeeding within 4 hours of rehydration. IV fluids for severe dehydration or ORT failure. Probiotics (LGG, S. boulardii) may reduce diarrhea duration. No routine antibiotics or anti-diarrheal agents.",
     "A", "Strong", ["pediatric gastroenteritis", "pediatric dehydration"], ["ondansetron", "oral rehydration solution"], ["weight", "urine output", "electrolytes"], ["gastroenteritis", "dehydration", "oral rehydration", "ondansetron"]),

    ("AAP Bronchiolitis Guidelines", "AAP", 2024,
     "Bronchiolitis Supportive Care",
     "Supportive care only: nasal suctioning, supplemental oxygen for SpO2 <90% persistently. Avoid routine use of bronchodilators, corticosteroids, antibiotics, or chest physiotherapy. High-flow nasal cannula for moderate-severe respiratory distress. Hypertonic saline nebulization may be considered for inpatients. Palivizumab prophylaxis for high-risk infants.",
     "A", "Strong", ["bronchiolitis", "rsv bronchiolitis"], ["palivizumab"], ["oxygen saturation", "respiratory rate"], ["bronchiolitis", "rsv", "supportive care", "oxygen"]),

    ("AAP Kawasaki Disease Guidelines", "AAP", 2024,
     "Kawasaki Disease Acute Management",
     "IVIG 2 g/kg single infusion within 10 days of fever onset plus high-dose aspirin (80-100 mg/kg/day in 4 divided doses). Step down aspirin to 3-5 mg/kg/day when afebrile 48-72h. Echocardiogram at diagnosis, 2 weeks, and 6-8 weeks. IVIG-resistant: repeat IVIG or infliximab. Corticosteroids for refractory cases.",
     "A", "Strong", ["kawasaki disease", "mucocutaneous lymph node syndrome"], ["ivig", "aspirin", "infliximab", "methylprednisolone"], ["echocardiogram", "esr", "crp", "cbc"], ["kawasaki", "ivig", "coronary aneurysm", "aspirin"]),

    ("AAP Pediatric Asthma Guidelines", "AAP/NAEPP", 2024,
     "Pediatric Asthma Stepwise Management",
     "Ages 0-4: Step 1 SABA PRN, Step 2 low-dose ICS, Step 3 medium-dose ICS, Step 4 medium-dose ICS + LABA or montelukast. Ages 5-11: Step 1 SABA PRN, Step 2 low-dose ICS, Step 3 low-dose ICS+LABA or medium-dose ICS, Step 4 medium-dose ICS+LABA. Step up if not controlled; step down after 3 months of good control.",
     "A", "Strong", ["pediatric asthma", "childhood asthma"], ["albuterol", "fluticasone", "budesonide", "montelukast", "salmeterol"], ["spirometry", "peak flow", "feno"], ["pediatric asthma", "stepwise", "ics", "laba"]),

    ("AAP Pediatric Constipation Guidelines", "NASPGHAN/AAP", 2024,
     "Functional Constipation in Children",
     "Diagnosis per Rome IV criteria. Disimpaction first: PEG 3350 1-1.5 g/kg/day for 3-6 days orally, or enema if oral fails. Maintenance: PEG 3350 0.4-0.8 g/kg/day for at least 2 months after regular stools. Behavioral: regular toilet sitting after meals, adequate fiber and fluid. Avoid stimulant laxative long-term.",
     "A", "Strong", ["functional constipation", "pediatric constipation"], ["polyethylene glycol 3350", "lactulose", "senna"], ["abdominal x-ray"], ["constipation", "peg 3350", "encopresis", "disimpaction"]),

    # ══════════════════════════════════════════
    # SURGERY EXPANSION (~25)
    # ══════════════════════════════════════════
    ("ACS ATLS Guidelines", "ACS", 2024,
     "Primary Survey Approach",
     "ABCDE approach: Airway with cervical spine protection, Breathing, Circulation with hemorrhage control, Disability (GCS), Exposure/Environment. Massive transfusion protocol for hemorrhagic shock (1:1:1 pRBC:FFP:platelets). Permissive hypotension (SBP 80-90) for penetrating trauma until surgical control.",
     "A", "Strong", ["trauma", "hemorrhagic shock"], ["tranexamic acid", "packed red blood cells", "fresh frozen plasma"], ["gcs", "blood pressure", "lactate", "hemoglobin"], ["atls", "trauma", "primary survey", "massive transfusion"]),

    ("SAGES Appendicitis Guidelines", "SAGES", 2024,
     "Acute Appendicitis Management",
     "Laparoscopic appendectomy is standard of care. Non-operative management with antibiotics (amoxicillin-clavulanate or piperacillin-tazobactam) is safe alternative for uncomplicated appendicitis. CT abdomen for diagnosis in adults; ultrasound first in children and pregnant patients. Interval appendectomy after percutaneous drainage for appendiceal abscess.",
     "A", "Strong", ["acute appendicitis"], ["piperacillin-tazobactam", "metronidazole", "ciprofloxacin"], ["ct abdomen", "wbc", "crp"], ["appendicitis", "laparoscopic", "appendectomy"]),

    ("SAGES Cholecystectomy Guidelines", "SAGES", 2024,
     "Laparoscopic Cholecystectomy Indications",
     "Laparoscopic cholecystectomy for symptomatic cholelithiasis, acute cholecystitis, gallstone pancreatitis (same admission), and gallbladder polyps ≥10 mm. Critical view of safety must be achieved. Intraoperative cholangiography or ICG fluorescence for bile duct identification. Subtotal cholecystectomy or bailout procedures for severe inflammation.",
     "A", "Strong", ["cholelithiasis", "cholecystitis", "gallstone pancreatitis"], ["ursodiol"], ["abdominal ultrasound", "mrcp", "hida scan"], ["cholecystectomy", "laparoscopic", "gallstones", "critical view of safety"]),

    ("ASMBS Bariatric Surgery Guidelines", "ASMBS", 2024,
     "Bariatric Surgery Indications and Selection",
     "Surgery indicated for BMI ≥35 (previously ≥40 or ≥35 with comorbidity). Roux-en-Y gastric bypass or sleeve gastrectomy as primary procedures. Preoperative evaluation: nutrition, psychiatric, cardiac, sleep study. Lifelong vitamin/mineral supplementation required. Multidisciplinary team approach.",
     "A", "Strong", ["morbid obesity", "metabolic surgery"], ["multivitamin", "calcium citrate", "vitamin d", "vitamin b12", "iron"], ["bmi", "hba1c", "lipid panel", "sleep study"], ["bariatric surgery", "sleeve gastrectomy", "gastric bypass", "obesity"]),

    ("ERAS Society Guidelines", "ERAS Society", 2024,
     "Enhanced Recovery After Colorectal Surgery",
     "Preoperative: counseling, carbohydrate loading, avoid prolonged fasting, no mechanical bowel prep routinely. Intraoperative: goal-directed fluid therapy, avoid hypothermia, multimodal analgesia (avoid opioids). Postoperative: early oral intake (day 0), early mobilization, remove urinary catheter early, thromboprophylaxis, alvimopan for ileus prevention.",
     "A", "Strong", ["colorectal surgery", "enhanced recovery"], ["alvimopan", "acetaminophen", "ketorolac", "lidocaine"], ["pain score", "flatus", "diet tolerance"], ["eras", "enhanced recovery", "colorectal", "early mobilization"]),

    ("ACS Surgical Site Infection Guidelines", "ACS/SHEA", 2024,
     "Surgical Site Infection Prevention Bundle",
     "Preoperative: chlorhexidine skin prep, appropriate antibiotic prophylaxis within 60 minutes, maintain normothermia, normoglycemia (glucose <200). Intraoperative: minimize traffic, maintain aseptic technique, re-dose antibiotics for prolonged cases. Postoperative: discontinue antibiotics within 24 hours (48h for cardiac). Avoid razor shaving.",
     "A", "Strong", ["surgical site infection"], ["cefazolin", "clindamycin", "chlorhexidine"], ["glucose", "temperature", "wound assessment"], ["ssi prevention", "antibiotic prophylaxis", "chlorhexidine"]),

    ("EAST Damage Control Surgery", "EAST", 2024,
     "Damage Control Surgery Principles",
     "Indicated for lethal triad: hypothermia (<35°C), acidosis (pH <7.2), coagulopathy. Abbreviated initial surgery focused on hemorrhage control and contamination control. Temporary abdominal closure. ICU resuscitation: correct coagulopathy, rewarm, restore physiology. Planned return to OR in 24-72 hours for definitive repair.",
     "B", "Strong", ["trauma", "hemorrhagic shock", "damage control"], ["tranexamic acid", "cryoprecipitate", "prothrombin complex concentrate"], ["ph", "lactate", "temperature", "inr", "fibrinogen"], ["damage control", "lethal triad", "trauma surgery"]),

    ("ACS VTE Prophylaxis Guidelines", "ACS", 2024,
     "Surgical VTE Prophylaxis",
     "Risk-stratify all surgical patients (Caprini score). Low risk: early ambulation. Moderate risk: LMWH or UFH. High risk: LMWH/UFH + mechanical prophylaxis. Extended prophylaxis (4 weeks) for major abdominal/pelvic cancer surgery. Neuraxial: follow ASRA guidelines for anticoagulation timing.",
     "A", "Strong", ["venous thromboembolism", "surgical dvt prophylaxis"], ["enoxaparin", "heparin", "rivaroxaban"], ["caprini score", "ultrasound doppler"], ["vte prophylaxis", "dvt", "enoxaparin", "caprini"]),

    ("SAGES Hernia Repair Guidelines", "SAGES/EHS", 2024,
     "Inguinal Hernia Repair",
     "Mesh repair (open Lichtenstein or laparoscopic TEP/TAPP) reduces recurrence vs tissue repair. Laparoscopic preferred for bilateral and recurrent hernias. Watchful waiting acceptable for minimally symptomatic hernias. Antibiotic prophylaxis for open mesh repair. Avoid mesh in contaminated fields.",
     "A", "Strong", ["inguinal hernia"], ["cefazolin"], ["clinical exam"], ["hernia", "mesh repair", "lichtenstein", "laparoscopic"]),

    ("ACS Breast Surgery Guidelines", "ASBrS/NCCN", 2024,
     "Breast-Conserving Surgery",
     "BCS + whole breast radiation equivalent to mastectomy for stages I-II. No ink on tumor (invasive) or 2 mm margin (DCIS) constitutes adequate margin. Sentinel lymph node biopsy standard for clinically node-negative. Omission of axillary dissection with 1-2 positive sentinel nodes (Z0011 criteria). Oncoplastic techniques for larger resections.",
     "A", "Strong", ["breast cancer", "breast-conserving surgery"], ["tamoxifen", "anastrozole"], ["mammogram", "mri breast", "pathology margins"], ["breast conservation", "sentinel node", "lumpectomy", "margins"]),

    ("ATA Thyroidectomy Guidelines", "ATA", 2024,
     "Thyroid Surgery Indications",
     "Lobectomy for solitary nodule 1-4 cm with Bethesda V-VI and no extrathyroidal extension. Total thyroidectomy for thyroid cancer >4 cm, bilateral disease, or high-risk features. Preoperative vocal cord assessment. Intraoperative nerve monitoring recommended. Monitor calcium postoperatively for hypoparathyroidism.",
     "A", "Strong", ["thyroid nodule", "thyroid cancer"], ["levothyroxine", "calcium carbonate", "calcitriol"], ["tsh", "thyroglobulin", "calcium", "pth", "ultrasound thyroid"], ["thyroidectomy", "thyroid cancer", "recurrent laryngeal nerve"]),

    # ══════════════════════════════════════════
    # NEUROLOGY EXPANSION (~25)
    # ══════════════════════════════════════════
    ("AAN Multiple Sclerosis Guidelines", "AAN", 2024,
     "MS Disease-Modifying Therapy Initiation",
     "Start DMT at diagnosis for relapsing MS. High-efficacy DMTs (natalizumab, ocrelizumab, ofatumumab) for highly active disease. Platform therapies (dimethyl fumarate, glatiramer, teriflunomide) for milder disease. JCV antibody testing before natalizumab. MRI surveillance every 6-12 months.",
     "A", "Strong", ["multiple sclerosis", "relapsing ms"], ["ocrelizumab", "natalizumab", "dimethyl fumarate", "glatiramer"], ["mri brain", "mri spine", "jcv antibody", "csf oligoclonal bands"], ["multiple sclerosis", "dmt", "relapse", "ocrelizumab"]),

    ("AAN Multiple Sclerosis Guidelines", "AAN", 2024,
     "MS Relapse Management",
     "High-dose IV methylprednisolone 1g/day for 3-5 days for acute relapses causing functional impairment. Oral equivalent (prednisone 1250 mg) is acceptable alternative. Plasma exchange (PLEX) for severe relapses unresponsive to steroids. Not all relapses require treatment (mild sensory symptoms may self-resolve).",
     "A", "Strong", ["ms relapse", "multiple sclerosis exacerbation"], ["methylprednisolone", "prednisone"], ["edss score", "mri brain"], ["ms relapse", "methylprednisolone", "plasmapheresis"]),

    ("MDS/AAN Parkinson Disease Guidelines", "MDS/AAN", 2024,
     "Parkinson Disease Motor Symptom Treatment",
     "Levodopa/carbidopa is most effective symptomatic therapy (start when symptoms affect function). Dopamine agonists (pramipexole, ropinirole) as initial therapy for younger patients to delay levodopa dyskinesia. MAO-B inhibitors (rasagiline, safinamide) for mild symptoms or adjunctive. COMT inhibitors for motor fluctuations. DBS for refractory motor fluctuations.",
     "A", "Strong", ["parkinson disease", "parkinsonism"], ["levodopa-carbidopa", "pramipexole", "ropinirole", "rasagiline", "entacapone"], ["updrs", "hoehn and yahr stage"], ["parkinson", "levodopa", "dopamine agonist", "dbs"]),

    ("MDS/AAN Parkinson Disease Guidelines", "MDS/AAN", 2024,
     "Parkinson Non-Motor Symptoms",
     "Depression: SSRIs or SNRIs. Cognitive impairment/dementia: rivastigmine (only approved PDD medication). Psychosis: pimavanserin (first-line) or quetiapine (avoid other antipsychotics). Orthostatic hypotension: fludrocortisone, midodrine, droxidopa. Constipation: PEG, lubiprostone. REM sleep behavior disorder: melatonin first, clonazepam second.",
     "B", "Strong", ["parkinson disease non-motor", "parkinson dementia", "parkinson psychosis"], ["rivastigmine", "pimavanserin", "fludrocortisone", "midodrine"], ["moca", "orthostatic bp", "sleep study"], ["parkinson", "non-motor", "dementia", "psychosis"]),

    ("AHS Migraine Guidelines", "AHS/AAN", 2024,
     "Migraine Acute Treatment",
     "Triptans remain first-line for moderate-severe migraine. Gepants (ubrogepant, rimegepant) for triptan contraindications or failure. Ditans (lasmiditan) for those with cardiovascular risk. NSAIDs + antiemetic for mild-moderate. IV metoclopramide + diphenhydramine for ED presentation. Limit acute medication to <10 days/month to prevent MOH.",
     "A", "Strong", ["migraine", "acute migraine"], ["sumatriptan", "rizatriptan", "ubrogepant", "rimegepant", "lasmiditan", "metoclopramide"], ["migraine disability assessment"], ["migraine", "triptan", "gepant", "acute treatment"]),

    ("AHS Migraine Guidelines", "AHS/AAN", 2024,
     "Migraine Preventive Treatment",
     "Preventive therapy for ≥4 headache days/month or significant disability. Oral: topiramate, propranolol, amitriptyline, valproate, candesartan. Anti-CGRP monoclonal antibodies (erenumab, fremanezumab, galcanezumab) for inadequate response to 2+ oral preventives. Atogepant (oral CGRP antagonist) as preventive. OnabotulinumtoxinA for chronic migraine (≥15 days/month).",
     "A", "Strong", ["chronic migraine", "migraine prevention"], ["topiramate", "propranolol", "amitriptyline", "erenumab", "galcanezumab", "onabotulinumtoxinA"], ["headache diary", "hit-6", "midas"], ["migraine prevention", "cgrp", "botox", "topiramate"]),

    ("AAN Alzheimer Disease Guidelines", "AAN/APA", 2024,
     "Alzheimer Disease Diagnosis and Treatment",
     "Diagnosis: clinical history, cognitive testing (MoCA, MMSE), MRI brain (atrophy pattern), and biomarkers (CSF Abeta42/tau, amyloid PET, plasma p-tau217). Cholinesterase inhibitors (donepezil, rivastigmine, galantamine) for mild-moderate AD. Memantine for moderate-severe. Lecanemab or donanemab (anti-amyloid antibodies) for early AD with confirmed amyloid pathology.",
     "A", "Strong", ["alzheimer disease", "dementia"], ["donepezil", "rivastigmine", "memantine", "lecanemab"], ["moca", "mmse", "mri brain", "amyloid pet", "csf biomarkers"], ["alzheimer", "dementia", "cholinesterase inhibitor", "anti-amyloid"]),

    ("AAN Essential Tremor Guidelines", "AAN", 2024,
     "Essential Tremor Treatment",
     "Propranolol and primidone are first-line pharmacotherapy. Second-line: topiramate, gabapentin, alprazolam. For refractory tremor: DBS (ventral intermediate nucleus of thalamus) or focused ultrasound thalamotomy. Botulinum toxin for head and voice tremor. Occupational therapy for adaptive strategies.",
     "A", "Strong", ["essential tremor"], ["propranolol", "primidone", "topiramate", "gabapentin"], [], ["essential tremor", "propranolol", "primidone", "dbs"]),

    ("AAN Restless Legs Syndrome Guidelines", "AAN", 2024,
     "RLS Management",
     "First-line: alpha-2-delta ligands (gabapentin enacarbil, pregabalin) or dopamine agonists (pramipexole, ropinirole, rotigotine patch). Iron supplementation if ferritin <75. Avoid dopamine agonists for augmentation risk (use lowest effective dose, consider switching). Low-dose opioids (oxycodone) for refractory cases. Address triggers (iron deficiency, caffeine, antidepressants).",
     "B", "Strong", ["restless legs syndrome", "willis-ekbom disease"], ["gabapentin enacarbil", "pregabalin", "pramipexole", "ropinirole", "iron"], ["ferritin", "iron studies", "sleep study"], ["restless legs", "rls", "dopamine agonist", "iron"]),

    ("AAN Bell Palsy Guidelines", "AAN", 2024,
     "Bell Palsy Management",
     "Oral corticosteroids (prednisone 60-80 mg/day for 1 week) within 72 hours of onset. Antiviral (valacyclovir) added for severe/complete paralysis (uncertain benefit). Eye protection: artificial tears, nighttime eye taping/moisture chamber. Prognosis: 70% full recovery without treatment, 90%+ with steroids. EMG/NCS at 2 weeks if no improvement.",
     "A", "Strong", ["bell palsy", "facial nerve palsy"], ["prednisone", "valacyclovir", "artificial tears"], ["house-brackmann scale", "emg", "nerve conduction study"], ["bell palsy", "facial palsy", "prednisone", "eye protection"]),

    ("AAN Brain Death Guidelines", "AAN/AHA", 2024,
     "Brain Death Determination",
     "Two clinical examinations by qualified physicians (interval per institutional policy). Prerequisites: known etiology, exclude confounders (sedation, hypothermia, metabolic derangements). Exam: absent brainstem reflexes (pupillary, corneal, vestibulo-ocular, gag, cough), no motor response, apnea testing (PaCO2 ≥60 AND ≥20 above baseline). Ancillary testing (cerebral angiography, EEG, nuclear scan) if clinical exam cannot be completed.",
     "A", "Strong", ["brain death", "death by neurologic criteria"], [], ["arterial blood gas", "eeg", "cerebral angiography", "nuclear perfusion scan"], ["brain death", "apnea test", "brainstem reflexes"]),

    # ══════════════════════════════════════════
    # ANESTHESIOLOGY (~15)
    # ══════════════════════════════════════════
    ("ASA Difficult Airway Guidelines", "ASA", 2024,
     "Difficult Airway Algorithm",
     "Preoperative assessment: Mallampati score, thyromental distance, neck mobility, mouth opening, prior airway history. If anticipated difficult airway: awake intubation (awake fiberoptic or awake video laryngoscopy). Unanticipated: after 2 failed attempts, call for help, consider supraglottic airway. Can't intubate/can't oxygenate: front-of-neck access (cricothyrotomy).",
     "A", "Strong", ["difficult airway", "airway management"], ["propofol", "succinylcholine", "rocuronium", "sugammadex"], ["mallampati score", "oxygen saturation", "etco2"], ["difficult airway", "intubation", "cricothyrotomy", "video laryngoscopy"]),

    ("ASA Neuraxial Anesthesia Guidelines", "ASA/ASRA", 2024,
     "Neuraxial Anesthesia Anticoagulation Timing",
     "Hold warfarin 5 days (INR <1.4). Hold LMWH 12 hours (prophylactic) or 24 hours (therapeutic). Hold UFH 4-6 hours (IV), check aPTT. Rivaroxaban/apixaban: hold 72 hours. Aspirin: may continue for neuraxial. Clopidogrel: hold 5-7 days. Re-start anticoagulation per specific intervals post-procedure.",
     "A", "Strong", ["neuraxial anesthesia", "epidural", "spinal anesthesia"], ["warfarin", "enoxaparin", "heparin", "rivaroxaban", "apixaban"], ["inr", "aptt", "platelet count"], ["neuraxial", "epidural", "anticoagulation timing", "asra"]),

    ("ASA Perioperative Pain Management", "ASA", 2024,
     "Multimodal Analgesia",
     "Multimodal approach: acetaminophen (scheduled), NSAIDs (if no contraindications), gabapentinoids (for neuropathic component), regional anesthesia/nerve blocks, IV lidocaine infusion. Minimize opioid use. Ketamine low-dose infusion for opioid-tolerant patients. PCA for major surgery. Transition to oral as soon as possible.",
     "A", "Strong", ["postoperative pain", "multimodal analgesia"], ["acetaminophen", "ketorolac", "gabapentin", "lidocaine", "ketamine", "morphine"], ["pain score", "opioid consumption"], ["multimodal analgesia", "pain management", "nerve block", "opioid sparing"]),

    ("ASA PONV Guidelines", "ASA/SAMBA", 2024,
     "Postoperative Nausea and Vomiting Prevention",
     "Risk stratify with Apfel score (female, non-smoker, history of PONV/motion sickness, postoperative opioids). Low risk: no prophylaxis. Moderate risk (1-2 factors): ondansetron + dexamethasone. High risk (3-4 factors): triple therapy (ondansetron + dexamethasone + scopolamine or droperidol). TIVA with propofol reduces PONV. Minimize opioids.",
     "A", "Strong", ["ponv", "postoperative nausea", "postoperative vomiting"], ["ondansetron", "dexamethasone", "scopolamine", "droperidol", "aprepitant"], ["apfel score"], ["ponv", "antiemetic", "ondansetron", "risk stratification"]),

    ("MHAUS Malignant Hyperthermia Guidelines", "MHAUS", 2024,
     "Malignant Hyperthermia Management",
     "Triggers: succinylcholine and volatile anesthetics (sevoflurane, desflurane, isoflurane). Presentation: unexplained rise in EtCO2, tachycardia, rigidity, hyperthermia (late sign). Immediate: stop trigger, hyperventilate with 100% O2, dantrolene 2.5 mg/kg IV bolus (repeat up to 10 mg/kg). Active cooling. Labs: ABG, CK, potassium, myoglobin. ICU admission. MH Hotline: 1-800-644-9737.",
     "A", "Strong", ["malignant hyperthermia"], ["dantrolene"], ["etco2", "temperature", "ck", "potassium", "arterial blood gas", "urine myoglobin"], ["malignant hyperthermia", "dantrolene", "volatile anesthetic"]),

    # ══════════════════════════════════════════
    # RADIOLOGY / IMAGING GUIDELINES (~15)
    # ══════════════════════════════════════════
    ("ACR Appropriateness Criteria - Chest Pain", "ACR", 2024,
     "Imaging for Acute Chest Pain",
     "Low-risk acute chest pain: coronary CT angiography (CCTA) preferred. Intermediate risk: stress testing or CCTA. High risk / STEMI: proceed to catheterization without imaging delay. CT PE study if PE suspected (D-dimer first for low-probability). CXR for all acute chest pain presentations. Avoid echocardiography as first-line for ACS evaluation.",
     "A", "Strong", ["acute chest pain", "coronary artery disease"], [], ["coronary ct angiography", "d-dimer", "troponin", "chest x-ray", "ct pulmonary angiogram"], ["chest pain imaging", "ccta", "appropriateness criteria"]),

    ("ACR Appropriateness Criteria - Headache", "ACR", 2024,
     "Imaging for Headache",
     "Routine headache without red flags: imaging not indicated. Red flags (thunderclap, worst headache, focal deficits, papilledema, fever, immunocompromised, age >50 new onset): CT head non-contrast first, MRI brain if CT negative and clinical suspicion persists. CT angiography/venography for suspected vascular cause. LP after normal imaging if SAH suspected.",
     "A", "Strong", ["headache", "migraine evaluation"], [], ["ct head", "mri brain", "ct angiography", "lumbar puncture"], ["headache imaging", "red flags", "appropriateness criteria"]),

    ("ACR Appropriateness Criteria - Low Back Pain", "ACR", 2024,
     "Imaging for Low Back Pain",
     "Acute low back pain without red flags: no imaging for first 6 weeks. Red flags requiring imaging: cauda equina, progressive neurologic deficit, cancer history, infection concern, fracture risk. MRI lumbar preferred for neurologic symptoms. CT for contraindication to MRI. Plain radiographs for suspected fracture or spondyloarthropathy. Avoid routine MRI for chronic back pain.",
     "A", "Strong", ["low back pain", "lumbar radiculopathy"], [], ["mri lumbar spine", "x-ray lumbar", "ct lumbar"], ["back pain imaging", "red flags", "appropriateness criteria"]),

    ("ACR Contrast Reaction Management", "ACR", 2024,
     "Contrast Allergy Premedication and Management",
     "For patients with prior moderate-severe contrast reaction: premedicate with prednisone 50 mg at 13, 7, and 1 hour before + diphenhydramine 50 mg 1 hour before. Use non-ionic low-osmolar contrast. Alternative contrast agent from a different class. Acute anaphylaxis: epinephrine 0.3 mg IM, stop contrast, IV fluids, oxygen. eGFR ≥30 for iodinated contrast; hold metformin if eGFR 30-44.",
     "A", "Strong", ["contrast allergy", "contrast-induced nephropathy"], ["prednisone", "diphenhydramine", "epinephrine"], ["egfr", "creatinine", "blood pressure"], ["contrast allergy", "premedication", "cin prevention", "anaphylaxis"]),

    ("Fleischner Society Pulmonary Nodule Guidelines", "Fleischner Society", 2024,
     "Incidental Pulmonary Nodule Follow-up",
     "Solid nodule <6 mm: no routine follow-up (unless high risk). Solid 6-8 mm: CT at 6-12 months, then consider CT at 18-24 months. Solid >8 mm: CT at 3 months, PET/CT, or tissue sampling. Subsolid ground-glass <6 mm: no follow-up. Ground-glass ≥6 mm: CT at 6-12 months, then every 2 years for 5 years. Part-solid: most aggressive follow-up.",
     "A", "Strong", ["pulmonary nodule", "incidental lung nodule"], [], ["ct chest", "pet-ct"], ["lung nodule", "fleischner", "follow-up", "incidental finding"]),

    ("ACR Incidental Adrenal Mass", "ACR", 2024,
     "Incidental Adrenal Mass Workup",
     "Lesion <1 cm with benign imaging features: no follow-up. 1-4 cm: biochemical workup (plasma free metanephrines, 1 mg dexamethasone suppression test, aldosterone/renin if hypertensive) + assess CT characteristics (HU <10 = lipid-rich adenoma, benign). >4 cm or indeterminate: adrenal protocol CT/MRI washout study, consider surgical referral. >6 cm: high suspicion for carcinoma.",
     "B", "Strong", ["adrenal incidentaloma", "adrenal mass"], ["dexamethasone"], ["plasma metanephrines", "cortisol", "aldosterone", "renin", "ct adrenal", "mri adrenal"], ["adrenal incidentaloma", "pheochromocytoma screening", "cushing screening"]),

    ("ACR Incidental Thyroid Nodule on CT", "ACR", 2024,
     "Incidental Thyroid Nodule Management",
     "Incidental thyroid nodule on CT/MRI/PET: assess size and features. ≥1 cm with suspicious features (calcification, irregular margins) or FDG-avid: thyroid ultrasound + TSH. <1 cm: ultrasound only if age <35 or high-risk history. ACR TI-RADS on ultrasound to determine need for FNA. FNA for TI-RADS 5 (≥1 cm), TI-RADS 4 (≥1.5 cm), TI-RADS 3 (≥2.5 cm).",
     "B", "Strong", ["thyroid nodule", "incidental thyroid nodule"], [], ["thyroid ultrasound", "tsh", "fna biopsy"], ["thyroid nodule", "ti-rads", "incidental finding", "fna"]),

    ("ACR Incidental Renal Mass", "ACR", 2024,
     "Incidental Renal Mass Evaluation",
     "Simple cyst (Bosniak I): no follow-up. Bosniak II: no follow-up. Bosniak IIF: follow-up imaging at 6 months, then annually for 5 years. Bosniak III: surgical excision or active surveillance. Bosniak IV: surgical excision (presumed malignant). Solid enhancing mass: renal protocol CT or MRI. Small renal mass <3 cm: partial nephrectomy, ablation, or active surveillance per age/comorbidity.",
     "B", "Strong", ["renal mass", "renal cyst", "renal cell carcinoma"], [], ["ct abdomen", "mri abdomen", "renal ultrasound"], ["renal mass", "bosniak", "incidental finding", "renal cell carcinoma"]),

    # ══════════════════════════════════════════
    # ORTHOPEDICS EXPANSION (~20)
    # ══════════════════════════════════════════
    ("AAOS ACL Injury Guidelines", "AAOS", 2024,
     "ACL Injury Management",
     "Complete ACL tear in active patients: ACL reconstruction recommended. Timing: 3-6 weeks post-injury after achieving full ROM and minimal swelling. Graft options: autograft (BTB, hamstring, quadriceps) vs allograft. Structured rehabilitation 6-9 months. Return-to-sport criteria: ≥90% limb symmetry on functional testing. Non-operative: activity modification, bracing, PT for low-demand patients.",
     "A", "Strong", ["acl tear", "anterior cruciate ligament injury"], ["nsaids"], ["mri knee", "lachman test", "pivot shift test"], ["acl", "reconstruction", "knee ligament", "rehabilitation"]),

    ("AAOS Meniscal Tear Guidelines", "AAOS", 2024,
     "Meniscal Tear Treatment",
     "Meniscal repair preferred over meniscectomy when feasible (peripheral tears, acute, young patient). Arthroscopic partial meniscectomy for irreparable tears causing mechanical symptoms. Non-operative management for degenerative meniscal tears in older adults (PT, NSAIDs). Concomitant ACL reconstruction improves meniscal repair healing. Root tears: repair to prevent rapid OA progression.",
     "B", "Strong", ["meniscal tear", "knee meniscus injury"], ["naproxen", "ibuprofen"], ["mri knee"], ["meniscus", "meniscectomy", "meniscal repair", "arthroscopy"]),

    ("AAOS Hip Fracture Guidelines", "AAOS", 2024,
     "Hip Fracture Management",
     "Surgery within 24-48 hours of admission reduces mortality. Femoral neck (displaced): hemiarthroplasty or THA (younger, active patients). Femoral neck (non-displaced): internal fixation with cannulated screws. Intertrochanteric: intramedullary nail or sliding hip screw. VTE prophylaxis. Early mobilization day 1. Osteoporosis workup and treatment initiation. Falls prevention program.",
     "A", "Strong", ["hip fracture", "femoral neck fracture", "intertrochanteric fracture"], ["enoxaparin", "alendronate", "denosumab", "calcium", "vitamin d"], ["x-ray hip", "ct hip", "dexa", "vitamin d level"], ["hip fracture", "hemiarthroplasty", "intramedullary nail", "osteoporosis"]),

    ("AAOS Total Knee Arthroplasty Guidelines", "AAOS", 2024,
     "Total Knee Arthroplasty Indications",
     "TKA for end-stage knee OA with failed conservative management (weight loss, PT, NSAIDs, injections, bracing). Preoperative optimization: BMI <40, HbA1c <8%, smoking cessation, dental clearance, nasal decolonization. Spinal anesthesia preferred. Multimodal pain protocol. DVT prophylaxis per AAOS guidelines. Outpatient TKA for appropriate candidates.",
     "A", "Strong", ["knee osteoarthritis", "total knee replacement"], ["tranexamic acid", "aspirin", "celecoxib", "acetaminophen"], ["knee x-ray", "hba1c", "bmi", "hemoglobin"], ["tka", "knee replacement", "osteoarthritis", "arthroplasty"]),

    ("AAOS Total Hip Arthroplasty Guidelines", "AAOS", 2024,
     "Total Hip Arthroplasty Approach",
     "Anterior approach: faster early recovery, lower dislocation risk, potentially more nerve injury. Posterior approach: familiar, versatile, good for complex cases. Direct lateral: good exposure, risk of abductor weakness. Bearing surfaces: ceramic-on-poly most common. Cemented vs cementless based on bone quality and surgeon preference. Perioperative tranexamic acid reduces transfusion.",
     "B", "Strong", ["hip osteoarthritis", "total hip replacement"], ["tranexamic acid", "aspirin", "enoxaparin"], ["hip x-ray", "hemoglobin", "crp"], ["tha", "hip replacement", "anterior approach", "arthroplasty"]),

    ("AAOS Distal Radius Fracture Guidelines", "AAOS", 2024,
     "Distal Radius Fracture Treatment",
     "Non-displaced/minimally displaced: closed reduction and casting for 4-6 weeks. Operative fixation (ORIF with volar locking plate) for: articular step-off >2 mm, dorsal tilt >10°, radial shortening >3 mm, or unstable fracture pattern. Hand therapy referral post-immobilization. Screen for osteoporosis in fragility fractures (age >50).",
     "A", "Strong", ["distal radius fracture", "wrist fracture"], ["acetaminophen", "ibuprofen"], ["x-ray wrist", "ct wrist"], ["distal radius", "wrist fracture", "orif", "volar plate"]),

    ("AAOS Carpal Tunnel Syndrome Guidelines", "AAOS", 2024,
     "Carpal Tunnel Syndrome Treatment",
     "Conservative: night splinting in neutral position, activity modification, corticosteroid injection (1-2 attempts). Electrodiagnostic testing (NCS/EMG) to confirm and grade severity. Surgical: open or endoscopic carpal tunnel release for moderate-severe CTS or failed conservative treatment. Surgery success rate >90%. Avoid steroid injection if considering surgery within 3 months.",
     "A", "Strong", ["carpal tunnel syndrome", "median neuropathy"], ["methylprednisolone injection", "naproxen"], ["nerve conduction study", "emg"], ["carpal tunnel", "nerve conduction", "surgical release", "splinting"]),

    # ══════════════════════════════════════════
    # OPHTHALMOLOGY EXPANSION (~12)
    # ══════════════════════════════════════════
    ("AAO Glaucoma Guidelines", "AAO", 2024,
     "Primary Open-Angle Glaucoma Treatment",
     "First-line: prostaglandin analog (latanoprost, travoprost, bimatoprost) for IOP lowering. Second-line: beta-blocker (timolol), alpha-agonist (brimonidine), or carbonic anhydrase inhibitor (dorzolamide). Selective laser trabeculoplasty (SLT) as alternative first-line. Trabeculectomy or tube shunt for medically uncontrolled glaucoma. Target IOP based on severity (typically 25-40% reduction).",
     "A", "Strong", ["primary open-angle glaucoma", "glaucoma"], ["latanoprost", "timolol", "brimonidine", "dorzolamide", "bimatoprost"], ["intraocular pressure", "visual field testing", "oct rnfl", "gonioscopy"], ["glaucoma", "iop", "prostaglandin", "slt"]),

    ("AAO Age-Related Macular Degeneration Guidelines", "AAO", 2024,
     "AMD Treatment",
     "Dry AMD: AREDS2 supplements (lutein, zeaxanthin, vitamin C, vitamin E, zinc) for intermediate AMD to slow progression. No treatment for geographic atrophy (pegcetacoplan and avacincaptad pegol approved for GA). Wet AMD: anti-VEGF intravitreal injections (aflibercept, ranibizumab, faricimab, bevacizumab) with treat-and-extend protocol. OCT monitoring every 4-16 weeks.",
     "A", "Strong", ["age-related macular degeneration", "wet amd", "dry amd"], ["aflibercept", "ranibizumab", "bevacizumab", "faricimab", "pegcetacoplan"], ["oct macula", "fundus photography", "fluorescein angiography", "visual acuity"], ["amd", "anti-vegf", "macular degeneration", "intravitreal"]),

    ("AAO Uveitis Guidelines", "AAO", 2024,
     "Uveitis Management",
     "Anterior uveitis: topical corticosteroids (prednisolone acetate 1%) with cycloplegic (cyclopentolate). Intermediate/posterior/panuveitis: systemic corticosteroids (prednisone), then steroid-sparing immunosuppression (methotrexate, mycophenolate, adalimumab). HLA-B27 testing for recurrent anterior uveitis. Rule out infectious causes (syphilis, TB, toxoplasmosis) before immunosuppression.",
     "A", "Strong", ["uveitis", "anterior uveitis", "posterior uveitis"], ["prednisolone acetate", "cyclopentolate", "methotrexate", "adalimumab", "mycophenolate"], ["slit lamp exam", "oct", "fta-abs", "quantiferon-tb"], ["uveitis", "corticosteroid", "immunosuppression", "hla-b27"]),

    ("AAO Retinal Detachment Guidelines", "AAO", 2024,
     "Retinal Detachment Management",
     "Rhegmatogenous RD: urgent surgical repair. Options: pneumatic retinopexy (for simple superior detachments), scleral buckle, or pars plana vitrectomy (PPV). PPV most common. Macula-on detachments: repair within 24 hours to preserve central vision. Macula-off: repair within 7-10 days. Vitreous hemorrhage with suspected RD: urgent B-scan and surgical evaluation.",
     "A", "Strong", ["retinal detachment", "rhegmatogenous retinal detachment"], [], ["dilated fundus exam", "oct", "b-scan ultrasound", "visual acuity"], ["retinal detachment", "vitrectomy", "scleral buckle", "retinal tear"]),

    # ══════════════════════════════════════════
    # DERMATOLOGY EXPANSION (~12)
    # ══════════════════════════════════════════
    ("AAD Acne Vulgaris Guidelines", "AAD", 2024,
     "Acne Vulgaris Management",
     "Mild: topical retinoid (adapalene, tretinoin) + benzoyl peroxide. Moderate: add topical antibiotic (clindamycin) or switch to combination (adapalene/BPO). Moderate-severe: oral antibiotics (doxycycline, minocycline) for 3 months + topical retinoid. Severe/nodular: isotretinoin (iPLEDGE program). Hormonal therapy (spironolactone, OCP) for adult female acne. Maintenance: topical retinoid + BPO.",
     "A", "Strong", ["acne vulgaris"], ["adapalene", "benzoyl peroxide", "clindamycin", "doxycycline", "isotretinoin", "spironolactone"], [], ["acne", "isotretinoin", "retinoid", "benzoyl peroxide"]),

    ("AAD Atopic Dermatitis Guidelines", "AAD", 2024,
     "Atopic Dermatitis Stepwise Treatment",
     "Mild: emollients + low-potency topical corticosteroids (hydrocortisone). Moderate: mid-potency TCS (triamcinolone), topical calcineurin inhibitors (tacrolimus, pimecrolimus), crisaborole, or ruxolitinib. Severe: dupilumab (IL-4/13 blocker, age ≥6 mo), tralokinumab (adults), JAK inhibitors (abrocitinib, upadacitinib). Avoid long-term high-potency TCS. Dilute bleach baths for secondary infection prevention.",
     "A", "Strong", ["atopic dermatitis", "eczema"], ["hydrocortisone", "triamcinolone", "tacrolimus", "dupilumab", "abrocitinib"], ["scorad", "easi", "iga score"], ["atopic dermatitis", "eczema", "dupilumab", "topical corticosteroid"]),

    ("AAD Alopecia Areata Guidelines", "AAD", 2024,
     "Alopecia Areata Treatment",
     "Limited patches: intralesional triamcinolone (5-10 mg/mL), topical corticosteroids, topical minoxidil. Extensive (>50%): JAK inhibitors (baricitinib FDA-approved, ritlecitinib FDA-approved). Short-course systemic corticosteroids for rapid progression. Contact immunotherapy (DPCP) for extensive refractory cases. Monitor for autoimmune comorbidities (thyroid, vitiligo).",
     "A", "Strong", ["alopecia areata"], ["triamcinolone", "minoxidil", "baricitinib", "ritlecitinib"], ["tsh", "cbc", "trichoscopy"], ["alopecia areata", "jak inhibitor", "baricitinib", "hair loss"]),

    ("AAD Rosacea Guidelines", "AAD", 2024,
     "Rosacea Management",
     "Erythematotelangiectatic: topical brimonidine or oxymetazoline for flushing, laser/IPL for telangiectasias. Papulopustular: topical ivermectin, metronidazole, or azelaic acid first-line; oral doxycycline 40 mg MR for moderate-severe. Phymatous: isotretinoin, procedural (CO2 laser, surgical). Ocular: artificial tears, topical cyclosporine, oral doxycycline. Trigger avoidance (sun, alcohol, spicy food, heat).",
     "B", "Strong", ["rosacea"], ["ivermectin topical", "metronidazole topical", "azelaic acid", "doxycycline", "brimonidine"], [], ["rosacea", "ivermectin", "doxycycline", "laser"]),

    ("AAD Hidradenitis Suppurativa Guidelines", "AAD", 2024,
     "Hidradenitis Suppurativa Treatment",
     "Mild (Hurley I): topical clindamycin, benzoyl peroxide wash. Moderate (Hurley II): oral antibiotics (doxycycline or clindamycin+rifampin), adalimumab (FDA-approved biologic), secukinumab. Severe (Hurley III): adalimumab, secukinumab, or surgical excision. Adjuncts: weight loss, smoking cessation, zinc supplementation, hormonal therapy (spironolactone). Pain management essential.",
     "A", "Strong", ["hidradenitis suppurativa"], ["adalimumab", "secukinumab", "clindamycin", "rifampin", "doxycycline"], ["hurley staging", "his4 score"], ["hidradenitis", "adalimumab", "secukinumab", "abscess"]),

    # ══════════════════════════════════════════
    # UROLOGY EXPANSION (~12)
    # ══════════════════════════════════════════
    ("AUA Kidney Stone Guidelines", "AUA/EAU", 2024,
     "Nephrolithiasis Management",
     "Stone <5 mm: observation with MET (tamsulosin) for distal ureteral stones, hydration, analgesia. Stone 5-10 mm: SWL or ureteroscopy. Stone >10 mm or complex: ureteroscopy or PCNL. Staghorn calculus: PCNL. 24-hour urine collection for recurrent stone formers. Increase fluid to >2.5 L/day. Thiazide for hypercalciuria, potassium citrate for hypocitraturia.",
     "A", "Strong", ["nephrolithiasis", "kidney stones", "ureteral stones"], ["tamsulosin", "hydrochlorothiazide", "potassium citrate", "ketorolac"], ["ct abdomen non-contrast", "24-hour urine", "bmp", "urinalysis"], ["kidney stone", "nephrolithiasis", "lithotripsy", "tamsulosin"]),

    ("AUA Overactive Bladder Guidelines", "AUA/SUFU", 2024,
     "Overactive Bladder Treatment",
     "First-line: behavioral therapy (bladder training, timed voiding, pelvic floor exercises, fluid management). Second-line: oral antimuscarinics (oxybutynin, tolterodine, solifenacin) or beta-3 agonist (mirabegron, vibegron). Avoid antimuscarinics in elderly (dementia risk). Third-line: onabotulinumtoxinA (100 units intravesical), sacral neuromodulation, PTNS.",
     "A", "Strong", ["overactive bladder", "urge incontinence"], ["oxybutynin", "tolterodine", "mirabegron", "vibegron", "onabotulinumtoxinA"], ["postvoid residual", "urinalysis", "voiding diary", "urodynamics"], ["overactive bladder", "antimuscarinic", "mirabegron", "botox"]),

    ("AUA Prostate Cancer Screening Guidelines", "AUA", 2024,
     "Prostate Cancer Screening and Detection",
     "Shared decision-making for PSA screening starting age 55-69 (or 40 for high-risk: Black men, family history). PSA >3 ng/mL: risk calculators, multiparametric MRI (mpMRI) before biopsy (PI-RADS ≥3 = biopsy). MRI-targeted biopsy plus systematic biopsy. Genomic classifiers (Decipher, Oncotype, Prolaris) for treatment decisions. Active surveillance for low-risk (Gleason 6).",
     "A", "Strong", ["prostate cancer", "prostate cancer screening"], [], ["psa", "multiparametric mri prostate", "prostate biopsy", "genomic classifier"], ["prostate cancer", "psa screening", "mpmri", "active surveillance"]),

    ("AUA Testicular Torsion Guidelines", "AUA", 2024,
     "Testicular Torsion Management",
     "Surgical emergency: scrotal exploration within 6 hours of symptom onset for best salvage. Do NOT delay for imaging if high clinical suspicion. Doppler ultrasound if diagnosis uncertain. Manual detorsion may be attempted as temporizing measure (medial to lateral). Orchiopexy of affected and contralateral testis. Orchiectomy if non-viable. Peak incidence: adolescents.",
     "A", "Strong", ["testicular torsion"], [], ["scrotal ultrasound doppler"], ["testicular torsion", "scrotal emergency", "orchiopexy"]),

    # ══════════════════════════════════════════
    # ENT EXPANSION (~12)
    # ══════════════════════════════════════════
    ("AAO-HNS Sinusitis Guidelines", "AAO-HNS", 2024,
     "Acute Rhinosinusitis Management",
     "Viral (most cases): symptomatic treatment (saline irrigation, decongestants, analgesics). Bacterial (symptoms >10 days, double worsening, severe onset): amoxicillin-clavulanate first-line. Second-line: doxycycline or respiratory fluoroquinolone. Duration: 5-7 days for adults, 10-14 days for children. Avoid CT for uncomplicated acute rhinosinusitis.",
     "A", "Strong", ["acute rhinosinusitis", "acute sinusitis"], ["amoxicillin-clavulanate", "doxycycline", "fluticasone nasal"], ["ct sinus"], ["sinusitis", "amoxicillin", "saline irrigation", "rhinosinusitis"]),

    ("AAO-HNS Tonsillectomy Guidelines", "AAO-HNS", 2024,
     "Tonsillectomy Indications",
     "Recurrent strep pharyngitis: ≥7 episodes in 1 year, ≥5/year for 2 years, or ≥3/year for 3 years (Paradise criteria). Sleep-disordered breathing/OSA in children: most common indication. Peritonsillar abscess (recurrent or unresolved). Asymmetric tonsil enlargement: rule out malignancy. Postoperative: pain management (acetaminophen, ibuprofen; avoid ketorolac in children due to bleeding risk).",
     "A", "Strong", ["recurrent tonsillitis", "pediatric osa", "tonsillar hypertrophy"], ["acetaminophen", "ibuprofen", "amoxicillin"], ["polysomnography", "rapid strep test", "throat culture"], ["tonsillectomy", "strep pharyngitis", "paradise criteria", "osa"]),

    ("AAO-HNS Epistaxis Guidelines", "AAO-HNS", 2024,
     "Epistaxis Management",
     "First aid: firm continuous pressure for 20 minutes, lean forward. Anterior: topical oxymetazoline, cauterization with silver nitrate, anterior nasal packing (absorbable or non-absorbable). Posterior: posterior packing or balloon catheter, may require hospital admission. Refractory: embolization or sphenopalatine artery ligation. Workup for recurrent: CBC, PT/INR, consider hereditary hemorrhagic telangiectasia.",
     "B", "Strong", ["epistaxis", "nosebleed"], ["oxymetazoline", "tranexamic acid topical"], ["cbc", "pt/inr", "blood type"], ["epistaxis", "nasal packing", "cauterization", "nosebleed"]),

    ("AAO-HNS Sudden Sensorineural Hearing Loss", "AAO-HNS", 2024,
     "Sudden Hearing Loss Management",
     "ENT emergency: ≥30 dB loss over ≤72 hours. Audiogram within 14 days. MRI IAC to rule out vestibular schwannoma. Oral corticosteroids (prednisone 1 mg/kg/day for 10-14 days) first-line. Intratympanic dexamethasone for salvage or steroid contraindication. Avoid unnecessary antibiotics and antivirals. Spontaneous recovery in ~50%; worse prognosis with profound loss, vertigo, age >40.",
     "A", "Strong", ["sudden sensorineural hearing loss", "sudden deafness"], ["prednisone", "dexamethasone intratympanic"], ["audiogram", "mri iac", "cbc", "glucose", "esr"], ["sudden hearing loss", "ssnhl", "intratympanic steroid"]),

    # ══════════════════════════════════════════
    # OB/GYN EXPANSION (~20)
    # ══════════════════════════════════════════
    ("ACOG Prenatal Care Guidelines", "ACOG", 2024,
     "Routine Prenatal Care Schedule",
     "Visits: every 4 weeks until 28 weeks, every 2 weeks 28-36, then weekly until delivery. First visit: comprehensive history, physical, dating ultrasound if uncertain LMP. Labs: blood type, Rh, antibody screen, CBC, RPR, HIV, HBsAg, rubella immunity, urine culture, GC/CT. Genetic screening options: cfDNA (NIPT) or sequential screen. Anatomy scan 18-22 weeks.",
     "A", "Strong", ["prenatal care", "pregnancy"], [], ["cbc", "blood type", "rh antibody", "hbsag", "hiv", "rubella igg", "nipt", "anatomy ultrasound"], ["prenatal care", "pregnancy", "first trimester", "screening"]),

    ("ACOG Gestational Hypertension Guidelines", "ACOG", 2024,
     "Gestational Hypertension and Preeclampsia Management",
     "Gestational HTN: BP ≥140/90 after 20 weeks without proteinuria. Preeclampsia: add proteinuria or end-organ damage. Severe features: BP ≥160/110, plt <100k, liver transaminases 2x, renal insufficiency, pulmonary edema, cerebral/visual symptoms. Delivery at 37 weeks for gestational HTN/preeclampsia without severe features. Delivery at 34 weeks with severe features. Magnesium sulfate for seizure prophylaxis.",
     "A", "Strong", ["gestational hypertension", "preeclampsia"], ["magnesium sulfate", "labetalol", "nifedipine", "hydralazine"], ["blood pressure", "urine protein", "cbc", "cmp", "uric acid"], ["preeclampsia", "gestational hypertension", "magnesium sulfate"]),

    ("ACOG Postpartum Hemorrhage Guidelines", "ACOG", 2024,
     "Postpartum Hemorrhage Management",
     "PPH: blood loss ≥1000 mL or signs of hypovolemia. Uterine atony (most common cause): uterine massage, oxytocin, methylergonovine, carboprost, misoprostol. Tranexamic acid 1g IV within 3 hours. Intrauterine balloon tamponade. If medical management fails: uterine compression sutures (B-Lynch), uterine artery embolization, or hysterectomy. Activate massive transfusion protocol if needed.",
     "A", "Strong", ["postpartum hemorrhage", "uterine atony"], ["oxytocin", "methylergonovine", "carboprost", "misoprostol", "tranexamic acid"], ["hemoglobin", "fibrinogen", "blood type", "crossmatch"], ["postpartum hemorrhage", "uterine atony", "tranexamic acid", "tamponade"]),

    ("ACOG Placenta Previa Guidelines", "ACOG", 2024,
     "Placenta Previa Management",
     "Diagnosis: transvaginal ultrasound (TVS) is safe and more accurate than transabdominal. Complete previa at term: cesarean delivery at 36-37 weeks. Marginal previa (edge <2 cm from os): likely cesarean. Low-lying (2-3.5 cm from os): trial of labor may be appropriate. Antenatal: pelvic rest, avoid digital exams. Active bleeding: hospitalization, type and screen, Rh status, steroids if preterm.",
     "A", "Strong", ["placenta previa", "antepartum hemorrhage"], ["betamethasone"], ["transvaginal ultrasound", "hemoglobin", "blood type"], ["placenta previa", "cesarean delivery", "antepartum hemorrhage"]),

    ("ACOG Contraception Guidelines", "ACOG", 2024,
     "Long-Acting Reversible Contraception",
     "LARCs (IUDs and implant) are first-line for most women due to highest efficacy and continuation rates. Copper IUD: 10-year duration, no hormones. Levonorgestrel IUD: 3-8 years depending on device, reduces menstrual bleeding. Etonogestrel implant: 3-5 year duration. Immediate postpartum or post-abortion LARC insertion is safe and reduces unintended pregnancy. No age or parity restrictions.",
     "A", "Strong", ["contraception", "family planning"], ["levonorgestrel iud", "copper iud", "etonogestrel implant"], ["pregnancy test"], ["larc", "iud", "implant", "contraception"]),

    ("ACOG Abnormal Uterine Bleeding Guidelines", "ACOG", 2024,
     "AUB Evaluation and Management",
     "Classify by PALM-COEIN system: structural (Polyp, Adenomyosis, Leiomyoma, Malignancy) and non-structural (Coagulopathy, Ovulatory dysfunction, Endometrial, Iatrogenic, Not classified). Workup: CBC, pregnancy test, TSH, coagulation studies if indicated. TVS ± saline infusion sonography. Endometrial biopsy for age ≥45 or risk factors. Treatment: hormonal (OCP, IUD, progestins) or surgical (hysteroscopy, ablation, myomectomy, hysterectomy).",
     "A", "Strong", ["abnormal uterine bleeding", "heavy menstrual bleeding"], ["combined oral contraceptives", "levonorgestrel iud", "medroxyprogesterone", "tranexamic acid"], ["cbc", "pregnancy test", "tsh", "transvaginal ultrasound", "endometrial biopsy"], ["aub", "heavy periods", "endometrial biopsy", "palm-coein"]),

    ("NAMS Menopause Guidelines", "NAMS", 2024,
     "Menopausal Hormone Therapy",
     "MHT is most effective treatment for vasomotor symptoms (hot flashes). Initiate in women <60 or within 10 years of menopause. Estrogen alone for hysterectomy; estrogen + progesterone for intact uterus. Transdermal estradiol preferred (lower VTE risk). Low-dose vaginal estrogen for genitourinary syndrome of menopause (GSM) — no progesterone needed. Non-hormonal: fezolinetant (NK3 antagonist, FDA-approved), SSRIs/SNRIs, gabapentin.",
     "A", "Strong", ["menopause", "vasomotor symptoms", "genitourinary syndrome of menopause"], ["estradiol", "progesterone", "fezolinetant", "paroxetine", "gabapentin"], ["fsh", "estradiol level", "lipid panel", "mammogram", "dexa"], ["menopause", "hormone therapy", "hot flashes", "estrogen"]),

    ("ACOG Infertility Workup Guidelines", "ACOG/ASRM", 2024,
     "Infertility Evaluation",
     "Evaluate after 12 months of unprotected intercourse (6 months if age ≥35). Female: cycle history, day 3 FSH/estradiol or AMH, TVS antral follicle count, HSG or SIS for tubal patency, TSH, prolactin. Male: semen analysis. Ovulatory dysfunction: letrozole first-line for ovulation induction (superior to clomiphene for PCOS). Unexplained infertility: controlled ovarian stimulation + IUI, then IVF.",
     "A", "Strong", ["infertility", "anovulation", "tubal factor infertility"], ["letrozole", "clomiphene", "gonadotropins"], ["fsh", "amh", "estradiol", "semen analysis", "hsg", "tsh", "prolactin"], ["infertility", "ovulation induction", "letrozole", "ivf"]),

    # ══════════════════════════════════════════
    # ADDITIONAL CARDIOLOGY (~10)
    # ══════════════════════════════════════════
    ("ACC/AHA STEMI Guidelines", "ACC/AHA", 2024,
     "STEMI Reperfusion Strategy",
     "Primary PCI preferred if door-to-balloon ≤90 minutes. Transfer for PCI if first-medical-contact-to-device ≤120 minutes. Fibrinolysis (tenecteplase preferred) within 30 minutes if PCI not available in timely fashion. Dual antiplatelet (aspirin + P2Y12 inhibitor) loading dose before PCI. Radial access preferred. Culprit-lesion-only PCI in most cases; complete revascularization in cardiogenic shock.",
     "A", "Strong", ["stemi", "st-elevation myocardial infarction"], ["aspirin", "ticagrelor", "prasugrel", "heparin", "tenecteplase"], ["ecg", "troponin", "coronary angiogram"], ["stemi", "primary pci", "door-to-balloon", "fibrinolysis"]),

    ("ACC/AHA NSTEMI Guidelines", "ACC/AHA", 2024,
     "NSTE-ACS Management Strategy",
     "Risk stratify with GRACE or TIMI score. Immediate invasive strategy (<2 hours) for: refractory angina, hemodynamic instability, new HF, sustained VT/VF. Early invasive (24 hours) for: troponin rise, new ST changes, GRACE >140. Ischemia-guided strategy for low-risk patients. Anticoagulation (UFH, enoxaparin, or bivalirudin) for all. P2Y12 inhibitor: ticagrelor or clopidogrel.",
     "A", "Strong", ["nstemi", "unstable angina", "nste-acs"], ["aspirin", "ticagrelor", "clopidogrel", "enoxaparin", "heparin"], ["ecg", "troponin", "bnp", "creatinine", "coronary angiogram"], ["nstemi", "unstable angina", "invasive strategy", "grace score"]),

    ("ACC/AHA Aortic Stenosis Guidelines", "ACC/AHA", 2024,
     "Aortic Stenosis Intervention Timing",
     "Severe AS (valve area <1.0 cm², mean gradient >40 mmHg, Vmax >4 m/s): intervene when symptomatic (dyspnea, angina, syncope) or LVEF <50%. Asymptomatic severe AS: intervention for very severe AS (Vmax >5 m/s), exercise intolerance, or rapid progression. TAVR for patients ≥65 or high surgical risk. SAVR for younger patients or bicuspid valve with aortopathy. Avoid vasodilators in severe symptomatic AS.",
     "A", "Strong", ["aortic stenosis", "aortic valve disease"], [], ["echocardiogram", "ct aorta", "cardiac catheterization"], ["aortic stenosis", "tavr", "savr", "valve replacement"]),

    ("ACC/AHA Mitral Regurgitation Guidelines", "ACC/AHA", 2024,
     "Mitral Regurgitation Surgery Indications",
     "Primary MR (degenerative): surgery when symptomatic or LV dilation (LVESD >40mm) or LV dysfunction (EF <60%). Repair preferred over replacement when feasible at centers of excellence. Asymptomatic severe MR: surgery if EF 30-60% or LVESD ≥40mm or new AF or PASP >50 mmHg. Secondary MR (functional): optimize GDMT first. TEER (MitraClip) for secondary MR if symptomatic on GDMT with suitable anatomy.",
     "A", "Strong", ["mitral regurgitation", "mitral valve disease"], ["lisinopril", "carvedilol"], ["echocardiogram", "cardiac mri", "ejection fraction"], ["mitral regurgitation", "mitral repair", "mitraclip", "teer"]),

    ("ACC/AHA Cardiac Rehabilitation", "ACC/AHA/AACVPR", 2024,
     "Cardiac Rehabilitation Indications",
     "Class I recommendation for: post-MI, post-CABG, post-PCI, stable angina, heart failure (EF ≤35%), post-heart transplant, post-valve surgery. Exercise-based CR reduces all-cause mortality by 20-25%. 36 sessions over 12 weeks (3x/week). Components: exercise training, education, psychosocial support, risk factor modification. Home-based CR as alternative for barriers to center-based.",
     "A", "Strong", ["cardiac rehabilitation", "post-mi rehabilitation"], [], ["stress test", "vo2 max", "6-minute walk", "ejection fraction"], ["cardiac rehabilitation", "exercise", "post-mi", "secondary prevention"]),

    # ══════════════════════════════════════════
    # ADDITIONAL INFECTIOUS DISEASE (~10)
    # ══════════════════════════════════════════
    ("IDSA C. difficile Guidelines", "IDSA/SHEA", 2024,
     "C. difficile Infection Treatment",
     "Non-severe initial episode: fidaxomicin 200 mg BID for 10 days (preferred) or vancomycin 125 mg QID for 10 days. Severe CDI (WBC >15k, Cr >1.5): vancomycin 125 mg QID PO. Fulminant: vancomycin PO + rectal + IV metronidazole, surgical consult. First recurrence: fidaxomicin or vancomycin taper/pulse. ≥2 recurrences: fecal microbiota transplant (FMT). Discontinue inciting antibiotic if possible.",
     "A", "Strong", ["clostridioides difficile infection", "c diff colitis"], ["fidaxomicin", "vancomycin oral", "metronidazole"], ["c diff toxin pcr", "wbc", "creatinine", "lactate", "ct abdomen"], ["c diff", "fidaxomicin", "vancomycin", "fecal transplant"]),

    ("IDSA MRSA Infection Guidelines", "IDSA", 2024,
     "MRSA Treatment by Infection Type",
     "Skin abscess: incision and drainage is primary treatment (antibiotics may not be needed for small abscesses). Purulent cellulitis: TMP-SMX or doxycycline. Bacteremia: vancomycin or daptomycin (not for pneumonia). Pneumonia: vancomycin or linezolid (daptomycin inactivated by surfactant). Bone/joint: vancomycin + rifampin. Duration guided by infection type. Target vancomycin AUC/MIC 400-600.",
     "A", "Strong", ["mrsa infection", "mrsa skin infection", "mrsa bacteremia"], ["vancomycin", "daptomycin", "linezolid", "trimethoprim-sulfamethoxazole", "doxycycline"], ["mrsa culture", "vancomycin trough", "blood culture", "creatinine"], ["mrsa", "vancomycin", "daptomycin", "skin abscess"]),

    ("IDSA Candidiasis Guidelines", "IDSA", 2024,
     "Invasive Candidiasis Treatment",
     "Candidemia: echinocandin first-line (micafungin, caspofungin, anidulafungin). Fluconazole step-down after species identification and susceptibility (C. albicans, C. parapsilosis). Remove all central venous catheters. Ophthalmology exam for endophthalmitis. Duration: 14 days after first negative blood culture. C. auris: echinocandin first-line; inherent fluconazole resistance.",
     "A", "Strong", ["invasive candidiasis", "candidemia"], ["micafungin", "caspofungin", "fluconazole", "amphotericin b"], ["blood culture", "beta-d-glucan", "fungal culture"], ["candidemia", "echinocandin", "c auris", "antifungal"]),

    ("IDSA Lyme Disease Guidelines", "IDSA/AAN/ACR", 2024,
     "Lyme Disease Treatment",
     "Early localized (erythema migrans): doxycycline 100 mg BID x 10 days (preferred; also covers Anaplasma coinfection). Amoxicillin or cefuroxime as alternatives. Early disseminated (multiple EM, facial palsy, carditis): doxycycline PO for most. Lyme meningitis: doxycycline PO or ceftriaxone IV. Lyme arthritis: doxycycline 28 days; refractory: ceftriaxone 28 days. Post-treatment Lyme disease syndrome: no additional antibiotics.",
     "A", "Strong", ["lyme disease", "borrelia burgdorferi"], ["doxycycline", "amoxicillin", "ceftriaxone", "cefuroxime"], ["lyme serology", "western blot", "csf analysis", "ecg"], ["lyme disease", "erythema migrans", "doxycycline", "tick-borne"]),

    ("IDSA Endocarditis Guidelines", "AHA/IDSA", 2024,
     "Infective Endocarditis Treatment",
     "Native valve: empiric vancomycin + ceftriaxone until culture results. MSSA: nafcillin/oxacillin 6 weeks. MRSA: vancomycin or daptomycin 6 weeks. Streptococci: penicillin/ceftriaxone 4 weeks. Enterococci: ampicillin + ceftriaxone or ampicillin + gentamicin 6 weeks. Prosthetic valve: longer duration + rifampin. Surgical indications: heart failure, uncontrolled infection, large vegetation >10 mm with emboli.",
     "A", "Strong", ["infective endocarditis", "native valve endocarditis", "prosthetic valve endocarditis"], ["vancomycin", "nafcillin", "ceftriaxone", "ampicillin", "gentamicin", "rifampin"], ["blood cultures", "echocardiogram", "esr", "crp"], ["endocarditis", "blood cultures", "nafcillin", "duke criteria"]),
]


def main():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "clinical_guidelines.json")
    with open(fixture_path) as f:
        data = json.load(f)

    existing_ids = {s["section_id"] for s in data["guidelines"]}
    added = 0

    for entry in SECTIONS:
        guideline, society, year, title, text, grade, strength, conditions, meds, measurements, keywords = entry
        sid = _id(guideline, title)
        if sid in existing_ids:
            continue
        existing_ids.add(sid)
        data["guidelines"].append({
            "section_id": sid,
            "guideline": f"{guideline} ({year})",
            "section_title": title,
            "recommendation_text": text,
            "evidence_grade": grade,
            "recommendation_level": strength,
            "source_society": society,
            "applies_to_conditions": conditions,
            "applies_to_medications": meds,
            "applies_to_measurements": measurements,
            "keywords": keywords,
        })
        added += 1

    with open(fixture_path, "w") as f:
        json.dump(data, f, indent=2)

    total = len(data["guidelines"])
    print(f"Batch 6: added {added} sections (total now {total})")


if __name__ == "__main__":
    main()
