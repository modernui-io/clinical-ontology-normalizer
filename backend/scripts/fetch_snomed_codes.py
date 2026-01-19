#!/usr/bin/env python3
"""Fetch and process SNOMED CT codes from available sources.

This script creates a comprehensive SNOMED CT fixture file with:
- Core clinical concepts (diseases, findings, procedures, body structures)
- Hierarchical relationships (is-a)
- Clinical synonyms for common conditions
- Cross-mappings to ICD-10 where available

SNOMED CT sources:
- NLM UMLS (requires license): https://www.nlm.nih.gov/research/umls/
- SNOMED International Browser: https://browser.ihtsdotools.org/
- US Clinical Core Subset: https://www.nlm.nih.gov/research/umls/Snomed/snomed_main.html

Usage:
    python scripts/fetch_snomed_codes.py

This will:
1. Load existing SNOMED concepts from fixtures
2. Expand with clinical synonyms
3. Add hierarchy relationships
4. Add ICD-10 cross-mappings
5. Generate fixtures/snomed_codes.json
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

# Output paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
OUTPUT_FILE = FIXTURES_DIR / "snomed_codes.json"
EXISTING_SNOMED_FILE = FIXTURES_DIR / "snomed_concepts.json"

# ============================================================================
# SNOMED CT Semantic Tags (concept types)
# ============================================================================
SEMANTIC_TAGS = {
    "disorder": "Clinical Finding",
    "finding": "Clinical Finding",
    "procedure": "Procedure",
    "body structure": "Body Structure",
    "organism": "Organism",
    "substance": "Substance",
    "pharmaceutical / biologic product": "Drug",
    "physical object": "Physical Object",
    "observable entity": "Observable",
    "qualifier value": "Qualifier",
    "morphologic abnormality": "Morphology",
    "environment": "Environment",
    "event": "Event",
    "situation": "Situation",
    "specimen": "Specimen",
    "occupation": "Social Context",
    "regime/therapy": "Procedure",
    "cell": "Body Structure",
    "cell structure": "Body Structure",
    "geographic location": "Location",
    "physical force": "Physical Force",
    "social context": "Social Context",
    "attribute": "Attribute",
    "linkage concept": "Link",
    "assessment scale": "Scale",
    "tumor staging": "Staging",
    "administration method": "Administration",
    "basic dose form": "Dose Form",
    "intended site": "Body Site",
    "release characteristic": "Drug Property",
    "transformation": "Process",
    "state of matter": "Physical State",
    "unit of presentation": "Unit",
    "supplier": "Supplier",
    "product name": "Product",
}

# ============================================================================
# Clinical Synonyms for Common SNOMED Concepts
# ============================================================================
# Format: SNOMED code -> list of clinical synonyms
CLINICAL_SYNONYMS: dict[str, list[str]] = {
    # ==========================================================================
    # CARDIOVASCULAR
    # ==========================================================================
    "38341003": ["hypertension", "htn", "high blood pressure", "elevated bp", "essential hypertension"],
    "59621000": ["hypertension", "essential hypertension", "primary hypertension"],
    "49436004": ["atrial fibrillation", "afib", "a-fib", "af", "irregular heartbeat"],
    "84114007": ["heart failure", "chf", "congestive heart failure", "cardiac failure"],
    "42343007": ["congestive heart failure", "chf", "heart failure with congestion"],
    "22298006": ["myocardial infarction", "heart attack", "mi", "ami", "cardiac infarction"],
    "230690007": ["stroke", "cva", "cerebrovascular accident", "brain attack"],
    "195080001": ["coronary artery disease", "cad", "ischemic heart disease", "chd", "coronary atherosclerosis"],
    "53741008": ["coronary artery disease", "cad", "atherosclerotic heart disease"],
    "59282003": ["pulmonary embolism", "pe", "pulmonary embolus", "lung clot"],
    "128053003": ["deep vein thrombosis", "dvt", "deep venous thrombosis", "leg clot"],
    "271327008": ["syncope", "fainting", "passed out", "blackout"],
    "426749004": ["chronic atrial fibrillation", "permanent afib", "persistent afib"],
    "233873004": ["tachycardia", "rapid heart rate", "fast heartbeat"],
    "48867003": ["bradycardia", "slow heart rate", "slow heartbeat"],
    "44808001": ["cardiac arrhythmia", "arrhythmia", "dysrhythmia", "irregular heartbeat"],
    "399211009": ["angina pectoris", "angina", "chest pain on exertion", "cardiac chest pain"],
    "233970002": ["aortic stenosis", "as", "aortic valve stenosis"],
    "79619009": ["mitral regurgitation", "mr", "mitral insufficiency", "leaky mitral valve"],
    "60573004": ["aortic regurgitation", "ar", "aortic insufficiency"],
    "48724000": ["mitral stenosis", "ms", "mitral valve stenosis"],
    "36971009": ["pericarditis", "pericardial inflammation"],
    "195139005": ["cardiomyopathy", "heart muscle disease"],
    "399261000": ["peripheral artery disease", "pad", "pvd", "peripheral vascular disease"],

    # ==========================================================================
    # RESPIRATORY
    # ==========================================================================
    "233604007": ["pneumonia", "lung infection", "pulmonary infection", "pna"],
    "385093006": ["community acquired pneumonia", "cap", "community pneumonia"],
    "195967001": ["asthma", "bronchial asthma", "reactive airway disease"],
    "195951007": ["acute asthma", "asthma exacerbation", "asthma attack", "acute asthma flare"],
    "13645005": ["copd", "chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis"],
    "195957006": ["copd exacerbation", "aecopd", "copd flare", "acute on chronic copd"],
    "54150009": ["upper respiratory infection", "uri", "common cold", "viral uri"],
    "65710008": ["acute bronchitis", "chest cold", "bronchitis"],
    "409622000": ["respiratory failure", "lung failure"],
    "67782005": ["acute respiratory failure", "arf", "acute respiratory insufficiency"],
    "51599000": ["chronic respiratory failure", "chronic lung failure"],
    "44169009": ["pulmonary fibrosis", "lung fibrosis", "ipf", "interstitial lung disease"],
    "60845006": ["pleural effusion", "fluid around lung", "water on lung"],
    "36118008": ["pneumothorax", "collapsed lung", "lung collapse"],
    "233678006": ["obstructive sleep apnea", "osa", "sleep apnea", "apnea"],
    "61047003": ["bronchiectasis", "dilated bronchi"],
    "304527002": ["acute respiratory distress syndrome", "ards", "acute lung injury"],
    "56265001": ["pulmonary edema", "fluid in lungs", "wet lung"],
    "70995007": ["pulmonary hypertension", "pulmonary htn", "pah"],
    "47505003": ["lung cancer", "lung malignancy", "bronchogenic carcinoma"],

    # ==========================================================================
    # GASTROINTESTINAL
    # ==========================================================================
    "235595009": ["gerd", "acid reflux", "gastroesophageal reflux disease", "heartburn"],
    "235494005": ["gastritis", "stomach inflammation"],
    "13200003": ["peptic ulcer", "stomach ulcer", "gastric ulcer"],
    "397825006": ["duodenal ulcer", "peptic ulcer disease"],
    "74400008": ["appendicitis", "inflamed appendix"],
    "235919008": ["acute appendicitis", "appendicitis attack"],
    "235796008": ["cholecystitis", "gallbladder inflammation", "inflamed gallbladder"],
    "60342002": ["cholelithiasis", "gallstones", "gallbladder stones"],
    "48340000": ["pancreatitis", "pancreas inflammation"],
    "197456007": ["acute pancreatitis", "pancreatic inflammation acute"],
    "235919008": ["chronic pancreatitis", "chronic pancreatic inflammation"],
    "197321007": ["fatty liver disease", "nafld", "hepatic steatosis", "nash"],
    "19943007": ["cirrhosis", "liver cirrhosis", "hepatic cirrhosis"],
    "109819003": ["alcoholic liver disease", "alcoholic cirrhosis"],
    "64766004": ["ulcerative colitis", "uc", "inflammatory bowel disease uc"],
    "34000006": ["crohn disease", "crohns", "crohn's disease", "regional enteritis"],
    "14760008": ["diverticulitis", "diverticular disease"],
    "69478009": ["diverticulosis", "colonic diverticula"],
    "40733004": ["gastrointestinal bleeding", "gi bleed", "gi hemorrhage"],
    "74474003": ["gastrointestinal hemorrhage", "intestinal bleeding"],
    "14350001": ["irritable bowel syndrome", "ibs", "spastic colon"],
    "425876004": ["small bowel obstruction", "sbo", "intestinal obstruction"],
    "87200004": ["large bowel obstruction", "lbo", "colonic obstruction"],
    "300927001": ["constipation", "difficulty having bowel movements"],
    "62315008": ["diarrhea", "loose stools", "frequent bowel movements"],

    # ==========================================================================
    # ENDOCRINE / METABOLIC
    # ==========================================================================
    "44054006": ["type 2 diabetes", "dm2", "diabetes mellitus type 2", "t2dm", "niddm", "adult onset diabetes"],
    "46635009": ["type 1 diabetes", "dm1", "diabetes mellitus type 1", "t1dm", "iddm", "juvenile diabetes"],
    "73211009": ["diabetes mellitus", "diabetes", "dm", "sugar diabetes"],
    "4855003": ["diabetic retinopathy", "diabetes eye disease", "dm retinopathy"],
    "127013003": ["diabetic nephropathy", "diabetic kidney disease", "dm nephropathy"],
    "230572002": ["diabetic neuropathy", "diabetic nerve damage", "dm neuropathy"],
    "280137006": ["diabetic foot", "diabetic foot ulcer", "dm foot"],
    "40930008": ["hypothyroidism", "low thyroid", "underactive thyroid", "hashimoto"],
    "34486009": ["hyperthyroidism", "overactive thyroid", "thyrotoxicosis", "graves disease"],
    "13644009": ["hypercholesterolemia", "high cholesterol", "elevated cholesterol"],
    "55822004": ["hyperlipidemia", "high lipids", "dyslipidemia", "hlp"],
    "414916001": ["obesity", "obese", "overweight"],
    "83911000119104": ["morbid obesity", "severe obesity", "class 3 obesity"],
    "14140009": ["hyperkalemia", "high potassium", "elevated potassium"],
    "43339004": ["hypokalemia", "low potassium"],
    "267036007": ["hyponatremia", "low sodium"],
    "66931009": ["hypernatremia", "high sodium", "elevated sodium"],
    "237602007": ["metabolic syndrome", "syndrome x", "insulin resistance syndrome"],
    "190268003": ["gout", "gouty arthritis", "uric acid arthritis"],
    "386584007": ["anemia", "anaemia", "low blood count"],
    "87522002": ["iron deficiency anemia", "ida", "low iron"],
    "234347009": ["vitamin b12 deficiency", "b12 deficiency", "pernicious anemia"],

    # ==========================================================================
    # NEUROLOGICAL
    # ==========================================================================
    "37796009": ["migraine", "migraine headache", "sick headache"],
    "84757009": ["epilepsy", "seizure disorder", "seizures"],
    "91175000": ["seizure", "convulsion", "fit"],
    "49049000": ["parkinson disease", "parkinsons", "parkinsonism", "pd"],
    "26929004": ["alzheimer disease", "alzheimers", "alzheimer dementia"],
    "52448006": ["dementia", "memory loss", "cognitive decline"],
    "24700007": ["multiple sclerosis", "ms", "demyelinating disease"],
    "398729009": ["stroke", "cva", "cerebrovascular accident"],
    "432504007": ["ischemic stroke", "cerebral infarction", "brain infarct"],
    "274100004": ["hemorrhagic stroke", "brain hemorrhage", "intracranial hemorrhage"],
    "230265002": ["transient ischemic attack", "tia", "mini stroke"],
    "25064002": ["headache", "head pain", "cephalgia"],
    "51771007": ["cluster headache", "cluster"],
    "82272006": ["tension headache", "tension type headache", "stress headache"],
    "31190002": ["trigeminal neuralgia", "tic douloureux", "facial nerve pain"],
    "56729008": ["bell palsy", "bells palsy", "facial paralysis"],
    "26889001": ["myasthenia gravis", "mg", "muscle weakness autoimmune"],
    "28442001": ["peripheral neuropathy", "nerve damage", "neuropathy"],
    "23986001": ["guillain barre syndrome", "gbs", "ascending paralysis"],
    "192127007": ["carpal tunnel syndrome", "cts", "median nerve compression"],
    "128189009": ["sciatica", "sciatic nerve pain", "lumbar radiculopathy"],
    "193570009": ["essential tremor", "benign tremor", "familial tremor"],

    # ==========================================================================
    # MENTAL HEALTH
    # ==========================================================================
    "35489007": ["depression", "major depression", "mdd", "clinical depression", "depressive disorder"],
    "370143000": ["major depressive disorder", "major depression", "unipolar depression"],
    "197480006": ["anxiety disorder", "anxiety", "gad", "generalized anxiety"],
    "13746004": ["bipolar disorder", "manic depression", "bipolar", "bpad"],
    "58214004": ["schizophrenia", "psychosis", "schizophrenic disorder"],
    "7200002": ["alcoholism", "alcohol use disorder", "alcohol dependence", "aud"],
    "66590003": ["alcohol dependence", "alcoholism", "chronic alcoholism"],
    "56882008": ["substance abuse", "drug abuse", "substance use disorder"],
    "191816009": ["panic disorder", "panic attacks", "panic"],
    "231504006": ["ptsd", "post traumatic stress disorder", "post-traumatic stress", "trauma disorder"],
    "197306002": ["obsessive compulsive disorder", "ocd", "obsessive thoughts"],
    "25501002": ["social anxiety", "social phobia", "social anxiety disorder"],
    "35252006": ["bulimia nervosa", "bulimia", "binging and purging"],
    "56882008": ["anorexia nervosa", "anorexia", "eating disorder"],
    "406506008": ["attention deficit disorder", "adhd", "add", "hyperactivity"],
    "86765009": ["insomnia", "sleep difficulty", "trouble sleeping"],

    # ==========================================================================
    # MUSCULOSKELETAL
    # ==========================================================================
    "279039007": ["low back pain", "lbp", "lumbar pain", "lumbago", "back pain"],
    "81680005": ["neck pain", "cervicalgia", "cervical pain"],
    "396275006": ["osteoarthritis", "oa", "degenerative joint disease", "djd", "wear and tear arthritis"],
    "69896004": ["rheumatoid arthritis", "ra", "inflammatory arthritis"],
    "64859006": ["osteoporosis", "bone loss", "brittle bones"],
    "202708005": ["knee osteoarthritis", "knee oa", "knee arthritis"],
    "202409002": ["hip osteoarthritis", "hip oa", "hip arthritis"],
    "67849003": ["lumbar disc herniation", "herniated disc", "slipped disc", "disc prolapse"],
    "22253000": ["sciatica", "sciatic nerve pain", "lumbar radiculopathy"],
    "203095000": ["fibromyalgia", "fibro", "chronic widespread pain"],
    "24484000": ["spinal stenosis", "narrowing of spine", "stenotic spine"],
    "239721001": ["rotator cuff tear", "shoulder tear", "rotator cuff injury"],
    "35708008": ["plantar fasciitis", "heel pain", "heel spur syndrome"],
    "128133004": ["carpal tunnel syndrome", "cts", "wrist nerve compression"],
    "111266001": ["gout", "gouty arthritis", "uric acid crystals"],
    "239872002": ["tendinitis", "tendonitis", "tendon inflammation"],
    "239873007": ["bursitis", "joint inflammation", "bursa inflammation"],
    "95417003": ["fracture", "broken bone", "bone fracture"],
    "71620000": ["hip fracture", "broken hip", "femoral neck fracture"],
    "263102004": ["compression fracture", "vertebral compression", "spinal fracture"],
    "359817006": ["muscle strain", "pulled muscle", "muscle tear"],
    "49374001": ["muscle sprain", "ligament sprain", "sprained joint"],

    # ==========================================================================
    # GENITOURINARY
    # ==========================================================================
    "68566005": ["urinary tract infection", "uti", "bladder infection", "cystitis"],
    "45816000": ["pyelonephritis", "kidney infection", "renal infection"],
    "709044004": ["chronic kidney disease", "ckd", "chronic renal failure", "crf"],
    "236425005": ["acute kidney injury", "aki", "acute renal failure", "arf"],
    "90708001": ["kidney failure", "renal failure", "kidney disease"],
    "236423003": ["nephrolithiasis", "kidney stones", "renal calculi", "urolithiasis"],
    "266569009": ["benign prostatic hyperplasia", "bph", "enlarged prostate", "prostate enlargement"],
    "399068003": ["prostate cancer", "prostatic carcinoma", "prostate malignancy"],
    "254837009": ["breast cancer", "breast malignancy", "mammary carcinoma"],
    "95315005": ["bladder cancer", "bladder malignancy", "bladder carcinoma"],
    "23717007": ["benign prostatic hypertrophy", "bph", "prostate hypertrophy"],
    "197782009": ["polycystic kidney disease", "pkd", "cystic kidney"],
    "236578006": ["nephrotic syndrome", "protein in urine syndrome"],
    "47693006": ["glomerulonephritis", "kidney inflammation", "gn"],
    "40617009": ["urinary incontinence", "bladder leakage", "incontinence"],
    "31681005": ["urinary retention", "inability to urinate"],
    "14350001": ["erectile dysfunction", "ed", "impotence"],
    "237091009": ["ovarian cyst", "cyst on ovary"],
    "95315005": ["endometriosis", "endo", "uterine tissue disorder"],

    # ==========================================================================
    # INFECTIOUS DISEASES
    # ==========================================================================
    "91302008": ["sepsis", "septicemia", "blood infection", "severe infection"],
    "10509002": ["septic shock", "severe sepsis", "systemic infection"],
    "840544004": ["covid-19", "coronavirus", "sars-cov-2", "covid"],
    "6142004": ["influenza", "flu", "viral flu"],
    "442696006": ["influenza a", "flu a", "h1n1"],
    "186431008": ["clostridioides difficile", "c diff", "cdiff", "clostridium difficile"],
    "47447009": ["cellulitis", "skin infection", "soft tissue infection"],
    "91302008": ["bacteremia", "bacteria in blood"],
    "266096002": ["meningitis", "brain infection", "meningeal infection"],
    "186403000": ["mrsa", "methicillin resistant staph aureus", "staph infection"],
    "40610006": ["endocarditis", "heart valve infection", "infective endocarditis"],
    "235726002": ["osteomyelitis", "bone infection"],
    "57676002": ["herpes zoster", "shingles", "herpes"],
    "91861009": ["tuberculosis", "tb", "mycobacterium tuberculosis"],
    "186150001": ["viral hepatitis", "hepatitis", "liver infection"],
    "61977001": ["hepatitis b", "hep b", "hbv"],
    "50711007": ["hepatitis c", "hep c", "hcv"],
    "186747009": ["hiv", "human immunodeficiency virus", "aids", "hiv infection"],
    "2919008": ["candidiasis", "yeast infection", "thrush"],
    "186431008": ["c difficile infection", "cdi", "antibiotic associated colitis"],

    # ==========================================================================
    # DERMATOLOGY
    # ==========================================================================
    "200936003": ["psoriasis", "plaque psoriasis", "skin psoriasis"],
    "24079001": ["atopic dermatitis", "eczema", "atopic eczema"],
    "402408009": ["contact dermatitis", "allergic rash", "skin allergy"],
    "91487003": ["urticaria", "hives", "allergic urticaria"],
    "6142004": ["acne", "acne vulgaris", "pimples"],
    "39065001": ["skin ulcer", "pressure ulcer", "decubitus ulcer", "bedsore"],
    "399939002": ["melanoma", "skin cancer", "malignant melanoma"],
    "254637007": ["basal cell carcinoma", "bcc", "basal cell skin cancer"],
    "402415003": ["squamous cell carcinoma", "scc", "squamous skin cancer"],
    "95320005": ["seborrheic dermatitis", "seborrhea", "dandruff"],
    "238575004": ["rosacea", "facial redness"],
    "50563003": ["herpes simplex", "cold sore", "hsv"],
    "61462000": ["tinea", "ringworm", "fungal skin infection"],
    "2304001": ["intertrigo", "skin fold rash"],
    "238600003": ["alopecia", "hair loss", "balding"],

    # ==========================================================================
    # HEMATOLOGY / ONCOLOGY
    # ==========================================================================
    "109989006": ["anemia", "low hemoglobin", "low blood count"],
    "93143009": ["leukemia", "blood cancer", "white blood cell cancer"],
    "109989006": ["lymphoma", "lymph node cancer"],
    "93143009": ["acute leukemia", "acute blood cancer"],
    "94217008": ["chronic leukemia", "chronic blood cancer"],
    "109962001": ["diffuse large b-cell lymphoma", "dlbcl", "large cell lymphoma"],
    "118601006": ["hodgkin lymphoma", "hodgkins disease", "hodgkin disease"],
    "118617000": ["non-hodgkin lymphoma", "nhl", "non hodgkins"],
    "109989006": ["multiple myeloma", "myeloma", "plasma cell cancer"],
    "2092003": ["thrombocytopenia", "low platelets", "low platelet count"],
    "302215000": ["thrombocytosis", "high platelets", "elevated platelets"],
    "439926001": ["neutropenia", "low neutrophils", "low white count"],
    "234336002": ["polycythemia", "high red blood cells", "polycythemia vera"],
    "11854002": ["pancytopenia", "low blood counts"],
    "165517008": ["leukocytosis", "high white blood cells", "elevated wbc"],
    "128118004": ["deep vein thrombosis", "dvt", "blood clot in leg"],
    "441469009": ["coagulopathy", "bleeding disorder", "clotting disorder"],
    "64779008": ["anticoagulant use", "on blood thinners", "on anticoagulation"],

    # ==========================================================================
    # PROCEDURES
    # ==========================================================================
    "232717009": ["coronary artery bypass", "cabg", "bypass surgery", "heart bypass"],
    "36969009": ["cardiac catheterization", "heart cath", "coronary angiogram"],
    "16958000": ["percutaneous coronary intervention", "pci", "angioplasty", "stent placement"],
    "18286008": ["colonoscopy", "colon scope", "bowel scope"],
    "174716005": ["esophagogastroduodenoscopy", "egd", "upper endoscopy", "gastroscopy"],
    "447365002": ["hemodialysis", "dialysis", "hd", "kidney dialysis"],
    "265764009": ["total hip replacement", "thr", "hip replacement", "total hip arthroplasty"],
    "265765005": ["total knee replacement", "tkr", "knee replacement", "total knee arthroplasty"],
    "112943005": ["echocardiogram", "echo", "cardiac ultrasound"],
    "77477000": ["ct scan", "cat scan", "computed tomography"],
    "113091000": ["mri", "magnetic resonance imaging", "mr scan"],
    "168537006": ["chest x-ray", "cxr", "chest radiograph"],
    "71388002": ["bronchoscopy", "lung scope", "airway scope"],
    "180256009": ["lumbar puncture", "spinal tap", "lp"],
    "16001004": ["biopsy", "tissue sample"],
    "387713003": ["surgery", "surgical procedure", "operation"],
    "18590009": ["blood transfusion", "transfusion", "prbc transfusion"],
    "225302006": ["intubation", "endotracheal intubation", "eti"],
    "40701008": ["mechanical ventilation", "ventilator", "vent"],

    # ==========================================================================
    # BODY STRUCTURES
    # ==========================================================================
    "80891009": ["heart", "cardiac", "heart organ"],
    "39607008": ["lung", "lungs", "pulmonary"],
    "10200004": ["liver", "hepatic", "liver organ"],
    "64033007": ["kidney", "renal", "kidney organ"],
    "15497006": ["brain", "cerebral", "brain organ"],
    "421060004": ["spleen", "splenic"],
    "78961009": ["spinal cord", "cord", "medulla spinalis"],
    "45048000": ["stomach", "gastric"],
    "113276009": ["colon", "large intestine", "colonic"],
    "2739003": ["appendix", "vermiform appendix"],
    "28231008": ["pancreas", "pancreatic"],
    "56459004": ["esophagus", "esophageal"],
    "181268008": ["trachea", "windpipe"],
    "13024002": ["aorta", "aortic"],
    "110861005": ["coronary artery", "coronary arteries"],
    "64739004": ["femur", "thigh bone"],
    "71341001": ["tibia", "shin bone"],
    "83323007": ["humerus", "upper arm bone"],
    "62413002": ["radius", "forearm bone"],
    "85562004": ["hand", "manus"],
    "56459004": ["foot", "pes"],

    # ==========================================================================
    # SYMPTOMS / FINDINGS
    # ==========================================================================
    "267036007": ["chest pain", "chest discomfort", "thoracic pain"],
    "161891005": ["dyspnea", "shortness of breath", "sob", "breathlessness"],
    "271807003": ["fever", "febrile", "elevated temperature", "pyrexia"],
    "422587007": ["nausea", "feeling sick", "queasy"],
    "422400008": ["vomiting", "emesis", "throwing up"],
    "25064002": ["headache", "cephalgia", "head pain"],
    "21522001": ["abdominal pain", "stomach pain", "belly pain"],
    "62315008": ["diarrhea", "loose stools", "watery stool"],
    "300927001": ["constipation", "hard stools", "difficulty passing stool"],
    "84229001": ["fatigue", "tiredness", "exhaustion", "malaise"],
    "404640003": ["dizziness", "lightheadedness", "vertigo"],
    "49727002": ["cough", "coughing"],
    "13791008": ["sore throat", "pharyngitis", "throat pain"],
    "386661006": ["fever", "high temperature", "febrile"],
    "225358003": ["swelling", "edema", "oedema"],
    "161891005": ["shortness of breath", "dyspnea", "breathlessness"],
    "414478001": ["weakness", "asthenia", "feeling weak"],
    "102497002": ["weight loss", "losing weight", "unintentional weight loss"],
    "8943002": ["weight gain", "gaining weight"],
    "247592009": ["numbness", "paresthesia", "tingling"],
    "26079004": ["tremor", "shaking", "tremors"],
    "40917007": ["confusion", "altered mental status", "ams", "disorientation"],

    # ==========================================================================
    # LAB FINDINGS
    # ==========================================================================
    "166717003": ["elevated creatinine", "high creatinine", "azotemia"],
    "166698001": ["elevated bun", "high bun", "uremia"],
    "365866000": ["elevated glucose", "high blood sugar", "hyperglycemia"],
    "302866003": ["low hemoglobin", "anemia", "low hgb"],
    "165517008": ["elevated wbc", "leukocytosis", "high white count"],
    "415116008": ["elevated troponin", "positive troponin"],
    "166816001": ["elevated bnp", "high bnp"],
    "165825000": ["elevated liver enzymes", "transaminitis", "elevated ast alt"],
    "165609004": ["elevated inr", "high inr", "prolonged inr"],
    "166557991000119104": ["elevated psa", "high psa"],
    "166601001": ["elevated cholesterol", "hypercholesterolemia"],
    "166632002": ["elevated triglycerides", "hypertriglyceridemia"],
    "165679005": ["low potassium", "hypokalemia"],
    "166702009": ["high potassium", "hyperkalemia"],
    "267036007": ["low sodium", "hyponatremia"],
    "166717003": ["high sodium", "hypernatremia"],
    "271737000": ["positive blood culture", "bacteremia"],
    "167217005": ["positive urine culture", "uti", "urinary infection"],
}

# ============================================================================
# Hierarchical Relationships (is-a)
# ============================================================================
# Format: child_code -> parent_code
HIERARCHY_RELATIONSHIPS: dict[str, str] = {
    # Cardiovascular hierarchy
    "84114007": "56265001",  # Heart failure -> Disease of cardiovascular system
    "49436004": "44808001",  # Atrial fibrillation -> Cardiac arrhythmia
    "22298006": "53741008",  # MI -> Coronary artery disease

    # Respiratory hierarchy
    "195967001": "50043002",  # Asthma -> Respiratory disorder
    "13645005": "50043002",   # COPD -> Respiratory disorder
    "233604007": "50043002",  # Pneumonia -> Respiratory disorder

    # Diabetes hierarchy
    "44054006": "73211009",   # T2DM -> Diabetes mellitus
    "46635009": "73211009",   # T1DM -> Diabetes mellitus
    "4855003": "73211009",    # Diabetic retinopathy -> Diabetes
    "127013003": "73211009",  # Diabetic nephropathy -> Diabetes

    # Mental health hierarchy
    "35489007": "74732009",   # Depression -> Mental disorder
    "197480006": "74732009",  # Anxiety -> Mental disorder
    "13746004": "74732009",   # Bipolar -> Mental disorder

    # Infection hierarchy
    "91302008": "40733004",   # Sepsis -> Infection
    "68566005": "40733004",   # UTI -> Infection
    "233604007": "40733004",  # Pneumonia -> Infection
}

# ============================================================================
# ICD-10 Cross-Mappings
# ============================================================================
# Format: SNOMED code -> list of ICD-10 codes
SNOMED_TO_ICD10: dict[str, list[str]] = {
    # Cardiovascular
    "38341003": ["I10"],  # Hypertension
    "49436004": ["I48.91", "I48.0", "I48.1", "I48.2"],  # Atrial fibrillation
    "84114007": ["I50.9", "I50.22", "I50.32"],  # Heart failure
    "22298006": ["I21.9", "I21.0", "I21.3"],  # Myocardial infarction
    "53741008": ["I25.10"],  # Coronary artery disease
    "230690007": ["I63.9", "I61.9"],  # Stroke
    "59282003": ["I26.99", "I26.92"],  # Pulmonary embolism
    "128053003": ["I82.409", "I82.401"],  # DVT

    # Respiratory
    "233604007": ["J18.9", "J15.9", "J12.9"],  # Pneumonia
    "195967001": ["J45.909", "J45.20", "J45.30"],  # Asthma
    "13645005": ["J44.9", "J44.1"],  # COPD
    "54150009": ["J06.9"],  # URI
    "233678006": ["G47.33"],  # Sleep apnea

    # Gastrointestinal
    "235595009": ["K21.0"],  # GERD
    "74400008": ["K35.80"],  # Appendicitis
    "235796008": ["K81.0"],  # Cholecystitis
    "60342002": ["K80.20"],  # Cholelithiasis
    "19943007": ["K74.60"],  # Cirrhosis
    "64766004": ["K51.90"],  # Ulcerative colitis
    "34000006": ["K50.90"],  # Crohn disease

    # Endocrine/Metabolic
    "44054006": ["E11.9", "E11.65"],  # Type 2 diabetes
    "46635009": ["E10.9"],  # Type 1 diabetes
    "40930008": ["E03.9"],  # Hypothyroidism
    "34486009": ["E05.90"],  # Hyperthyroidism
    "55822004": ["E78.5"],  # Hyperlipidemia
    "414916001": ["E66.9", "E66.01"],  # Obesity
    "190268003": ["M10.9"],  # Gout

    # Neurological
    "37796009": ["G43.909"],  # Migraine
    "84757009": ["G40.909"],  # Epilepsy
    "49049000": ["G20"],  # Parkinson
    "26929004": ["G30.9"],  # Alzheimer
    "24700007": ["G35"],  # Multiple sclerosis

    # Mental Health
    "35489007": ["F32.9", "F33.0"],  # Depression
    "197480006": ["F41.1", "F41.9"],  # Anxiety
    "13746004": ["F31.9"],  # Bipolar
    "58214004": ["F20.9"],  # Schizophrenia

    # Musculoskeletal
    "279039007": ["M54.5"],  # Low back pain
    "81680005": ["M54.2"],  # Neck pain
    "396275006": ["M19.90"],  # Osteoarthritis
    "69896004": ["M06.9"],  # Rheumatoid arthritis
    "64859006": ["M81.0"],  # Osteoporosis
    "203095000": ["M79.7"],  # Fibromyalgia

    # Genitourinary
    "68566005": ["N39.0"],  # UTI
    "709044004": ["N18.9", "N18.3", "N18.4", "N18.5"],  # CKD
    "236425005": ["N17.9"],  # AKI
    "236423003": ["N20.0"],  # Kidney stones
    "266569009": ["N40.0", "N40.1"],  # BPH

    # Infectious
    "91302008": ["A41.9"],  # Sepsis
    "840544004": ["U07.1"],  # COVID-19
    "6142004": ["J11.1", "J10.1"],  # Influenza
    "47447009": ["L03.90"],  # Cellulitis

    # Symptoms
    "267036007": ["R07.9"],  # Chest pain
    "161891005": ["R06.02"],  # Dyspnea
    "271807003": ["R50.9"],  # Fever
    "25064002": ["R51"],  # Headache
    "21522001": ["R10.9"],  # Abdominal pain
    "84229001": ["R53.83"],  # Fatigue
    "404640003": ["R42"],  # Dizziness
}


def load_existing_snomed_concepts() -> list[dict[str, Any]]:
    """Load existing SNOMED concepts from fixture file."""
    concepts = []

    if EXISTING_SNOMED_FILE.exists():
        try:
            with open(EXISTING_SNOMED_FILE, "r") as f:
                data = json.load(f)
            concepts = data.get("concepts", [])
            print(f"Loaded {len(concepts)} existing SNOMED concepts")
        except Exception as e:
            print(f"Error loading existing SNOMED concepts: {e}")

    return concepts


def enrich_concept_with_synonyms(concept: dict[str, Any]) -> dict[str, Any]:
    """Add clinical synonyms to a concept."""
    code = concept.get("concept_code", "")

    # Check if we have clinical synonyms for this code
    if code in CLINICAL_SYNONYMS:
        existing_synonyms = set(concept.get("synonyms", []))
        clinical_syns = set(CLINICAL_SYNONYMS[code])
        concept["synonyms"] = list(existing_synonyms | clinical_syns)

    return concept


def add_hierarchy_info(concept: dict[str, Any]) -> dict[str, Any]:
    """Add hierarchy relationship information."""
    code = concept.get("concept_code", "")

    if code in HIERARCHY_RELATIONSHIPS:
        concept["parent_code"] = HIERARCHY_RELATIONSHIPS[code]

    return concept


def add_icd10_mapping(concept: dict[str, Any]) -> dict[str, Any]:
    """Add ICD-10 cross-mapping if available."""
    code = concept.get("concept_code", "")

    if code in SNOMED_TO_ICD10:
        concept["icd10_mappings"] = SNOMED_TO_ICD10[code]

    return concept


def determine_semantic_type(concept: dict[str, Any]) -> str:
    """Determine the semantic type from concept class or name."""
    concept_class = concept.get("concept_class_id", "").lower()
    concept_name = concept.get("concept_name", "").lower()

    # Check concept class
    for tag, semantic_type in SEMANTIC_TAGS.items():
        if tag in concept_class:
            return semantic_type

    # Infer from name
    if "(disorder)" in concept_name or "(disease)" in concept_name:
        return "Clinical Finding"
    elif "(finding)" in concept_name:
        return "Clinical Finding"
    elif "(procedure)" in concept_name:
        return "Procedure"
    elif "(body structure)" in concept_name:
        return "Body Structure"
    elif "(organism)" in concept_name:
        return "Organism"
    elif "(substance)" in concept_name:
        return "Substance"

    return concept.get("concept_class_id", "Unknown")


def generate_core_snomed_concepts() -> list[dict[str, Any]]:
    """Generate core SNOMED CT concepts programmatically.

    This creates essential clinical concepts that should be available
    even without an external data source.
    """
    concepts = []

    # Generate concepts from our synonym database
    for snomed_code, synonyms in CLINICAL_SYNONYMS.items():
        # First synonym is typically the primary name
        primary_name = synonyms[0] if synonyms else f"SNOMED {snomed_code}"

        # Determine semantic type from code patterns
        semantic_type = "Clinical Finding"  # Default

        # Try to determine more specific type from synonyms
        name_lower = primary_name.lower()
        if any(proc in name_lower for proc in ["surgery", "replacement", "catheterization", "scope", "biopsy"]):
            semantic_type = "Procedure"
        elif any(struct in name_lower for struct in ["heart", "lung", "liver", "kidney", "brain", "bone"]):
            semantic_type = "Body Structure"

        concept = {
            "concept_code": snomed_code,
            "concept_name": primary_name.title(),
            "domain_id": "Condition" if semantic_type == "Clinical Finding" else semantic_type,
            "vocabulary_id": "SNOMED",
            "concept_class_id": semantic_type,
            "standard_concept": "S",
            "synonyms": synonyms,
        }

        # Add ICD-10 mapping
        if snomed_code in SNOMED_TO_ICD10:
            concept["icd10_mappings"] = SNOMED_TO_ICD10[snomed_code]

        # Add hierarchy
        if snomed_code in HIERARCHY_RELATIONSHIPS:
            concept["parent_code"] = HIERARCHY_RELATIONSHIPS[snomed_code]

        concepts.append(concept)

    return concepts


def process_concepts(concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process and enrich all concepts."""
    processed = []
    seen_codes = set()

    for concept in concepts:
        code = concept.get("concept_code", "")
        if not code or code in seen_codes:
            continue

        # Enrich concept
        concept = enrich_concept_with_synonyms(concept)
        concept = add_hierarchy_info(concept)
        concept = add_icd10_mapping(concept)

        # Add semantic type if missing
        if "semantic_type" not in concept:
            concept["semantic_type"] = determine_semantic_type(concept)

        processed.append(concept)
        seen_codes.add(code)

    return processed


def calculate_statistics(concepts: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate statistics about the concept database."""
    stats = {
        "total_concepts": len(concepts),
        "with_synonyms": 0,
        "with_icd10_mapping": 0,
        "with_hierarchy": 0,
        "by_domain": {},
        "by_semantic_type": {},
    }

    for concept in concepts:
        if concept.get("synonyms"):
            stats["with_synonyms"] += 1
        if concept.get("icd10_mappings"):
            stats["with_icd10_mapping"] += 1
        if concept.get("parent_code"):
            stats["with_hierarchy"] += 1

        domain = concept.get("domain_id", "Unknown")
        stats["by_domain"][domain] = stats["by_domain"].get(domain, 0) + 1

        sem_type = concept.get("semantic_type", concept.get("concept_class_id", "Unknown"))
        stats["by_semantic_type"][sem_type] = stats["by_semantic_type"].get(sem_type, 0) + 1

    return stats


def main():
    """Main function to generate SNOMED CT codes fixture."""
    print("=" * 60)
    print("SNOMED CT Code Database Generator")
    print("=" * 60)

    # Ensure fixtures directory exists
    FIXTURES_DIR.mkdir(exist_ok=True)

    # Load existing concepts
    existing_concepts = load_existing_snomed_concepts()

    # Generate core concepts from our synonym database
    core_concepts = generate_core_snomed_concepts()
    print(f"Generated {len(core_concepts)} core concepts from clinical synonyms")

    # Merge: existing + core (core takes precedence for enrichment)
    all_concepts = []
    seen_codes = set()

    # First add core concepts (they have richer synonym data)
    for concept in core_concepts:
        code = concept.get("concept_code", "")
        if code:
            all_concepts.append(concept)
            seen_codes.add(code)

    # Then add existing concepts that aren't in core
    for concept in existing_concepts:
        code = concept.get("concept_code", "")
        if code and code not in seen_codes:
            # Enrich existing concept with our data
            concept = enrich_concept_with_synonyms(concept)
            concept = add_hierarchy_info(concept)
            concept = add_icd10_mapping(concept)
            concept["semantic_type"] = determine_semantic_type(concept)
            all_concepts.append(concept)
            seen_codes.add(code)

    # Process all concepts
    processed_concepts = process_concepts(all_concepts)

    # Sort by code
    processed_concepts.sort(key=lambda x: x.get("concept_code", ""))

    # Calculate statistics
    stats = calculate_statistics(processed_concepts)

    # Build output data
    output_data = {
        "metadata": {
            "source": "SNOMED CT Clinical Expansion",
            "description": "SNOMED CT concepts with clinical synonyms and ICD-10 mappings",
            **stats,
        },
        "concepts": processed_concepts,
    }

    # Save to file
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output_data, f, indent=2)

    print()
    print("=" * 60)
    print(f"Generated: {OUTPUT_FILE}")
    print(f"Total concepts: {stats['total_concepts']:,}")
    print(f"With synonyms: {stats['with_synonyms']:,}")
    print(f"With ICD-10 mapping: {stats['with_icd10_mapping']:,}")
    print(f"With hierarchy: {stats['with_hierarchy']:,}")
    print()
    print("By Domain:")
    for domain, count in sorted(stats["by_domain"].items(), key=lambda x: -x[1]):
        print(f"  {domain}: {count:,}")
    print()
    print("By Semantic Type:")
    for sem_type, count in sorted(stats["by_semantic_type"].items(), key=lambda x: -x[1])[:10]:
        print(f"  {sem_type}: {count:,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
