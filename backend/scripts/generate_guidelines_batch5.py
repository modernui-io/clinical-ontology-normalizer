#!/usr/bin/env python3
"""Batch 5: Large batch with improved ID generation to reach ~800+ sections.

Covers: Additional sub-specialty topics, screening guidelines, perioperative medicine,
transplant medicine, adolescent medicine, sports medicine, wound care, and more.
"""

import json, os, re, hashlib

GUIDELINES = [
    # ── PERIOPERATIVE MEDICINE ──
    ("ACC/AHA Perioperative Cardiovascular Evaluation", "ACC/AHA", 2024, [
        ("Preoperative Cardiac Risk Assessment", "Use Revised Cardiac Risk Index (RCRI) for risk stratification. Functional capacity ≥4 METs: proceed to surgery. Low risk (<1% MACE): no further testing. Elevated risk with poor functional capacity: pharmacologic stress testing if result will change management. Continue beta-blockers if already on them; do not start de novo for surgery.", "A", "Strong",
         ["preoperative evaluation", "cardiac risk assessment", "non-cardiac surgery"], ["metoprolol", "atenolol"], ["ecg", "stress test", "bnp", "creatinine"], ["preoperative", "rcri", "cardiac risk", "stress testing"]),
        ("Perioperative Anticoagulation Management", "Bridge anticoagulation with LMWH for mechanical valves or high-risk AF (CHA2DS2-VASc ≥7). No bridging for most AF patients on DOACs—hold 2-3 days preop. Resume anticoagulation 24-72 hours postop based on bleeding risk. DOACs preferred over warfarin for AF patients resuming therapy. Neuraxial anesthesia timing considerations.", "A", "Strong",
         ["perioperative anticoagulation", "bridging therapy"], ["enoxaparin", "warfarin", "apixaban", "rivaroxaban", "heparin"], ["inr", "creatinine clearance", "aptt"], ["perioperative", "bridging", "anticoagulation", "doac"]),
    ]),
    ("ASA Perioperative Blood Management", "ASA", 2024, [
        ("Transfusion Thresholds", "Restrictive transfusion strategy: Hb trigger 7 g/dL for stable non-cardiac surgery patients. Hb 8 g/dL for cardiac surgery and ACS. Single-unit transfusion with reassessment. Tranexamic acid for major surgery to reduce bleeding. Cell salvage for major orthopedic and cardiac surgery. Patient blood management program recommended.", "A", "Strong",
         ["blood transfusion", "perioperative bleeding", "anemia"], ["tranexamic acid", "iron sucrose", "epoetin alfa", "packed rbc"], ["hemoglobin", "hematocrit", "coagulation studies", "type and screen"], ["transfusion", "restrictive", "tranexamic acid", "blood management"]),
    ]),
    ("ASA Preoperative Fasting", "ASA", 2024, [
        ("NPO Guidelines", "Clear liquids up to 2 hours before elective surgery. Light meal 6 hours before. Full meal or fatty/fried foods 8 hours before. Carbohydrate-rich clear drinks 2-3 hours preop improve patient experience and reduce insulin resistance. Breast milk 4 hours, formula 6 hours for infants.", "A", "Strong",
         ["preoperative fasting", "npo guidelines", "aspiration risk"], [], [], ["npo", "fasting", "preoperative", "clear liquids"]),
    ]),

    # ── ADDITIONAL SCREENING GUIDELINES ──
    ("USPSTF Breast Cancer Screening", "USPSTF", 2024, [
        ("Mammography Screening", "Biennial mammography for average-risk women aged 40-74. Consider starting at age 40 based on individual risk assessment. Screening mammography reduces breast cancer mortality by 20-30%. Supplemental MRI for women with lifetime risk ≥20%. Breast density notification and shared decision-making for additional screening.", "B", "Strong",
         ["breast cancer screening", "mammography"], [], ["mammogram", "breast mri", "breast density"], ["mammography", "breast cancer screening", "uspstf", "dense breasts"]),
    ]),
    ("USPSTF Osteoporosis Screening", "USPSTF", 2024, [
        ("Bone Density Screening", "DEXA screening for all women ≥65 and younger postmenopausal women with increased fracture risk (FRAX ≥9.3% 10-year hip fracture risk). Insufficient evidence for men. Repeat DEXA every 2-5 years based on T-score. Treatment threshold: T-score ≤-2.5 or FRAX ≥20% major osteoporotic fracture.", "B", "Strong",
         ["osteoporosis screening", "bone density"], [], ["dexa scan", "t-score", "frax"], ["osteoporosis screening", "dexa", "frax", "bone density"]),
    ]),
    ("USPSTF Hepatitis C Screening", "USPSTF", 2024, [
        ("HCV Universal Screening", "Screen all adults aged 18-79 at least once. One-time screening with anti-HCV antibody. Confirm reactive results with HCV RNA. Linkage to treatment: pan-genotypic DAA regimens cure >95%. Screen pregnant women during each pregnancy. No repeat screening needed for low-risk if previously negative.", "A", "Strong",
         ["hepatitis c screening", "hcv screening"], [], ["anti-hcv antibody", "hcv rna", "alt"], ["hepatitis c", "screening", "universal", "uspstf"]),
    ]),
    ("USPSTF HIV Screening", "USPSTF", 2024, [
        ("HIV Universal Screening", "Screen all adults and adolescents aged 15-65 at least once. Screen younger/older if at increased risk. Fourth-generation Ag/Ab combination test preferred. Repeat screening annually for high-risk individuals. Opt-out screening in all healthcare settings. Immediate linkage to ART for positive results.", "A", "Strong",
         ["hiv screening", "hiv testing"], [], ["hiv ag/ab combo test", "hiv rna", "cd4 count"], ["hiv screening", "universal", "fourth generation", "opt-out"]),
    ]),
    ("USPSTF Colorectal Cancer Screening", "USPSTF", 2024, [
        ("CRC Screening Methods", "Begin screening at age 45 for average-risk adults. Continue through age 75. Colonoscopy every 10 years, FIT annually, FIT-DNA every 1-3 years, CT colonography every 5 years, flexible sigmoidoscopy every 5-10 years. Positive non-invasive tests require colonoscopy follow-up. Earlier screening for family history.", "A", "Strong",
         ["colorectal cancer screening", "colon cancer screening"], [], ["colonoscopy", "fit test", "cologuard", "ct colonography"], ["colorectal screening", "colonoscopy", "fit", "cologuard"]),
    ]),
    ("ACS Prostate Cancer Screening", "ACS", 2024, [
        ("PSA Screening", "Shared decision-making starting at age 50 for average-risk men. Age 45 for high-risk (Black men, first-degree relative with prostate cancer <65). Age 40 for very high risk (multiple first-degree relatives). If PSA <2.5: repeat every 2 years. If ≥2.5: annual testing. Consider mpMRI before biopsy for elevated PSA.", "B", "Moderate",
         ["prostate cancer screening", "psa screening"], [], ["psa", "dre", "mpmri", "prostate biopsy"], ["prostate screening", "psa", "shared decision", "mpmri"]),
    ]),

    # ── TRANSPLANT MEDICINE ──
    ("AASLD Liver Transplant", "AASLD", 2024, [
        ("Liver Transplant Evaluation", "Indicated for decompensated cirrhosis (MELD ≥15), HCC within Milan criteria, acute liver failure, and select metabolic diseases. Evaluate: cardiac clearance, psychosocial assessment, substance use history (6 months abstinence for ALD). Living donor liver transplant as alternative. Post-transplant immunosuppression: tacrolimus, mycophenolate, corticosteroids.", "A", "Strong",
         ["liver transplant", "decompensated cirrhosis", "hepatocellular carcinoma"], ["tacrolimus", "mycophenolate", "prednisone", "basiliximab", "everolimus"], ["meld score", "afp", "ct abdomen", "echocardiogram"], ["liver transplant", "meld", "immunosuppression", "milan criteria"]),
    ]),
    ("ATS/ISHLT Lung Transplant", "ATS/ISHLT", 2024, [
        ("Lung Transplant Guidelines", "Consider referral for progressive lung disease despite optimal therapy: FVC <80% and declining in IPF, FEV1 <25% in COPD, CF with FEV1 <30%. Bilateral transplant preferred. Immunosuppression: tacrolimus, mycophenolate, corticosteroids. Monitor for chronic lung allograft dysfunction (CLAD). Surveillance bronchoscopy with transbronchial biopsy.", "A", "Strong",
         ["lung transplant", "end-stage lung disease", "pulmonary fibrosis", "copd"], ["tacrolimus", "mycophenolate", "prednisone", "azithromycin"], ["fev1", "fvc", "6-minute walk test", "ct chest"], ["lung transplant", "clad", "rejection", "bronchoscopy"]),
    ]),

    # ── SPORTS MEDICINE ──
    ("NCAA/AAN Concussion in Sport", "NCAA/AAN", 2024, [
        ("Sport-Related Concussion", "Remove from play immediately if concussion suspected. No same-day return to play. Graduated return-to-play protocol over minimum 6 days. Physical and cognitive rest for 24-48 hours, then gradual symptom-limited activity. Neuropsychological testing for baseline comparison. Emergency evaluation for red flags: seizure, worsening headache, repeated vomiting, prolonged LOC.", "A", "Strong",
         ["concussion", "sport-related concussion", "mild tbi"], ["acetaminophen"], ["scat5", "neuropsychological testing", "ct head"], ["concussion", "return to play", "graduated protocol", "sport"]),
    ]),
    ("ACSM Exercise Prescription", "ACSM", 2024, [
        ("Exercise for Chronic Disease", "150 minutes/week moderate-intensity or 75 minutes vigorous aerobic activity. Resistance training 2-3 days/week. Flexibility and neuromotor exercises. Exercise prescription for diabetes: improves A1c by 0.5-0.7%. Heart failure: cardiac rehabilitation improves functional capacity. COPD: pulmonary rehabilitation reduces exacerbations. Cancer survivors: exercise reduces fatigue and recurrence.", "A", "Strong",
         ["exercise prescription", "physical activity", "chronic disease"], [], ["vo2 max", "heart rate", "blood pressure", "hba1c"], ["exercise", "physical activity", "cardiac rehabilitation", "chronic disease"]),
    ]),

    # ── WOUND CARE ──
    ("WHS Chronic Wound Management", "WHS", 2024, [
        ("Pressure Injury Prevention and Treatment", "Braden Scale for risk assessment. Repositioning every 2 hours for bed-bound patients. Pressure-redistribution mattress for at-risk patients. Stage I-II: moisture management, barrier creams, foam dressings. Stage III-IV: debridement, negative pressure wound therapy, skin substitutes. Nutritional optimization: protein 1.25-1.5 g/kg/day.", "A", "Strong",
         ["pressure injury", "pressure ulcer", "decubitus ulcer"], [], ["braden scale", "wound dimensions", "albumin", "prealbumin"], ["pressure injury", "prevention", "repositioning", "wound care"]),
        ("Venous Leg Ulcer Management", "Compression therapy (30-40 mmHg) as cornerstone treatment. Multilayer compression bandaging or stockings. Pentoxifylline as adjunct to compression. Wound bed preparation: debridement, moisture balance, infection control. Duplex ultrasound to assess venous reflux. Skin grafting for refractory ulcers >6 months.", "A", "Strong",
         ["venous leg ulcer", "venous insufficiency", "chronic wound"], ["pentoxifylline"], ["duplex ultrasound", "abi", "wound culture"], ["venous ulcer", "compression therapy", "wound healing"]),
    ]),

    # ── ADDITIONAL NEPHROLOGY ──
    ("KDIGO CKD General Management", "KDIGO", 2024, [
        ("CKD Progression Slowing", "SGLT2 inhibitors for CKD with eGFR 20-90 and albuminuria (regardless of diabetes). ACEi or ARB titrated to maximum tolerated dose for proteinuric CKD. Blood pressure target <120/80 for CKD. Finerenone for DKD. Avoid NSAIDs. Dietary sodium restriction <2g/day. Protein intake 0.8 g/kg/day for non-dialysis CKD.", "A", "Strong",
         ["chronic kidney disease", "ckd", "ckd progression"], ["dapagliflozin", "empagliflozin", "lisinopril", "losartan", "finerenone"], ["egfr", "uacr", "creatinine", "blood pressure", "potassium"], ["ckd", "sglt2", "ras blockade", "progression"]),
        ("CKD Anemia Management", "Iron supplementation first: target ferritin >100 ng/mL (>200 for dialysis), TSAT >20%. ESAs (epoetin, darbepoetin) for Hb <10 g/dL after iron repletion. Target Hb 10-11.5 g/dL, avoid exceeding 13 g/dL. HIF-PHI (roxadustat, daprodustat) as oral alternatives to ESAs. IV iron preferred for hemodialysis patients.", "A", "Strong",
         ["ckd anemia", "renal anemia", "chronic kidney disease"], ["ferric carboxymaltose", "iron sucrose", "epoetin alfa", "darbepoetin", "roxadustat"], ["hemoglobin", "ferritin", "tsat", "reticulocyte count"], ["ckd anemia", "esa", "iron", "hif-phi"]),
    ]),
    ("KDIGO Hypertension in CKD", "KDIGO", 2024, [
        ("BP Management in CKD", "Target SBP <120 mmHg by standardized office BP measurement. ACEi or ARB as first-line for CKD with albuminuria. Add CCB or diuretic as second agent. Thiazide-like diuretics for eGFR ≥30; loop diuretics for <30. Avoid dual RAS blockade. Monitor potassium and creatinine after ACEi/ARB initiation.", "A", "Strong",
         ["hypertension in ckd", "chronic kidney disease", "renal hypertension"], ["lisinopril", "losartan", "amlodipine", "chlorthalidone", "furosemide"], ["blood pressure", "egfr", "potassium", "creatinine", "uacr"], ["ckd hypertension", "ras blockade", "bp target", "diuretic"]),
    ]),

    # ── ADDITIONAL GI ──
    ("ACG Functional Dyspepsia", "ACG", 2024, [
        ("Functional Dyspepsia Treatment", "H. pylori test and treat as initial strategy. PPI trial for 4-8 weeks. Tricyclic antidepressants (amitriptyline 10-25mg) for PPI non-responders. Prokinetics (metoclopramide) for postprandial distress syndrome. Psychological therapies (CBT, hypnotherapy). Avoid chronic PPI use without indication. EGD for alarm features: weight loss, dysphagia, anemia, age >60 with new symptoms.", "B", "Strong",
         ["functional dyspepsia", "dyspepsia", "indigestion"], ["omeprazole", "amitriptyline", "metoclopramide"], ["h pylori test", "upper endoscopy", "cbc"], ["functional dyspepsia", "ppi", "tca", "h pylori"]),
    ]),
    ("ACG Microscopic Colitis", "ACG", 2024, [
        ("Microscopic Colitis Treatment", "Budesonide 9mg daily for 6-8 weeks as first-line induction. Taper over 2-3 months. Maintenance budesonide 3-6mg for relapsing disease. Cholestyramine as adjunct for bile acid malabsorption. Bismuth subsalicylate for mild cases. Immunomodulators (azathioprine, methotrexate) for budesonide-dependent or refractory. Biologics (vedolizumab) for refractory cases.", "A", "Strong",
         ["microscopic colitis", "collagenous colitis", "lymphocytic colitis"], ["budesonide", "cholestyramine", "bismuth", "azathioprine", "vedolizumab"], ["colonoscopy with biopsy", "stool studies"], ["microscopic colitis", "budesonide", "collagenous", "lymphocytic"]),
    ]),

    # ── ADDITIONAL HEMATOLOGY ──
    ("ASH TTP Guidelines", "ASH", 2024, [
        ("Thrombotic Thrombocytopenic Purpura", "Therapeutic plasma exchange (TPE) within 4-8 hours of diagnosis. Caplacizumab (anti-vWF nanobody) plus TPE and immunosuppression. Corticosteroids and rituximab for immune TTP. ADAMTS13 activity <10% confirms diagnosis. Monitor ADAMTS13 for relapse prediction. Avoid platelet transfusion unless life-threatening bleeding.", "A", "Strong",
         ["thrombotic thrombocytopenic purpura", "ttp", "thrombotic microangiopathy"], ["caplacizumab", "rituximab", "prednisone", "plasma exchange"], ["adamts13", "ldh", "haptoglobin", "peripheral smear", "platelet count"], ["ttp", "plasma exchange", "caplacizumab", "adamts13"]),
    ]),
    ("ASH Myeloproliferative Neoplasms", "ASH", 2024, [
        ("Polycythemia Vera", "Phlebotomy to maintain hematocrit <45%. Low-dose aspirin for all PV patients. Hydroxyurea as first-line cytoreduction for high-risk PV (age ≥60 or prior thrombosis). Ruxolitinib for hydroxyurea-resistant or intolerant PV. Ropeginterferon alfa-2b as alternative first-line. JAK2 V617F mutation in >95% of PV.", "A", "Strong",
         ["polycythemia vera", "pv", "myeloproliferative neoplasm"], ["hydroxyurea", "aspirin", "ruxolitinib", "ropeginterferon"], ["hematocrit", "jak2", "cbc", "erythropoietin level"], ["polycythemia vera", "phlebotomy", "jak2", "hydroxyurea"]),
        ("Essential Thrombocythemia", "Low-dose aspirin for all ET patients. Cytoreduction for high-risk: hydroxyurea first-line, anagrelide as alternative. Ropeginterferon alfa-2b for younger patients. Target platelet count <400K for high-risk. JAK2, CALR, and MPL mutation testing. Risk stratification with IPSET-T score.", "A", "Strong",
         ["essential thrombocythemia", "et", "myeloproliferative neoplasm"], ["aspirin", "hydroxyurea", "anagrelide", "ropeginterferon"], ["platelet count", "jak2", "calr", "mpl", "bone marrow biopsy"], ["essential thrombocythemia", "hydroxyurea", "calr", "ipset"]),
        ("Myelofibrosis", "Ruxolitinib as first-line for symptomatic intermediate-2 or high-risk myelofibrosis. Pacritinib for platelet count <50K. Momelotinib for anemia-predominant MF. Allogeneic stem cell transplant for eligible intermediate-2 and high-risk patients. DIPSS-Plus for risk stratification. Luspatercept or danazol for MF-associated anemia.", "A", "Strong",
         ["myelofibrosis", "mf", "myeloproliferative neoplasm"], ["ruxolitinib", "pacritinib", "momelotinib", "danazol", "luspatercept"], ["cbc", "bone marrow biopsy", "jak2", "calr", "spleen size"], ["myelofibrosis", "ruxolitinib", "jak inhibitor", "transplant"]),
    ]),

    # ── ADDITIONAL PSYCHIATRY ──
    ("APA Autism Spectrum Disorder", "APA", 2024, [
        ("ASD Assessment and Intervention", "M-CHAT-R/F screening at 18 and 24 months. Comprehensive diagnostic evaluation with validated instruments (ADOS-2, ADI-R). Early intensive behavioral intervention (ABA-based) for children <5 years. Speech-language therapy for communication deficits. Social skills training for school-age children. Risperidone or aripiprazole for severe irritability/aggression.", "A", "Strong",
         ["autism spectrum disorder", "asd", "autism"], ["risperidone", "aripiprazole"], ["m-chat", "ados-2"], ["autism", "asd", "early intervention", "behavioral"]),
    ]),

    # ── ADDITIONAL ID ──
    ("IDSA Diabetic Foot Infection", "IDSA", 2024, [
        ("Diabetic Foot Infection Classification and Treatment", "IDSA/IWGDF classification: mild (superficial, <2cm cellulitis), moderate (deeper or >2cm), severe (systemic toxicity or metabolic derangement). Mild: oral antibiotics (cephalexin, TMP-SMX, or amoxicillin-clavulanate). Moderate: IV antibiotics (ampicillin-sulbactam, ertapenem). Severe: broad-spectrum IV (piperacillin-tazobactam + vancomycin). Surgical debridement for abscess or necrosis. Probe-to-bone test for osteomyelitis.", "A", "Strong",
         ["diabetic foot infection", "cellulitis", "osteomyelitis", "diabetic foot"], ["cephalexin", "amoxicillin-clavulanate", "ampicillin-sulbactam", "ertapenem", "piperacillin-tazobactam", "vancomycin"], ["wound culture", "x-ray foot", "mri foot", "esr", "crp", "probe-to-bone"], ["diabetic foot infection", "iwgdf", "osteomyelitis", "debridement"]),
    ]),
    ("IDSA Intra-Abdominal Infection", "IDSA/SIS", 2024, [
        ("Complicated Intra-Abdominal Infection", "Source control (drainage, repair, resection) within 24 hours as primary intervention. Community-acquired mild-moderate: ceftriaxone + metronidazole, ertapenem, or moxifloxacin. Healthcare-associated or severe: piperacillin-tazobactam, meropenem, or cefepime + metronidazole ± vancomycin. Duration 4 days (4-day fixed course equals longer courses) after adequate source control.", "A", "Strong",
         ["intra-abdominal infection", "peritonitis", "intra-abdominal abscess"], ["ceftriaxone", "metronidazole", "ertapenem", "piperacillin-tazobactam", "meropenem"], ["ct abdomen", "wbc", "lactate", "blood culture"], ["intra-abdominal infection", "source control", "peritonitis", "drainage"]),
    ]),

    # ── ADDITIONAL PEDIATRICS ──
    ("AAP Immunization Schedule 2025", "AAP/CDC", 2025, [
        ("Childhood Immunization", "DTaP at 2, 4, 6, 15-18 months, 4-6 years. IPV at 2, 4, 6-18 months, 4-6 years. MMR at 12-15 months and 4-6 years. Varicella at 12-15 months and 4-6 years. Hepatitis B at birth, 1-2 months, 6-18 months. PCV15/20 at 2, 4, 6, 12-15 months. Rotavirus at 2, 4, (6) months. Annual influenza ≥6 months. HPV at 11-12 years.", "A", "Strong",
         ["childhood immunization", "vaccination schedule", "pediatric vaccines"], ["dtap", "ipv", "mmr", "varicella vaccine", "pcv", "rotavirus vaccine", "hpv vaccine"], [], ["immunization", "vaccine schedule", "childhood", "dtap"]),
    ]),
    ("AAP Pediatric Type 1 Diabetes", "AAP/ADA", 2025, [
        ("Pediatric T1DM Management", "Insulin therapy from diagnosis: basal-bolus or insulin pump. HCL (hybrid closed-loop) systems as preferred delivery. CGM for all pediatric T1DM. A1c target <7% (individualized). Screen for celiac disease and thyroid disease at diagnosis and periodically. DKA prevention education. Teplizumab for stage 2 T1DM (presymptomatic).", "A", "Strong",
         ["pediatric type 1 diabetes", "childhood diabetes", "juvenile diabetes"], ["insulin lispro", "insulin aspart", "insulin glargine", "insulin degludec", "teplizumab"], ["hba1c", "cgm", "c-peptide", "gad antibodies", "tsh", "ttg-iga"], ["pediatric diabetes", "insulin pump", "cgm", "closed-loop"]),
    ]),
    ("AAP Pediatric Obesity", "AAP", 2024, [
        ("Pediatric Obesity Treatment", "Motivational interviewing and family-based lifestyle interventions for all overweight/obese children. Structured weight management program for BMI ≥95th percentile. Consider pharmacotherapy (semaglutide, liraglutide approved ≥12 years; orlistat ≥12 years) for BMI ≥95th with comorbidities. Metabolic and bariatric surgery for adolescents ≥35 kg/m² with severe comorbidities. Screen for T2DM, NAFLD, dyslipidemia, HTN, OSA, depression.", "A", "Strong",
         ["pediatric obesity", "childhood obesity", "adolescent obesity"], ["semaglutide", "liraglutide", "orlistat"], ["bmi", "fasting glucose", "hba1c", "lipid panel", "alt"], ["pediatric obesity", "weight management", "semaglutide", "bariatric"]),
    ]),

    # ── GENETIC MEDICINE ──
    ("ACMG Hereditary Cancer Syndromes", "ACMG/NCCN", 2024, [
        ("Lynch Syndrome Management", "Germline testing for MLH1, MSH2, MSH6, PMS2, EPCAM for suspected Lynch syndrome (Amsterdam II or revised Bethesda criteria, or universal tumor MSI/IHC screening). Colonoscopy every 1-2 years starting age 20-25. Consider aspirin chemoprevention. Enhanced gynecologic surveillance for women. Risk-reducing hysterectomy/BSO after childbearing for MSH2/MLH1.", "A", "Strong",
         ["lynch syndrome", "hereditary nonpolyposis colorectal cancer", "hnpcc"], ["aspirin"], ["colonoscopy", "msi", "ihc", "genetic testing"], ["lynch syndrome", "msi", "colonoscopy", "genetic testing"]),
        ("BRCA1/2 Management", "Enhanced breast screening: annual mammogram and breast MRI from age 25 (or 10 years before youngest family diagnosis). Risk-reducing mastectomy reduces breast cancer risk by >90%. Risk-reducing BSO recommended by age 35-40 for BRCA1, 40-45 for BRCA2. PARP inhibitors for BRCA-associated cancers. Cascade testing for family members.", "A", "Strong",
         ["brca1", "brca2", "hereditary breast ovarian cancer"], ["olaparib", "talazoparib"], ["mammogram", "breast mri", "genetic testing", "ca-125"], ["brca", "risk-reducing surgery", "parp inhibitor", "cascade testing"]),
    ]),

    # ── ADDICTION MEDICINE ──
    ("ASAM Opioid Withdrawal", "ASAM", 2024, [
        ("Opioid Withdrawal Management", "Buprenorphine induction using COWS score ≥8 for short-acting opioids. Micro-dosing protocols (Bernese method) for fentanyl-exposed patients. Clonidine for adjunctive symptom management. Lofexidine as FDA-approved non-opioid for withdrawal symptoms. Bridge to long-term MOUD (buprenorphine or methadone). Avoid using withdrawal management alone—link to ongoing treatment.", "A", "Strong",
         ["opioid withdrawal", "opioid detoxification", "opioid use disorder"], ["buprenorphine", "clonidine", "lofexidine", "methadone"], ["cows score", "urine drug screen"], ["opioid withdrawal", "buprenorphine induction", "cows", "micro-dosing"]),
    ]),

    # ── INTENSIVE CARE - ADDITIONAL ──
    ("SCCM Shock Management", "SCCM", 2024, [
        ("Cardiogenic Shock", "Identify and treat underlying cause (ACS, arrhythmia, valvular emergency). Inotropes: dobutamine or milrinone for low cardiac output. Vasopressors: norepinephrine if hypotensive. Temporary MCS: IABP, Impella, or VA-ECMO for refractory cardiogenic shock. Avoid excessive fluid administration. Invasive hemodynamic monitoring with PA catheter.", "A", "Strong",
         ["cardiogenic shock", "acute heart failure", "hemodynamic instability"], ["dobutamine", "milrinone", "norepinephrine", "dopamine"], ["echocardiogram", "cardiac output", "lactate", "svo2", "pa catheter"], ["cardiogenic shock", "inotrope", "impella", "ecmo"]),
    ]),
    ("SCCM ICU-Acquired Weakness", "SCCM", 2024, [
        ("ICU-Acquired Weakness Prevention", "Early mobilization within 24-48 hours of ICU admission reduces ICU-AW incidence. Progressive mobility protocol: passive ROM → active ROM → sitting → standing → walking. Minimize sedation and neuromuscular blockade duration. Optimize nutrition (protein 1.2-2g/kg/day). Physical and occupational therapy consultation. Screen with MRC scale.", "A", "Strong",
         ["icu-acquired weakness", "critical illness myopathy", "critical illness polyneuropathy"], [], ["mrc scale", "handgrip dynamometry", "emg", "nerve conduction"], ["icu weakness", "early mobilization", "rehabilitation", "critical illness"]),
    ]),

    # ── BIOETHICS-ADJACENT CLINICAL ──
    ("AMA Code-Status Discussions", "AMA/AAHPM", 2024, [
        ("Goals of Care and Advance Directives", "Initiate goals-of-care conversations for all seriously ill patients. Document code status (full code, DNR/DNI, comfort measures). POLST for patients with serious illness or frailty. Surrogate decision-making for incapacitated patients. Regular reassessment of goals, especially with clinical changes. Palliative care consultation for symptom management and complex decisions.", "B", "Strong",
         ["advance directives", "goals of care", "end-of-life"], [], [], ["goals of care", "dnr", "polst", "advance directive"]),
    ]),

    # ── ALLERGY/IMMUNOLOGY EXPANSION ──
    ("AAAAI Drug Allergy", "AAAAI", 2024, [
        ("Penicillin Allergy Evaluation", "90% of patients labeled penicillin-allergic can safely receive penicillin after evaluation. Penicillin skin testing with PPL and penicillin G: negative predictive value >97%. Direct oral amoxicillin challenge for low-risk histories. Delabeling reduces broad-spectrum antibiotic use, C. difficile, MRSA, and healthcare costs.", "A", "Strong",
         ["penicillin allergy", "drug allergy", "beta-lactam allergy"], ["penicillin", "amoxicillin", "cephalexin"], ["penicillin skin test"], ["penicillin allergy", "delabeling", "skin testing", "cross-reactivity"]),
    ]),
    ("AAAAI Hereditary Angioedema", "AAAAI/WAO", 2024, [
        ("Hereditary Angioedema Management", "On-demand treatment with C1 inhibitor concentrate, icatibant, or ecallantide for acute attacks. Long-term prophylaxis with lanadelumab, berotralstat, or subcutaneous C1 inhibitor. Fresh frozen plasma as emergency backup if specific therapies unavailable. C4 level as screening test; confirm with C1-INH level and function. Self-administration of on-demand therapy at home.", "A", "Strong",
         ["hereditary angioedema", "hae", "c1 inhibitor deficiency"], ["icatibant", "c1 inhibitor concentrate", "lanadelumab", "berotralstat", "ecallantide"], ["c4 level", "c1 inhibitor level", "c1 inhibitor function"], ["hereditary angioedema", "c1 inhibitor", "lanadelumab", "icatibant"]),
    ]),
]


def generate_section_id(guideline_name: str, section_title: str) -> str:
    """Improved ID generation using hash to avoid collisions."""
    raw = f"{guideline_name}|{section_title}".lower()
    # Use first 4 meaningful words from guideline + first 3 from section + short hash
    words = re.sub(r'[^a-z0-9\s]', '', guideline_name.lower()).split()
    stop = {"the", "of", "for", "and", "in", "a", "an", "to", "with", "on"}
    abbr = "-".join(w for w in words[:4] if w not in stop)
    sec_words = re.sub(r'[^a-z0-9\s]', '', section_title.lower()).split()
    sec_abbr = "-".join(w for w in sec_words[:3] if w not in stop)
    # Add short hash suffix to prevent collisions
    h = hashlib.md5(raw.encode()).hexdigest()[:6]
    return f"{abbr}-{sec_abbr}-{h}"


def main():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "clinical_guidelines.json")
    fixture_path = os.path.normpath(fixture_path)
    with open(fixture_path) as f:
        existing = json.load(f)
    existing_ids = {s["section_id"] for s in existing["guidelines"]}
    print(f"Before: {len(existing['guidelines'])} sections")
    new_sections = []
    for guideline_name, society, year, sections in GUIDELINES:
        full_guideline = f"{guideline_name} ({year})"
        for (title, rec_text, grade, strength, conditions, meds, measurements, keywords) in sections:
            section_id = generate_section_id(guideline_name, title)
            if section_id in existing_ids:
                continue
            existing_ids.add(section_id)
            new_sections.append({
                "section_id": section_id, "guideline": full_guideline,
                "section_title": title, "recommendation_text": rec_text,
                "evidence_grade": grade, "recommendation_level": strength,
                "applies_to_conditions": conditions, "applies_to_medications": meds,
                "applies_to_measurements": measurements, "keywords": keywords,
            })
    all_sections = existing["guidelines"] + new_sections
    print(f"Added: {len(new_sections)} sections")
    print(f"Total: {len(all_sections)} sections")
    unique = set(s["guideline"] for s in all_sections)
    print(f"Unique guidelines: {len(unique)}")
    grades = {}
    for s in all_sections:
        g = s["evidence_grade"]
        grades[g] = grades.get(g, 0) + 1
    print(f"Grade distribution: {grades}")
    with open(fixture_path, "w") as f:
        json.dump({"guidelines": all_sections}, f, indent=2)
    print(f"Written to {fixture_path}")


if __name__ == "__main__":
    main()
