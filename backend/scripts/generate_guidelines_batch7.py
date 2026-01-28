#!/usr/bin/env python3
"""Batch 7: ~250 sections to reach ~1000 total.

Focuses on deep-dive expansions in Oncology, GI, Endocrinology, Nephrology,
Rheumatology, Critical Care, Emergency Medicine, Hematology, Preventive Medicine,
Rehabilitation, and Palliative Care.
"""

import json, os, hashlib

def _id(guideline, title):
    raw = f"{guideline}|{title}"
    h = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"b7-{h}"

SECTIONS = [
    # ══════════════════════════════════════════
    # ONCOLOGY DEEP DIVE (~30)
    # ══════════════════════════════════════════
    ("NCCN Non-Small Cell Lung Cancer Guidelines", "NCCN", 2025,
     "NSCLC Stage I-II Treatment",
     "Stage I-II NSCLC: surgical resection (lobectomy preferred, segmentectomy for small peripheral tumors or poor candidates). SBRT for medically inoperable. Adjuvant chemotherapy (cisplatin-based doublet) for stage II and high-risk IB (tumor >4 cm). Adjuvant osimertinib for EGFR+ resected IB-IIIA. Adjuvant atezolizumab for PD-L1 ≥1% resected II-IIIA after chemo.",
     "A", "Strong", ["non-small cell lung cancer", "nsclc"], ["cisplatin", "osimertinib", "atezolizumab", "pemetrexed"], ["ct chest", "pet-ct", "pulmonary function tests", "mediastinoscopy"], ["nsclc", "lobectomy", "adjuvant chemo", "osimertinib"]),

    ("NCCN Non-Small Cell Lung Cancer Guidelines", "NCCN", 2025,
     "NSCLC Advanced Stage Treatment",
     "Stage IV: molecular testing (EGFR, ALK, ROS1, BRAF, KRAS G12C, MET, RET, NTRK, HER2) and PD-L1 before treatment. No driver mutation and PD-L1 ≥50%: pembrolizumab monotherapy or chemo-IO. PD-L1 <50%: chemo + pembrolizumab. EGFR+: osimertinib first-line. ALK+: alectinib or lorlatinib first-line. Brain metastases: targeted therapy with CNS activity or radiation.",
     "A", "Strong", ["advanced nsclc", "metastatic nsclc"], ["pembrolizumab", "osimertinib", "alectinib", "lorlatinib", "carboplatin", "pemetrexed"], ["ct chest", "mri brain", "pet-ct", "pd-l1", "molecular panel"], ["nsclc", "immunotherapy", "targeted therapy", "pd-l1"]),

    ("NCCN Small Cell Lung Cancer Guidelines", "NCCN", 2025,
     "SCLC Treatment",
     "Limited stage: concurrent chemoradiation (cisplatin/etoposide + thoracic RT) followed by prophylactic cranial irradiation (PCI) for responders. Extensive stage: carboplatin/etoposide + atezolizumab or durvalumab (IO) for 4 cycles, then IO maintenance. PCI or MRI surveillance for extensive stage. Topotecan or lurbinectedin for relapse.",
     "A", "Strong", ["small cell lung cancer", "sclc"], ["cisplatin", "etoposide", "atezolizumab", "durvalumab", "topotecan", "lurbinectedin"], ["ct chest", "mri brain", "pet-ct"], ["sclc", "chemoradiation", "immunotherapy", "prophylactic cranial"]),

    ("NCCN Pancreatic Cancer Guidelines", "NCCN", 2025,
     "Pancreatic Adenocarcinoma Treatment",
     "Resectable: upfront surgery (Whipple or distal pancreatectomy) followed by adjuvant modified FOLFIRINOX (preferred) or gemcitabine/capecitabine for 6 months. Borderline resectable: neoadjuvant FOLFIRINOX or gemcitabine/nab-paclitaxel then reassess. Unresectable/metastatic: FOLFIRINOX or gemcitabine/nab-paclitaxel. BRCA+: platinum-based chemo then olaparib maintenance. CA 19-9 for monitoring.",
     "A", "Strong", ["pancreatic cancer", "pancreatic adenocarcinoma"], ["fluorouracil", "oxaliplatin", "irinotecan", "gemcitabine", "nab-paclitaxel", "olaparib"], ["ct abdomen", "ca 19-9", "eus", "mri abdomen", "genetic testing"], ["pancreatic cancer", "whipple", "folfirinox", "brca"]),

    ("NCCN Renal Cell Carcinoma Guidelines", "NCCN", 2025,
     "RCC Treatment by Stage",
     "Localized (T1a ≤4 cm): partial nephrectomy preferred, ablation for poor surgical candidates, active surveillance for small masses in elderly. Localized (T1b-T3): partial or radical nephrectomy. Adjuvant: pembrolizumab for high-risk resected ccRCC. Metastatic first-line: ipilimumab/nivolumab or cabozantinib/nivolumab or pembrolizumab/lenvatinib (IMDC intermediate/poor risk). Cytoreductive nephrectomy selectively.",
     "A", "Strong", ["renal cell carcinoma", "kidney cancer"], ["nivolumab", "ipilimumab", "cabozantinib", "pembrolizumab", "lenvatinib", "sunitinib"], ["ct abdomen", "mri brain", "bone scan"], ["rcc", "nephrectomy", "immunotherapy", "imdc"]),

    ("NCCN Melanoma Guidelines", "NCCN", 2025,
     "Cutaneous Melanoma Treatment",
     "In situ: excision with 5 mm margins. Stage I (<1mm): WLE 1 cm margins; SLN biopsy if ≥0.8 mm or ulcerated. Stage II (1-4mm): WLE 1-2 cm margins, SLN biopsy. Stage III (node-positive): adjuvant nivolumab, pembrolizumab, or dabrafenib/trametinib (BRAF V600+). Stage IV: first-line nivolumab+relatlimab or pembrolizumab; BRAF+: targeted therapy option. BRAF testing for all stage III-IV.",
     "A", "Strong", ["cutaneous melanoma", "malignant melanoma"], ["nivolumab", "pembrolizumab", "dabrafenib", "trametinib", "relatlimab"], ["dermoscopy", "sentinel node biopsy", "pet-ct", "ldh", "braf mutation"], ["melanoma", "immunotherapy", "braf", "sentinel node"]),

    ("NCCN Immunotherapy Management Guidelines", "NCCN", 2025,
     "Immune Checkpoint Inhibitor Toxicity Management",
     "Grade 1 irAE: continue ICI with close monitoring. Grade 2: hold ICI, prednisone 0.5-1 mg/kg. Grade 3: hold ICI, methylprednisolone 1-2 mg/kg IV. Grade 4: permanently discontinue ICI, methylprednisolone 1-2 mg/kg IV, organ-specific management. Common irAEs: dermatitis (most frequent), colitis, hepatitis, pneumonitis, thyroiditis, hypophysitis, myocarditis (rare, life-threatening). Endocrine irAEs may require lifelong replacement.",
     "A", "Strong", ["immune checkpoint inhibitor toxicity", "immune-related adverse events"], ["prednisone", "methylprednisolone", "infliximab", "mycophenolate"], ["cbc", "cmp", "tsh", "ft4", "cortisol", "troponin", "lipase"], ["irae", "immunotherapy toxicity", "checkpoint inhibitor", "colitis"]),

    ("NCCN Cancer Pain Management Guidelines", "NCCN", 2025,
     "Cancer Pain Assessment and Treatment",
     "Comprehensive pain assessment using validated scale. Mild pain (1-3): non-opioid analgesics (acetaminophen, NSAIDs). Moderate (4-6): weak opioid (tramadol) or low-dose strong opioid. Severe (7-10): strong opioids (morphine, hydromorphone, oxycodone, fentanyl). Short-acting for breakthrough, long-acting for baseline. Opioid rotation for tolerance or side effects. Adjuvants: gabapentin for neuropathic, steroids for bone/inflammation. Palliative radiation for bone metastases.",
     "A", "Strong", ["cancer pain", "malignant pain"], ["morphine", "hydromorphone", "oxycodone", "fentanyl", "gabapentin", "dexamethasone"], ["pain score", "functional assessment"], ["cancer pain", "opioid", "pain management", "palliative"]),

    ("NCCN Antiemesis Guidelines", "NCCN/ASCO", 2025,
     "Chemotherapy-Induced Nausea and Vomiting Prevention",
     "High emetic risk (cisplatin, AC): NK1 antagonist (aprepitant/fosaprepitant) + 5-HT3 antagonist (ondansetron/palonosetron) + dexamethasone + olanzapine. Moderate risk: 5-HT3 + dexamethasone ± NK1. Low risk: dexamethasone or 5-HT3 alone. Minimal risk: PRN only. Delayed CINV: olanzapine 10 mg days 1-4 or NK1 antagonist continuation. Anticipatory: lorazepam, behavioral therapy.",
     "A", "Strong", ["chemotherapy-induced nausea", "cinv"], ["aprepitant", "ondansetron", "palonosetron", "dexamethasone", "olanzapine"], [], ["cinv", "antiemetic", "olanzapine", "nk1 antagonist"]),

    ("NCCN Febrile Neutropenia Guidelines", "NCCN/IDSA", 2025,
     "Febrile Neutropenia Management",
     "Fever ≥38.3°C or sustained ≥38.0°C with ANC <500. Immediate blood cultures (2 sets, peripheral + central line) and empiric broad-spectrum antibiotics within 1 hour: cefepime, meropenem, or piperacillin-tazobactam. Add vancomycin for hemodynamic instability, skin/soft tissue infection, or MRSA risk. Persistent fever day 4-7: add antifungal (caspofungin or voriconazole). G-CSF for high-risk patients.",
     "A", "Strong", ["febrile neutropenia"], ["cefepime", "meropenem", "piperacillin-tazobactam", "vancomycin", "caspofungin", "filgrastim"], ["anc", "blood cultures", "lactate", "procalcitonin", "ct chest"], ["febrile neutropenia", "empiric antibiotics", "g-csf"]),

    ("NCCN Survivorship Guidelines", "NCCN", 2025,
     "Cancer Survivorship Care",
     "Survivorship care plan after completion of active treatment. Surveillance schedule per cancer type. Late effects monitoring: cardiotoxicity (anthracyclines, radiation), secondary malignancies, neuropathy, cognitive dysfunction, endocrine dysfunction, fertility, psychosocial distress. Annual screening: mammography, colonoscopy per risk. Exercise 150 min/week. Psychosocial support and screening (distress thermometer). Smoking cessation.",
     "B", "Strong", ["cancer survivorship", "late effects of cancer treatment"], [], ["echocardiogram", "tsh", "fsh", "bone density"], ["survivorship", "late effects", "surveillance", "distress"]),

    ("NCCN Palliative Radiation Guidelines", "NCCN/ASTRO", 2025,
     "Palliative Radiotherapy Indications",
     "Bone metastases: single fraction 8 Gy as effective as multifraction for pain relief. Brain metastases: whole brain RT (WBRT) or stereotactic radiosurgery (SRS) based on number, size, and performance status. Spinal cord compression: urgent RT ± surgery. Tumor bleeding: hemostatic RT. Superior vena cava syndrome: RT + stent. Hypofractionated regimens preferred for convenience.",
     "A", "Strong", ["bone metastases", "brain metastases", "spinal cord compression"], ["dexamethasone"], ["mri spine", "ct", "bone scan"], ["palliative radiation", "bone metastases", "brain metastases", "srs"]),

    # ══════════════════════════════════════════
    # GI DEEP DIVE (~20)
    # ══════════════════════════════════════════
    ("ACG Acute Pancreatitis Guidelines", "ACG", 2024,
     "Acute Pancreatitis Management",
     "Diagnosis: 2 of 3 (abdominal pain, lipase >3x ULN, imaging findings). Goal-directed fluid resuscitation with LR (not NS). Early oral feeding within 24 hours as tolerated. No role for prophylactic antibiotics. ERCP within 24h for acute cholangitis or biliary obstruction. Cholecystectomy during same admission for mild gallstone pancreatitis. Necrosectomy (endoscopic step-up approach) for infected necrosis.",
     "A", "Strong", ["acute pancreatitis", "gallstone pancreatitis"], ["lactated ringers", "acetaminophen"], ["lipase", "ct abdomen", "mrcp", "cbc", "bmp", "crp"], ["pancreatitis", "lipase", "ercp", "necrosectomy"]),

    ("ACG Chronic Pancreatitis Guidelines", "ACG", 2024,
     "Chronic Pancreatitis Management",
     "Pain management: non-opioid first (acetaminophen, NSAIDs), then weak opioids, then strong opioids. Pancreatic enzyme replacement therapy (PERT) for exocrine insufficiency (steatorrhea, weight loss). Fecal elastase-1 <200 = exocrine insufficiency. Fat-soluble vitamin monitoring (A, D, E, K). Endoscopic therapy for ductal stones/strictures. Total pancreatectomy with islet autotransplant for refractory pain.",
     "B", "Strong", ["chronic pancreatitis", "exocrine insufficiency"], ["pancrelipase", "acetaminophen", "pregabalin"], ["fecal elastase", "ct abdomen", "mrcp", "vitamin d", "hba1c"], ["chronic pancreatitis", "enzyme replacement", "pert", "fecal elastase"]),

    ("AASLD Hepatitis B Guidelines", "AASLD", 2024,
     "Chronic Hepatitis B Treatment",
     "Treat if: immune-active phase (elevated ALT + HBV DNA >2000 for HBeAg- or >20,000 for HBeAg+), cirrhosis with detectable HBV DNA, or immunosuppression-related reactivation risk. First-line: entecavir or tenofovir (TDF or TAF). TAF preferred for bone/renal risk. Peg-IFN-alpha for finite therapy attempt. HCC surveillance: ultrasound ± AFP every 6 months for cirrhosis or high-risk. HBV DNA and ALT every 3-6 months on therapy.",
     "A", "Strong", ["chronic hepatitis b", "hbv"], ["entecavir", "tenofovir alafenamide", "tenofovir disoproxil", "peginterferon alfa"], ["hbv dna", "alt", "hbeag", "hbsag", "afp", "abdominal ultrasound", "fibroscan"], ["hepatitis b", "entecavir", "tenofovir", "hcc surveillance"]),

    ("AASLD Hepatitis C Guidelines", "AASLD/IDSA", 2024,
     "Chronic Hepatitis C Treatment",
     "Pan-genotypic DAA regimens for all patients: sofosbuvir/velpatasvir (12 weeks) or glecaprevir/pibrentasvir (8-12 weeks). Cure rate (SVR12) >95%. Check genotype, fibrosis stage (FIB-4, fibroscan), and decompensation. Ribavirin-containing regimens for decompensated cirrhosis. No NS3/4A protease inhibitors in decompensated cirrhosis. HCC screening continues post-SVR for cirrhosis patients.",
     "A", "Strong", ["chronic hepatitis c", "hcv"], ["sofosbuvir-velpatasvir", "glecaprevir-pibrentasvir", "ribavirin"], ["hcv rna", "hcv genotype", "fibroscan", "fib-4", "cbc", "inr", "alt"], ["hepatitis c", "daa", "svr12", "sofosbuvir"]),

    ("AASLD Alcoholic Hepatitis Guidelines", "AASLD", 2024,
     "Severe Alcoholic Hepatitis Treatment",
     "Severity: Maddrey discriminant function (MDF) ≥32 = severe, or MELD ≥21. Severe AH: prednisolone 40 mg/day for 28 days (if no contraindications: infection, GI bleeding, renal failure). Assess Lille score at day 7: >0.45 = non-responder (stop steroids). Pentoxifylline no longer recommended. NAC as adjunct to steroids may improve survival. Nutritional support 35-40 kcal/kg/day. Early liver transplant for selected non-responders.",
     "A", "Strong", ["alcoholic hepatitis", "alcohol-associated hepatitis"], ["prednisolone", "n-acetylcysteine"], ["maddrey df", "meld", "lille score", "bilirubin", "inr", "creatinine"], ["alcoholic hepatitis", "maddrey", "prednisolone", "lille score"]),

    ("AASLD Portal Hypertension Guidelines", "AASLD/Baveno VII", 2024,
     "Portal Hypertension and Variceal Bleeding",
     "Screening: EGD for all cirrhotics at diagnosis. LSM by FibroScan: <20 kPa with platelets >150k = low risk (avoid EGD). Small varices no red signs: non-selective beta-blocker (NSBB: carvedilol 6.25-12.5 mg/day preferred). Large varices: NSBB or endoscopic variceal ligation (EVL) for primary prophylaxis. Acute variceal bleed: octreotide + antibiotics + EVL within 12 hours. TIPS if refractory bleed or early TIPS for high-risk.",
     "A", "Strong", ["portal hypertension", "esophageal varices", "variceal bleeding"], ["carvedilol", "octreotide", "ceftriaxone", "nadolol"], ["egd", "fibroscan", "platelet count", "hepatic venous pressure gradient"], ["portal hypertension", "varices", "carvedilol", "evl", "tips"]),

    ("AASLD Drug-Induced Liver Injury Guidelines", "AASLD/ACG", 2024,
     "DILI Recognition and Management",
     "Diagnosis of exclusion: temporal relationship to drug exposure, exclude viral hepatitis, autoimmune hepatitis, biliary obstruction. Roussel Uclaf Causality Assessment Method (RUCAM). Patterns: hepatocellular (ALT >5x, R >5), cholestatic (ALP >2x, R <2), mixed. Offending agent withdrawal is primary treatment. N-acetylcysteine for non-APAP DILI may improve outcomes. Corticosteroids for DILI with autoimmune features. Hy's Law (ALT >3x + bilirubin >2x + no ALP) predicts fulminant hepatic failure risk.",
     "B", "Strong", ["drug-induced liver injury", "dili", "hepatotoxicity"], ["n-acetylcysteine", "prednisone"], ["alt", "ast", "alp", "bilirubin", "inr", "hepatitis panel", "autoimmune markers"], ["dili", "hepatotoxicity", "rucam", "hys law"]),

    ("ACG Upper GI Bleeding Guidelines", "ACG", 2024,
     "Upper GI Hemorrhage Management",
     "Risk stratify: Glasgow-Blatchford score (GBS) 0-1 = outpatient management. Resuscitation: IV access, crystalloid, type and crossmatch. PPI infusion (esomeprazole 80 mg bolus then 8 mg/h) for suspected peptic ulcer bleed. EGD within 24 hours (urgent <12 hours for hemodynamically unstable). Hemostatic therapy: epinephrine injection + thermal/mechanical or hemoclip. Transfuse for Hb <7 g/dL (threshold <8 for CAD). Rebleed: repeat endoscopy or angiographic embolization.",
     "A", "Strong", ["upper gi bleeding", "peptic ulcer bleeding"], ["esomeprazole", "pantoprazole", "octreotide", "tranexamic acid"], ["hemoglobin", "bun", "creatinine", "inr", "type and screen", "egd"], ["upper gi bleed", "ppi", "endoscopy", "glasgow-blatchford"]),

    ("ACG Lower GI Bleeding Guidelines", "ACG", 2024,
     "Lower GI Bleeding Management",
     "Most common: diverticular bleeding (self-limited in 80%). Risk stratify: hemodynamic stability, anticoagulation status, comorbidities. Colonoscopy within 24 hours for hospitalized patients after bowel prep. CT angiography for massive bleeding or unstable patients. Interventional radiology embolization for active bleeding on CTA. Surgery for recurrent or life-threatening hemorrhage. Resume anticoagulation as soon as hemostasis confirmed.",
     "B", "Strong", ["lower gi bleeding", "diverticular bleeding"], [], ["hemoglobin", "inr", "ct angiography", "colonoscopy", "type and screen"], ["lower gi bleed", "diverticular", "colonoscopy", "ct angiography"]),

    ("ACG Cholangitis Guidelines", "ACG/ASGE", 2024,
     "Acute Cholangitis Management",
     "Tokyo Guidelines severity grading: Grade I (mild), Grade II (moderate: WBC >12k or >39°C or age >75 or bilirubin >5), Grade III (severe: organ dysfunction). All: IV antibiotics (piperacillin-tazobactam or carbapenem) + biliary drainage. Grade I-II: ERCP within 24-48 hours. Grade III: urgent ERCP or percutaneous drainage after ICU stabilization. Blood cultures before antibiotics. Definitive treatment of underlying cause (stone, stricture, tumor).",
     "A", "Strong", ["acute cholangitis", "ascending cholangitis"], ["piperacillin-tazobactam", "meropenem", "ciprofloxacin", "metronidazole"], ["bilirubin", "wbc", "blood cultures", "mrcp", "eus"], ["cholangitis", "ercp", "tokyo guidelines", "biliary drainage"]),

    # ══════════════════════════════════════════
    # ENDOCRINOLOGY EXPANSION (~15)
    # ══════════════════════════════════════════
    ("Endocrine Society Primary Hyperparathyroidism Guidelines", "Endocrine Society", 2024,
     "Primary Hyperparathyroidism Management",
     "Diagnosis: elevated calcium + elevated or inappropriately normal PTH. Surgery (parathyroidectomy) recommended for: symptomatic, calcium >1 mg/dL above ULN, T-score ≤-2.5 (any site), eGFR <60, age <50, nephrolithiasis/nephrocalcinosis. Preoperative localization: sestamibi scan + ultrasound. Intraoperative PTH monitoring. If surgery declined: cinacalcet for hypercalcemia, bisphosphonate/denosumab for bone.",
     "A", "Strong", ["primary hyperparathyroidism"], ["cinacalcet", "alendronate", "denosumab"], ["calcium", "pth", "vitamin d", "24-hour urine calcium", "dexa", "egfr", "renal ultrasound"], ["hyperparathyroidism", "parathyroidectomy", "hypercalcemia", "cinacalcet"]),

    ("Endocrine Society Adrenal Insufficiency Guidelines", "Endocrine Society", 2024,
     "Adrenal Insufficiency Diagnosis and Treatment",
     "Primary AI (Addison disease): low morning cortisol (<3), high ACTH, cosyntropin stim test (cortisol <18 at 30/60 min). Secondary AI: low cortisol, low/normal ACTH. Replacement: hydrocortisone 15-25 mg/day in 2-3 divided doses (mimicking diurnal rhythm). Fludrocortisone 0.05-0.2 mg/day for primary AI (mineralocorticoid). Stress dosing: double/triple dose for illness/surgery. Medical alert bracelet. Emergency injection training.",
     "A", "Strong", ["adrenal insufficiency", "addison disease", "secondary adrenal insufficiency"], ["hydrocortisone", "fludrocortisone", "dexamethasone"], ["morning cortisol", "acth", "cosyntropin stimulation test", "renin", "aldosterone", "electrolytes"], ["adrenal insufficiency", "hydrocortisone", "stress dosing", "addison"]),

    ("Endocrine Society Hypogonadism Guidelines", "Endocrine Society", 2024,
     "Male Hypogonadism Treatment",
     "Diagnosis: symptoms + 2 morning total testosterone <300 ng/dL. Confirm with repeat measurement + free T or SHBG. Evaluate: LH/FSH to distinguish primary vs secondary. MRI pituitary if secondary. Testosterone replacement: topical gel (most common), IM injection (cypionate or enanthate), subcutaneous pellets. Monitor: hematocrit (stop if >54%), PSA, lipids. Contraindicated: desire for fertility (use hCG/clomiphene), active prostate cancer, uncontrolled HF, severe OSA.",
     "A", "Strong", ["male hypogonadism", "testosterone deficiency"], ["testosterone cypionate", "testosterone gel", "clomiphene", "hcg"], ["total testosterone", "free testosterone", "lh", "fsh", "shbg", "hematocrit", "psa"], ["hypogonadism", "testosterone replacement", "hematocrit"]),

    ("Endocrine Society Transgender Hormone Therapy Guidelines", "Endocrine Society/WPATH", 2024,
     "Gender-Affirming Hormone Therapy",
     "Transfeminine: estradiol (oral, transdermal, or IM) + anti-androgen (spironolactone, GnRH agonist, or cyproterone). Monitor estradiol 100-200 pg/mL, testosterone <50 ng/dL. Transmasculine: testosterone (IM cypionate/enanthate or topical gel). Target testosterone 300-1000 ng/dL. Both: assess cardiovascular risk, bone density, mental health. VTE risk higher with oral estradiol. Fertility preservation counseling before initiation.",
     "B", "Strong", ["gender dysphoria", "transgender care"], ["estradiol", "spironolactone", "testosterone cypionate", "leuprolide"], ["estradiol level", "testosterone level", "cbc", "lipid panel", "bmp", "prolactin"], ["transgender", "hormone therapy", "gender affirming", "estradiol"]),

    ("Endocrine Society Metabolic Syndrome Guidelines", "Endocrine Society/AHA", 2024,
     "Metabolic Syndrome Management",
     "Diagnosis: ≥3 of 5 criteria (waist >40 in M/35 in F, TG ≥150, HDL <40 M/<50 F, BP ≥130/85, fasting glucose ≥100). Lifestyle modification is cornerstone: weight loss 7-10%, Mediterranean diet, 150 min/week exercise. Treat individual components to target. GLP-1 RA (semaglutide, liraglutide) for obesity + cardiometabolic benefit. Metformin for prediabetes. Statin for elevated ASCVD risk.",
     "A", "Strong", ["metabolic syndrome"], ["metformin", "semaglutide", "atorvastatin", "lisinopril"], ["waist circumference", "fasting glucose", "triglycerides", "hdl", "blood pressure", "hba1c"], ["metabolic syndrome", "insulin resistance", "lifestyle modification"]),

    ("Endocrine Society Prolactinoma Guidelines", "Endocrine Society", 2024,
     "Prolactinoma Management",
     "Microprolactinoma (<10 mm): cabergoline first-line (superior efficacy and tolerability vs bromocriptine). Target: normalize prolactin, restore gonadal function. Macroprolactinoma (≥10 mm): cabergoline, higher doses may be needed. MRI at 3-6 months. Surgery (transsphenoidal) for medication intolerance, resistance, or apoplexy. Taper/discontinue after 2+ years if prolactin normal and tumor shrinkage. Monitor visual fields for macroadenoma.",
     "A", "Strong", ["prolactinoma", "hyperprolactinemia"], ["cabergoline", "bromocriptine"], ["prolactin", "mri pituitary", "visual field testing", "lh", "fsh", "testosterone", "estradiol"], ["prolactinoma", "cabergoline", "pituitary adenoma"]),

    ("Endocrine Society Diabetes Insipidus Guidelines", "Endocrine Society", 2024,
     "Diabetes Insipidus Diagnosis and Treatment",
     "Suspect DI: polyuria (>3 L/day), polydipsia, dilute urine (osmolality <300). Copeptin-based diagnosis replacing water deprivation test: arginine-stimulated copeptin differentiates central vs nephrogenic. Central DI: desmopressin (DDAVP) intranasal, oral, or SC. Nephrogenic DI: treat underlying cause, thiazide diuretic + amiloride, low-sodium/low-protein diet, NSAIDs. Monitor serum sodium to avoid hyponatremia on DDAVP.",
     "A", "Strong", ["diabetes insipidus", "central diabetes insipidus", "nephrogenic diabetes insipidus"], ["desmopressin", "hydrochlorothiazide", "amiloride", "indomethacin"], ["serum sodium", "urine osmolality", "serum osmolality", "copeptin", "mri pituitary"], ["diabetes insipidus", "desmopressin", "copeptin", "polyuria"]),

    # ══════════════════════════════════════════
    # NEPHROLOGY EXPANSION (~15)
    # ══════════════════════════════════════════
    ("KDIGO Acute Kidney Injury Guidelines", "KDIGO", 2024,
     "AKI Staging and Management",
     "KDIGO staging: Stage 1 (Cr 1.5-1.9x or UO <0.5 mL/kg/h x6h), Stage 2 (Cr 2.0-2.9x or UO <0.5 x12h), Stage 3 (Cr ≥3x or ≥4 mg/dL or UO <0.3 x24h or anuria x12h or RRT). Management: identify and treat cause, optimize volume status, avoid nephrotoxins, adjust medications for GFR. RRT indications: refractory hyperkalemia, acidosis, fluid overload, uremia symptoms. No benefit of early vs late RRT initiation for most.",
     "A", "Strong", ["acute kidney injury", "aki"], ["sodium bicarbonate", "calcium gluconate", "furosemide"], ["creatinine", "bun", "urine output", "urinalysis", "renal ultrasound", "fractional excretion of sodium"], ["aki", "kdigo", "renal replacement therapy", "creatinine"]),

    ("KDIGO Glomerulonephritis Guidelines", "KDIGO", 2024,
     "Glomerulonephritis Workup and Treatment",
     "Workup: UA with microscopy (dysmorphic RBC, RBC casts), 24-hour urine protein or UPCR, serum complement (C3/C4), ANCA, anti-GBM, ANA, anti-dsDNA, hepatitis B/C, HIV, SPEP/UPEP, cryoglobulins. Renal biopsy for definitive diagnosis. IgA nephropathy: SGLT2 inhibitor + RAS blockade; sparsentan. Membranous: anti-PLA2R; rituximab first-line. ANCA vasculitis: rituximab + glucocorticoids. Lupus nephritis: mycophenolate + glucocorticoids induction.",
     "A", "Strong", ["glomerulonephritis", "iga nephropathy", "membranous nephropathy", "anca vasculitis"], ["mycophenolate", "rituximab", "cyclophosphamide", "prednisone", "sparsentan"], ["urinalysis", "upcr", "c3", "c4", "anca", "anti-gbm", "anti-pla2r", "renal biopsy"], ["glomerulonephritis", "iga nephropathy", "rituximab", "renal biopsy"]),

    ("KDIGO Nephrotic Syndrome Guidelines", "KDIGO", 2024,
     "Adult Nephrotic Syndrome Management",
     "Diagnosis: proteinuria >3.5 g/day, hypoalbuminemia, edema, hyperlipidemia. Renal biopsy for adults (unlike children). MCD: prednisone 1 mg/kg/day x 4-16 weeks, taper slowly. FSGS: prednisone or calcineurin inhibitor (tacrolimus). Membranous: anti-PLA2R guided; rituximab first-line. General: ACEi/ARB for proteinuria reduction, SGLT2 inhibitor, diuretics for edema, statin, anticoagulation if albumin <2.5 (high VTE risk).",
     "A", "Strong", ["nephrotic syndrome", "minimal change disease", "focal segmental glomerulosclerosis"], ["prednisone", "tacrolimus", "rituximab", "furosemide", "lisinopril", "atorvastatin"], ["24h urine protein", "albumin", "lipid panel", "renal biopsy", "anti-pla2r"], ["nephrotic syndrome", "proteinuria", "rituximab", "albumin"]),

    ("KDIGO Polycystic Kidney Disease Guidelines", "KDIGO", 2024,
     "ADPKD Management",
     "Tolvaptan for rapidly progressive ADPKD (Mayo classification 1C-1E, eGFR >25, age 18-55). Monitor for hepatotoxicity (LFTs monthly for 18 months). Adequate hydration (3+ L/day) to suppress vasopressin. BP target <110/75 for young adults with preserved GFR. ACEi/ARB first-line for hypertension. Avoid caffeine. Screen for intracranial aneurysm with MRA if family history of aneurysm/SAH. Monitor eGFR and total kidney volume.",
     "A", "Strong", ["autosomal dominant polycystic kidney disease", "adpkd"], ["tolvaptan", "lisinopril"], ["egfr", "total kidney volume", "mri kidneys", "mra brain", "alt", "ast"], ["adpkd", "tolvaptan", "polycystic", "total kidney volume"]),

    ("KDIGO Electrolyte Disorders Guidelines", "KDIGO", 2024,
     "Hyponatremia Management",
     "Classify: hypovolemic, euvolemic (SIADH most common), hypervolemic (HF, cirrhosis). Acute (<48h) or symptomatic: 3% NaCl 100-150 mL bolus, may repeat x2. Rate limit: <10 mEq/L in 24h, <18 in 48h (6-8 mEq/L/24h for high ODS risk: chronic hyponatremia, hypokalemia, malnutrition, alcoholism). SIADH chronic: fluid restriction, salt tabs, urea, tolvaptan (avoid in liver disease). If overcorrected: D5W ± desmopressin to re-lower sodium.",
     "A", "Strong", ["hyponatremia", "siadh"], ["sodium chloride 3%", "tolvaptan", "desmopressin", "urea"], ["serum sodium", "serum osmolality", "urine sodium", "urine osmolality", "tsh", "cortisol"], ["hyponatremia", "siadh", "osmotic demyelination", "sodium correction"]),

    ("KDIGO Electrolyte Disorders Guidelines", "KDIGO", 2024,
     "Hyperkalemia Emergency Management",
     "Severe (>6.5 or ECG changes): IV calcium gluconate (membrane stabilization, onset 1-3 min). Shift potassium intracellularly: insulin 10 units + D50 (onset 15-30 min), sodium bicarbonate if acidotic, albuterol nebulized. Remove potassium: furosemide, sodium polystyrene sulfonate (SPS) or patiromer or SZC (sodium zirconium cyclosilicate). Hemodialysis for refractory or severe. Continuous cardiac monitoring. Avoid succinylcholine.",
     "A", "Strong", ["hyperkalemia"], ["calcium gluconate", "insulin", "dextrose", "albuterol", "patiromer", "sodium zirconium cyclosilicate", "furosemide"], ["potassium", "ecg", "bmp"], ["hyperkalemia", "ecg changes", "calcium gluconate", "emergency"]),

    # ══════════════════════════════════════════
    # RHEUMATOLOGY EXPANSION (~15)
    # ══════════════════════════════════════════
    ("ACR/EULAR Systemic Lupus Erythematosus Guidelines", "ACR/EULAR", 2024,
     "SLE Treatment Strategy",
     "Hydroxychloroquine for ALL SLE patients (reduces flares, damage accrual, mortality). Skin/joints: hydroxychloroquine ± short-course low-dose steroids. Moderate: add methotrexate or azathioprine. Severe (nephritis, cerebritis): mycophenolate or cyclophosphamide + glucocorticoids. Belimumab or anifrolumab as add-on for refractory. Lupus nephritis Class III/IV: mycophenolate or cyclophosphamide induction, voclosporin as add-on; maintenance mycophenolate. Target: steroid-free remission.",
     "A", "Strong", ["systemic lupus erythematosus", "lupus nephritis"], ["hydroxychloroquine", "mycophenolate", "cyclophosphamide", "belimumab", "anifrolumab", "voclosporin"], ["ana", "anti-dsdna", "complement c3/c4", "cbc", "creatinine", "upcr", "renal biopsy"], ["sle", "lupus", "hydroxychloroquine", "mycophenolate"]),

    ("ACR ANCA Vasculitis Guidelines", "ACR/EULAR", 2024,
     "ANCA-Associated Vasculitis Treatment",
     "Remission induction: rituximab (preferred) or cyclophosphamide + glucocorticoids. Avacopan (C5a receptor inhibitor) as glucocorticoid-sparing adjunct. Rapid taper glucocorticoids. Severe renal involvement (creatinine >5.7 or dialysis-dependent): consider plasma exchange (limited evidence). Maintenance: rituximab every 6 months (at least 2 years). Alternative maintenance: azathioprine or methotrexate. Monitor ANCA titers, eGFR, CRP.",
     "A", "Strong", ["anca vasculitis", "granulomatosis with polyangiitis", "microscopic polyangiitis"], ["rituximab", "cyclophosphamide", "avacopan", "prednisone", "azathioprine"], ["anca", "mpo", "pr3", "creatinine", "urinalysis", "crp", "ct chest"], ["anca vasculitis", "rituximab", "avacopan", "gpa"]),

    ("GRAPPA Psoriatic Arthritis Guidelines", "GRAPPA/EULAR", 2024,
     "Psoriatic Arthritis Treatment",
     "Mild peripheral arthritis: NSAIDs, then csDMARD (methotrexate). Moderate-severe: bDMARD (TNF inhibitor: adalimumab, etanercept; IL-17: secukinumab, ixekizumab; IL-23: guselkumab, risankizumab) or tsDMARD (JAK inhibitor: tofacitinib, upadacitinib). Axial disease: TNFi or IL-17i (no role for methotrexate). Enthesitis: TNFi, IL-17i. Dactylitis: TNFi or IL-17i. Skin dominant: IL-23i or IL-17i preferred. Consider domain-based approach.",
     "A", "Strong", ["psoriatic arthritis"], ["methotrexate", "adalimumab", "secukinumab", "guselkumab", "tofacitinib", "upadacitinib"], ["crp", "esr", "joint x-rays", "mri", "skin assessment"], ["psoriatic arthritis", "biologics", "il-17", "domain-based"]),

    ("ACR Antiphospholipid Syndrome Guidelines", "ACR/EULAR", 2024,
     "Antiphospholipid Syndrome Management",
     "Thrombotic APS: lifelong anticoagulation with warfarin (target INR 2-3 for venous, 3-4 for arterial in some). Avoid DOACs (inferior for APS, especially triple-positive). Obstetric APS: low-dose aspirin + prophylactic heparin during pregnancy. Catastrophic APS: anticoagulation + high-dose steroids + plasma exchange + IVIG. Risk stratification: triple positivity (LA + aCL + anti-β2GPI) = highest thrombotic risk. Hydroxychloroquine may reduce recurrent thrombosis.",
     "A", "Strong", ["antiphospholipid syndrome", "aps"], ["warfarin", "heparin", "aspirin", "hydroxychloroquine"], ["lupus anticoagulant", "anticardiolipin", "anti-beta2 glycoprotein", "inr", "aptt"], ["antiphospholipid", "warfarin", "triple positive", "catastrophic aps"]),

    ("ACR IgG4-Related Disease Guidelines", "ACR", 2024,
     "IgG4-Related Disease Treatment",
     "Glucocorticoids are first-line: prednisone 0.6 mg/kg/day for 2-4 weeks then taper over 3-6 months. Steroid-sparing agents: rituximab (most evidence), mycophenolate, azathioprine. Rituximab for relapsing or steroid-dependent disease. Organ damage may be irreversible (fibrosis). Monitor IgG4 levels (not always reliable). Common manifestations: autoimmune pancreatitis, retroperitoneal fibrosis, sclerosing cholangitis, orbital pseudotumor, lymphadenopathy.",
     "B", "Strong", ["igg4-related disease", "autoimmune pancreatitis"], ["prednisone", "rituximab", "mycophenolate", "azathioprine"], ["igg4 level", "igg subclasses", "ct abdomen", "mri", "tissue biopsy"], ["igg4", "rituximab", "autoimmune pancreatitis", "fibrosis"]),

    ("ACR Sarcoidosis Guidelines", "ACR/ATS/ERS", 2024,
     "Sarcoidosis Treatment",
     "Observation for asymptomatic stage I/II with normal pulmonary function. Treatment indications: symptomatic, progressive lung disease, extrapulmonary involvement (cardiac, neuro, eye, liver, hypercalcemia). First-line: prednisone 20-40 mg/day, taper over 6-12 months. Steroid-sparing: methotrexate, azathioprine, mycophenolate. Refractory: infliximab or adalimumab. Cardiac sarcoidosis: immunosuppression + device evaluation (ICD if EF <35% or sustained VT).",
     "B", "Strong", ["sarcoidosis", "pulmonary sarcoidosis", "cardiac sarcoidosis"], ["prednisone", "methotrexate", "infliximab", "azathioprine"], ["ct chest", "pfts", "ace level", "calcium", "cardiac mri", "pet-ct"], ["sarcoidosis", "granulomatous", "methotrexate", "infliximab"]),

    # ══════════════════════════════════════════
    # CRITICAL CARE EXPANSION (~20)
    # ══════════════════════════════════════════
    ("ARDS Network / ATS/ESICM ARDS Guidelines", "ATS/ESICM", 2024,
     "ARDS Ventilator Management",
     "Low tidal volume ventilation: 6 mL/kg predicted body weight. Plateau pressure ≤30 cmH2O. PEEP titration per FiO2-PEEP table (or driving pressure ≤15). Prone positioning ≥16 hours/day for P/F <150. Neuromuscular blockade (cisatracurium) for 48h if severe ARDS. Conservative fluid strategy. Recruitment maneuvers with caution. ECMO for refractory hypoxemia (P/F <80 despite optimal ventilation).",
     "A", "Strong", ["ards", "acute respiratory distress syndrome"], ["cisatracurium", "fentanyl", "propofol", "midazolam"], ["pao2/fio2 ratio", "plateau pressure", "driving pressure", "tidal volume", "abg"], ["ards", "lung protective ventilation", "prone positioning", "ecmo"]),

    ("SSC Sepsis Guidelines", "SCCM/ESICM", 2024,
     "Sepsis Hour-1 Bundle",
     "Within 1 hour: measure lactate (re-measure if initial >2), obtain blood cultures before antibiotics, administer broad-spectrum antibiotics, give 30 mL/kg crystalloid for hypotension or lactate ≥4. If hypotension persists after fluids: start vasopressors (norepinephrine first-line) targeting MAP ≥65. Dynamic measures to guide further fluids (passive leg raise, stroke volume variation). Source control within 6-12 hours. De-escalate antibiotics when culture data available.",
     "A", "Strong", ["sepsis", "septic shock"], ["norepinephrine", "vasopressin", "hydrocortisone", "piperacillin-tazobactam", "meropenem"], ["lactate", "blood cultures", "procalcitonin", "map", "urine output", "creatinine"], ["sepsis bundle", "norepinephrine", "lactate", "hour-1"]),

    ("SSC Vasopressor Management", "SCCM", 2024,
     "Vasopressor Selection in Shock",
     "Septic shock: norepinephrine first-line (target MAP ≥65). Add vasopressin 0.03-0.04 U/min as second agent (catecholamine-sparing). Third-line: epinephrine. Stress-dose hydrocortisone 200 mg/day if vasopressor requirements escalate despite norepinephrine + vasopressin. Cardiogenic shock: norepinephrine or dobutamine (or combination). Avoid dopamine except in bradycardia without pacer access. Phenylephrine: pure vasoconstriction for neurogenic shock.",
     "A", "Strong", ["septic shock", "vasodilatory shock", "cardiogenic shock"], ["norepinephrine", "vasopressin", "epinephrine", "dobutamine", "hydrocortisone", "phenylephrine"], ["map", "cardiac output", "svr", "lactate", "central venous oxygen saturation"], ["vasopressor", "norepinephrine", "vasopressin", "shock"]),

    ("PADIS ICU Sedation Guidelines", "SCCM", 2024,
     "ICU Sedation and Analgesia Protocol",
     "Pain first (analgesia-first sedation): fentanyl or hydromorphone drip. Sedation assessment: RASS target 0 to -2 for most patients. Propofol or dexmedetomidine preferred over benzodiazepines (less delirium). Daily sedation interruption (SAT) + spontaneous breathing trial (SBT). Delirium prevention: minimize benzodiazepines, early mobilization, sleep promotion. Delirium treatment: address underlying cause; haloperidol or quetiapine for hyperactive delirium.",
     "A", "Strong", ["icu sedation", "icu delirium", "icu pain management"], ["fentanyl", "propofol", "dexmedetomidine", "haloperidol", "quetiapine"], ["rass score", "cam-icu", "cpot pain scale", "bps"], ["sedation", "dexmedetomidine", "cam-icu", "delirium"]),

    ("TRICC / AABB Blood Transfusion Guidelines", "AABB", 2024,
     "Restrictive Transfusion Strategy",
     "Restrictive transfusion threshold: Hb <7 g/dL for hemodynamically stable adults (including ICU). Hb <8 g/dL for acute coronary syndrome, major orthopedic surgery, or symptomatic anemia. Single-unit transfusion with reassessment. Massive transfusion (>10 units in 24h): 1:1:1 ratio pRBC:FFP:platelets. Transfuse platelets <10k (non-bleeding) or <50k (active bleeding/procedure). Cryoprecipitate for fibrinogen <150.",
     "A", "Strong", ["anemia", "blood transfusion", "massive hemorrhage"], ["packed red blood cells", "fresh frozen plasma", "platelets", "cryoprecipitate", "tranexamic acid"], ["hemoglobin", "hematocrit", "inr", "fibrinogen", "platelet count", "type and screen"], ["transfusion", "restrictive", "massive transfusion", "hemoglobin"]),

    ("ATS Ventilator Liberation Guidelines", "ATS/ACCP", 2024,
     "Weaning from Mechanical Ventilation",
     "Daily screening for readiness: FiO2 ≤40%, PEEP ≤5-8, hemodynamically stable, adequate mentation, minimal vasopressors. Spontaneous breathing trial (SBT): 30-120 minutes on T-piece, CPAP, or pressure support ≤5-7. Extubation if SBT successful: RR <35, SpO2 ≥90%, stable HR/BP, no distress. Cuff leak test for high-risk patients (prolonged intubation, prior failed extubation). High-flow nasal cannula post-extubation for high risk. NIV for hypercapnic patients or post-extubation respiratory failure.",
     "A", "Strong", ["ventilator weaning", "extubation readiness"], [], ["rapid shallow breathing index", "negative inspiratory force", "pao2/fio2", "etco2"], ["ventilator liberation", "sbt", "extubation", "weaning"]),

    ("TTM2/ILCOR Targeted Temperature Management", "ILCOR/AHA", 2024,
     "Post-Cardiac Arrest Temperature Management",
     "Actively prevent fever (target ≤37.5°C) for all comatose post-cardiac arrest patients. Targeted hypothermia (32-36°C for 24 hours) no longer universally recommended (TTM2 trial: normothermia = hypothermia). Active temperature control for at least 72 hours. Neuroprognostication: multimodal approach at ≥72 hours post-arrest (neurologic exam, EEG, SSEP, neuron-specific enolase, MRI brain). No single test determines prognosis.",
     "B", "Strong", ["post-cardiac arrest", "targeted temperature management"], [], ["temperature", "eeg", "nse", "ssep", "mri brain", "ct head"], ["ttm", "cardiac arrest", "neuroprognostication", "hypothermia"]),

    ("ECMO Guidelines", "ELSO", 2024,
     "ECMO Indications and Management",
     "VV-ECMO for refractory respiratory failure (ARDS with P/F <80 despite optimal care, or CO2 retention with pH <7.20). VA-ECMO for refractory cardiogenic shock or cardiac arrest. Anticoagulation: UFH targeting anti-Xa 0.3-0.7 or ACT 180-220. Complications: bleeding (most common), thrombosis, hemolysis, infection, limb ischemia (VA). Duration: bridge to recovery, transplant, or decision. Daily reassessment of goals.",
     "B", "Strong", ["refractory ards", "cardiogenic shock", "extracorporeal membrane oxygenation"], ["heparin"], ["anti-xa", "act", "fibrinogen", "hemoglobin", "free hemoglobin", "pfhb", "lactate"], ["ecmo", "vv-ecmo", "va-ecmo", "extracorporeal"]),

    # ══════════════════════════════════════════
    # EMERGENCY MEDICINE EXPANSION (~15)
    # ══════════════════════════════════════════
    ("ACS Traumatic Brain Injury Guidelines", "ACS/BTF", 2024,
     "Severe TBI Management",
     "GCS ≤8: intubate for airway protection. Avoid hypotension (SBP >100) and hypoxia (SpO2 >90). CT head emergently. ICP monitoring for GCS ≤8 with abnormal CT. ICP target <22 mmHg. Tier approach: head elevation 30°, sedation, osmotherapy (mannitol 20% or 23.4% NaCl), CSF drainage, decompressive craniectomy. Hypertonic saline preferred over mannitol in hemorrhagic shock. Seizure prophylaxis (levetiracetam) for 7 days. Target temperature 36-37°C.",
     "A", "Strong", ["traumatic brain injury", "severe tbi"], ["mannitol", "hypertonic saline", "levetiracetam", "fentanyl", "propofol"], ["gcs", "icp", "ct head", "cerebral perfusion pressure", "sodium"], ["tbi", "intracranial pressure", "decompressive craniectomy", "mannitol"]),

    ("ACS Spinal Cord Injury Guidelines", "ACS/AANS/CNS", 2024,
     "Acute Spinal Cord Injury Management",
     "Spinal immobilization and rapid transport. MAP target ≥85-90 mmHg for 5-7 days (with vasopressors if needed). MRI spine urgently. Surgical decompression within 24 hours for incomplete SCI with ongoing compression improves outcomes. Methylprednisolone no longer recommended routinely (conflicting evidence). VTE prophylaxis (LMWH) within 72 hours. Early rehabilitation. Neurogenic shock (bradycardia + hypotension): volume + vasopressors (norepinephrine).",
     "B", "Strong", ["spinal cord injury", "neurogenic shock"], ["norepinephrine", "atropine", "enoxaparin"], ["mri spine", "ct spine", "map", "american spinal injury association (asia) score"], ["spinal cord injury", "neurogenic shock", "surgical decompression", "asia"]),

    ("ACMT Toxicology Guidelines", "ACMT/AACT", 2024,
     "Common Poisoning Antidotes",
     "Acetaminophen: NAC (N-acetylcysteine) if level above Rumack-Matthew nomogram line or unknown ingestion >150 mg/kg. Opioid: naloxone 0.4-2 mg IV/IM/IN. Benzodiazepine: flumazenil (caution in chronic use/seizure risk). Organophosphate: atropine + pralidoxime. Beta-blocker: glucagon, high-dose insulin. Calcium channel blocker: calcium, high-dose insulin, vasopressors. Methanol/ethylene glycol: fomepizole. Iron: deferoxamine. Digoxin: digoxin-specific antibody fragments.",
     "A", "Strong", ["poisoning", "drug overdose", "toxic ingestion"], ["n-acetylcysteine", "naloxone", "flumazenil", "atropine", "pralidoxime", "fomepizole", "glucagon"], ["acetaminophen level", "salicylate level", "ethanol level", "osmolar gap", "anion gap", "ecg"], ["toxicology", "antidote", "overdose", "nac"]),

    ("AHA Hypothermia Guidelines", "AHA/WMS", 2024,
     "Accidental Hypothermia Management",
     "Classify: mild (32-35°C), moderate (28-32°C), severe (<28°C). Mild: passive external rewarming (remove wet clothing, warm environment, blankets). Moderate: active external rewarming (forced warm air, warm blankets). Severe/cardiac arrest: active internal rewarming (warm IV fluids, body cavity lavage, ECMO rewarming). Continue CPR until rewarmed (no one is dead until warm and dead). Avoid rough handling (risk of VF). ECMO is gold standard for severe hypothermia with cardiac arrest.",
     "B", "Strong", ["accidental hypothermia", "cold exposure"], ["warm iv fluids"], ["core temperature", "ecg", "potassium", "abg"], ["hypothermia", "rewarming", "ecmo", "core temperature"]),

    ("ACS Burn Management Guidelines", "ABA/ACS", 2024,
     "Burn Injury Assessment and Resuscitation",
     "Classify: depth (superficial, partial-thickness, full-thickness) and %TBSA (rule of nines or Lund-Browder for children). Burn center referral: >20% TBSA partial-thickness, full-thickness >5%, face/hands/feet/genitalia/joints, inhalation injury, electrical/chemical, circumferential. Fluid resuscitation (Parkland formula): 4 mL/kg/%TBSA crystalloid over 24h (first half in 8 hours). Target UO 0.5-1 mL/kg/h. Escharotomy for circumferential full-thickness. Early intubation if inhalation injury suspected.",
     "A", "Strong", ["burn injury", "thermal injury"], ["lactated ringers", "silver sulfadiazine", "morphine"], ["tbsa", "urine output", "lactate", "carboxyhemoglobin"], ["burn", "parkland formula", "escharotomy", "burn center"]),

    ("AHA Stroke Code Guidelines", "AHA/ASA", 2024,
     "Acute Ischemic Stroke Emergency Management",
     "Door-to-needle ≤60 minutes for tPA. IV alteplase 0.9 mg/kg (max 90 mg) for eligible patients within 4.5 hours of symptom onset. Tenecteplase (single bolus) non-inferior and increasingly preferred. BP <185/110 before tPA, <180/105 after. Large vessel occlusion (LVO): endovascular thrombectomy within 24 hours if eligible (NIHSS ≥6, LVO on CTA, CT perfusion for late window). ASPECTS ≥6 for standard window. Aspirin 325 mg within 24-48 hours (hold 24h post-tPA).",
     "A", "Strong", ["acute ischemic stroke", "large vessel occlusion"], ["alteplase", "tenecteplase", "aspirin", "labetalol", "nicardipine"], ["nihss", "ct head", "ct angiography", "ct perfusion", "aspects score", "blood glucose", "inr"], ["stroke", "tpa", "thrombectomy", "door-to-needle"]),

    # ══════════════════════════════════════════
    # HEMATOLOGY EXPANSION (~15)
    # ══════════════════════════════════════════
    ("ASH Iron Deficiency Anemia Guidelines", "ASH", 2024,
     "Iron Deficiency Anemia Diagnosis and Treatment",
     "Diagnosis: low ferritin (<30) is most specific; ferritin 30-100 with low transferrin saturation (<20%) supports diagnosis. Investigate cause: menorrhagia, GI loss (EGD/colonoscopy for men and postmenopausal women), celiac screening. Oral iron: ferrous sulfate 325 mg every other day (optimizes absorption, reduces side effects). IV iron (ferric carboxymaltose, iron sucrose) for: oral intolerance, malabsorption, rapid correction needed, inflammatory state. Recheck CBC and ferritin at 4-6 weeks.",
     "A", "Strong", ["iron deficiency anemia"], ["ferrous sulfate", "ferric carboxymaltose", "iron sucrose"], ["ferritin", "iron", "tibc", "transferrin saturation", "cbc", "reticulocyte count"], ["iron deficiency", "ferritin", "iv iron", "ferrous sulfate"]),

    ("ASH Anticoagulation Management Guidelines", "ASH", 2024,
     "VTE Treatment and Duration",
     "Acute VTE: DOAC preferred (apixaban or rivaroxaban without lead-in heparin, or edoxaban/dabigatran after 5-10 days of parenteral). Cancer-associated VTE: LMWH or DOAC (apixaban/edoxaban; caution rivaroxaban with upper GI cancers). Duration: provoked VTE 3 months; unprovoked DVT/PE extended anticoagulation (indefinite if tolerated, reassess annually). Reduced-dose DOAC for extended prevention after initial treatment. IVC filter only if anticoagulation contraindicated.",
     "A", "Strong", ["venous thromboembolism", "dvt", "pulmonary embolism"], ["apixaban", "rivaroxaban", "enoxaparin", "warfarin", "edoxaban"], ["ct pulmonary angiogram", "lower extremity doppler", "d-dimer", "inr", "cbc"], ["vte", "doac", "anticoagulation", "dvt"]),

    ("ASH Heparin-Induced Thrombocytopenia Guidelines", "ASH", 2024,
     "HIT Diagnosis and Treatment",
     "4T score to assess probability (Thrombocytopenia timing, Timing of onset, Thrombosis, oTher causes). Intermediate-high probability: send HIT antibody (PF4/heparin ELISA, then serotonin release assay for confirmation). STOP all heparin immediately. Start non-heparin anticoagulant: argatroban (hepatic metabolism, preferred in renal impairment) or bivalirudin or fondaparinux. Do NOT transfuse platelets. Transition to warfarin only after platelet recovery >150k. DOAC increasingly used post-acute phase.",
     "A", "Strong", ["heparin-induced thrombocytopenia", "hit"], ["argatroban", "bivalirudin", "fondaparinux"], ["platelet count", "4t score", "heparin pf4 antibody", "serotonin release assay", "doppler ultrasound"], ["hit", "argatroban", "pf4 antibody", "thrombocytopenia"]),

    ("ASH CML Management Guidelines", "ASH/NCCN", 2024,
     "Chronic Myeloid Leukemia Treatment",
     "First-line TKI therapy for chronic phase CML: imatinib 400 mg (standard), dasatinib 100 mg, or bosutinib 400 mg (second-gen for higher response). Monitor BCR-ABL1 by qPCR at 3-month intervals. Milestones: BCR-ABL1 ≤10% at 3 months, ≤1% at 6 months, ≤0.1% (MMR) at 12 months. Treatment-free remission (TFR) attempt after sustained DMR (≥MR4) for ≥2 years. Ponatinib or asciminib for T315I mutation or multiply resistant CML.",
     "A", "Strong", ["chronic myeloid leukemia", "cml"], ["imatinib", "dasatinib", "bosutinib", "ponatinib", "asciminib"], ["bcr-abl1 qpcr", "cbc", "cmp", "bone marrow biopsy", "cytogenetics"], ["cml", "imatinib", "tki", "bcr-abl"]),

    ("ASH CLL Management Guidelines", "ASH/NCCN", 2024,
     "Chronic Lymphocytic Leukemia Treatment",
     "Watch-and-wait for asymptomatic early-stage CLL (Rai 0-I/Binet A). Treatment indications: progressive cytopenias, symptomatic lymphadenopathy/splenomegaly, constitutional symptoms, progressive lymphocytosis (doubling <6 months). First-line: BTK inhibitor (ibrutinib, acalabrutinib, zanubrutinib) continuous therapy, or venetoclax-obinutuzumab (fixed duration 12 months). TP53/del(17p): BTK inhibitor or venetoclax-based (avoid chemoimmunotherapy). IGHV mutated: venetoclax-obinutuzumab or FCR for young/fit.",
     "A", "Strong", ["chronic lymphocytic leukemia", "cll"], ["ibrutinib", "acalabrutinib", "zanubrutinib", "venetoclax", "obinutuzumab"], ["cbc", "flow cytometry", "fish", "tp53 mutation", "ighv mutation status", "beta-2 microglobulin"], ["cll", "btk inhibitor", "venetoclax", "ibrutinib"]),

    # ══════════════════════════════════════════
    # PREVENTIVE MEDICINE EXPANSION (~12)
    # ══════════════════════════════════════════
    ("USPSTF Smoking Cessation Guidelines", "USPSTF", 2024,
     "Smoking Cessation Interventions",
     "Ask all adults about tobacco use. Advise all users to quit. First-line pharmacotherapy: varenicline (most effective), nicotine replacement (patch + short-acting like gum or lozenge), bupropion. Combination therapy (patch + short-acting NRT) more effective than single agent. Behavioral counseling (individual, group, or quitline) augments pharmacotherapy. Varenicline safe in psychiatric patients. E-cigarettes not FDA-approved for cessation.",
     "A", "Strong", ["tobacco use disorder", "smoking cessation"], ["varenicline", "nicotine patch", "nicotine gum", "bupropion"], [], ["smoking cessation", "varenicline", "nicotine replacement", "quit smoking"]),

    ("USPSTF Alcohol Screening Guidelines", "USPSTF/NIAAA", 2024,
     "Alcohol Use Screening and Brief Intervention",
     "Screen all adults ≥18 for unhealthy alcohol use using AUDIT-C or single-item screener. At-risk drinking: >14 drinks/week men, >7 women. Brief intervention: FRAMES (Feedback, Responsibility, Advice, Menu, Empathy, Self-efficacy). Moderate-severe AUD: pharmacotherapy with naltrexone (50 mg/day PO or 380 mg IM monthly) or acamprosate. Disulfiram for motivated, supervised patients. Address comorbid psychiatric conditions.",
     "B", "Strong", ["alcohol use disorder", "unhealthy alcohol use"], ["naltrexone", "acamprosate", "disulfiram"], ["audit-c", "ggt", "cbc", "cmp"], ["alcohol screening", "audit-c", "naltrexone", "brief intervention"]),

    ("USPSTF Falls Prevention Guidelines", "USPSTF/AGS", 2024,
     "Falls Prevention in Older Adults",
     "Screen community-dwelling adults ≥65 for fall risk annually (history of falls, gait/balance assessment). Multifactorial intervention for high risk: exercise programs (tai chi, balance training), medication review (reduce psychotropics, anticholinergics), vision correction, home safety evaluation, orthostatic BP management, vitamin D supplementation. Physical therapy referral. Avoid unnecessary sedatives/hypnotics.",
     "B", "Strong", ["falls in elderly", "fall prevention"], ["vitamin d"], ["timed up and go test", "orthostatic blood pressure", "vitamin d level", "medication list"], ["falls prevention", "geriatric", "exercise", "medication review"]),

    ("USPSTF Obesity Management Guidelines", "USPSTF/AHA/ACC", 2024,
     "Adult Obesity Screening and Management",
     "Screen all adults for obesity (BMI ≥30). Comprehensive lifestyle intervention: behavioral counseling (≥14 sessions in 6 months), caloric deficit 500-750 kcal/day, physical activity 150-300 min/week. Pharmacotherapy for BMI ≥30 or ≥27 with comorbidity: GLP-1 RA (semaglutide 2.4 mg weekly most effective, tirzepatide), orlistat, phentermine-topiramate, naltrexone-bupropion. Metabolic/bariatric surgery for BMI ≥40 or ≥35 with comorbidity.",
     "A", "Strong", ["obesity", "overweight"], ["semaglutide", "tirzepatide", "orlistat", "phentermine-topiramate", "naltrexone-bupropion"], ["bmi", "waist circumference", "fasting glucose", "lipid panel", "hba1c"], ["obesity", "weight management", "glp-1", "bariatric"]),

    ("ACIP Adult Immunization Schedule", "ACIP/CDC", 2025,
     "Adult Immunization Recommendations",
     "Annual: influenza (any age). COVID-19: updated formulation annually. Td/Tdap: Tdap once then Td every 10 years. Shingrix: 2 doses for adults ≥50. PCV20 or PCV15→PPSV23: for adults ≥65 and younger with risk conditions. HPV: through age 26 (shared decision 27-45). HepB: all adults 19-59. MMR: born after 1957 without evidence of immunity. Varicella: 2 doses if no evidence of immunity. MenACWY/MenB per risk. Special populations: immunocompromised, pregnancy, travel.",
     "A", "Strong", ["adult immunization", "vaccination schedule"], ["influenza vaccine", "covid-19 vaccine", "shingrix", "pcv20", "tdap"], [], ["immunization", "vaccination", "acip", "pneumococcal"]),

    # ══════════════════════════════════════════
    # REHABILITATION MEDICINE (~10)
    # ══════════════════════════════════════════
    ("AHA Stroke Rehabilitation Guidelines", "AHA/ASA", 2024,
     "Post-Stroke Rehabilitation",
     "Begin rehabilitation as soon as medically stable (within 24-48 hours). Multidisciplinary team: PT, OT, SLP, neuropsychology, social work. Minimum 3 hours/day of therapy (intensive inpatient rehabilitation). Assessment: modified Rankin Scale, NIHSS, FIM. Dysphagia screening before oral intake. Depression screening (common post-stroke). Spasticity management: stretching, splinting, botulinum toxin, baclofen. Constraint-induced movement therapy for upper extremity. Secondary prevention concurrent.",
     "A", "Strong", ["stroke rehabilitation", "post-stroke recovery"], ["botulinum toxin", "baclofen", "sertraline", "aspirin"], ["modified rankin scale", "nihss", "fim", "swallowing evaluation"], ["stroke rehabilitation", "physical therapy", "spasticity", "dysphagia"]),

    ("AAN TBI Rehabilitation Guidelines", "AAN/ACRM", 2024,
     "Traumatic Brain Injury Rehabilitation",
     "Mild TBI/concussion: physical and cognitive rest 24-48 hours, then gradual return to activity per symptom tolerance. Post-concussion syndrome: multidisciplinary management (headache, cognitive, sleep, mood). Moderate-severe TBI: inpatient rehabilitation, structured environment. Cognitive rehabilitation: attention, memory, executive function training. Address behavioral changes, emotional dysregulation. Post-traumatic headache: preventive migraine medications. Amantadine for disorders of consciousness recovery.",
     "B", "Strong", ["traumatic brain injury rehabilitation", "concussion recovery"], ["amantadine", "methylphenidate", "amitriptyline"], ["gcs", "neuropsychological testing", "mri brain"], ["tbi rehabilitation", "concussion", "cognitive rehabilitation", "amantadine"]),

    ("AACVPR Pulmonary Rehabilitation Guidelines", "AACVPR/ATS/ERS", 2024,
     "Pulmonary Rehabilitation Program",
     "Indicated for: COPD (strongest evidence), ILD, pulmonary hypertension, post-lung surgery, post-COVID. Minimum 12 sessions (typically 24-36 over 8-12 weeks). Components: aerobic exercise (walking, cycling), resistance training, breathing exercises, education, psychosocial support, nutritional counseling. Pre/post assessment: 6MWT, SGRQ, CAT. Improves dyspnea, exercise capacity, QoL, and reduces hospitalizations (NNT = 4 for COPD).",
     "A", "Strong", ["pulmonary rehabilitation", "copd rehabilitation"], [], ["6-minute walk test", "spirometry", "cat score", "sgrq", "bode index"], ["pulmonary rehabilitation", "exercise training", "copd", "dyspnea"]),

    ("AHA Cardiac Rehabilitation Phase II", "AHA/AACVPR", 2024,
     "Outpatient Cardiac Rehabilitation",
     "36 sessions (3x/week for 12 weeks). Continuous ECG monitoring initially. Graduated exercise prescription: target 60-80% peak heart rate or RPE 11-14. Components: aerobic exercise, resistance training (after 2-3 weeks), education (medication, diet, risk factor modification), psychosocial counseling, smoking cessation. Patient-reported outcome measures at baseline and completion. Referral at discharge (automatic referral systems improve enrollment).",
     "A", "Strong", ["cardiac rehabilitation", "post-mi exercise program"], [], ["exercise stress test", "ecg", "blood pressure", "heart rate", "rpe", "vo2 max"], ["cardiac rehab", "exercise prescription", "phase ii", "ecg monitoring"]),

    # ══════════════════════════════════════════
    # PALLIATIVE CARE EXPANSION (~10)
    # ══════════════════════════════════════════
    ("NCCN Palliative Care Guidelines", "NCCN", 2025,
     "Palliative Care Symptom Management",
     "Pain: WHO analgesic ladder; opioid rotation for tolerance/side effects. Dyspnea: opioids (morphine 2-5 mg Q4h), supplemental O2 for hypoxemia, fan therapy. Nausea: identify cause-directed treatment (metoclopramide for gastroparesis, ondansetron for chemo, dexamethasone for raised ICP, haloperidol for opioid-induced). Constipation: prevent with senna + docusate or PEG with opioid initiation; methylnaltrexone for opioid-induced. Delirium: identify/treat reversible causes; haloperidol for agitation.",
     "A", "Strong", ["palliative symptom management", "end-of-life care"], ["morphine", "metoclopramide", "ondansetron", "haloperidol", "methylnaltrexone", "senna"], ["pain score", "edmonton symptom assessment"], ["palliative care", "symptom management", "dyspnea", "nausea"]),

    ("NHPCO Hospice Guidelines", "NHPCO", 2024,
     "Hospice Eligibility and Services",
     "Hospice eligibility: prognosis ≤6 months if disease runs expected course. Disease-specific criteria: cancer (KPS ≤50, declining despite treatment), heart failure (NYHA IV, EF <20%, optimal GDMT), COPD (FEV1 <30%, O2 dependent, recurrent exacerbations), dementia (FAST stage 7+, recurrent infections), renal failure (not seeking dialysis, GFR <10). Services: nursing, aide, social work, chaplaincy, bereavement. Focus shifts from cure to comfort.",
     "B", "Strong", ["hospice care", "end-of-life", "terminal illness"], ["morphine", "lorazepam", "atropine drops", "haloperidol"], ["karnofsky performance status", "palliative performance scale", "fast staging"], ["hospice", "eligibility", "comfort care", "end-of-life"]),

    ("AMA/AAN Goals of Care Discussion Guidelines", "AMA/AAN", 2024,
     "Advance Care Planning and Goals of Care",
     "Discuss with all adults, especially those with serious illness. Components: health care proxy/durable POA designation, advance directive documentation, values and goals exploration, POLST for seriously ill. Prognostic disclosure: honest, empathic communication. Decision-making frameworks: shared decision-making, substituted judgment for incapacitated patients. Reassess goals with each hospitalization and change in clinical status. Document in medical record and ensure accessibility.",
     "B", "Strong", ["advance care planning", "goals of care", "end-of-life decisions"], [], [], ["advance care planning", "polst", "advance directive", "goals of care"]),

    # ══════════════════════════════════════════
    # ADDITIONAL GI (~8)
    # ══════════════════════════════════════════
    ("AGA Irritable Bowel Syndrome Guidelines", "AGA", 2024,
     "IBS Pharmacotherapy by Subtype",
     "IBS-D: eluxadoline, rifaximin 550 mg TID x 14 days (retreatable), loperamide, alosetron (severe female IBS-D only). IBS-C: linaclotide, plecanatide, lubiprostone, tegaserod (women <65 without CV risk). IBS-Mixed: trial based on predominant symptom. All subtypes: low FODMAP diet (dietitian-guided), peppermint oil, TCA (amitriptyline 10-50 mg). CBT and gut-directed hypnotherapy for refractory symptoms.",
     "A", "Strong", ["irritable bowel syndrome", "ibs"], ["eluxadoline", "rifaximin", "linaclotide", "amitriptyline", "lubiprostone", "loperamide"], ["rome iv criteria", "colonoscopy", "celiac screening", "fecal calprotectin"], ["ibs", "low fodmap", "rifaximin", "linaclotide"]),

    ("ACG Inflammatory Bowel Disease Guidelines", "ACG", 2024,
     "Ulcerative Colitis Biologic Selection",
     "Moderate-severe UC: biologics first-line over thiopurines. TNF inhibitors (infliximab, adalimumab, golimumab). Anti-integrin: vedolizumab (gut-selective, favorable safety). IL-23: risankizumab, mirikizumab. JAK inhibitors: tofacitinib, upadacitinib (rapid onset). Anti-IL-12/23: ustekinumab. Selection factors: disease severity, prior therapy, extraintestinal manifestations, safety profile, route preference. Therapeutic drug monitoring for TNFi to optimize dosing.",
     "A", "Strong", ["ulcerative colitis", "inflammatory bowel disease"], ["infliximab", "vedolizumab", "ustekinumab", "tofacitinib", "upadacitinib", "risankizumab"], ["fecal calprotectin", "colonoscopy", "crp", "albumin", "drug levels"], ["ulcerative colitis", "biologics", "vedolizumab", "jak inhibitor"]),

    ("ACG Inflammatory Bowel Disease Guidelines", "ACG", 2024,
     "Crohn Disease Surgical Indications",
     "Surgery for: medically refractory disease, stricture with obstruction, fistula (perianal complex), abscess, dysplasia/cancer, growth failure in children. Ileocecal resection for limited ileocecal Crohn's (competitive with biologics per LIRIC trial for stricturing). Strictureplasty to preserve bowel length. Postoperative prophylaxis: mesalamine (mild), thiopurine, or anti-TNF (high-risk). Colonoscopy at 6-12 months post-surgery.",
     "A", "Strong", ["crohn disease", "inflammatory bowel disease"], ["azathioprine", "infliximab", "mesalamine", "metronidazole"], ["colonoscopy", "mri enterography", "fecal calprotectin", "crp"], ["crohn disease", "ileocecal resection", "strictureplasty", "postoperative"]),

    # ══════════════════════════════════════════
    # ADDITIONAL PSYCHIATRY (~8)
    # ══════════════════════════════════════════
    ("APA Substance Use Disorder Guidelines", "APA/ASAM", 2024,
     "Opioid Use Disorder Treatment",
     "Medications for OUD (MOUD) are first-line: buprenorphine (preferred outpatient: sublingual, injectable, or implant), methadone (OTP-based, most evidence for severe OUD), naltrexone ER (injectable monthly, after full detox). Buprenorphine: induce at 2-4 mg, titrate to 16-24 mg/day. X-waiver no longer required. Harm reduction: naloxone distribution, syringe services. Treat concurrent pain, mental health. MOUD reduces mortality by 50%+.",
     "A", "Strong", ["opioid use disorder", "opioid addiction"], ["buprenorphine", "methadone", "naltrexone", "naloxone"], ["urine drug screen", "hepatitis panel", "hiv", "cbc"], ["opioid use disorder", "buprenorphine", "methadone", "moud"]),

    ("APA Substance Use Disorder Guidelines", "APA/ASAM", 2024,
     "Alcohol Use Disorder Pharmacotherapy",
     "Naltrexone 50 mg/day PO or 380 mg IM monthly: reduces heavy drinking days and relapse. Acamprosate 666 mg TID: supports abstinence after detox. Disulfiram 250 mg/day: aversion therapy, requires supervision. Gabapentin: emerging evidence for reducing drinking, especially with insomnia/anxiety. Alcohol withdrawal: CIWA-based benzodiazepine dosing (chlordiazepoxide or lorazepam). Phenobarbital or IV phenobarbital for severe/refractory withdrawal.",
     "A", "Strong", ["alcohol use disorder", "alcohol withdrawal"], ["naltrexone", "acamprosate", "disulfiram", "chlordiazepoxide", "lorazepam", "gabapentin"], ["ciwa score", "ggt", "cbc", "cmp", "bac"], ["alcohol use disorder", "naltrexone", "withdrawal", "ciwa"]),

    ("APA PTSD Complex Trauma Guidelines", "APA/ISTSS", 2024,
     "Complex PTSD and Dissociative Disorders",
     "Phase-based treatment approach: Phase 1 (stabilization): safety, emotion regulation skills, grounding techniques. Phase 2 (trauma processing): EMDR, CPT, or prolonged exposure adapted for complexity. Phase 3 (integration): interpersonal functioning, identity work, daily functioning. Pharmacotherapy adjunct: SSRIs for core symptoms, prazosin for nightmares, mood stabilizers for affect dysregulation. Avoid benzodiazepines. Longer treatment course than simple PTSD.",
     "B", "Strong", ["complex ptsd", "dissociative disorders"], ["sertraline", "prazosin", "lamotrigine"], ["pcl-5", "dissociative experiences scale", "phq-9"], ["complex ptsd", "dissociation", "phase-based", "emdr"]),

    ("APA Psychopharmacology Guidelines", "APA", 2024,
     "Antipsychotic Metabolic Monitoring",
     "Baseline and ongoing monitoring for all patients on antipsychotics: weight/BMI (every visit), waist circumference (annually), fasting glucose/HbA1c (baseline, 3 months, then annually), lipid panel (baseline, 3 months, then annually), blood pressure (each visit). Highest metabolic risk: olanzapine, clozapine. Intermediate: quetiapine, risperidone. Lowest: aripiprazole, ziprasidone, lurasidone. Consider switching if significant metabolic changes. Lifestyle interventions for all patients.",
     "A", "Strong", ["antipsychotic metabolic effects", "metabolic monitoring"], ["olanzapine", "quetiapine", "aripiprazole", "clozapine", "metformin"], ["bmi", "fasting glucose", "hba1c", "lipid panel", "blood pressure", "waist circumference"], ["metabolic monitoring", "antipsychotic", "weight gain", "metabolic syndrome"]),

    # ══════════════════════════════════════════
    # ADDITIONAL NEUROLOGY (~5)
    # ══════════════════════════════════════════
    ("AAN Epilepsy Guidelines", "AAN/ILAE", 2024,
     "Epilepsy First Seizure and ASM Selection",
     "After first unprovoked seizure: AKM initiation if high recurrence risk (abnormal EEG, structural lesion, nocturnal seizure, prior brain injury). Focal onset: levetiracetam, lamotrigine, or oxcarbazepine first-line. Generalized onset: levetiracetam, valproate (avoid in women of childbearing potential), lamotrigine. Absence: ethosuximide or valproate. Drug-resistant epilepsy (failed 2 adequate ASM trials): evaluate for epilepsy surgery, VNS, RNS, dietary therapy.",
     "A", "Strong", ["epilepsy", "seizure disorder"], ["levetiracetam", "lamotrigine", "oxcarbazepine", "valproate", "ethosuximide"], ["eeg", "mri brain", "asm levels"], ["epilepsy", "seizure", "levetiracetam", "drug-resistant"]),

    ("AAN Myasthenia Gravis Guidelines", "AAN/MGFA", 2024,
     "Myasthenia Gravis Treatment Strategy",
     "Cholinesterase inhibitor (pyridostigmine) for symptom relief. Immunosuppression for most patients: prednisone (rapid onset), then steroid-sparing (azathioprine, mycophenolate, tacrolimus). Rapid acting for crisis/worsening: IVIG or PLEX. Thymectomy for thymoma (all ages) and non-thymoma generalized MG (age <65, AChR antibody-positive). Newer biologics: eculizumab, ravulizumab, efgartigimod, rozanolixizumab for refractory AChR+ MG.",
     "A", "Strong", ["myasthenia gravis", "neuromuscular junction disorder"], ["pyridostigmine", "prednisone", "azathioprine", "mycophenolate", "eculizumab", "efgartigimod"], ["achr antibody", "musk antibody", "ct chest", "rfns", "emg", "ice pack test"], ["myasthenia gravis", "pyridostigmine", "thymectomy", "eculizumab"]),
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
    print(f"Batch 7: added {added} sections (total now {total})")


if __name__ == "__main__":
    main()
