#!/usr/bin/env python3
"""Batch 8: Final push to ~1000 total sections (~315 needed).

Fills remaining gaps across ALL specialties with granular subsections.
Uses a template-driven approach to systematically generate screening,
diagnosis, treatment, and monitoring sections for common conditions.
"""

import json, os, hashlib

def _id(guideline, title):
    raw = f"{guideline}|{title}"
    h = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"b8-{h}"

SECTIONS = [
    # ══════════════════════════════════════════
    # CARDIOLOGY — GRANULAR SUB-SECTIONS (~25)
    # ══════════════════════════════════════════
    ("ACC/AHA Atrial Fibrillation Guidelines", "ACC/AHA", 2024,
     "AF Rate vs Rhythm Control Decision",
     "Rate control preferred for older patients with minimal symptoms and permanent AF. Rhythm control preferred if: symptomatic, younger, HF, recent onset (<1 year), active lifestyle. EAST-AFNET 4: early rhythm control reduces cardiovascular events. Rate targets: strict <80 bpm vs lenient <110 bpm (RACE II: lenient non-inferior). Beta-blockers or CCBs for rate control. Avoid digoxin as first-line.",
     "A", "Strong", ["atrial fibrillation"], ["metoprolol", "diltiazem", "amiodarone", "flecainide", "digoxin"], ["ecg", "holter monitor", "heart rate", "echocardiogram"], ["af", "rate control", "rhythm control", "east-afnet"]),

    ("ACC/AHA Atrial Fibrillation Guidelines", "ACC/AHA", 2024,
     "AF Catheter Ablation",
     "Pulmonary vein isolation (PVI) as first-line rhythm control option for symptomatic paroxysmal AF. CABANA and CASTLE-AF: ablation superior to drugs for AF with HF. Repeat ablation for recurrence. Pulsed field ablation (PFA) emerging technique with tissue selectivity. Anticoagulation continues for at least 2 months post-ablation regardless of CHA2DS2-VASc. Long-term anticoagulation based on stroke risk, not ablation success.",
     "A", "Strong", ["atrial fibrillation", "catheter ablation"], ["apixaban", "rivaroxaban", "amiodarone"], ["ecg", "cardiac mri", "holter monitor", "echocardiogram"], ["af ablation", "pulmonary vein isolation", "pfa", "rhythm control"]),

    ("ACC/AHA Stable Ischemic Heart Disease Guidelines", "ACC/AHA", 2024,
     "Chronic Coronary Disease Management",
     "Optimal medical therapy (OMT): aspirin + high-intensity statin + ACEi/ARB (if HF, DM, HTN) + beta-blocker (if prior MI or HF). Anti-anginal: beta-blocker first-line, CCB or long-acting nitrate as alternative/add-on. Ranolazine for refractory angina. Colchicine 0.5 mg daily reduces cardiovascular events (COLCOT/LoDoCo2). Revascularization: PCI or CABG for refractory symptoms despite OMT or left main/3-vessel disease.",
     "A", "Strong", ["stable angina", "chronic coronary disease"], ["aspirin", "atorvastatin", "metoprolol", "amlodipine", "ranolazine", "colchicine", "nitroglycerin"], ["stress test", "coronary cta", "lipid panel", "hba1c"], ["stable angina", "omt", "colchicine", "revascularization"]),

    ("HRS ICD Guidelines", "HRS/ACC/AHA", 2024,
     "ICD Implantation Indications",
     "Primary prevention: LVEF ≤35% despite ≥3 months GDMT (NYHA II-III). Wait ≥40 days post-MI, ≥3 months post-revascularization. Secondary prevention: survived cardiac arrest, sustained VT with hemodynamic compromise, syncope with inducible VT. Wearable defibrillator (LifeVest) as bridge during waiting period. S-ICD for patients without pacing indication. CRT-D for LVEF ≤35% + LBBB + QRS ≥150 ms.",
     "A", "Strong", ["sudden cardiac death prevention", "ventricular tachycardia"], [], ["ejection fraction", "ecg", "echocardiogram", "signal-averaged ecg"], ["icd", "primary prevention", "crt", "sudden cardiac death"]),

    ("ACC/AHA Myocarditis Guidelines", "ACC/AHA/ESC", 2024,
     "Acute Myocarditis Management",
     "Cardiac MRI (Lake Louise criteria) for diagnosis: edema, late gadolinium enhancement, T1/T2 mapping. Endomyocardial biopsy for fulminant or refractory cases. Supportive care: restrict exercise for 3-6 months. HF management with GDMT if reduced EF. Mechanical circulatory support for cardiogenic shock. Immunosuppression only for proven autoimmune/giant cell myocarditis or eosinophilic. Avoid NSAIDs in acute phase.",
     "B", "Strong", ["myocarditis", "inflammatory cardiomyopathy"], ["lisinopril", "carvedilol", "furosemide", "prednisone"], ["cardiac mri", "troponin", "bnp", "echocardiogram", "endomyocardial biopsy"], ["myocarditis", "cardiac mri", "lake louise", "exercise restriction"]),

    ("ACC/AHA Peripheral Artery Disease Guidelines", "ACC/AHA", 2024,
     "PAD Diagnosis and Management",
     "Screening: ABI in symptomatic or at-risk patients (age ≥65, or ≥50 with DM/smoking). ABI ≤0.9 diagnostic. Claudication: supervised exercise therapy (SET) 3x/week for 12 weeks (first-line). Cilostazol for symptom improvement. Antiplatelet: aspirin or clopidogrel. Statin therapy. Revascularization: endovascular or surgical for lifestyle-limiting claudication despite SET or critical limb ischemia (rest pain, tissue loss). Wound care for critical limb ischemia.",
     "A", "Strong", ["peripheral artery disease", "claudication", "critical limb ischemia"], ["aspirin", "clopidogrel", "cilostazol", "atorvastatin", "rivaroxaban"], ["abi", "duplex ultrasound", "ct angiography", "toe pressure"], ["pad", "claudication", "abi", "supervised exercise"]),

    # ══════════════════════════════════════════
    # ONCOLOGY — MORE GRANULAR (~20)
    # ══════════════════════════════════════════
    ("NCCN Colorectal Cancer Screening", "NCCN/USPSTF", 2025,
     "Colorectal Cancer Screening Strategies",
     "Average risk: begin at age 45. Colonoscopy every 10 years (gold standard). Alternatives: FIT annually, FIT-DNA (Cologuard) every 3 years, CT colonography every 5 years, flexible sigmoidoscopy every 5 years. High risk (family history, Lynch, IBD): colonoscopy starting age 40 or 10 years before youngest affected relative. Lynch syndrome: colonoscopy every 1-2 years from age 20-25. FAP: sigmoidoscopy annually from age 10-12.",
     "A", "Strong", ["colorectal cancer screening", "colon cancer prevention"], [], ["colonoscopy", "fit", "cologuard", "ct colonography"], ["colon cancer screening", "colonoscopy", "fit", "lynch syndrome"]),

    ("NCCN Breast Cancer Treatment Guidelines", "NCCN", 2025,
     "Early Breast Cancer Systemic Therapy",
     "HR+/HER2-: adjuvant endocrine therapy (tamoxifen premenopausal, AI postmenopausal) for 5-10 years. Add abemaciclib for high-risk node-positive. Oncotype DX for node-negative to guide chemotherapy (RS ≥26: chemo benefit). HER2+: trastuzumab-based chemo (TH, TCHP). Neoadjuvant preferred for HER2+ and TNBC. TNBC: pembrolizumab + chemo neoadjuvant if stage II-III, then adjuvant pembrolizumab ± olaparib (gBRCA+). Capecitabine adjuvant for residual TNBC after neoadjuvant.",
     "A", "Strong", ["breast cancer", "early breast cancer"], ["tamoxifen", "anastrozole", "trastuzumab", "pertuzumab", "pembrolizumab", "abemaciclib", "olaparib", "capecitabine"], ["er", "pr", "her2", "oncotype dx", "ki-67", "mammogram", "mri breast"], ["breast cancer", "adjuvant", "oncotype", "immunotherapy"]),

    ("NCCN Prostate Cancer Guidelines", "NCCN", 2025,
     "Prostate Cancer Treatment by Risk Group",
     "Very low/low risk: active surveillance (PSA Q6mo, DRE Q12mo, mpMRI Q12-24mo, biopsy Q2-4y). Favorable intermediate: active surveillance or definitive treatment. Unfavorable intermediate: radical prostatectomy (RP) or radiation (EBRT + ADT 4-6 months). High risk: RP with extended PLND or EBRT + long-term ADT (18-36 months). Metastatic hormone-sensitive: ADT + doublet/triplet (docetaxel, abiraterone, enzalutamide, darolutamide, apalutamide).",
     "A", "Strong", ["prostate cancer"], ["enzalutamide", "abiraterone", "darolutamide", "docetaxel", "leuprolide"], ["psa", "mpmri prostate", "gleason score", "bone scan", "psma pet"], ["prostate cancer", "active surveillance", "radical prostatectomy", "adt"]),

    ("NCCN Head and Neck Cancer Guidelines", "NCCN", 2025,
     "Oropharyngeal Cancer Treatment",
     "HPV-positive (p16+): better prognosis. Early stage: single modality (surgery or radiation). Locally advanced: concurrent chemoradiation (cisplatin 100 mg/m² Q3wk + RT 70 Gy) standard. Post-operative: RT ± cisplatin for high-risk features. De-escalation trials ongoing for HPV+ (lower radiation, immunotherapy substitution). Nutrition support: PEG placement if dysphagia expected. Speech and swallowing rehabilitation.",
     "A", "Strong", ["oropharyngeal cancer", "head and neck squamous cell carcinoma"], ["cisplatin", "cetuximab", "pembrolizumab", "nivolumab"], ["p16", "hpv testing", "ct neck", "pet-ct", "direct laryngoscopy"], ["oropharyngeal cancer", "hpv", "chemoradiation", "cisplatin"]),

    ("NCCN Hepatocellular Carcinoma Guidelines", "NCCN/AASLD", 2025,
     "HCC Staging and Treatment",
     "BCLC staging guides treatment. Very early/early (BCLC 0-A): resection, ablation, or liver transplant (Milan criteria: single ≤5 cm or ≤3 nodules each ≤3 cm). Intermediate (BCLC B): TACE (transarterial chemoembolization). Advanced (BCLC C): atezolizumab + bevacizumab (first-line systemic), or durvalumab + tremelimumab, or lenvatinib/sorafenib. AFP, imaging Q3-6 months for surveillance in cirrhosis.",
     "A", "Strong", ["hepatocellular carcinoma", "liver cancer"], ["atezolizumab", "bevacizumab", "lenvatinib", "sorafenib", "durvalumab"], ["afp", "ct abdomen triphasic", "mri liver", "liver biopsy"], ["hcc", "bclc", "tace", "liver transplant"]),

    ("NCCN Bladder Cancer Guidelines", "NCCN/AUA", 2025,
     "Bladder Cancer Treatment by Stage",
     "Non-muscle invasive (Ta/T1/CIS): TURBT + intravesical BCG (induction + maintenance). BCG-unresponsive: pembrolizumab, nadofaragene (Adstiladrin), or radical cystectomy. Muscle-invasive (T2+): neoadjuvant cisplatin-based chemo (dose-dense MVAC or GC) then radical cystectomy. Adjuvant nivolumab for high-risk post-cystectomy. Metastatic: enfortumab vedotin + pembrolizumab (first-line), or cisplatin-based chemo then avelumab maintenance.",
     "A", "Strong", ["bladder cancer", "urothelial carcinoma"], ["bcg", "cisplatin", "gemcitabine", "pembrolizumab", "enfortumab vedotin", "nivolumab"], ["cystoscopy", "ct urogram", "urine cytology"], ["bladder cancer", "bcg", "cystectomy", "immunotherapy"]),

    # ══════════════════════════════════════════
    # PULMONOLOGY EXPANSION (~15)
    # ══════════════════════════════════════════
    ("GOLD COPD Guidelines", "GOLD", 2025,
     "COPD Group E Initial Pharmacotherapy",
     "Group E (any exacerbation history with symptoms): LAMA + LABA (preferred initial). If eosinophils ≥300: LAMA + LABA + ICS triple therapy upfront. ICS escalation if exacerbations persist with eosinophils ≥100. Add roflumilast if FEV1 <50% with continued exacerbations. Azithromycin 250 mg daily for ex-smokers with persistent exacerbations despite optimal inhaler therapy. Pneumococcal and influenza vaccination.",
     "A", "Strong", ["copd", "chronic obstructive pulmonary disease"], ["umeclidinium-vilanterol", "tiotropium", "fluticasone-vilanterol", "roflumilast", "azithromycin"], ["spirometry", "fev1", "eosinophil count", "chest x-ray"], ["copd", "triple therapy", "gold", "exacerbation"]),

    ("GOLD COPD Guidelines", "GOLD", 2025,
     "COPD Acute Exacerbation Management",
     "Mild: increase SABA frequency. Moderate: SABA + oral corticosteroids (prednisone 40 mg x 5 days). Severe (hospitalized): SABA neb, systemic steroids, antibiotics if purulent sputum/severe (amoxicillin-clavulanate, doxycycline, or azithromycin x 5 days). NIV (BiPAP) for respiratory acidosis (pH <7.35, PaCO2 >45). Intubation if NIV fails. Assess inhaler technique and adherence at discharge. Follow-up within 1-4 weeks.",
     "A", "Strong", ["copd exacerbation", "aecopd"], ["albuterol", "ipratropium", "prednisone", "amoxicillin-clavulanate", "azithromycin"], ["spirometry", "abg", "chest x-ray", "sputum culture"], ["copd exacerbation", "niv", "systemic steroids", "antibiotics"]),

    ("GINA Asthma Guidelines", "GINA", 2025,
     "Asthma Severe Exacerbation Management",
     "Immediate: high-flow oxygen targeting SpO2 93-95%. SABA via MDI+spacer or nebulizer Q20min x 3. Ipratropium bromide for severe. Systemic corticosteroids within 1 hour (prednisolone 40-50 mg or IV methylprednisolone). Reassess at 1 hour. Poor response: IV magnesium sulfate 2g over 20 min. Consider IV aminophylline or terbutaline. ICU if: deteriorating PEF, worsening hypoxia, drowsy/confused, silent chest. Intubation for respiratory failure.",
     "A", "Strong", ["asthma exacerbation", "status asthmaticus"], ["albuterol", "ipratropium", "prednisone", "methylprednisolone", "magnesium sulfate"], ["peak flow", "spirometry", "oxygen saturation", "abg"], ["asthma exacerbation", "status asthmaticus", "magnesium sulfate"]),

    ("ATS/ERS Interstitial Lung Disease Guidelines", "ATS/ERS", 2024,
     "Idiopathic Pulmonary Fibrosis Treatment",
     "Antifibrotic therapy for all IPF patients: nintedanib 150 mg BID or pirfenidone 801 mg TID (titrate over 2 weeks). Both slow FVC decline by ~50%. Most common side effects: GI (diarrhea for nintedanib, nausea/photosensitivity for pirfenidone). Avoid combination. Supplemental O2 for resting hypoxemia. Pulmonary rehabilitation. Lung transplant evaluation for eligible patients. Acute exacerbation: high-dose corticosteroids (limited evidence), supportive care.",
     "A", "Strong", ["idiopathic pulmonary fibrosis", "ipf"], ["nintedanib", "pirfenidone"], ["hrct chest", "spirometry", "fvc", "dlco", "6-minute walk test", "oxygen saturation"], ["ipf", "antifibrotic", "nintedanib", "pirfenidone"]),

    ("ATS Pulmonary Embolism Guidelines", "ATS/ESC", 2024,
     "Pulmonary Embolism Risk Stratification and Treatment",
     "Low risk (sPESI 0): outpatient DOAC. Intermediate-low: hospital, DOAC, monitor. Intermediate-high (RV dysfunction on echo/CT + elevated troponin): anticoagulation, close monitoring, consider rescue thrombolysis if deterioration. Massive PE (hemodynamic instability): systemic thrombolysis (alteplase 100 mg over 2 hours) or catheter-directed therapy. Surgical embolectomy for failed thrombolysis. ECMO as bridge. IVC filter only if anticoagulation absolutely contraindicated.",
     "A", "Strong", ["pulmonary embolism", "venous thromboembolism"], ["apixaban", "rivaroxaban", "enoxaparin", "alteplase"], ["ct pulmonary angiogram", "d-dimer", "troponin", "bnp", "echocardiogram", "lower extremity doppler"], ["pulmonary embolism", "thrombolysis", "spesi", "doac"]),

    ("ATS Pleural Effusion Guidelines", "ATS/BTS", 2024,
     "Pleural Effusion Evaluation and Management",
     "Diagnostic thoracentesis for clinically significant new effusions. Light criteria to distinguish transudative (all met: protein ratio <0.5, LDH ratio <0.6, LDH <2/3 upper limit) vs exudative. Exudative workup: cell count, glucose, pH, cytology, cultures, triglycerides, amylase. Empyema (pH <7.2, positive culture, pus): chest tube + fibrinolytics (tPA + DNase) or VATS. Malignant effusion: indwelling pleural catheter or talc pleurodesis.",
     "A", "Strong", ["pleural effusion", "empyema", "malignant effusion"], ["tpa", "dornase alfa"], ["chest x-ray", "ct chest", "pleural fluid analysis", "pleural fluid ph", "ldh"], ["pleural effusion", "light criteria", "thoracentesis", "empyema"]),

    ("ATS Pneumothorax Guidelines", "ATS/BTS", 2024,
     "Spontaneous Pneumothorax Management",
     "Primary spontaneous pneumothorax: small (<2 cm at apex on CXR) + stable: observation with repeat imaging. Large or symptomatic: needle aspiration first (success ~70%), chest tube if aspiration fails. Persistent air leak >5 days: consider VATS with bleb resection + pleurodesis. Secondary spontaneous (underlying lung disease): chest tube insertion, lower threshold for VATS. Tension pneumothorax: immediate needle decompression (2nd ICS MCL or 5th ICS MAL) then chest tube.",
     "A", "Strong", ["pneumothorax", "tension pneumothorax"], [], ["chest x-ray", "ct chest", "oxygen saturation"], ["pneumothorax", "chest tube", "needle decompression", "vats"]),

    # ══════════════════════════════════════════
    # INFECTIOUS DISEASE — MORE DEPTH (~20)
    # ══════════════════════════════════════════
    ("IDSA HIV Treatment Guidelines", "DHHS/IAS", 2024,
     "HIV Antiretroviral Therapy Initiation",
     "Start ART for ALL people with HIV regardless of CD4 count (test-and-treat). Preferred initial regimens: bictegravir/emtricitabine/TAF (Biktarvy) or dolutegravir + emtricitabine/TAF. Long-acting: cabotegravir/rilpivirine IM monthly or bimonthly for virologically suppressed. Resistance testing (genotype) before starting. Rapid ART start (same day or next day) improves retention. Monitor: viral load Q4-8 weeks until undetectable, then Q3-6 months. CD4 annually once stable.",
     "A", "Strong", ["hiv", "hiv treatment"], ["bictegravir-emtricitabine-taf", "dolutegravir", "cabotegravir-rilpivirine"], ["hiv viral load", "cd4 count", "hiv genotype", "cbc", "cmp", "lipid panel", "hba1c"], ["hiv", "art", "biktarvy", "dolutegravir"]),

    ("IDSA HIV Prevention Guidelines", "CDC/USPSTF", 2024,
     "HIV Pre-Exposure Prophylaxis (PrEP)",
     "PrEP for all persons at substantial risk of HIV. Options: oral TDF/FTC (Truvada) daily, oral TAF/FTC (Descovy) daily (not for receptive vaginal sex), long-acting cabotegravir (Apretude) IM Q2months (most effective). Before initiation: HIV test (negative), eGFR, HBV status, STI screening. Follow-up: HIV testing Q3 months, eGFR Q6-12 months, STI screening Q3-6 months. PrEP on demand (2-1-1) for MSM with oral TDF/FTC.",
     "A", "Strong", ["hiv prevention", "prep"], ["tenofovir-emtricitabine", "cabotegravir injectable"], ["hiv test", "egfr", "hbsag", "sti screening"], ["prep", "hiv prevention", "cabotegravir", "truvada"]),

    ("IDSA Pneumonia Guidelines", "ATS/IDSA", 2024,
     "Community-Acquired Pneumonia Empiric Therapy",
     "Outpatient, no comorbidities: amoxicillin 1g TID or doxycycline. Outpatient with comorbidities: amoxicillin-clavulanate + azithromycin/doxycycline, or respiratory fluoroquinolone. Inpatient non-ICU: beta-lactam (ceftriaxone, ampicillin-sulbactam) + azithromycin/doxycycline, or respiratory fluoroquinolone. ICU: beta-lactam + azithromycin (or fluoroquinolone). Add MRSA coverage (vancomycin/linezolid) if risk factors. Procalcitonin to guide antibiotic duration (stop if <0.25).",
     "A", "Strong", ["community-acquired pneumonia", "cap"], ["amoxicillin", "azithromycin", "ceftriaxone", "levofloxacin", "vancomycin"], ["chest x-ray", "procalcitonin", "blood cultures", "sputum culture", "urinary antigens"], ["cap", "pneumonia", "empiric antibiotics", "procalcitonin"]),

    ("IDSA Urinary Tract Infection Guidelines", "IDSA/AUA", 2024,
     "Uncomplicated Cystitis Treatment",
     "First-line: nitrofurantoin 100 mg BID x 5 days (avoid if eGFR <30), TMP-SMX DS BID x 3 days (if resistance <20%), fosfomycin 3g single dose. Second-line: fluoroquinolone (reserve for complicated UTI). Uncomplicated pyelonephritis: outpatient ciprofloxacin 7 days or TMP-SMX 14 days; inpatient ceftriaxone or fluoroquinolone IV then step-down. Recurrent UTI (≥3/year): antibiotic prophylaxis, vaginal estrogen for postmenopausal, cranberry supplements (limited evidence).",
     "A", "Strong", ["cystitis", "pyelonephritis", "urinary tract infection"], ["nitrofurantoin", "trimethoprim-sulfamethoxazole", "ciprofloxacin", "ceftriaxone", "fosfomycin"], ["urinalysis", "urine culture", "egfr"], ["uti", "cystitis", "nitrofurantoin", "pyelonephritis"]),

    ("IDSA Skin and Soft Tissue Infection Guidelines", "IDSA", 2024,
     "Cellulitis and Abscess Management",
     "Purulent SSTI (abscess): I&D is primary treatment. Mild: I&D alone may suffice. Moderate: I&D + oral antibiotic (TMP-SMX, doxycycline for MRSA coverage). Non-purulent cellulitis: oral cephalexin or dicloxacillin (streptococcal coverage). MRSA risk: add TMP-SMX or doxycycline. Severe (SIRS criteria): IV antibiotics — vancomycin + piperacillin-tazobactam. Necrotizing fasciitis: emergent surgical exploration + broad-spectrum IV antibiotics + ID consult.",
     "A", "Strong", ["cellulitis", "skin abscess", "necrotizing fasciitis"], ["cephalexin", "trimethoprim-sulfamethoxazole", "doxycycline", "vancomycin", "piperacillin-tazobactam"], ["wound culture", "blood cultures", "ct soft tissue", "crp", "lactate"], ["cellulitis", "abscess", "mrsa", "necrotizing fasciitis"]),

    ("IDSA Septic Arthritis Guidelines", "IDSA/ACR", 2024,
     "Septic Joint Management",
     "Joint aspiration is essential: WBC >50,000, >75% PMN, positive gram stain/culture. Staph aureus most common. Empiric: vancomycin (covers MRSA) ± 3rd-gen cephalosporin (GNR coverage). Gonococcal: ceftriaxone 1g IV/IM + azithromycin. Prosthetic joint: additional surgical washout/debridement. Native joint: repeated aspiration or arthroscopic lavage. Duration: 2-4 weeks for native joints (S. aureus 4 weeks). De-escalate based on culture.",
     "A", "Strong", ["septic arthritis", "infectious arthritis"], ["vancomycin", "ceftriaxone", "nafcillin", "azithromycin"], ["synovial fluid analysis", "blood cultures", "crp", "esr", "joint x-ray", "mri joint"], ["septic arthritis", "joint aspiration", "vancomycin"]),

    ("IDSA Meningitis Guidelines", "IDSA", 2024,
     "Bacterial Meningitis Empiric Therapy",
     "Empiric (adults): vancomycin + ceftriaxone + ampicillin (age >50 or immunocompromised for Listeria). Dexamethasone 0.15 mg/kg Q6h before or with first antibiotic dose (reduces mortality in pneumococcal meningitis). Neonates: ampicillin + cefotaxime (or gentamicin). Children: vancomycin + ceftriaxone. LP: opening pressure, cell count, protein, glucose, gram stain, culture, multiplex PCR. Chemoprophylaxis for close contacts of N. meningitidis (ciprofloxacin, rifampin, or ceftriaxone).",
     "A", "Strong", ["bacterial meningitis"], ["vancomycin", "ceftriaxone", "ampicillin", "dexamethasone"], ["lumbar puncture", "csf analysis", "csf culture", "blood cultures", "ct head"], ["meningitis", "dexamethasone", "lumbar puncture", "empiric"]),

    ("IDSA Clostridioides difficile Guidelines", "IDSA", 2024,
     "CDI Prevention and Recurrence Strategies",
     "Prevention: antimicrobial stewardship (most important), contact precautions, hand hygiene with soap and water (not alcohol gel alone), environmental cleaning with sporicidal agents. Probiotics (S. boulardii, LGG) may reduce CDI in high-risk antibiotic recipients. Bezlotoxumab (anti-toxin B monoclonal antibody) reduces recurrence. FMT for ≥2 recurrences (SER-109/Vowst approved oral formulation). Fidaxomicin for first episode reduces recurrence vs vancomycin.",
     "A", "Strong", ["c difficile prevention", "c difficile recurrence"], ["fidaxomicin", "bezlotoxumab"], ["c diff toxin", "c diff pcr"], ["c diff prevention", "fmt", "bezlotoxumab", "stewardship"]),

    ("IDSA Tuberculosis Guidelines", "ATS/CDC/IDSA", 2024,
     "Active TB Treatment",
     "Standard regimen: RIPE (rifampin, isoniazid, pyrazinamide, ethambutol) x 2 months intensive, then rifampin + isoniazid x 4 months continuation (6 months total). Alternative: 4-month regimen with rifapentine + isoniazid + moxifloxacin + pyrazinamide (TB-PRACTECAL). DOT recommended. Monitor LFTs monthly (especially if baseline abnormal, age >35, alcohol use). Pyridoxine (B6) 25 mg/day with isoniazid. MDR-TB: individualized based on susceptibility; bedaquiline-based regimen.",
     "A", "Strong", ["tuberculosis", "active tb"], ["rifampin", "isoniazid", "pyrazinamide", "ethambutol", "pyridoxine", "moxifloxacin"], ["sputum afb smear", "sputum culture", "tb pcr", "chest x-ray", "alt", "bilirubin"], ["tuberculosis", "ripe", "dot", "mdr-tb"]),

    ("IDSA Fungal Infections Guidelines", "IDSA", 2024,
     "Invasive Aspergillosis Treatment",
     "Primary therapy: voriconazole (IV then oral, target trough 1-5.5 mg/L) or isavuconazole. Combination voriconazole + anidulafungin for initial severe disease (ELIOT study). Salvage: lipid amphotericin B, posaconazole. Duration: minimum 6-12 weeks, until resolution of signs/symptoms AND immune reconstitution. Galactomannan (serum and BAL) for diagnosis. CT chest: halo sign (early), air crescent (recovery). Reduce immunosuppression if possible.",
     "A", "Strong", ["invasive aspergillosis", "aspergillus"], ["voriconazole", "isavuconazole", "anidulafungin", "amphotericin b liposomal", "posaconazole"], ["galactomannan", "beta-d-glucan", "ct chest", "bal culture", "voriconazole trough"], ["aspergillosis", "voriconazole", "galactomannan", "halo sign"]),

    # ══════════════════════════════════════════
    # ADDITIONAL ENDOCRINOLOGY (~10)
    # ══════════════════════════════════════════
    ("ATA Hypothyroidism Guidelines", "ATA", 2024,
     "Primary Hypothyroidism Treatment",
     "Levothyroxine monotherapy is standard of care. Starting dose: 1.6 mcg/kg/day for young healthy adults; start lower (25-50 mcg) for elderly or cardiac patients. Take on empty stomach, 30-60 minutes before breakfast. TSH target: 0.5-2.5 for most adults; higher (4-6) for elderly >70. Recheck TSH at 6-8 weeks after dose change. Avoid T3/T4 combination routinely. Subclinical hypothyroidism (TSH 5-10): treat if symptomatic, TPO antibody positive, or pregnant.",
     "A", "Strong", ["hypothyroidism", "subclinical hypothyroidism"], ["levothyroxine"], ["tsh", "free t4", "tpo antibodies"], ["hypothyroidism", "levothyroxine", "tsh", "thyroid"]),

    ("ATA Thyroid Nodule Guidelines", "ATA", 2024,
     "Thyroid Nodule Evaluation",
     "TSH first: if low, perform radionuclide scan (hot nodule = unlikely malignant). Ultrasound for all palpable nodules. ACR TI-RADS guides FNA: highly suspicious (TI-RADS 5) ≥1 cm, moderately suspicious (TI-RADS 4) ≥1.5 cm, mildly suspicious (TI-RADS 3) ≥2.5 cm. Bethesda classification: I (non-diagnostic: repeat), II (benign: follow), III-IV (indeterminate: molecular testing or lobectomy), V-VI (suspicious/malignant: surgery). Molecular testing: Afirma GSC or ThyroSeq v3 for indeterminate.",
     "A", "Strong", ["thyroid nodule", "thyroid cancer evaluation"], [], ["tsh", "thyroid ultrasound", "fna biopsy", "molecular testing"], ["thyroid nodule", "ti-rads", "fna", "bethesda"]),

    ("Endocrine Society Osteoporosis Guidelines", "Endocrine Society/NOF", 2024,
     "Osteoporosis Treatment Selection",
     "First-line: oral bisphosphonate (alendronate 70 mg weekly, risedronate 35 mg weekly). Take upright with full glass of water, remain upright 30 min. IV zoledronic acid 5 mg annually (alternative). High fracture risk or very low BMD: anabolic first (teriparatide or romosozumab x 1-2 years) then transition to antiresorptive. Denosumab 60 mg SC Q6months (rebound risk if discontinued without transition). Monitor: DEXA every 2 years, P1NP/CTX for treatment response.",
     "A", "Strong", ["osteoporosis", "fragility fracture prevention"], ["alendronate", "zoledronic acid", "teriparatide", "romosozumab", "denosumab"], ["dexa", "vitamin d level", "calcium", "p1np", "ctx", "x-ray spine"], ["osteoporosis", "bisphosphonate", "dexa", "anabolic"]),

    # ══════════════════════════════════════════
    # ADDITIONAL NEPHROLOGY (~8)
    # ══════════════════════════════════════════
    ("KDIGO Lupus Nephritis Guidelines", "KDIGO/ACR", 2024,
     "Lupus Nephritis Treatment",
     "Class III/IV (proliferative): induction with mycophenolate 3g/day + low-dose glucocorticoids (preferred) or IV cyclophosphamide (Euro-Lupus). Add voclosporin for improved complete remission. Belimumab add-on improves renal response. Class V (membranous): mycophenolate + glucocorticoids. Maintenance: mycophenolate (at least 3 years) or azathioprine. Hydroxychloroquine for ALL lupus nephritis. Target: complete renal response (UPCR <0.5, normal GFR) by 12 months.",
     "A", "Strong", ["lupus nephritis", "sle nephritis"], ["mycophenolate", "cyclophosphamide", "voclosporin", "belimumab", "hydroxychloroquine", "prednisone"], ["upcr", "creatinine", "c3", "c4", "anti-dsdna", "renal biopsy"], ["lupus nephritis", "mycophenolate", "voclosporin", "belimumab"]),

    ("KDIGO IgA Nephropathy Guidelines", "KDIGO", 2024,
     "IgA Nephropathy Management",
     "Supportive care first (3-6 months): maximal RAS blockade (ACEi/ARB titrated to maximum tolerated), SGLT2 inhibitor (dapagliflozin), BP <130/80. Sparsentan (dual endothelin/angiotensin receptor antagonist) reduces proteinuria. If proteinuria >0.75-1 g/day despite supportive care: targeted-release budesonide (Nefecon, Tarpeyo) for 9 months. Systemic immunosuppression (corticosteroids) only for rapidly progressive disease. Avoid fish oil as sole therapy.",
     "A", "Strong", ["iga nephropathy", "berger disease"], ["lisinopril", "dapagliflozin", "sparsentan", "budesonide targeted-release"], ["upcr", "creatinine", "egfr", "renal biopsy"], ["iga nephropathy", "sparsentan", "sglt2", "budesonide"]),

    # ══════════════════════════════════════════
    # ADDITIONAL PSYCHIATRY / BEHAVIORAL (~10)
    # ══════════════════════════════════════════
    ("APA MDD Treatment Guidelines", "APA/ACP", 2024,
     "Treatment-Resistant Depression Strategies",
     "TRD defined as failure of ≥2 adequate antidepressant trials. Options: augmentation (lithium, aripiprazole 2-5 mg, quetiapine), switch class (SNRI if failed SSRI, or TCA/MAOI). Esketamine nasal spray (Spravato) with oral AD for TRD. Psilocybin-assisted therapy (emerging evidence, not yet FDA-approved). ECT most effective for severe TRD. TMS (transcranial magnetic stimulation) for moderate TRD. VNS (vagus nerve stimulation) for chronic refractory depression.",
     "A", "Strong", ["treatment-resistant depression", "refractory depression"], ["lithium", "aripiprazole", "esketamine", "venlafaxine", "tranylcypromine"], ["phq-9", "ham-d", "lithium level", "tsh"], ["treatment resistant depression", "esketamine", "ect", "tms"]),

    ("APA Autism Spectrum Disorder Guidelines", "APA/AAP", 2024,
     "ASD Behavioral and Pharmacologic Interventions",
     "Early intensive behavioral intervention (EIBI/ABA) is evidence-based for core ASD symptoms. Speech/language therapy for communication deficits. Occupational therapy for sensory and motor skills. Social skills training for school-age children. No FDA-approved medication for core ASD symptoms. Risperidone and aripiprazole FDA-approved for irritability/aggression in ASD. SSRIs for anxiety/repetitive behaviors. Melatonin for sleep disturbance.",
     "B", "Strong", ["autism spectrum disorder", "asd"], ["risperidone", "aripiprazole", "fluoxetine", "melatonin"], ["ados-2", "developmental assessment", "adaptive behavior scales"], ["autism", "asd", "aba therapy", "behavioral intervention"]),

    ("APA Eating Disorder Guidelines", "APA", 2024,
     "Anorexia Nervosa Treatment",
     "Medical stabilization priority: correct electrolytes (refeeding syndrome risk: phosphorus, magnesium, potassium), cardiac monitoring, nutritional rehabilitation (start low, advance slowly). Psychotherapy: FBT (family-based treatment/Maudsley) for adolescents (most evidence). CBT-E for adults. No FDA-approved medications; olanzapine may support weight restoration. Target weight: individualized (not BMI-based), restore menses. Higher level of care if: <75% IBW, unstable vitals, rapid weight loss, failed outpatient.",
     "A", "Strong", ["anorexia nervosa", "eating disorder"], ["olanzapine", "phosphorus supplement", "potassium supplement"], ["bmi", "phosphorus", "magnesium", "potassium", "ecg", "cbc", "cmp"], ["anorexia nervosa", "refeeding syndrome", "fbt", "weight restoration"]),

    # ══════════════════════════════════════════
    # ADDITIONAL HEMATOLOGY (~10)
    # ══════════════════════════════════════════
    ("ASH Thalassemia Guidelines", "ASH/TIF", 2024,
     "Beta-Thalassemia Management",
     "Thalassemia major: regular transfusions (target pre-transfusion Hb 9-10.5 g/dL) to suppress ineffective erythropoiesis. Iron chelation: deferasirox (oral, preferred), deferoxamine (SC/IV), deferiprone (oral, crosses BBB). Monitor: ferritin Q3 months, cardiac MRI T2* annually, liver iron concentration. Luspatercept for transfusion-dependent thal (reduces transfusion burden). Gene therapy (betibeglogene autotemcel/Zynteglo) for eligible patients. Allogeneic HSCT is potentially curative.",
     "A", "Strong", ["beta-thalassemia", "thalassemia major"], ["deferasirox", "deferoxamine", "luspatercept"], ["hemoglobin", "ferritin", "cardiac mri t2*", "liver iron concentration", "iron studies"], ["thalassemia", "iron chelation", "luspatercept", "gene therapy"]),

    ("ASH G6PD Deficiency Guidelines", "ASH", 2024,
     "G6PD Deficiency Management",
     "Avoid triggers: oxidant drugs (primaquine, dapsone, rasburicase, methylene blue, sulfonamides, nitrofurantoin), fava beans, mothballs (naphthalene). Acute hemolytic crisis: supportive care, transfusion for severe anemia (Hb <7), IV fluids, monitor renal function. G6PD enzyme assay may be falsely normal during acute crisis (young reticulocytes have higher activity); retest 2-3 months later. Screen before prescribing rasburicase or primaquine.",
     "B", "Strong", ["g6pd deficiency", "hemolytic anemia"], [], ["g6pd enzyme level", "reticulocyte count", "ldh", "haptoglobin", "coombs test", "peripheral blood smear"], ["g6pd", "hemolytic anemia", "oxidant drugs", "favism"]),

    ("ASH Autoimmune Hemolytic Anemia Guidelines", "ASH", 2024,
     "Warm AIHA Treatment",
     "First-line: prednisone 1 mg/kg/day (response in 80%, but relapse common on taper). Rituximab as second-line (or first-line with steroids in severe cases). Splenectomy: declining role, but option for refractory cases. Sutimlimab (anti-C1s complement inhibitor) for cold agglutinin disease. Avoid transfusion if possible (crossmatch difficult); transfuse for life-threatening anemia regardless. Folate supplementation. DAT (Coombs) for diagnosis. Rule out secondary causes (lymphoma, SLE, medications).",
     "B", "Strong", ["autoimmune hemolytic anemia", "warm aiha", "cold agglutinin disease"], ["prednisone", "rituximab", "sutimlimab", "folic acid"], ["direct antiglobulin test", "reticulocyte count", "ldh", "haptoglobin", "peripheral smear", "flow cytometry"], ["aiha", "coombs test", "rituximab", "warm antibody"]),

    # ══════════════════════════════════════════
    # GERIATRICS / AGING (~10)
    # ══════════════════════════════════════════
    ("AGS Beers Criteria", "AGS", 2024,
     "Potentially Inappropriate Medications in Older Adults",
     "Avoid: benzodiazepines (fall risk, cognitive impairment), first-generation antihistamines (anticholinergic), long-acting sulfonylureas (hypoglycemia), strong anticholinergics (cognitive decline), meperidine, non-COX selective NSAIDs with chronic use. Use caution: antipsychotics (increased mortality in dementia), PPIs >8 weeks (C. diff, fractures, hypomagnesemia), SSRIs (hyponatremia). Deprescribing: structured medication review, prioritize, taper when appropriate. Involve patient/caregiver in decisions.",
     "A", "Strong", ["polypharmacy", "medication safety in elderly"], [], ["medication reconciliation", "cognitive assessment", "fall risk assessment"], ["beers criteria", "polypharmacy", "deprescribing", "geriatric"]),

    ("AGS Dementia Management Guidelines", "AGS/AAN", 2024,
     "Dementia Non-Pharmacologic Interventions",
     "Non-pharmacologic approaches first for BPSD (behavioral and psychological symptoms of dementia): identify triggers, structured routine, caregiver education, music therapy, exercise, meaningful activities, environmental modification (lighting, noise reduction). Agitation: person-centered care, reduce pain, avoid confrontation. Pharmacologic only for severe agitation/psychosis causing danger: low-dose atypical antipsychotic (risperidone, brexpiprazole) short-term with informed consent. Avoid physical restraints.",
     "B", "Strong", ["dementia behavioral symptoms", "bpsd", "alzheimer behavioral management"], ["risperidone", "brexpiprazole", "acetaminophen"], ["moca", "npi", "cornell depression in dementia scale"], ["dementia", "bpsd", "non-pharmacologic", "caregiver"]),

    ("AGS Frailty Guidelines", "AGS", 2024,
     "Frailty Screening and Management",
     "Screen older adults for frailty: Fried frailty phenotype (≥3 of: unintentional weight loss, exhaustion, slow walking speed, weak grip strength, low physical activity). FRAIL scale for quick screening. Interventions: progressive resistance exercise (most evidence), nutritional supplementation (protein 1.0-1.2 g/kg/day), comprehensive geriatric assessment, medication review, social support. Pre-surgical frailty assessment improves outcomes. Frailty-adjusted treatment decisions for cancer, cardiac surgery.",
     "B", "Strong", ["frailty", "geriatric assessment"], ["vitamin d"], ["grip strength", "gait speed", "timed up and go", "bmi", "albumin"], ["frailty", "fried phenotype", "exercise", "geriatric assessment"]),

    ("AGS Urinary Incontinence Guidelines", "AGS/AUA", 2024,
     "Urinary Incontinence in Older Adults",
     "Classify: stress, urge, mixed, overflow, functional. First-line (all types): behavioral (pelvic floor exercises, bladder training, timed voiding, fluid management, weight loss). Stress: pelvic floor muscle training (Kegel), pessary, surgery (midurethral sling). Urge: behavioral + antimuscarinic or beta-3 agonist (prefer vibegron/mirabegron over antimuscarinics in elderly due to cognitive risk). OnabotulinumtoxinA for refractory urge. Assess for contributing medications and reversible causes.",
     "B", "Strong", ["urinary incontinence", "overactive bladder elderly"], ["mirabegron", "vibegron", "onabotulinumtoxinA"], ["postvoid residual", "urinalysis", "voiding diary", "urodynamics"], ["incontinence", "pelvic floor", "geriatric", "antimuscarinic"]),

    # ══════════════════════════════════════════
    # ADDITIONAL MISCELLANEOUS (~25)
    # ══════════════════════════════════════════
    ("AACE/ACE Lipid Management Guidelines", "AACE/ACC", 2024,
     "Advanced Lipid Management and PCSK9 Inhibitors",
     "Statin maximization first: atorvastatin 40-80 mg or rosuvastatin 20-40 mg. Add ezetimibe 10 mg if LDL above target. PCSK9 inhibitors (evolocumab, alirocumab) if LDL still above target on max statin + ezetimibe. Bempedoic acid (non-statin LDL lowering) for statin-intolerant. Inclisiran (siRNA) Q6 months injection for LDL lowering. Targets: extreme risk (ASCVD + DM/CKD/HeFH/recurrent events) LDL <55; very high risk LDL <70; high risk LDL <100. Icosapent ethyl for TG ≥135 with ASCVD.",
     "A", "Strong", ["dyslipidemia", "hypercholesterolemia"], ["atorvastatin", "rosuvastatin", "ezetimibe", "evolocumab", "alirocumab", "bempedoic acid", "inclisiran", "icosapent ethyl"], ["ldl", "total cholesterol", "triglycerides", "hdl", "apolipoprotein b", "lp(a)"], ["lipid management", "pcsk9", "statin", "ezetimibe"]),

    ("AHA/ACC Hypertension Guidelines", "AHA/ACC", 2024,
     "Resistant Hypertension Management",
     "Definition: BP above goal despite 3 medications (including diuretic) at optimal doses. Confirm: out-of-office BP monitoring (ABPM or HBPM) to exclude white coat effect. Address: adherence (most common cause), secondary causes (primary aldosteronism screen with ARR, renal artery stenosis, pheochromocytoma, OSA, CKD). Add spironolactone 25-50 mg (most evidence for 4th agent) or eplerenone 50-100 mg. Alternative 4th agents: bisoprolol, doxazosin, clonidine, minoxidil.",
     "A", "Strong", ["resistant hypertension"], ["spironolactone", "eplerenone", "chlorthalidone", "amlodipine", "lisinopril", "minoxidil"], ["blood pressure", "aldosterone-renin ratio", "renal artery duplex", "plasma metanephrines", "sleep study", "potassium"], ["resistant hypertension", "spironolactone", "secondary hypertension", "abpm"]),

    ("ACC/AHA Heart Failure Guidelines", "ACC/AHA", 2024,
     "HFrEF Quadruple Therapy",
     "Four pillars of GDMT for HFrEF (EF ≤40%): 1) ACEi/ARB/ARNI (sacubitril-valsartan preferred), 2) Beta-blocker (carvedilol, metoprolol succinate, or bisoprolol), 3) MRA (spironolactone or eplerenone), 4) SGLT2 inhibitor (dapagliflozin or empagliflozin). Initiate all four simultaneously or rapidly sequentially (within 4-6 weeks). Up-titrate to target doses. Hydralazine-isosorbide dinitrate for self-identified Black patients. IV iron (ferric carboxymaltose) for iron deficiency (ferritin <100 or TSAT <20%).",
     "A", "Strong", ["hfref", "heart failure reduced ejection fraction"], ["sacubitril-valsartan", "carvedilol", "spironolactone", "dapagliflozin", "empagliflozin", "ferric carboxymaltose"], ["ejection fraction", "bnp", "nt-probnp", "ferritin", "tsat", "potassium", "creatinine"], ["hfref", "gdmt", "sglt2", "arni", "quadruple therapy"]),

    ("ACC/AHA Heart Failure Guidelines", "ACC/AHA", 2024,
     "HFpEF Management",
     "SGLT2 inhibitor (empagliflozin — EMPEROR-Preserved; dapagliflozin — DELIVER) for ALL HFpEF. Diuretics for congestion. BP control. Weight management (semaglutide shown to improve HF symptoms in obese HFpEF per STEP-HFpEF). Treat underlying comorbidities: AF, CAD, DM, OSA, anemia. MRA (spironolactone) may reduce hospitalizations. Finerenone for HFpEF with CKD and T2DM. Exercise training improves functional capacity. No clear role for ACEi/ARB/ARNI in HFpEF.",
     "A", "Strong", ["hfpef", "heart failure preserved ejection fraction"], ["empagliflozin", "dapagliflozin", "spironolactone", "semaglutide", "furosemide"], ["ejection fraction", "bnp", "nt-probnp", "e/e prime ratio", "bmi"], ["hfpef", "sglt2", "preserved ejection fraction", "diastolic"]),

    ("ADA Diabetes Technology Guidelines", "ADA", 2025,
     "Continuous Glucose Monitoring and Insulin Pump Therapy",
     "CGM recommended for all patients on intensive insulin therapy (MDI or pump). Real-time CGM (Dexcom G7, Libre 3) improves A1c and reduces hypoglycemia. Time in range (70-180 mg/dL) >70% as target. Insulin pump therapy (CSII) for T1DM or selected T2DM on intensive insulin. Automated insulin delivery (AID) / hybrid closed-loop systems (Tandem Control-IQ, Omnipod 5, Medtronic 780G) further improve glycemic outcomes. CGM for T2DM on basal insulin: intermittently scanned or real-time.",
     "A", "Strong", ["diabetes technology", "insulin delivery systems"], ["insulin lispro", "insulin aspart", "insulin glargine"], ["cgm time in range", "gmi", "hba1c", "hypoglycemia frequency"], ["cgm", "insulin pump", "automated insulin delivery", "time in range"]),

    ("ADA Type 2 Diabetes Treatment Guidelines", "ADA", 2025,
     "T2DM Glucose-Lowering Algorithm",
     "First-line: metformin + lifestyle modifications. If established ASCVD or high risk: add GLP-1 RA (semaglutide, dulaglutide, liraglutide) or SGLT2i regardless of A1c. If HF or CKD: add SGLT2i. If additional A1c lowering needed: GLP-1 RA, SGLT2i, DPP-4i, TZD, sulfonylurea, or insulin. Tirzepatide (dual GIP/GLP-1) for additional A1c lowering and weight loss. Insulin: basal first (glargine, degludec), add prandial or switch to premix if needed. De-intensify in older adults if at risk for hypoglycemia.",
     "A", "Strong", ["type 2 diabetes", "diabetes treatment algorithm"], ["metformin", "semaglutide", "empagliflozin", "tirzepatide", "insulin glargine", "dulaglutide"], ["hba1c", "fasting glucose", "egfr", "uacr"], ["t2dm", "metformin", "glp-1", "sglt2", "algorithm"]),

    ("ACR Low Back Pain Imaging Guidelines", "ACR/ACP", 2024,
     "Low Back Pain Red Flags and Evaluation",
     "Red flags requiring urgent evaluation: cauda equina syndrome (saddle anesthesia, bilateral LE weakness, urinary retention/incontinence), progressive neurologic deficit, suspected spinal infection (fever, IV drug use, immunosuppression), suspected malignancy (history of cancer, unexplained weight loss, age >50 with new severe pain). Cauda equina: emergent MRI and surgical consultation. Cancer: MRI with contrast. Infection: MRI with contrast + blood cultures + ESR/CRP.",
     "A", "Strong", ["low back pain red flags", "cauda equina syndrome"], [], ["mri lumbar spine", "esr", "crp", "blood cultures", "psa"], ["back pain", "red flags", "cauda equina", "emergent mri"]),

    ("ACOG Group B Streptococcus Guidelines", "ACOG/CDC", 2024,
     "GBS Screening and Intrapartum Prophylaxis",
     "Universal GBS screening: vaginal-rectal swab at 36-37 weeks. Intrapartum antibiotic prophylaxis (IAP) for: positive GBS screen, GBS bacteriuria during pregnancy, prior infant with GBS disease, unknown GBS status with risk factors (preterm <37 weeks, ROM ≥18 hours, intrapartum fever ≥38°C). Penicillin G first-line (5 million units IV then 2.5-3 million Q4h). Ampicillin alternative. Penicillin allergy: cefazolin (low risk), clindamycin (if susceptible), or vancomycin.",
     "A", "Strong", ["group b streptococcus", "gbs in pregnancy"], ["penicillin g", "ampicillin", "cefazolin", "clindamycin", "vancomycin"], ["gbs vaginal-rectal culture", "urine culture"], ["gbs", "intrapartum prophylaxis", "penicillin", "neonatal sepsis prevention"]),

    ("WHO Breastfeeding Guidelines", "WHO/AAP", 2024,
     "Breastfeeding Recommendations and Support",
     "Exclusive breastfeeding for first 6 months. Continue breastfeeding with complementary foods until at least 12 months (AAP) or 24 months (WHO). Initiate within 1 hour of birth. Skin-to-skin contact. Lactation consultant referral for difficulties. Contraindications: HIV in resource-rich settings (formula safer), active TB (until treated 2 weeks), galactosemia, certain medications (chemotherapy, radioactive isotopes). Common challenges: insufficient supply, latch difficulties, mastitis (antibiotic if not improving with conservative measures).",
     "A", "Strong", ["breastfeeding", "lactation"], [], [], ["breastfeeding", "lactation", "exclusive breastfeeding", "newborn"]),

    ("AAP Newborn Screening", "AAP/ACMG", 2024,
     "Recommended Uniform Screening Panel",
     "All newborns screened within 24-48 hours of birth via dried blood spot (heel stick). Core conditions include: PKU, congenital hypothyroidism, sickle cell disease, cystic fibrosis, galactosemia, CAH, biotinidase deficiency, MCAD, critical congenital heart disease (pulse oximetry), hearing loss (OAE/ABR). Repeat screening at 1-2 weeks for early discharge. Abnormal screen: confirmatory testing and subspecialty referral. Early detection enables treatment before irreversible damage.",
     "A", "Strong", ["newborn screening", "inborn errors of metabolism"], ["levothyroxine", "phenylalanine-restricted diet"], ["newborn screening panel", "tsh", "hemoglobin electrophoresis", "immunoreactive trypsinogen", "pulse oximetry", "hearing screen"], ["newborn screening", "rusp", "pku", "congenital hypothyroidism"]),

    ("AHA BLS/ACLS Guidelines", "AHA", 2024,
     "Adult Basic and Advanced Life Support",
     "BLS: CAB sequence (Compressions, Airway, Breathing). High-quality CPR: rate 100-120/min, depth 2-2.4 inches, full chest recoil, minimize interruptions. AED as soon as available. ACLS: shockable (VF/pVT) — defibrillation + epinephrine Q3-5min + amiodarone (300mg then 150mg). Non-shockable (PEA/asystole) — epinephrine Q3-5min + identify reversible causes (Hs and Ts). Post-ROSC: targeted temperature management, coronary angiography if STEMI, avoid hyperoxia, hemodynamic optimization.",
     "A", "Strong", ["cardiac arrest", "cardiopulmonary resuscitation"], ["epinephrine", "amiodarone", "lidocaine"], ["ecg", "etco2", "arterial blood gas"], ["acls", "cpr", "defibrillation", "cardiac arrest"]),

    ("AAFP Chronic Disease Management", "AAFP/ACP", 2024,
     "Multimorbidity Management in Primary Care",
     "Patient-centered approach: prioritize based on patient's goals and functional impact. Minimize treatment burden: simplify regimens, reduce polypharmacy. Regular medication reconciliation. Address interactions between conditions and treatments. Shared decision-making with realistic expectations. Care coordination across specialists. Advance care planning. Address social determinants of health. Depression screening (common comorbidity). Exercise prescription tailored to limitations. Caregiver support.",
     "B", "Moderate", ["multimorbidity", "chronic disease management"], [], ["medication list review", "functional assessment", "phq-9"], ["multimorbidity", "polypharmacy", "primary care", "care coordination"]),

    ("WHO Palliative Sedation Guidelines", "WHO/EAPC", 2024,
     "Palliative Sedation for Refractory Symptoms",
     "Indication: truly refractory symptoms at end of life (pain, dyspnea, delirium, seizures) where all other interventions have failed. Informed consent from patient/surrogate. Proportional sedation first (lowest effective level). Medications: midazolam infusion (most common), propofol, phenobarbital. Monitor comfort level (RASS). Maintain comfort-focused symptom management. Not euthanasia — intent is symptom relief, not hastening death. Ethics consultation recommended. Continue comfort medications (opioids for pain/dyspnea).",
     "B", "Moderate", ["palliative sedation", "refractory symptoms", "end-of-life"], ["midazolam", "propofol", "phenobarbital", "morphine"], ["rass score", "comfort assessment"], ["palliative sedation", "refractory symptoms", "end of life", "midazolam"]),

    ("ACC/AHA Cardiac Amyloidosis Guidelines", "ACC/AHA", 2024,
     "Cardiac Amyloidosis Diagnosis and Treatment",
     "Suspect in HFpEF with LVH, low voltage on ECG, elevated troponin/BNP. Diagnosis: technetium pyrophosphate (PYP) scan for ATTR (grade 2-3 = positive without monoclonal protein). Biopsy with Congo red staining for AL. AL amyloidosis: hematology referral, chemo (daratumumab-CyBorD). ATTR amyloidosis: tafamidis 80 mg (stabilizer, reduces mortality and hospitalization per ATTR-ACT). Patisiran/vutrisiran (RNA silencers) for hereditary ATTR with polyneuropathy. Avoid digoxin and CCBs.",
     "A", "Strong", ["cardiac amyloidosis", "attr amyloidosis", "al amyloidosis"], ["tafamidis", "patisiran", "vutrisiran", "daratumumab"], ["pyp scan", "echocardiogram", "cardiac mri", "serum free light chains", "spep", "upep", "troponin", "bnp"], ["cardiac amyloidosis", "tafamidis", "pyp scan", "attr"]),

    ("ISHLT Heart Transplant Guidelines", "ISHLT", 2024,
     "Heart Transplant Evaluation and Management",
     "Indications: end-stage HF refractory to optimal medical/device therapy, peak VO2 <14 mL/kg/min (or <12 with beta-blocker), INTERMACS profile 1-4. Evaluation: comprehensive including RHC (PVR <5 Wood units), psychosocial, cancer screening, infectious disease workup. Post-transplant: triple immunosuppression (tacrolimus, mycophenolate, prednisone). Surveillance endomyocardial biopsy for rejection. CMV/EBV prophylaxis. Annual coronary angiography + IVUS for cardiac allograft vasculopathy.",
     "A", "Strong", ["heart transplant", "advanced heart failure"], ["tacrolimus", "mycophenolate", "prednisone", "valganciclovir"], ["right heart catheterization", "echocardiogram", "endomyocardial biopsy", "vo2 max", "coronary angiography"], ["heart transplant", "immunosuppression", "rejection", "cardiac allograft vasculopathy"]),

    ("AAN/AAN Status Epilepticus Guidelines", "AAN/AES", 2024,
     "Status Epilepticus Treatment Algorithm",
     "Stabilize (ABCs) and give benzodiazepine immediately: lorazepam 4 mg IV or midazolam 10 mg IM (if no IV access). Can repeat once. If seizure continues at 5-10 min (established SE): IV fosphenytoin 20 mg PE/kg, or levetiracetam 60 mg/kg (max 4500 mg), or valproate 40 mg/kg. Refractory SE (seizure at 30 min): continuous IV anesthesia (midazolam, propofol, or pentobarbital) with continuous EEG monitoring. ICU admission. Identify and treat underlying cause (infection, metabolic, structural, drug withdrawal).",
     "A", "Strong", ["status epilepticus", "prolonged seizure"], ["lorazepam", "midazolam", "fosphenytoin", "levetiracetam", "valproate", "propofol"], ["eeg", "glucose", "electrolytes", "ct head", "toxicology screen", "lumbar puncture"], ["status epilepticus", "benzodiazepine", "fosphenytoin", "refractory"]),

    ("ASGE Colonoscopy Quality Guidelines", "ASGE/ACG", 2024,
     "Colonoscopy Quality Metrics",
     "Key quality indicators: adenoma detection rate (ADR) ≥25% (target ≥30%). Cecal intubation rate ≥95%. Withdrawal time ≥6 minutes. Boston Bowel Preparation Scale ≥6 for adequate prep. Appropriate surveillance intervals: low-risk adenoma (1-2 tubular <10mm) → 7-10 years; high-risk (≥3 adenomas, ≥10mm, villous, HGD) → 3 years; sessile serrated polyps ≥10mm or with dysplasia → 3 years. Post-polypectomy bleeding rate <1%. Perforation rate <1:1000.",
     "A", "Strong", ["colonoscopy quality", "colon polyp surveillance"], [], ["colonoscopy", "adr", "cecal intubation rate", "boston bowel prep scale"], ["colonoscopy quality", "adr", "surveillance intervals", "polyp"]),

    ("ASN Chronic Kidney Disease Guidelines", "ASN/KDIGO", 2024,
     "CKD Classification and Monitoring",
     "Stage by eGFR (CKD-EPI 2021, race-free): G1 ≥90, G2 60-89, G3a 45-59, G3b 30-44, G4 15-29, G5 <15. Albuminuria: A1 <30, A2 30-300, A3 >300 mg/g. Monitor eGFR and UACR at least annually. Progress to quarterly monitoring for G4-G5. Nephrology referral: eGFR <30, rapid decline (>5 mL/min/year), persistent significant albuminuria (A3), unclear etiology. Begin dialysis preparation (access, education) at G4. Kidney transplant referral at eGFR <20.",
     "A", "Strong", ["chronic kidney disease", "ckd staging"], [], ["egfr", "uacr", "creatinine", "cystatin c", "bmp"], ["ckd", "egfr", "albuminuria", "kdigo staging"]),

    ("ASH Venous Thromboembolism Prevention", "ASH", 2024,
     "Medical Patient VTE Prophylaxis",
     "Risk-assess all hospitalized medical patients. IMPROVE or Padua score for risk stratification. High risk (acutely ill, reduced mobility, active cancer, prior VTE): LMWH (enoxaparin 40 mg SC daily) or UFH (5000 units SC Q8-12h) or fondaparinux. Duration: hospital stay only (extended prophylaxis with rivaroxaban 10 mg for selected high-risk patients per MARINER/MICHELLE). Mechanical prophylaxis (IPC) if anticoagulation contraindicated. COVID-19 hospitalized: prophylactic dose preferred.",
     "A", "Strong", ["vte prophylaxis medical", "hospital-acquired vte"], ["enoxaparin", "heparin", "fondaparinux", "rivaroxaban"], ["padua score", "improve score", "creatinine", "platelet count"], ["vte prophylaxis", "medical patients", "enoxaparin", "padua"]),

    ("IDSA COVID-19 Treatment Guidelines", "NIH/IDSA", 2024,
     "COVID-19 Outpatient and Inpatient Treatment",
     "Outpatient high-risk: nirmatrelvir-ritonavir (Paxlovid) within 5 days of symptom onset (first-line). Remdesivir 3-day IV course if oral not possible. Inpatient mild-moderate: remdesivir. Inpatient severe (O2 required): remdesivir + dexamethasone 6 mg/day x 10 days. Critical (mechanical ventilation): dexamethasone ± remdesivir; add tocilizumab or baricitinib for progressive disease. Avoid nirmatrelvir-ritonavir drug interactions (ritonavir is potent CYP3A4 inhibitor).",
     "A", "Strong", ["covid-19", "sars-cov-2"], ["nirmatrelvir-ritonavir", "remdesivir", "dexamethasone", "tocilizumab", "baricitinib"], ["sars-cov-2 pcr", "oxygen saturation", "crp", "d-dimer", "ferritin", "il-6", "ct chest"], ["covid-19", "paxlovid", "remdesivir", "dexamethasone"]),

    ("AGS Pain Management in Older Adults", "AGS/APS", 2024,
     "Chronic Pain in Elderly Patients",
     "Non-pharmacologic first: exercise, physical therapy, CBT, tai chi, heat/cold, TENS. Topical agents preferred: diclofenac gel, lidocaine patch, capsaicin. Oral: acetaminophen (max 2g/day for frail elderly). Duloxetine or gabapentin for neuropathic. Avoid NSAIDs if possible (GI, renal, CV risk). Opioids: lowest effective dose, short-acting, start 25-50% of adult dose, monitor closely. Tramadol: caution (seizure risk, serotonin syndrome). Interventional: joint injections, nerve blocks. Regular reassessment with functional outcome measures.",
     "B", "Strong", ["chronic pain in elderly", "geriatric pain management"], ["acetaminophen", "diclofenac topical", "lidocaine patch", "duloxetine", "gabapentin"], ["pain score", "functional assessment", "egfr", "gfr"], ["geriatric pain", "topical analgesic", "non-pharmacologic", "opioid risk"]),
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
    print(f"Batch 8: added {added} sections (total now {total})")


if __name__ == "__main__":
    main()
