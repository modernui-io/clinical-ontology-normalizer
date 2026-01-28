#!/usr/bin/env python3
"""Generate ~1000 clinical guidelines systematically by medical specialty.

Merges with existing fixtures/clinical_guidelines.json and writes the expanded file.
"""

import json
import os
import re

# Each specialty has: (society, guideline_name, year, sections)
# Each section: (title, rec_text, grade, strength, conditions, meds, measurements, keywords)

SPECIALTIES = {
    # ── CARDIOLOGY ──────────────────────────────────────────────
    "cardiology": [
        ("ESC Heart Failure Guidelines", "ESC", 2023, [
            ("Pharmacotherapy for HFrEF", "For patients with heart failure with reduced ejection fraction (HFrEF, LVEF ≤40%), foundational therapy includes an ACE inhibitor or ARNI, a beta-blocker, an MRA, and an SGLT2 inhibitor. All four classes have been shown to reduce mortality and hospitalization. Initiation should begin as early as possible, with uptitration to maximally tolerated doses.", "A", "Strong",
             ["heart failure", "hfref", "cardiomyopathy", "systolic heart failure"], ["sacubitril-valsartan", "carvedilol", "metoprolol", "spironolactone", "dapagliflozin", "empagliflozin"], ["ejection fraction", "bnp", "nt-probnp"], ["heart failure", "hfref", "arni", "beta-blocker", "mra", "sglt2"]),
            ("Device Therapy in Heart Failure", "An implantable cardioverter-defibrillator (ICD) is recommended for primary prevention of sudden cardiac death in patients with symptomatic HF (NYHA class II-III) and LVEF ≤35% despite ≥3 months of optimal medical therapy, provided survival >1 year is expected. Cardiac resynchronization therapy (CRT) is recommended for symptomatic HF patients with LVEF ≤35%, QRS ≥150ms with LBBB, in sinus rhythm.", "A", "Strong",
             ["heart failure", "cardiomyopathy", "arrhythmia"], [], ["ejection fraction", "qrs duration"], ["icd", "crt", "defibrillator", "resynchronization", "device"]),
            ("Management of HFpEF", "For patients with heart failure with preserved ejection fraction (HFpEF, LVEF ≥50%), SGLT2 inhibitors are recommended to reduce heart failure hospitalization. Diuretics are recommended for congestion relief. Blood pressure and atrial fibrillation should be managed according to guidelines. Weight loss is recommended for obese patients with HFpEF.", "B", "Strong",
             ["heart failure", "hfpef", "diastolic heart failure"], ["empagliflozin", "dapagliflozin", "furosemide"], ["ejection fraction", "bnp"], ["hfpef", "preserved", "sglt2", "diuretic"]),
            ("Acute Heart Failure Management", "Patients presenting with acute decompensated heart failure should receive IV loop diuretics for decongestion. Vasodilators may be considered for hypertensive patients. Inotropes should be reserved for cardiogenic shock or severe low-output states. Non-invasive ventilation is recommended for respiratory distress.", "B", "Strong",
             ["acute heart failure", "cardiogenic shock", "pulmonary edema"], ["furosemide", "nitroglycerin", "dobutamine", "milrinone"], ["bnp", "lactate", "creatinine"], ["acute", "decompensated", "diuretic", "inotrope"]),
        ]),
        ("ACC/AHA Valvular Heart Disease Guidelines", "ACC/AHA", 2020, [
            ("Aortic Stenosis Management", "Aortic valve replacement (surgical or transcatheter) is recommended for symptomatic patients with severe aortic stenosis (aortic valve area ≤1.0 cm², mean gradient ≥40 mmHg, or peak velocity ≥4.0 m/s). TAVR is recommended for patients at prohibitive or high surgical risk. Surgical AVR is recommended for low-risk patients <65 years.", "A", "Strong",
             ["aortic stenosis", "valvular heart disease"], [], ["echocardiogram", "aortic valve area", "mean gradient"], ["aortic stenosis", "tavr", "avr", "valve replacement"]),
            ("Mitral Regurgitation", "For patients with chronic severe primary mitral regurgitation, mitral valve surgery is recommended when symptomatic or when LVEF ≤60% or LVESD ≥40mm. Mitral valve repair is preferred over replacement when feasible. Transcatheter edge-to-edge repair may be considered for high surgical risk patients.", "B", "Strong",
             ["mitral regurgitation", "valvular heart disease"], [], ["echocardiogram", "ejection fraction"], ["mitral", "regurgitation", "repair", "replacement"]),
            ("Anticoagulation in Valvular Disease", "Warfarin is recommended for patients with mechanical heart valves. DOACs are contraindicated in mechanical valves. For bioprosthetic valves, anticoagulation with warfarin for 3-6 months post-surgery may be considered. Aspirin is recommended long-term after bioprosthetic AVR.", "A", "Strong",
             ["valvular heart disease", "prosthetic valve"], ["warfarin", "aspirin"], ["inr", "pt"], ["anticoagulation", "warfarin", "mechanical valve", "prosthetic"]),
        ]),
        ("ACC/AHA Coronary Artery Disease Guidelines", "ACC/AHA", 2023, [
            ("Stable Angina Medical Therapy", "Beta-blockers or calcium channel blockers are recommended as first-line antianginal therapy. Sublingual nitroglycerin should be prescribed for acute relief. Long-acting nitrates may be added for persistent symptoms. Ranolazine may be considered as add-on therapy.", "A", "Strong",
             ["coronary artery disease", "stable angina", "ischemic heart disease"], ["metoprolol", "amlodipine", "nitroglycerin", "ranolazine", "isosorbide"], ["stress test", "troponin"], ["angina", "antianginal", "beta-blocker", "ccb", "nitrate"]),
            ("Revascularization for Stable CAD", "PCI is reasonable for patients with significant left main or multivessel CAD. CABG is recommended for patients with left main disease, three-vessel disease, or two-vessel disease with proximal LAD involvement and reduced LVEF. Heart team discussion is recommended for complex disease.", "A", "Strong",
             ["coronary artery disease", "stable angina"], [], ["coronary angiogram", "fractional flow reserve"], ["revascularization", "pci", "cabg", "stent", "bypass"]),
            ("Secondary Prevention After ACS", "High-intensity statin therapy is recommended. DAPT with aspirin and a P2Y12 inhibitor for 12 months after ACS. ACE inhibitor or ARB for patients with LVEF ≤40%, hypertension, diabetes, or stable CKD. Beta-blocker therapy for at least 3 years post-MI.", "A", "Strong",
             ["acute coronary syndrome", "myocardial infarction", "unstable angina"], ["aspirin", "ticagrelor", "clopidogrel", "atorvastatin", "rosuvastatin"], ["troponin", "ldl", "ejection fraction"], ["secondary prevention", "dapt", "statin", "acs", "mi"]),
            ("Antiplatelet Therapy Duration", "After drug-eluting stent placement, DAPT for a minimum of 6 months is recommended. Extended DAPT beyond 12 months may be considered for patients at high ischemic risk and low bleeding risk. De-escalation to P2Y12 monotherapy after 1-3 months may be considered for high bleeding risk.", "B", "Strong",
             ["coronary artery disease", "acute coronary syndrome"], ["aspirin", "clopidogrel", "ticagrelor", "prasugrel"], ["platelet function"], ["antiplatelet", "dapt", "stent", "duration"]),
        ]),
        ("ESC Peripheral Arterial Disease", "ESC", 2024, [
            ("PAD Screening and Diagnosis", "Ankle-brachial index (ABI) measurement is recommended for suspected PAD. An ABI ≤0.90 is diagnostic. Duplex ultrasound is recommended as first-line imaging. CT or MR angiography should be performed when revascularization is considered.", "A", "Strong",
             ["peripheral arterial disease", "claudication", "critical limb ischemia"], [], ["ankle-brachial index", "abi"], ["pad", "abi", "claudication", "screening"]),
            ("PAD Medical Management", "Antiplatelet therapy with aspirin or clopidogrel is recommended. Statin therapy is recommended for all PAD patients. Supervised exercise therapy for at least 30-45 minutes, 3 times weekly for 12 weeks is recommended for claudication. Cilostazol may improve walking distance.", "A", "Strong",
             ["peripheral arterial disease", "claudication"], ["aspirin", "clopidogrel", "atorvastatin", "cilostazol"], ["ldl", "ankle-brachial index"], ["pad", "exercise", "antiplatelet", "statin"]),
        ]),
        ("ACC/AHA Supraventricular Tachycardia", "ACC/AHA", 2023, [
            ("Acute SVT Management", "Vagal maneuvers are recommended as first-line treatment for acute SVT. If unsuccessful, IV adenosine is recommended. IV verapamil or diltiazem may be used if adenosine fails. Synchronized cardioversion for hemodynamically unstable patients.", "A", "Strong",
             ["supraventricular tachycardia", "svt", "avnrt", "avrt"], ["adenosine", "verapamil", "diltiazem"], ["ecg", "heart rate"], ["svt", "adenosine", "vagal", "cardioversion"]),
            ("Catheter Ablation for SVT", "Catheter ablation is recommended as first-line therapy for symptomatic WPW syndrome and recurrent AVNRT. Success rates exceed 95% with low complication rates. Ablation is preferred over long-term antiarrhythmic drug therapy for recurrent SVT.", "A", "Strong",
             ["supraventricular tachycardia", "wpw", "avnrt"], [], ["ecg", "electrophysiology study"], ["ablation", "wpw", "avnrt", "electrophysiology"]),
        ]),
    ],

    # ── ONCOLOGY ────────────────────────────────────────────────
    "oncology": [
        ("NCCN Non-Small Cell Lung Cancer Guidelines", "NCCN", 2025, [
            ("Early-Stage NSCLC Treatment", "Surgical resection is the primary treatment for stage I-II NSCLC. Lobectomy with mediastinal lymph node dissection is preferred. Adjuvant cisplatin-based chemotherapy is recommended for stage II and select stage IB. Adjuvant osimertinib is recommended for EGFR-mutated resected NSCLC.", "A", "Strong",
             ["non-small cell lung cancer", "nsclc", "lung cancer"], ["cisplatin", "carboplatin", "osimertinib"], ["ct chest", "pet scan", "egfr mutation"], ["nsclc", "surgery", "adjuvant", "lobectomy"]),
            ("Advanced NSCLC First-Line Therapy", "Molecular testing for EGFR, ALK, ROS1, BRAF, NTRK, MET, RET, KRAS G12C, and HER2 is recommended. PD-L1 testing is required. For PD-L1 ≥50% without driver mutations, pembrolizumab monotherapy or chemo-immunotherapy is recommended. For EGFR-mutated NSCLC, osimertinib is first-line.", "A", "Strong",
             ["non-small cell lung cancer", "nsclc", "metastatic lung cancer"], ["pembrolizumab", "osimertinib", "carboplatin", "pemetrexed"], ["pd-l1", "egfr", "alk", "ct scan"], ["nsclc", "immunotherapy", "targeted therapy", "first-line"]),
            ("Small Cell Lung Cancer", "For limited-stage SCLC, concurrent chemoradiation with cisplatin/etoposide is recommended followed by prophylactic cranial irradiation. For extensive-stage, carboplatin/etoposide plus atezolizumab or durvalumab is standard first-line.", "A", "Strong",
             ["small cell lung cancer", "sclc"], ["cisplatin", "etoposide", "carboplatin", "atezolizumab", "durvalumab"], ["ct scan", "brain mri"], ["sclc", "chemoradiation", "immunotherapy"]),
        ]),
        ("NCCN Breast Cancer Guidelines", "NCCN", 2025, [
            ("Early-Stage HR+ Breast Cancer", "Adjuvant endocrine therapy with tamoxifen or an aromatase inhibitor for 5-10 years is recommended for HR+ early breast cancer. Genomic assays (Oncotype DX, MammaPrint) should guide chemotherapy decisions. CDK4/6 inhibitors may be considered for high-risk node-positive disease.", "A", "Strong",
             ["breast cancer", "hr positive breast cancer"], ["tamoxifen", "anastrozole", "letrozole", "abemaciclib"], ["estrogen receptor", "progesterone receptor", "oncotype dx"], ["breast cancer", "endocrine therapy", "adjuvant", "hormone receptor"]),
            ("HER2-Positive Breast Cancer", "Neoadjuvant pertuzumab, trastuzumab, and chemotherapy is recommended for HER2+ breast cancer. Adjuvant T-DM1 for residual disease after neoadjuvant therapy. Trastuzumab deruxtecan for metastatic HER2+ after prior trastuzumab-based therapy.", "A", "Strong",
             ["breast cancer", "her2 positive breast cancer"], ["trastuzumab", "pertuzumab", "t-dm1", "trastuzumab deruxtecan"], ["her2", "fish", "ihc"], ["her2", "trastuzumab", "neoadjuvant", "targeted therapy"]),
            ("Triple-Negative Breast Cancer", "Neoadjuvant pembrolizumab plus chemotherapy is recommended for early-stage TNBC with tumor ≥2cm or node-positive disease. Adjuvant capecitabine for residual disease. Sacituzumab govitecan for pretreated metastatic TNBC.", "A", "Strong",
             ["breast cancer", "triple negative breast cancer", "tnbc"], ["pembrolizumab", "carboplatin", "paclitaxel", "capecitabine", "sacituzumab govitecan"], ["pd-l1", "ki-67"], ["tnbc", "immunotherapy", "neoadjuvant", "triple negative"]),
            ("Breast Cancer Screening", "Annual mammography starting at age 40 is recommended. MRI screening recommended for high-risk women (lifetime risk ≥20%). Genetic testing for BRCA1/2 mutations in appropriate candidates. Risk-reducing mastectomy may be discussed for BRCA carriers.", "B", "Strong",
             ["breast cancer screening"], [], ["mammogram", "breast mri", "brca"], ["screening", "mammography", "brca", "genetic testing"]),
        ]),
        ("NCCN Colorectal Cancer Guidelines", "NCCN", 2025, [
            ("Colon Cancer Adjuvant Therapy", "FOLFOX (5-FU, leucovorin, oxaliplatin) for 3-6 months is standard adjuvant therapy for stage III colon cancer. For stage II with high-risk features, adjuvant chemotherapy should be considered. MSI-H/dMMR testing is recommended for all patients.", "A", "Strong",
             ["colon cancer", "colorectal cancer"], ["5-fluorouracil", "oxaliplatin", "leucovorin", "capecitabine"], ["cea", "ct scan", "msi", "mmr"], ["colon cancer", "folfox", "adjuvant", "stage iii"]),
            ("Metastatic CRC First-Line", "FOLFOX or FOLFIRI plus bevacizumab or cetuximab (RAS wild-type, left-sided) is standard first-line. All patients should have RAS/BRAF/MSI testing. Pembrolizumab is first-line for MSI-H/dMMR metastatic CRC.", "A", "Strong",
             ["colorectal cancer", "metastatic colon cancer"], ["bevacizumab", "cetuximab", "pembrolizumab", "5-fluorouracil", "irinotecan"], ["cea", "ras mutation", "braf", "msi"], ["colorectal", "metastatic", "bevacizumab", "cetuximab", "first-line"]),
            ("Colorectal Cancer Screening", "Colonoscopy every 10 years starting at age 45 for average risk. Annual FIT or fecal DNA test as alternatives. Earlier and more frequent screening for high-risk individuals (family history, IBD, Lynch syndrome).", "A", "Strong",
             ["colorectal cancer screening", "colon polyps"], [], ["colonoscopy", "fit test", "fecal dna"], ["screening", "colonoscopy", "fit", "prevention"]),
        ]),
        ("NCCN Prostate Cancer Guidelines", "NCCN", 2025, [
            ("Localized Prostate Cancer", "Active surveillance is recommended for very low and low-risk prostate cancer. Radical prostatectomy or radiation therapy for intermediate and high-risk disease. Androgen deprivation therapy combined with radiation for high-risk localized disease.", "A", "Strong",
             ["prostate cancer"], ["leuprolide", "bicalutamide", "enzalutamide"], ["psa", "gleason score", "mri prostate"], ["prostate", "active surveillance", "prostatectomy", "radiation"]),
            ("Metastatic Castration-Resistant Prostate Cancer", "First-line options include abiraterone, enzalutamide, or docetaxel. PARP inhibitors (olaparib, rucaparib) for BRCA-mutated mCRPC. Radium-223 for symptomatic bone metastases without visceral disease. PSMA-targeted therapy (lutetium-177) after prior taxane and AR-pathway inhibitor.", "A", "Strong",
             ["prostate cancer", "castration-resistant prostate cancer", "mcrpc"], ["abiraterone", "enzalutamide", "docetaxel", "olaparib", "radium-223"], ["psa", "testosterone", "ct scan", "bone scan"], ["mcrpc", "abiraterone", "enzalutamide", "parp inhibitor"]),
        ]),
        ("ASCO Pancreatic Cancer Guidelines", "ASCO", 2024, [
            ("Resectable Pancreatic Cancer", "Surgical resection (pancreaticoduodenectomy or distal pancreatectomy) is recommended for resectable pancreatic ductal adenocarcinoma. Adjuvant modified FOLFIRINOX for 6 months is recommended for fit patients. Gemcitabine plus capecitabine is an alternative.", "A", "Strong",
             ["pancreatic cancer", "pancreatic adenocarcinoma"], ["5-fluorouracil", "irinotecan", "oxaliplatin", "gemcitabine", "capecitabine"], ["ca 19-9", "ct abdomen", "mri pancreas"], ["pancreatic cancer", "whipple", "folfirinox", "adjuvant"]),
            ("Advanced Pancreatic Cancer", "FOLFIRINOX or gemcitabine/nab-paclitaxel is recommended for metastatic disease in fit patients. BRCA/PALB2 testing recommended; platinum-based therapy and olaparib maintenance for BRCA-mutated tumors. MSI-H tumors may benefit from pembrolizumab.", "A", "Strong",
             ["pancreatic cancer", "metastatic pancreatic cancer"], ["gemcitabine", "nab-paclitaxel", "olaparib", "pembrolizumab"], ["ca 19-9", "ct scan"], ["pancreatic", "metastatic", "folfirinox", "gemcitabine"]),
        ]),
        ("NCCN Melanoma Guidelines", "NCCN", 2025, [
            ("Early-Stage Melanoma", "Wide local excision with appropriate margins is the primary treatment. Sentinel lymph node biopsy recommended for tumors >0.8mm or with ulceration. Adjuvant nivolumab or pembrolizumab for stage IIB-IV resected melanoma.", "A", "Strong",
             ["melanoma", "skin cancer"], ["nivolumab", "pembrolizumab"], ["ldh", "ct scan", "pet scan"], ["melanoma", "excision", "sentinel node", "adjuvant immunotherapy"]),
            ("Advanced Melanoma", "First-line nivolumab plus ipilimumab or nivolumab plus relatlimab for unresectable/metastatic melanoma. BRAF/MEK inhibitor combination for BRAF V600-mutated melanoma. T-VEC for injectable unresectable disease.", "A", "Strong",
             ["melanoma", "metastatic melanoma"], ["nivolumab", "ipilimumab", "dabrafenib", "trametinib", "pembrolizumab"], ["braf mutation", "ldh", "pet scan"], ["melanoma", "immunotherapy", "braf", "checkpoint inhibitor"]),
        ]),
        ("NCCN Renal Cell Carcinoma", "NCCN", 2025, [
            ("Localized RCC", "Partial nephrectomy is preferred for T1a tumors when technically feasible. Radical nephrectomy for larger tumors. Active surveillance may be appropriate for small renal masses in elderly or comorbid patients. Adjuvant pembrolizumab for high-risk clear cell RCC after nephrectomy.", "A", "Strong",
             ["renal cell carcinoma", "kidney cancer"], ["pembrolizumab"], ["ct abdomen", "creatinine", "egfr"], ["rcc", "nephrectomy", "partial", "adjuvant"]),
            ("Metastatic RCC First-Line", "Ipilimumab plus nivolumab for intermediate/poor-risk. Pembrolizumab plus axitinib or lenvatinib for favorable-to-poor risk. Cabozantinib plus nivolumab as an alternative. TKI monotherapy (sunitinib, pazopanib) if immunotherapy contraindicated.", "A", "Strong",
             ["renal cell carcinoma", "metastatic kidney cancer"], ["nivolumab", "ipilimumab", "pembrolizumab", "axitinib", "lenvatinib", "cabozantinib"], ["ct scan", "creatinine"], ["rcc", "metastatic", "immunotherapy", "tki"]),
        ]),
    ],

    # ── PULMONOLOGY ─────────────────────────────────────────────
    "pulmonology": [
        ("ATS/ERS Idiopathic Pulmonary Fibrosis", "ATS/ERS", 2022, [
            ("IPF Diagnosis", "High-resolution CT showing usual interstitial pneumonia (UIP) pattern is sufficient for diagnosis in appropriate clinical context. Surgical lung biopsy may be needed for indeterminate patterns. Multidisciplinary discussion is recommended for uncertain cases.", "A", "Strong",
             ["idiopathic pulmonary fibrosis", "ipf", "interstitial lung disease"], [], ["hrct", "pulmonary function tests", "fvc", "dlco"], ["ipf", "uip", "hrct", "diagnosis"]),
            ("IPF Treatment", "Antifibrotic therapy with nintedanib or pirfenidone is recommended for IPF. Both slow FVC decline. Lung transplant referral for eligible patients. Pulmonary rehabilitation is recommended. Supplemental oxygen for resting hypoxemia.", "A", "Strong",
             ["idiopathic pulmonary fibrosis", "ipf"], ["nintedanib", "pirfenidone"], ["fvc", "dlco", "6-minute walk test"], ["ipf", "antifibrotic", "nintedanib", "pirfenidone"]),
        ]),
        ("ATS/IDSA Pneumonia Guidelines", "ATS/IDSA", 2024, [
            ("Hospital-Acquired Pneumonia", "Empiric therapy should cover MRSA and Pseudomonas in patients with risk factors. Vancomycin or linezolid for MRSA coverage. Anti-pseudomonal beta-lactam (piperacillin-tazobactam, cefepime, meropenem) as backbone. De-escalation based on cultures within 48-72 hours.", "A", "Strong",
             ["hospital-acquired pneumonia", "hap", "ventilator-associated pneumonia"], ["vancomycin", "linezolid", "piperacillin-tazobactam", "cefepime", "meropenem"], ["sputum culture", "blood culture", "procalcitonin"], ["hap", "vap", "mrsa", "pseudomonas", "empiric"]),
            ("Aspiration Pneumonia", "Amoxicillin-clavulanate or clindamycin for community-acquired aspiration pneumonia. Broad-spectrum coverage for hospital-acquired aspiration. Swallow evaluation and aspiration precautions are recommended. Routine anaerobic coverage is not necessary for uncomplicated cases.", "B", "Moderate",
             ["aspiration pneumonia", "pneumonia"], ["amoxicillin-clavulanate", "clindamycin"], ["chest x-ray", "ct chest"], ["aspiration", "pneumonia", "swallow", "anaerobic"]),
        ]),
        ("ERS/ATS Severe Asthma", "ERS/ATS", 2024, [
            ("Biologic Therapy Selection", "Omalizumab for allergic asthma with elevated IgE. Mepolizumab, reslizumab, or benralizumab for eosinophilic asthma. Dupilumab for eosinophilic or oral corticosteroid-dependent asthma. Tezepelumab for severe asthma regardless of phenotype.", "A", "Strong",
             ["severe asthma", "asthma"], ["omalizumab", "mepolizumab", "benralizumab", "dupilumab", "tezepelumab"], ["ige", "eosinophils", "feno", "fev1"], ["biologic", "severe asthma", "eosinophilic", "omalizumab"]),
            ("Asthma-COPD Overlap", "Patients with features of both asthma and COPD should receive ICS-containing therapy. LABA/LAMA/ICS triple therapy for persistent symptoms. Biologic therapy may be considered if eosinophilic inflammation present. Avoid LABA monotherapy without ICS.", "B", "Strong",
             ["asthma", "copd", "asthma-copd overlap"], ["fluticasone", "budesonide", "formoterol", "tiotropium"], ["fev1", "eosinophils", "ige"], ["aco", "overlap", "ics", "triple therapy"]),
        ]),
        ("BTS Pleural Disease Guidelines", "BTS", 2023, [
            ("Pleural Effusion Investigation", "Diagnostic thoracentesis recommended for all new unilateral effusions. Light's criteria to differentiate transudative from exudative. pH, glucose, LDH, cytology, and culture of pleural fluid. CT thorax with contrast for suspected malignancy.", "A", "Strong",
             ["pleural effusion", "empyema"], [], ["pleural fluid analysis", "ct chest", "ldh", "protein"], ["pleural", "effusion", "thoracentesis", "lights criteria"]),
            ("Pneumothorax Management", "Primary spontaneous pneumothorax: observation if small and stable, aspiration for larger. Secondary pneumothorax: chest drain insertion. Surgical intervention (VATS pleurodesis) for recurrent pneumothorax. Smoking cessation is critical.", "A", "Strong",
             ["pneumothorax"], [], ["chest x-ray", "ct chest"], ["pneumothorax", "chest drain", "aspiration", "pleurodesis"]),
        ]),
    ],

    # ── GASTROENTEROLOGY ────────────────────────────────────────
    "gastroenterology": [
        ("ACG Peptic Ulcer Disease", "ACG", 2024, [
            ("H. pylori Eradication", "Bismuth quadruple therapy (PPI, bismuth, metronidazole, tetracycline) for 14 days or vonoprazan-based triple therapy is recommended as first-line. Clarithromycin-based triple therapy only if local resistance <15%. Test of cure 4 weeks after completing therapy.", "A", "Strong",
             ["peptic ulcer disease", "h pylori", "gastric ulcer", "duodenal ulcer"], ["omeprazole", "bismuth", "metronidazole", "tetracycline", "amoxicillin", "clarithromycin"], ["h pylori test", "urea breath test", "stool antigen"], ["h pylori", "eradication", "quadruple therapy", "ppi"]),
            ("NSAID-Related Ulcer Prevention", "PPI co-therapy is recommended for patients requiring chronic NSAIDs with ulcer risk factors. COX-2 selective inhibitors with PPI for highest-risk patients. H. pylori testing and treatment before starting chronic NSAIDs.", "A", "Strong",
             ["peptic ulcer disease", "nsaid gastropathy"], ["omeprazole", "pantoprazole", "celecoxib"], ["endoscopy"], ["nsaid", "ulcer prevention", "ppi", "cox-2"]),
        ]),
        ("AGA Hepatitis B Guidelines", "AGA", 2024, [
            ("Chronic Hepatitis B Treatment", "Antiviral therapy recommended for immune-active chronic HBV (elevated ALT + HBV DNA >2000 IU/mL for HBeAg-negative, >20000 for HBeAg-positive). Entecavir or tenofovir (TAF or TDF) as first-line. Treatment duration is indefinite for most patients.", "A", "Strong",
             ["hepatitis b", "chronic hepatitis b", "hbv"], ["entecavir", "tenofovir", "tenofovir alafenamide"], ["hbv dna", "hbsag", "alt", "hbeag"], ["hepatitis b", "antiviral", "entecavir", "tenofovir"]),
            ("Hepatitis B Screening", "Universal screening for HBV with HBsAg, anti-HBs, and anti-HBc is recommended for all adults at least once. Vaccination for all susceptible individuals. Screen pregnant women at first prenatal visit.", "A", "Strong",
             ["hepatitis b", "hbv screening"], [], ["hbsag", "anti-hbs", "anti-hbc"], ["screening", "hepatitis b", "vaccination", "prevention"]),
        ]),
        ("AASLD Hepatitis C Guidelines", "AASLD", 2024, [
            ("HCV Treatment", "Pan-genotypic DAA regimens (sofosbuvir/velpatasvir or glecaprevir/pibrentasvir) are recommended for all treatment-naive patients. 8-12 week duration based on regimen and cirrhosis status. SVR12 confirms cure. No pretreatment resistance testing needed for first-line regimens.", "A", "Strong",
             ["hepatitis c", "chronic hepatitis c", "hcv"], ["sofosbuvir", "velpatasvir", "glecaprevir", "pibrentasvir"], ["hcv rna", "hcv genotype", "alt", "fibroscan"], ["hepatitis c", "daa", "sofosbuvir", "cure"]),
        ]),
        ("ACG Liver Cirrhosis Guidelines", "ACG", 2024, [
            ("Cirrhosis Complications Screening", "Upper endoscopy for varices screening at diagnosis. HCC surveillance with ultrasound every 6 months. MELD score calculation for transplant referral. Hepatic encephalopathy prevention with lactulose and rifaximin.", "A", "Strong",
             ["cirrhosis", "portal hypertension", "liver disease"], ["lactulose", "rifaximin", "nadolol", "propranolol"], ["meld score", "inr", "bilirubin", "albumin", "creatinine"], ["cirrhosis", "varices", "hcc screening", "transplant"]),
            ("Ascites Management", "Sodium restriction and diuretics (spironolactone ± furosemide) for first-line management. Large volume paracentesis with albumin replacement for tense ascites. TIPS consideration for refractory ascites. SBP prophylaxis after first episode.", "A", "Strong",
             ["ascites", "cirrhosis", "portal hypertension"], ["spironolactone", "furosemide", "albumin", "norfloxacin"], ["sodium", "creatinine", "ascitic fluid analysis"], ["ascites", "diuretic", "paracentesis", "tips"]),
        ]),
        ("ACG Acute Pancreatitis", "ACG", 2024, [
            ("Acute Pancreatitis Initial Management", "Aggressive IV fluid resuscitation with lactated Ringer's is recommended. Early oral feeding (within 24 hours) when tolerated. Pain management with multimodal analgesia. No role for prophylactic antibiotics. ERCP within 24 hours for acute cholangitis.", "A", "Strong",
             ["acute pancreatitis", "pancreatitis"], ["lactated ringers"], ["lipase", "amylase", "ct abdomen"], ["pancreatitis", "fluid resuscitation", "early feeding"]),
            ("Necrotizing Pancreatitis", "Delayed intervention (≥4 weeks) preferred for walled-off necrosis. Step-up approach: percutaneous drainage → endoscopic necrosectomy → surgery. Antibiotics only for confirmed infected necrosis. Nutritional support via nasojejunal tube.", "A", "Strong",
             ["necrotizing pancreatitis", "pancreatic necrosis"], ["meropenem", "imipenem"], ["ct abdomen", "procalcitonin"], ["necrotizing", "walled-off necrosis", "step-up", "drainage"]),
        ]),
    ],

    # ── NEPHROLOGY ──────────────────────────────────────────────
    "nephrology": [
        ("KDIGO Acute Kidney Injury", "KDIGO", 2024, [
            ("AKI Prevention and Early Management", "Avoid nephrotoxic agents in at-risk patients. Maintain adequate volume status. Monitor serum creatinine and urine output in critically ill patients. Discontinue ACE/ARBs during acute illness. Use isotonic crystalloids for volume resuscitation.", "A", "Strong",
             ["acute kidney injury", "aki", "renal failure"], [], ["creatinine", "urine output", "bun", "potassium"], ["aki", "prevention", "nephrotoxic", "volume"]),
            ("Renal Replacement Therapy Initiation", "Initiate RRT for life-threatening changes: severe hyperkalemia, metabolic acidosis, pulmonary edema refractory to diuretics, uremic complications. Continuous RRT preferred for hemodynamically unstable patients. Timing based on clinical context rather than absolute creatinine.", "B", "Strong",
             ["acute kidney injury", "dialysis", "renal failure"], [], ["creatinine", "potassium", "bicarbonate", "bun"], ["dialysis", "rrt", "crrt", "hemodialysis"]),
        ]),
        ("KDIGO Glomerulonephritis", "KDIGO", 2024, [
            ("IgA Nephropathy", "Optimized supportive care with RAS blockade as foundation. SGLT2 inhibitors for eGFR ≥20 and proteinuria. Targeted-release budesonide (Nefecon) for high-risk patients with persistent proteinuria >0.75 g/day despite maximal supportive care. Avoid prolonged systemic corticosteroids.", "A", "Strong",
             ["iga nephropathy", "glomerulonephritis"], ["lisinopril", "losartan", "budesonide", "dapagliflozin"], ["egfr", "proteinuria", "uacr", "creatinine"], ["iga nephropathy", "proteinuria", "ras blockade", "budesonide"]),
            ("Membranous Nephropathy", "Rituximab is first-line immunosuppressive therapy for moderate-to-high risk primary membranous nephropathy. Cyclophosphamide-based regimens as alternative. Monitor PLA2R antibodies for treatment response. Conservative management for 6 months if low risk.", "A", "Strong",
             ["membranous nephropathy", "nephrotic syndrome", "glomerulonephritis"], ["rituximab", "cyclophosphamide", "tacrolimus"], ["proteinuria", "albumin", "pla2r antibody", "creatinine"], ["membranous", "rituximab", "nephrotic", "pla2r"]),
        ]),
        ("KDIGO CKD-MBD Guidelines", "KDIGO", 2024, [
            ("CKD Mineral and Bone Disorder", "Limit dietary phosphorus and use phosphate binders for hyperphosphatemia. Correct vitamin D deficiency. Calcimimetics (cinacalcet) for secondary hyperparathyroidism in dialysis patients. Target PTH 2-9x upper normal for dialysis patients. Avoid adynamic bone disease.", "B", "Strong",
             ["chronic kidney disease", "ckd", "secondary hyperparathyroidism", "renal osteodystrophy"], ["sevelamer", "calcium carbonate", "cinacalcet", "cholecalciferol", "calcitriol"], ["pth", "calcium", "phosphorus", "vitamin d", "alkaline phosphatase"], ["ckd-mbd", "phosphate", "pth", "vitamin d", "bone"]),
        ]),
    ],

    # ── NEUROLOGY ───────────────────────────────────────────────
    "neurology": [
        ("AAN Multiple Sclerosis Guidelines", "AAN", 2024, [
            ("MS Disease-Modifying Therapy", "Early initiation of disease-modifying therapy is recommended for relapsing MS. High-efficacy therapies (natalizumab, ocrelizumab, ofatumumab) should be considered for active disease. Escalation from platform therapies if breakthrough activity occurs.", "A", "Strong",
             ["multiple sclerosis", "ms", "relapsing ms"], ["ocrelizumab", "natalizumab", "ofatumumab", "dimethyl fumarate", "fingolimod"], ["mri brain", "mri spine", "csf oligoclonal bands"], ["multiple sclerosis", "dmt", "relapsing", "high-efficacy"]),
            ("MS Relapse Management", "High-dose IV methylprednisolone (1g daily for 3-5 days) for acute relapses causing functional impairment. Plasma exchange for steroid-refractory relapses. Oral taper not routinely required. Distinguish pseudo-relapse (infection, heat) from true relapse.", "A", "Strong",
             ["multiple sclerosis", "ms relapse"], ["methylprednisolone"], ["mri brain"], ["relapse", "methylprednisolone", "plasma exchange", "acute"]),
        ]),
        ("AAN Migraine Prevention Guidelines", "AAN", 2024, [
            ("Migraine Preventive Medications", "CGRP monoclonal antibodies (erenumab, fremanezumab, galcanezumab) are effective for episodic and chronic migraine prevention. Topiramate, propranolol, and amitriptyline remain first-line oral options. Consider patient comorbidities when selecting therapy.", "A", "Strong",
             ["migraine", "chronic migraine", "headache"], ["erenumab", "fremanezumab", "galcanezumab", "topiramate", "propranolol", "amitriptyline"], ["headache diary"], ["migraine", "prevention", "cgrp", "prophylaxis"]),
            ("Acute Migraine Treatment", "Triptans remain first-line for moderate-severe migraine. Gepants (ubrogepant, rimegepant) and ditans (lasmiditan) for triptan-refractory or cardiovascular risk patients. NSAIDs for mild-moderate attacks. Avoid opioids and barbiturates.", "A", "Strong",
             ["migraine", "acute migraine", "headache"], ["sumatriptan", "rizatriptan", "ubrogepant", "rimegepant", "lasmiditan", "ibuprofen"], [], ["migraine", "acute", "triptan", "gepant", "treatment"]),
        ]),
        ("AAN Parkinson Disease Guidelines", "AAN", 2024, [
            ("Parkinson Disease Motor Symptoms", "Levodopa/carbidopa is the most effective treatment for motor symptoms. MAO-B inhibitors (rasagiline, safinamide) for early mild disease. Dopamine agonists (pramipexole, ropinirole) as initial therapy in younger patients. COMT inhibitors for motor fluctuations.", "A", "Strong",
             ["parkinson disease", "parkinsonism"], ["levodopa", "carbidopa", "rasagiline", "pramipexole", "ropinirole", "entacapone"], ["updrs"], ["parkinson", "levodopa", "dopamine", "motor symptoms"]),
            ("Advanced Parkinson Therapy", "Deep brain stimulation (STN or GPi) for motor fluctuations despite optimized medical therapy. Levodopa-carbidopa intestinal gel for severe fluctuations. Consider at least 4 years disease duration and good levodopa response for DBS candidacy.", "A", "Strong",
             ["parkinson disease", "advanced parkinson"], ["levodopa", "apomorphine"], ["mri brain"], ["dbs", "deep brain stimulation", "advanced therapy", "motor fluctuations"]),
        ]),
        ("AAN Dementia Guidelines", "AAN", 2024, [
            ("Alzheimer Disease Treatment", "Cholinesterase inhibitors (donepezil, rivastigmine, galantamine) for mild-moderate Alzheimer disease. Memantine for moderate-severe disease. Lecanemab and donanemab (anti-amyloid antibodies) for early symptomatic AD with confirmed amyloid. ARIA monitoring with MRI required for anti-amyloid therapy.", "A", "Strong",
             ["alzheimer disease", "dementia"], ["donepezil", "rivastigmine", "memantine", "lecanemab", "donanemab"], ["mri brain", "amyloid pet", "csf biomarkers", "mmse", "moca"], ["alzheimer", "dementia", "cholinesterase", "anti-amyloid"]),
        ]),
        ("AHA/ASA Intracerebral Hemorrhage", "AHA/ASA", 2024, [
            ("ICH Acute Management", "Rapid blood pressure lowering to <140 mmHg systolic within 2 hours for patients presenting with SBP 150-220 mmHg. Reversal of anticoagulation: 4-factor PCC for warfarin, idarucizumab for dabigatran, andexanet alfa for factor Xa inhibitors. Neurosurgical evaluation for cerebellar hemorrhage or hydrocephalus.", "A", "Strong",
             ["intracerebral hemorrhage", "hemorrhagic stroke", "ich"], ["nicardipine", "labetalol", "4-factor pcc", "idarucizumab"], ["ct head", "inr", "blood pressure"], ["ich", "blood pressure", "reversal", "anticoagulation"]),
        ]),
    ],

    # ── INFECTIOUS DISEASE ──────────────────────────────────────
    "infectious_disease": [
        ("IDSA/ATS Sepsis Guidelines", "IDSA", 2024, [
            ("Sepsis Bundle", "Measure serum lactate. Obtain blood cultures before antibiotics. Administer broad-spectrum antibiotics within 1 hour of recognition. Administer 30 mL/kg crystalloid for hypotension or lactate ≥4 mmol/L. Reassess volume status and tissue perfusion.", "A", "Strong",
             ["sepsis", "septic shock", "severe sepsis"], ["vancomycin", "piperacillin-tazobactam", "meropenem", "norepinephrine"], ["lactate", "blood culture", "procalcitonin", "creatinine"], ["sepsis", "bundle", "antibiotics", "resuscitation"]),
            ("Septic Shock Vasopressor Management", "Norepinephrine as first-line vasopressor targeting MAP ≥65 mmHg. Add vasopressin as second-line. Dobutamine for cardiac dysfunction with adequate volume status. Corticosteroids (hydrocortisone 200mg/day) for refractory septic shock.", "A", "Strong",
             ["septic shock", "sepsis"], ["norepinephrine", "vasopressin", "dobutamine", "hydrocortisone"], ["blood pressure", "lactate", "central venous oxygen saturation"], ["vasopressor", "norepinephrine", "septic shock", "map"]),
        ]),
        ("IDSA Skin and Soft Tissue Infections", "IDSA", 2024, [
            ("Cellulitis Treatment", "Oral antibiotics (cephalexin, dicloxacillin) for non-purulent cellulitis. Incision and drainage plus antibiotics (TMP-SMX, doxycycline) for purulent infections/abscesses. IV antibiotics for systemic toxicity or failed oral therapy. MRSA coverage based on local epidemiology.", "A", "Strong",
             ["cellulitis", "skin infection", "abscess"], ["cephalexin", "dicloxacillin", "trimethoprim-sulfamethoxazole", "doxycycline", "vancomycin"], ["wound culture", "blood culture"], ["cellulitis", "abscess", "mrsa", "skin infection"]),
            ("Necrotizing Fasciitis", "Urgent surgical debridement is the cornerstone of treatment. Broad-spectrum antibiotics: vancomycin or linezolid plus piperacillin-tazobactam or carbapenem plus clindamycin. IV immunoglobulin may be considered for streptococcal toxic shock. Serial debridements often required.", "A", "Strong",
             ["necrotizing fasciitis", "necrotizing soft tissue infection"], ["vancomycin", "piperacillin-tazobactam", "meropenem", "clindamycin"], ["crp", "lactate", "wbc", "creatinine"], ["necrotizing fasciitis", "debridement", "surgical emergency"]),
        ]),
        ("IDSA Clostridioides difficile Infection", "IDSA", 2024, [
            ("C. difficile Initial Treatment", "Fidaxomicin is preferred over vancomycin for initial and recurrent CDI. Oral vancomycin 125mg QID for 10 days as alternative. Metronidazole no longer recommended for initial episode. Bezlotoxumab for patients at high risk of recurrence.", "A", "Strong",
             ["clostridioides difficile", "c difficile", "pseudomembranous colitis"], ["fidaxomicin", "vancomycin", "bezlotoxumab"], ["c difficile toxin", "gdi antigen"], ["c diff", "fidaxomicin", "vancomycin", "diarrhea"]),
            ("Recurrent CDI Management", "Fidaxomicin with extended-pulsed regimen for first recurrence. Fecal microbiota transplantation for multiple recurrences after appropriate antibiotic therapy. SER-109 (fecal microbiota spores) as FDA-approved option. Bezlotoxumab as adjunct to antibiotics.", "A", "Strong",
             ["clostridioides difficile", "recurrent c difficile"], ["fidaxomicin", "vancomycin", "bezlotoxumab"], ["c difficile toxin"], ["recurrent", "fmt", "fecal transplant", "microbiota"]),
        ]),
        ("IDSA HIV Treatment Guidelines", "IDSA/HHS", 2024, [
            ("Antiretroviral Therapy Initiation", "ART is recommended for all persons with HIV regardless of CD4 count. Rapid ART initiation (same day when possible). Preferred initial regimens: bictegravir/TAF/emtricitabine (Biktarvy) or dolutegravir-based regimens. Cabotegravir/rilpivirine injectable for virologically suppressed patients.", "A", "Strong",
             ["hiv", "aids", "hiv infection"], ["bictegravir", "dolutegravir", "emtricitabine", "tenofovir", "cabotegravir", "rilpivirine"], ["cd4 count", "hiv viral load", "hiv resistance testing"], ["hiv", "antiretroviral", "art", "biktarvy"]),
            ("HIV Pre-Exposure Prophylaxis", "PrEP recommended for all persons at substantial risk of HIV acquisition. Oral TDF/FTC (Truvada) or TAF/FTC (Descovy) daily. Long-acting cabotegravir injection every 2 months as alternative. Screening for HIV, STIs, renal function, and HBV before initiation.", "A", "Strong",
             ["hiv prevention", "prep"], ["tenofovir", "emtricitabine", "cabotegravir"], ["hiv test", "creatinine", "hbsag"], ["prep", "prevention", "cabotegravir", "truvada"]),
        ]),
    ],

    # ── ENDOCRINOLOGY ───────────────────────────────────────────
    "endocrinology": [
        ("ATA Hypothyroidism Guidelines", "ATA", 2024, [
            ("Hypothyroidism Treatment", "Levothyroxine is the standard treatment for hypothyroidism. Dose based on weight (~1.6 mcg/kg/day for full replacement). TSH monitoring 6-8 weeks after dose changes. Take on empty stomach, 30-60 minutes before breakfast. Subclinical hypothyroidism: treat if TSH >10 or symptomatic.", "A", "Strong",
             ["hypothyroidism", "thyroid disease"], ["levothyroxine", "liothyronine"], ["tsh", "free t4", "free t3"], ["hypothyroidism", "levothyroxine", "tsh", "thyroid"]),
            ("Thyroid Nodule Evaluation", "Ultrasound for all palpable nodules. FNA biopsy based on size and ultrasound features (ACR TI-RADS). Molecular testing for indeterminate cytology. Observation for benign nodules with periodic ultrasound. TSH as initial screening.", "A", "Strong",
             ["thyroid nodule", "thyroid cancer"], [], ["thyroid ultrasound", "tsh", "fna biopsy"], ["thyroid nodule", "fna", "tirads", "biopsy"]),
        ]),
        ("Endocrine Society Osteoporosis Guidelines", "Endocrine Society", 2024, [
            ("Osteoporosis Pharmacotherapy", "Bisphosphonates (alendronate, zoledronic acid) as first-line for most patients. Denosumab for bisphosphonate-intolerant or CKD stage 4-5. Anabolic agents (teriparatide, romosozumab) for very high fracture risk. Sequential therapy: anabolic first, then antiresorptive.", "A", "Strong",
             ["osteoporosis", "osteopenia", "fragility fracture"], ["alendronate", "zoledronic acid", "denosumab", "teriparatide", "romosozumab"], ["dexa scan", "t-score", "calcium", "vitamin d", "ctx"], ["osteoporosis", "bisphosphonate", "dexa", "fracture prevention"]),
        ]),
        ("Endocrine Society Adrenal Insufficiency", "Endocrine Society", 2024, [
            ("Primary Adrenal Insufficiency", "Hydrocortisone 15-25 mg/day in 2-3 divided doses as glucocorticoid replacement. Fludrocortisone 0.05-0.2 mg/day for mineralocorticoid replacement. Stress dose steroids during illness or surgery. Medic alert identification recommended.", "A", "Strong",
             ["adrenal insufficiency", "addison disease", "adrenal crisis"], ["hydrocortisone", "fludrocortisone", "prednisone"], ["cortisol", "acth", "renin", "sodium", "potassium"], ["adrenal insufficiency", "hydrocortisone", "stress dosing", "addison"]),
        ]),
        ("AACE Obesity Guidelines", "AACE", 2024, [
            ("Obesity Pharmacotherapy", "Anti-obesity medications recommended as adjunct to lifestyle modification for BMI ≥30 or ≥27 with comorbidities. Semaglutide 2.4mg weekly and tirzepatide as most effective options. Phentermine-topiramate, naltrexone-bupropion as alternatives. Consider metabolic surgery for BMI ≥40 or ≥35 with comorbidities.", "A", "Strong",
             ["obesity", "overweight", "metabolic syndrome"], ["semaglutide", "tirzepatide", "phentermine", "topiramate", "naltrexone", "bupropion", "liraglutide"], ["bmi", "waist circumference", "hba1c", "lipid panel"], ["obesity", "weight loss", "glp-1", "semaglutide", "tirzepatide"]),
        ]),
    ],

    # ── RHEUMATOLOGY ────────────────────────────────────────────
    "rheumatology": [
        ("ACR Psoriatic Arthritis Guidelines", "ACR", 2024, [
            ("PsA Treatment", "TNF inhibitors as first-line biologic for most patients. IL-17 inhibitors (secukinumab, ixekizumab) especially for axial disease and skin involvement. IL-23 inhibitors (guselkumab) for peripheral arthritis. JAK inhibitors (tofacitinib, upadacitinib) as alternative. Methotrexate for mild disease.", "A", "Strong",
             ["psoriatic arthritis", "psoriasis", "spondyloarthritis"], ["adalimumab", "etanercept", "secukinumab", "ixekizumab", "guselkumab", "tofacitinib", "methotrexate"], ["crp", "esr", "x-ray hands feet"], ["psoriatic arthritis", "biologic", "tnf", "il-17"]),
        ]),
        ("ACR Systemic Lupus Erythematosus", "ACR", 2024, [
            ("SLE Treatment", "Hydroxychloroquine is recommended for all SLE patients without contraindication. Belimumab or anifrolumab for active disease despite standard therapy. Mycophenolate mofetil as first-line for lupus nephritis class III-V. Minimize corticosteroid exposure. Voclosporin as add-on for lupus nephritis.", "A", "Strong",
             ["systemic lupus erythematosus", "lupus", "sle", "lupus nephritis"], ["hydroxychloroquine", "mycophenolate", "belimumab", "anifrolumab", "voclosporin"], ["ana", "anti-dsdna", "complement c3 c4", "creatinine", "proteinuria"], ["sle", "lupus", "hydroxychloroquine", "belimumab"]),
        ]),
        ("ACR Vasculitis Guidelines", "ACR", 2024, [
            ("ANCA-Associated Vasculitis", "Rituximab or cyclophosphamide plus glucocorticoids for remission induction. Rituximab preferred for relapsing disease. Avacopan (complement C5a receptor inhibitor) as glucocorticoid-sparing strategy. Maintenance with rituximab for at least 2 years. Plasma exchange for severe renal disease or pulmonary hemorrhage.", "A", "Strong",
             ["anca vasculitis", "granulomatosis with polyangiitis", "microscopic polyangiitis"], ["rituximab", "cyclophosphamide", "avacopan", "prednisone"], ["anca", "creatinine", "urinalysis", "crp"], ["vasculitis", "anca", "rituximab", "avacopan"]),
        ]),
        ("ACR Axial Spondyloarthritis", "ACR", 2024, [
            ("Axial SpA Treatment", "NSAIDs as first-line for active axial spondyloarthritis. TNF inhibitors for inadequate response to NSAIDs. IL-17 inhibitors (secukinumab, ixekizumab) as alternative biologic. JAK inhibitors (upadacitinib, tofacitinib) for biologic-refractory. Physical therapy and exercise are essential.", "A", "Strong",
             ["ankylosing spondylitis", "axial spondyloarthritis"], ["naproxen", "indomethacin", "adalimumab", "secukinumab", "upadacitinib"], ["hla-b27", "crp", "mri sacroiliac joints"], ["axial spa", "ankylosing spondylitis", "tnf", "il-17", "nsaid"]),
        ]),
    ],

    # ── PSYCHIATRY ──────────────────────────────────────────────
    "psychiatry": [
        ("APA Bipolar Disorder Guidelines", "APA", 2024, [
            ("Bipolar Mania Treatment", "Lithium or valproate as first-line mood stabilizers for acute mania. Second-generation antipsychotics (quetiapine, aripiprazole, olanzapine) effective as monotherapy or adjunct. Avoid antidepressant monotherapy in bipolar disorder. Combination therapy often necessary.", "A", "Strong",
             ["bipolar disorder", "mania", "bipolar mania"], ["lithium", "valproate", "quetiapine", "aripiprazole", "olanzapine"], ["lithium level", "valproate level", "tsh", "creatinine"], ["bipolar", "mania", "lithium", "mood stabilizer"]),
            ("Bipolar Depression", "Quetiapine, lurasidone, or cariprazine recommended for bipolar depression. Lamotrigine for maintenance prevention of depressive episodes. Lithium has anti-suicidal properties. ECT for treatment-resistant bipolar depression.", "A", "Strong",
             ["bipolar disorder", "bipolar depression"], ["quetiapine", "lurasidone", "cariprazine", "lamotrigine", "lithium"], ["lithium level", "metabolic panel"], ["bipolar depression", "quetiapine", "lamotrigine", "lurasidone"]),
        ]),
        ("APA Schizophrenia Guidelines", "APA", 2024, [
            ("Schizophrenia Pharmacotherapy", "Second-generation antipsychotics as first-line treatment. Clozapine for treatment-resistant schizophrenia (failed ≥2 adequate trials). Long-acting injectable antipsychotics for adherence concerns. Monitor metabolic parameters (weight, glucose, lipids) regularly.", "A", "Strong",
             ["schizophrenia", "psychosis", "schizoaffective disorder"], ["risperidone", "paliperidone", "aripiprazole", "clozapine", "olanzapine"], ["cbc", "fasting glucose", "lipid panel", "bmi"], ["schizophrenia", "antipsychotic", "clozapine", "treatment-resistant"]),
        ]),
        ("APA PTSD Guidelines", "APA", 2024, [
            ("PTSD Treatment", "Trauma-focused psychotherapy (CPT, PE, EMDR) as first-line treatment. SSRIs (sertraline, paroxetine) and venlafaxine as first-line pharmacotherapy. Prazosin for PTSD-related nightmares. Avoid benzodiazepines. Combined therapy may offer additional benefit.", "A", "Strong",
             ["ptsd", "post-traumatic stress disorder", "trauma"], ["sertraline", "paroxetine", "venlafaxine", "prazosin"], [], ["ptsd", "trauma", "ssri", "psychotherapy"]),
        ]),
        ("APA Anxiety Disorders", "APA", 2024, [
            ("Generalized Anxiety Disorder", "SSRIs (escitalopram, sertraline) and SNRIs (duloxetine, venlafaxine) as first-line pharmacotherapy. CBT as first-line psychotherapy. Buspirone as alternative. Benzodiazepines only short-term for severe symptoms. Pregabalin as alternative in some guidelines.", "A", "Strong",
             ["generalized anxiety disorder", "gad", "anxiety"], ["escitalopram", "sertraline", "duloxetine", "venlafaxine", "buspirone"], [], ["gad", "anxiety", "ssri", "cbt"]),
        ]),
    ],

    # ── OBSTETRICS/GYNECOLOGY ───────────────────────────────────
    "ob_gyn": [
        ("ACOG Gestational Hypertension", "ACOG", 2024, [
            ("Gestational Hypertension Management", "Low-dose aspirin (81mg) starting at 12-16 weeks for preeclampsia prevention in high-risk patients. Labetalol or nifedipine as first-line antihypertensives. Target BP <140/90 mmHg. IV magnesium sulfate for seizure prophylaxis in severe preeclampsia. Delivery at 37 weeks for gestational HTN without severe features.", "A", "Strong",
             ["gestational hypertension", "preeclampsia", "eclampsia", "pregnancy"], ["aspirin", "labetalol", "nifedipine", "magnesium sulfate"], ["blood pressure", "proteinuria", "uric acid", "creatinine", "platelets", "alt", "ast"], ["preeclampsia", "aspirin", "labetalol", "delivery timing"]),
        ]),
        ("ACOG Postpartum Hemorrhage", "ACOG", 2024, [
            ("PPH Prevention and Treatment", "Active management of third stage of labor with oxytocin. Quantitative blood loss measurement. Uterine massage and uterotonics (oxytocin, methylergonovine, carboprost, misoprostol) for atonic PPH. Tranexamic acid within 3 hours of onset. Massive transfusion protocol if needed.", "A", "Strong",
             ["postpartum hemorrhage", "pph", "obstetric hemorrhage"], ["oxytocin", "methylergonovine", "carboprost", "misoprostol", "tranexamic acid"], ["hemoglobin", "blood type", "coagulation studies"], ["pph", "postpartum", "hemorrhage", "uterotonic"]),
        ]),
        ("ACOG Cervical Cancer Screening", "ACOG", 2024, [
            ("Cervical Screening Guidelines", "HPV primary screening every 5 years starting at age 25 is preferred. Co-testing (HPV + cytology) every 5 years or cytology alone every 3 years as alternatives. No screening before age 21 or after age 65 with adequate negative prior results. Colposcopy for abnormal results.", "A", "Strong",
             ["cervical cancer", "hpv", "cervical screening"], [], ["hpv test", "pap smear", "colposcopy"], ["cervical screening", "hpv", "pap smear", "colposcopy"]),
        ]),
        ("ACOG Contraception", "ACOG", 2024, [
            ("Long-Acting Reversible Contraception", "LARCs (IUDs and implants) are recommended as first-line contraception for most women. Hormonal IUD (levonorgestrel) and copper IUD are highly effective (>99%). Etonogestrel implant as alternative. No age restrictions. Can be placed immediately postpartum.", "A", "Strong",
             ["contraception", "family planning"], ["levonorgestrel iud", "copper iud", "etonogestrel implant"], [], ["larc", "iud", "implant", "contraception"]),
        ]),
    ],

    # ── PEDIATRICS ──────────────────────────────────────────────
    "pediatrics": [
        ("AAP Neonatal Hyperbilirubinemia", "AAP", 2024, [
            ("Neonatal Jaundice Management", "Universal bilirubin screening before discharge. Phototherapy based on hour-specific bilirubin nomograms adjusted for gestational age and risk factors. Exchange transfusion for critically elevated levels. Intensive phototherapy with irradiance ≥30 µW/cm²/nm.", "A", "Strong",
             ["neonatal jaundice", "hyperbilirubinemia", "kernicterus"], [], ["total bilirubin", "direct bilirubin", "reticulocyte count", "blood type"], ["jaundice", "phototherapy", "bilirubin", "neonatal"]),
        ]),
        ("AAP ADHD Guidelines", "AAP", 2024, [
            ("ADHD Diagnosis and Treatment", "Behavioral therapy as first-line for preschool children (4-5 years). Stimulant medications (methylphenidate, amphetamine) as first-line for school-age children. Non-stimulants (atomoxetine, guanfacine, viloxazine) as alternatives. Combined behavioral and pharmacological therapy recommended.", "A", "Strong",
             ["adhd", "attention deficit hyperactivity disorder"], ["methylphenidate", "amphetamine", "atomoxetine", "guanfacine", "viloxazine"], ["vanderbilt scale", "conners rating"], ["adhd", "stimulant", "methylphenidate", "behavioral therapy"]),
        ]),
        ("AAP Febrile Seizures", "AAP", 2024, [
            ("Febrile Seizure Management", "Simple febrile seizures are benign and do not require routine neuroimaging, EEG, or lumbar puncture in well-appearing children ≥12 months with up-to-date vaccinations. Continuous antiepileptic therapy is not recommended. Antipyretics do not prevent recurrence. Parental education and reassurance.", "A", "Strong",
             ["febrile seizure", "seizure", "pediatric seizure"], ["acetaminophen", "ibuprofen"], ["temperature", "cbc"], ["febrile seizure", "benign", "reassurance"]),
        ]),
        ("AAP Otitis Media Guidelines", "AAP", 2024, [
            ("Acute Otitis Media Treatment", "Amoxicillin (80-90 mg/kg/day) as first-line. Watchful waiting for mild AOM in children ≥2 years. Amoxicillin-clavulanate for treatment failure. Tympanostomy tubes for recurrent AOM (≥3 in 6 months or ≥4 in 12 months). Pain management is essential.", "A", "Strong",
             ["acute otitis media", "ear infection", "pediatric otitis"], ["amoxicillin", "amoxicillin-clavulanate", "ceftriaxone"], ["otoscopy", "tympanometry"], ["otitis media", "amoxicillin", "ear infection", "tympanostomy"]),
        ]),
    ],

    # ── EMERGENCY MEDICINE ──────────────────────────────────────
    "emergency_medicine": [
        ("ACEP Acute Appendicitis", "ACEP", 2024, [
            ("Appendicitis Diagnosis and Management", "CT abdomen/pelvis is the preferred imaging for adults. Ultrasound preferred in children and pregnant women. Appendectomy remains standard treatment. Antibiotics-first approach may be considered for uncomplicated appendicitis in select patients.", "A", "Strong",
             ["appendicitis", "acute abdomen"], ["ceftriaxone", "metronidazole", "piperacillin-tazobactam"], ["ct abdomen", "wbc", "crp"], ["appendicitis", "appendectomy", "ct scan", "antibiotics"]),
        ]),
        ("ACEP Traumatic Brain Injury", "ACEP", 2024, [
            ("Mild TBI/Concussion Management", "CT head indicated by Canadian CT Head Rule or New Orleans Criteria. Observation for GCS 13-15 without CT indications. Return-to-activity graduated protocol. Avoid anticoagulants during acute period. Follow-up for persistent symptoms beyond 2 weeks.", "B", "Strong",
             ["traumatic brain injury", "concussion", "head injury"], [], ["ct head", "gcs"], ["tbi", "concussion", "ct head", "return to activity"]),
        ]),
        ("ACEP Pulmonary Embolism", "ACEP", 2024, [
            ("PE Risk Stratification", "Wells score or Geneva score for pretest probability. D-dimer for low/intermediate probability. CTPA as definitive imaging. PESI or sPESI for severity. Systemic thrombolysis for massive PE with hemodynamic instability. Anticoagulation with DOAC for uncomplicated PE.", "A", "Strong",
             ["pulmonary embolism", "pe", "venous thromboembolism"], ["heparin", "enoxaparin", "rivaroxaban", "apixaban", "alteplase"], ["d-dimer", "ctpa", "troponin", "bnp"], ["pulmonary embolism", "anticoagulation", "thrombolysis", "wells score"]),
        ]),
    ],

    # ── CRITICAL CARE ───────────────────────────────────────────
    "critical_care": [
        ("SCCM ARDS Guidelines", "SCCM", 2024, [
            ("ARDS Ventilator Management", "Low tidal volume ventilation (6 mL/kg predicted body weight). Plateau pressure ≤30 cmH2O. Driving pressure ≤15 cmH2O. Higher PEEP strategy for moderate-severe ARDS. Prone positioning for P/F ratio <150 for ≥12 hours daily.", "A", "Strong",
             ["ards", "acute respiratory distress syndrome", "respiratory failure"], [], ["pao2", "fio2", "plateau pressure", "peep", "tidal volume"], ["ards", "lung protective ventilation", "prone", "peep"]),
            ("ARDS Adjunctive Therapies", "Neuromuscular blockade for 48 hours in early severe ARDS. Conservative fluid strategy after initial resuscitation. Corticosteroids (dexamethasone) for moderate-severe ARDS. ECMO for refractory hypoxemia in specialized centers.", "B", "Strong",
             ["ards", "respiratory failure"], ["cisatracurium", "dexamethasone"], ["pao2", "paco2", "lactate"], ["ards", "paralysis", "ecmo", "steroids"]),
        ]),
        ("SCCM Pain/Agitation/Delirium", "SCCM", 2024, [
            ("ICU Sedation", "Pain assessment with validated tools (BPS, CPOT). Analgesia-first approach with opioids or non-opioid adjuncts. Light sedation targeting RASS 0 to -2. Propofol or dexmedetomidine preferred over benzodiazepines. Daily sedation interruption and spontaneous breathing trials.", "A", "Strong",
             ["icu sedation", "mechanical ventilation", "agitation"], ["fentanyl", "propofol", "dexmedetomidine", "ketamine"], ["rass", "cam-icu"], ["sedation", "analgesia", "delirium", "rass"]),
            ("ICU Delirium Prevention", "Screen for delirium with CAM-ICU or ICDSC every shift. Non-pharmacologic prevention: early mobilization, sleep promotion, reorientation. Avoid benzodiazepines and anticholinergics. Dexmedetomidine for agitated delirium requiring sedation. No pharmacologic prevention recommended.", "A", "Strong",
             ["delirium", "icu delirium", "confusion"], ["dexmedetomidine", "haloperidol"], ["cam-icu"], ["delirium", "cam-icu", "prevention", "mobilization"]),
        ]),
    ],

    # ── HEMATOLOGY ──────────────────────────────────────────────
    "hematology": [
        ("ASH Iron Deficiency Anemia", "ASH", 2024, [
            ("Iron Deficiency Treatment", "Oral iron therapy as first-line for mild-moderate IDA. IV iron (ferric carboxymaltose, iron sucrose) for intolerance, malabsorption, severe deficiency, or inflammatory conditions. Target ferritin >100 ng/mL and TSAT >20%. Investigate underlying cause: GI evaluation for men and postmenopausal women.", "A", "Strong",
             ["iron deficiency anemia", "anemia", "iron deficiency"], ["ferrous sulfate", "ferric carboxymaltose", "iron sucrose"], ["ferritin", "tsat", "iron", "hemoglobin", "mcv"], ["iron deficiency", "anemia", "iv iron", "ferritin"]),
        ]),
        ("ASH Anticoagulation Management", "ASH", 2024, [
            ("VTE Treatment Duration", "3 months minimum for provoked VTE. Extended anticoagulation for unprovoked VTE with low bleeding risk. Low-dose rivaroxaban or apixaban for extended therapy. Annual reassessment of risk-benefit. D-dimer and ultrasound may guide decision-making.", "A", "Strong",
             ["venous thromboembolism", "dvt", "pulmonary embolism"], ["rivaroxaban", "apixaban", "warfarin", "enoxaparin"], ["d-dimer", "ultrasound"], ["vte", "anticoagulation", "duration", "extended therapy"]),
        ]),
        ("NCCN Chronic Lymphocytic Leukemia", "NCCN", 2025, [
            ("CLL First-Line Treatment", "BTK inhibitors (ibrutinib, acalabrutinib, zanubrutinib) or venetoclax-obinutuzumab as first-line. Treatment selection based on TP53/del(17p) status, IGHV mutation, fitness, and comorbidities. Fixed-duration venetoclax-obinutuzumab preferred for certain patients. FCR for young fit patients with mutated IGHV.", "A", "Strong",
             ["chronic lymphocytic leukemia", "cll", "leukemia"], ["ibrutinib", "acalabrutinib", "zanubrutinib", "venetoclax", "obinutuzumab"], ["cbc", "flow cytometry", "fish", "ighv mutation"], ["cll", "btk inhibitor", "venetoclax", "first-line"]),
        ]),
    ],

    # ── DERMATOLOGY ─────────────────────────────────────────────
    "dermatology": [
        ("AAD Atopic Dermatitis Guidelines", "AAD", 2024, [
            ("Atopic Dermatitis Treatment", "Emollients as foundation of therapy. Topical corticosteroids for flares. Topical calcineurin inhibitors (tacrolimus, pimecrolimus) for maintenance and sensitive areas. Dupilumab as first-line biologic for moderate-severe AD. JAK inhibitors (abrocitinib, upadacitinib) as alternatives.", "A", "Strong",
             ["atopic dermatitis", "eczema"], ["hydrocortisone", "triamcinolone", "tacrolimus", "dupilumab", "abrocitinib", "upadacitinib"], ["ige", "eosinophils"], ["atopic dermatitis", "eczema", "dupilumab", "topical steroid"]),
        ]),
        ("AAD Acne Vulgaris Guidelines", "AAD", 2024, [
            ("Acne Treatment", "Topical retinoids as foundation for most acne. Benzoyl peroxide for antimicrobial activity. Oral antibiotics (doxycycline) for moderate-severe inflammatory acne, limited duration. Isotretinoin for severe/refractory acne. Hormonal therapy (spironolactone, combined OCP) for females with hormonal pattern.", "A", "Strong",
             ["acne", "acne vulgaris"], ["tretinoin", "adapalene", "benzoyl peroxide", "doxycycline", "isotretinoin", "spironolactone"], [], ["acne", "retinoid", "isotretinoin", "benzoyl peroxide"]),
        ]),
    ],

    # ── UROLOGY ─────────────────────────────────────────────────
    "urology": [
        ("AUA Urinary Incontinence", "AUA", 2024, [
            ("Stress Urinary Incontinence", "Pelvic floor muscle training as first-line. Pessary for women who decline or fail conservative therapy. Midurethral sling as standard surgical treatment. Bulking agents as less invasive option. Weight loss for overweight patients.", "A", "Strong",
             ["stress urinary incontinence", "urinary incontinence"], [], ["urinalysis", "post-void residual", "urodynamics"], ["stress incontinence", "pelvic floor", "midurethral sling"]),
        ]),
        ("AUA Kidney Stones", "AUA", 2024, [
            ("Nephrolithiasis Management", "NSAIDs and alpha-blockers for medical expulsive therapy (stones <10mm). Shock wave lithotripsy or ureteroscopy for stones failing conservative management. PCNL for large renal stones (>20mm). 24-hour urine collection for metabolic evaluation in recurrent stone formers. Hydration (>2.5L/day) for prevention.", "A", "Strong",
             ["nephrolithiasis", "kidney stones", "renal colic"], ["ketorolac", "tamsulosin", "potassium citrate"], ["ct abdomen", "urinalysis", "24-hour urine", "calcium", "uric acid"], ["kidney stones", "lithotripsy", "ureteroscopy", "prevention"]),
        ]),
    ],

    # ── OPHTHALMOLOGY ───────────────────────────────────────────
    "ophthalmology": [
        ("AAO Age-Related Macular Degeneration", "AAO", 2024, [
            ("Wet AMD Treatment", "Anti-VEGF intravitreal injections (aflibercept, ranibizumab, brolucizumab, faricimab) as standard of care for neovascular AMD. Treatment initiated promptly after diagnosis. Treat-and-extend regimen to optimize injection frequency. OCT monitoring at each visit.", "A", "Strong",
             ["age-related macular degeneration", "amd", "wet amd"], ["aflibercept", "ranibizumab", "brolucizumab", "faricimab"], ["oct", "fluorescein angiography", "visual acuity"], ["amd", "anti-vegf", "intravitreal", "macular degeneration"]),
        ]),
        ("AAO Glaucoma Guidelines", "AAO", 2024, [
            ("Open-Angle Glaucoma Treatment", "Prostaglandin analogs (latanoprost, bimatoprost) as first-line topical therapy. Target IOP reduction of ≥20% from baseline. Selective laser trabeculoplasty as first-line alternative. Combination therapy for inadequate response. MIGS for mild-moderate disease. Trabeculectomy or tube shunt for advanced disease.", "A", "Strong",
             ["glaucoma", "open-angle glaucoma", "ocular hypertension"], ["latanoprost", "bimatoprost", "timolol", "brimonidine", "dorzolamide"], ["iop", "visual field", "oct rnfl", "gonioscopy"], ["glaucoma", "iop", "prostaglandin", "laser trabeculoplasty"]),
        ]),
    ],

    # ── ORTHOPEDICS ─────────────────────────────────────────────
    "orthopedics": [
        ("AAOS Hip Fracture Guidelines", "AAOS", 2024, [
            ("Hip Fracture Management", "Surgical fixation within 24-48 hours of admission improves outcomes. Internal fixation for non-displaced femoral neck fractures in younger patients. Hemiarthroplasty or total hip arthroplasty for displaced femoral neck fractures in elderly. Cephalomedullary nailing for intertrochanteric fractures.", "A", "Strong",
             ["hip fracture", "femoral neck fracture", "intertrochanteric fracture"], ["enoxaparin", "tranexamic acid"], ["x-ray hip", "ct hip", "hemoglobin"], ["hip fracture", "arthroplasty", "fixation", "surgical timing"]),
        ]),
        ("AAOS ACL Injury Guidelines", "AAOS", 2024, [
            ("ACL Reconstruction", "ACL reconstruction recommended for active patients with functional instability. Prehabilitation to restore ROM and reduce swelling before surgery. Hamstring tendon, patellar tendon, or quadriceps tendon autograft. Structured rehabilitation for 9-12 months. Return-to-sport criteria-based, not time-based.", "A", "Strong",
             ["acl tear", "acl injury", "knee injury"], [], ["mri knee", "lachman test"], ["acl", "reconstruction", "rehabilitation", "return to sport"]),
        ]),
    ],

    # ── PREVENTIVE MEDICINE ─────────────────────────────────────
    "preventive_medicine": [
        ("USPSTF Lung Cancer Screening", "USPSTF", 2024, [
            ("Lung Cancer Screening", "Annual low-dose CT screening recommended for adults aged 50-80 years with 20 pack-year smoking history who currently smoke or quit within the past 15 years. Shared decision-making discussion. Screening should be discontinued once the person has not smoked for 15 years or has limited life expectancy.", "A", "Strong",
             ["lung cancer screening", "lung cancer"], [], ["low-dose ct chest"], ["lung cancer", "screening", "ldct", "smoking"]),
        ]),
        ("USPSTF Abdominal Aortic Aneurysm", "USPSTF", 2024, [
            ("AAA Screening", "One-time screening ultrasonography for men aged 65-75 who have ever smoked. Selective screening for men who have never smoked based on risk factors. Insufficient evidence for screening women. Refer for surgical evaluation if AAA ≥5.5cm.", "B", "Strong",
             ["abdominal aortic aneurysm", "aaa"], [], ["abdominal ultrasound"], ["aaa", "screening", "ultrasound", "aneurysm"]),
        ]),
        ("ACS Cancer Screening Recommendations", "ACS", 2024, [
            ("Multi-Cancer Early Detection", "Discuss multi-cancer early detection blood tests with patients aged 50-79. These are not replacements for standard screening. Follow up positive results with diagnostic imaging. Standard screening guidelines for breast, cervical, colorectal, prostate, and lung cancer should be followed.", "C", "Moderate",
             ["cancer screening", "multi-cancer detection"], [], ["mced blood test"], ["cancer screening", "early detection", "liquid biopsy"]),
        ]),
    ],
}


def generate_section_id(guideline_name: str, section_title: str) -> str:
    """Generate a unique section_id from guideline and section names."""
    # Take abbreviated guideline name
    words = re.sub(r'[^a-z0-9\s]', '', guideline_name.lower()).split()
    # Use first few meaningful words
    stop = {"the", "of", "for", "and", "in", "a", "an", "to", "with", "on"}
    abbr = "-".join(w for w in words[:4] if w not in stop)

    # Abbreviated section title
    sec_words = re.sub(r'[^a-z0-9\s]', '', section_title.lower()).split()
    sec_abbr = "-".join(w for w in sec_words[:3] if w not in stop)

    return f"{abbr}-{sec_abbr}"


def build_guidelines():
    """Build the full guidelines JSON from the specialty definitions."""
    # Load existing guidelines
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "clinical_guidelines.json")
    fixture_path = os.path.normpath(fixture_path)

    with open(fixture_path) as f:
        existing = json.load(f)

    existing_ids = {s["section_id"] for s in existing["guidelines"]}
    print(f"Existing guidelines: {len(existing['guidelines'])} sections")

    new_sections = []

    for specialty, guidelines in SPECIALTIES.items():
        for guideline_name, society, year, sections in guidelines:
            full_guideline = f"{guideline_name} ({year})"

            for (title, rec_text, grade, strength, conditions, meds, measurements, keywords) in sections:
                section_id = generate_section_id(guideline_name, title)

                # Skip if already exists
                if section_id in existing_ids:
                    continue
                existing_ids.add(section_id)

                new_sections.append({
                    "section_id": section_id,
                    "guideline": full_guideline,
                    "section_title": title,
                    "recommendation_text": rec_text,
                    "evidence_grade": grade,
                    "recommendation_level": strength,
                    "applies_to_conditions": conditions,
                    "applies_to_medications": meds,
                    "applies_to_measurements": measurements,
                    "keywords": keywords,
                })

    # Merge
    all_sections = existing["guidelines"] + new_sections
    print(f"New sections added: {len(new_sections)}")
    print(f"Total sections: {len(all_sections)}")

    # Count unique guidelines
    unique_guidelines = set(s["guideline"] for s in all_sections)
    print(f"Unique guidelines: {len(unique_guidelines)}")

    # Grade distribution
    grades = {}
    for s in all_sections:
        g = s["evidence_grade"]
        grades[g] = grades.get(g, 0) + 1
    print(f"Grade distribution: {grades}")

    # Write
    output = {"guidelines": all_sections}
    with open(fixture_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWritten to {fixture_path}")


if __name__ == "__main__":
    build_guidelines()
