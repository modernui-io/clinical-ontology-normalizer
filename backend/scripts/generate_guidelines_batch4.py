#!/usr/bin/env python3
"""Batch 4: Add ~200 more sections - additional specialties and sub-specialty depth."""

import json, os, re

GUIDELINES = [
    # ── ADDITIONAL CARDIOLOGY ──
    ("ACC/AHA Cardiac Arrest / ACLS", "AHA", 2024, [
        ("Adult Cardiac Arrest Management", "High-quality CPR: rate 100-120/min, depth 2-2.4 inches, full recoil. Defibrillation for VF/pVT as early as possible. Epinephrine 1mg IV/IO every 3-5 minutes. Amiodarone 300mg IV for shock-refractory VF/pVT. Post-ROSC: targeted temperature management 32-36°C for 24 hours. Coronary angiography for suspected cardiac etiology.", "A", "Strong",
         ["cardiac arrest", "ventricular fibrillation", "pulseless ventricular tachycardia"], ["epinephrine", "amiodarone", "lidocaine"], ["ecg", "troponin", "lactate", "blood gas"], ["cardiac arrest", "acls", "cpr", "defibrillation"]),
        ("Post-Cardiac Arrest Care", "Targeted temperature management (TTM) at 32-36°C for 24 hours for comatose survivors. Avoid hyperthermia. Coronary angiography if STEMI or high suspicion for ACS. Neuroprognostication at ≥72 hours using multimodal approach (clinical exam, EEG, SSEP, NSE, MRI). Avoid early withdrawal of care.", "A", "Strong",
         ["post-cardiac arrest", "return of spontaneous circulation"], [], ["eeg", "nsae", "ssep", "mri brain", "troponin"], ["post-cardiac arrest", "ttm", "neuroprognostication", "rosc"]),
    ]),
    ("ACC Chest Pain Evaluation", "ACC", 2024, [
        ("Acute Chest Pain Pathway", "High-sensitivity troponin at 0 and 1-3 hours for rapid rule-out. HEART score for risk stratification. Low-risk patients with negative troponins: discharge with outpatient follow-up. Intermediate-risk: stress testing or CCTA. High-risk: invasive coronary angiography. ECG within 10 minutes of arrival.", "A", "Strong",
         ["chest pain", "acute coronary syndrome", "myocardial infarction"], ["aspirin", "nitroglycerin", "heparin"], ["troponin", "ecg", "heart score", "ccta"], ["chest pain", "troponin", "heart score", "acs"]),
    ]),
    ("ACC/AHA Heart Transplant", "ISHLT/ACC", 2024, [
        ("Heart Transplant Selection and Management", "Indicated for advanced HF (ACC/AHA Stage D) refractory to GDMT. Bridge with LVAD or inotropes. Immunosuppression: tacrolimus, mycophenolate, corticosteroids with induction (basiliximab or ATG). Surveillance endomyocardial biopsy. Monitor for cardiac allograft vasculopathy with annual angiography or IVUS. Lifetime immunosuppression.", "A", "Strong",
         ["heart transplant", "advanced heart failure", "cardiac transplant"], ["tacrolimus", "mycophenolate", "prednisone", "basiliximab", "everolimus"], ["echocardiogram", "endomyocardial biopsy", "bmp", "tacrolimus level"], ["heart transplant", "immunosuppression", "rejection", "vasculopathy"]),
    ]),

    # ── ADDITIONAL ONCOLOGY ──
    ("NCCN Testicular Cancer", "NCCN", 2025, [
        ("Testicular Germ Cell Tumors", "Radical inguinal orchiectomy for diagnosis and staging. Seminoma stage I: surveillance, radiation, or single-dose carboplatin. Non-seminoma stage I: surveillance or nerve-sparing RPLND. Advanced disease: BEP chemotherapy (bleomycin, etoposide, cisplatin). AFP, hCG, and LDH for monitoring. Sperm banking before treatment.", "A", "Strong",
         ["testicular cancer", "seminoma", "non-seminoma germ cell tumor"], ["bleomycin", "etoposide", "cisplatin", "carboplatin"], ["afp", "beta-hcg", "ldh", "ct abdomen pelvis", "testicular ultrasound"], ["testicular cancer", "bep", "orchiectomy", "seminoma"]),
    ]),
    ("NCCN Neuroendocrine Tumors", "NCCN", 2025, [
        ("GI Neuroendocrine Tumors", "Surgical resection for localized NETs. Somatostatin analogs (octreotide, lanreotide) for functional symptoms and tumor control. Everolimus or sunitinib for progressive pancreatic NETs. PRRT with lutetium-177 dotatate for somatostatin receptor-positive progressive NETs. Ki-67 index for grading.", "A", "Strong",
         ["neuroendocrine tumor", "carcinoid", "pancreatic net"], ["octreotide", "lanreotide", "everolimus", "sunitinib", "lutetium-177 dotatate", "temozolomide"], ["chromogranin a", "5-hiaa", "gallium-68 dotatate pet", "ki-67"], ["neuroendocrine tumor", "somatostatin analog", "prrt", "ki-67"]),
    ]),
    ("NCCN CNS Tumors", "NCCN", 2025, [
        ("Glioblastoma Treatment", "Maximal safe surgical resection. Concurrent temozolomide plus radiation (Stupp protocol) for newly diagnosed GBM. Adjuvant temozolomide for 6-12 cycles. MGMT methylation predicts temozolomide response. Tumor treating fields (TTFields) as adjunct. Bevacizumab for recurrent GBM. Lomustine as alternative.", "A", "Strong",
         ["glioblastoma", "gbm", "brain tumor", "malignant glioma"], ["temozolomide", "bevacizumab", "lomustine"], ["mri brain", "mgmt methylation", "idh mutation", "1p19q"], ["glioblastoma", "stupp protocol", "temozolomide", "ttfields"]),
        ("Low-Grade Glioma", "Observation for incidental low-grade glioma without mass effect. Surgical resection for symptomatic or growing tumors. Radiation plus PCV chemotherapy (procarbazine, lomustine, vincristine) for IDH-mutant 1p19q-codeleted oligodendroglioma. Vorasidenib for IDH-mutant grade 2 glioma. Serial MRI surveillance every 3-6 months.", "A", "Strong",
         ["low-grade glioma", "oligodendroglioma", "astrocytoma"], ["temozolomide", "procarbazine", "lomustine", "vincristine", "vorasidenib"], ["mri brain", "idh mutation", "1p19q codeletion"], ["low-grade glioma", "idh", "vorasidenib", "oligodendroglioma"]),
    ]),
    ("ASCO Supportive Care - Antiemetics", "ASCO", 2024, [
        ("Chemotherapy-Induced Nausea and Vomiting", "High emetogenic risk (HEC): NK1 antagonist + 5-HT3 antagonist + dexamethasone ± olanzapine. Moderate emetogenic (MEC): 5-HT3 antagonist + dexamethasone. Olanzapine 5-10mg days 1-4 reduces CINV. Breakthrough: different-class antiemetic from prophylaxis. Anticipatory N/V: benzodiazepines and behavioral therapy.", "A", "Strong",
         ["chemotherapy-induced nausea", "cinv", "chemotherapy side effects"], ["ondansetron", "granisetron", "aprepitant", "fosaprepitant", "olanzapine", "dexamethasone"], [], ["cinv", "antiemetic", "nk1 antagonist", "olanzapine"]),
    ]),
    ("ASCO Neutropenic Fever", "ASCO/IDSA", 2024, [
        ("Febrile Neutropenia Management", "Blood cultures (2 sets) and empiric broad-spectrum antibiotics within 1 hour. Cefepime, meropenem, or piperacillin-tazobactam as monotherapy. Add vancomycin for suspected MRSA, catheter infection, or hemodynamic instability. G-CSF prophylaxis for regimens with ≥20% febrile neutropenia risk. MASCC score for risk stratification.", "A", "Strong",
         ["febrile neutropenia", "neutropenic fever", "chemotherapy complication"], ["cefepime", "meropenem", "piperacillin-tazobactam", "vancomycin", "filgrastim", "pegfilgrastim"], ["anc", "blood culture", "chest x-ray", "procalcitonin"], ["febrile neutropenia", "empiric antibiotics", "g-csf", "mascc"]),
    ]),

    # ── ADDITIONAL NEUROLOGY ──
    ("AAN Guillain-Barré Syndrome", "AAN", 2024, [
        ("GBS Treatment", "IVIG 0.4g/kg/day × 5 days or plasma exchange (5 sessions over 2 weeks) equally effective. Start within 2 weeks of symptom onset. Monitor respiratory function (FVC) every 4-6 hours—intubate if FVC <20 mL/kg. Pain management with gabapentin or carbamazepine. VTE prophylaxis. Physical therapy during recovery.", "A", "Strong",
         ["guillain-barre syndrome", "gbs", "acute inflammatory demyelinating polyneuropathy"], ["ivig", "gabapentin", "enoxaparin"], ["fvc", "nerve conduction study", "csf protein"], ["guillain-barre", "ivig", "plasma exchange", "fvc"]),
    ]),
    ("AAN ALS Guidelines", "AAN", 2024, [
        ("ALS Treatment", "Riluzole as only disease-modifying therapy with modest survival benefit. Edaravone for selected patients with early ALS. Tofersen for SOD1-ALS. Multidisciplinary care improves survival and quality of life. NIV for FVC <50% or nocturnal hypoventilation. PEG placement before FVC drops below 50%. Palliative care involvement early.", "A", "Strong",
         ["amyotrophic lateral sclerosis", "als", "motor neuron disease"], ["riluzole", "edaravone", "tofersen"], ["fvc", "emg", "mri spine"], ["als", "riluzole", "niv", "multidisciplinary"]),
    ]),
    ("AAN Bacterial Meningitis", "IDSA", 2024, [
        ("Bacterial Meningitis Treatment", "Empiric antibiotics within 1 hour: vancomycin + third-gen cephalosporin (ceftriaxone 2g q12h). Add ampicillin for Listeria coverage if age >50, immunocompromised, or alcoholism. Dexamethasone before or with first antibiotic dose for suspected pneumococcal meningitis. Lumbar puncture with CSF analysis: cell count, protein, glucose, Gram stain, culture, PCR panel.", "A", "Strong",
         ["bacterial meningitis", "meningitis", "meningococcal disease"], ["ceftriaxone", "vancomycin", "ampicillin", "dexamethasone"], ["csf analysis", "csf culture", "blood culture", "ct head"], ["meningitis", "ceftriaxone", "vancomycin", "dexamethasone"]),
    ]),
    ("AAN Stroke Prevention", "AHA/ASA", 2024, [
        ("Secondary Stroke Prevention", "Antiplatelet therapy: aspirin, clopidogrel, or aspirin-dipyridamole. Dual antiplatelet (aspirin + clopidogrel) for 21 days after minor stroke or high-risk TIA. Anticoagulation for cardioembolic stroke (AF, mechanical valve). High-intensity statin. Blood pressure target <130/80. Carotid endarterectomy for symptomatic ≥50% stenosis.", "A", "Strong",
         ["stroke prevention", "ischemic stroke", "tia", "cerebrovascular disease"], ["aspirin", "clopidogrel", "ticagrelor", "apixaban", "rivaroxaban", "atorvastatin"], ["ct head", "mri brain", "carotid ultrasound", "echocardiogram", "ldl"], ["stroke prevention", "antiplatelet", "carotid endarterectomy", "statin"]),
    ]),

    # ── ADDITIONAL INFECTIOUS DISEASE ──
    ("IDSA COVID-19 Treatment", "IDSA/NIH", 2024, [
        ("COVID-19 Outpatient Treatment", "Nirmatrelvir-ritonavir (Paxlovid) within 5 days of symptom onset for high-risk patients. Remdesivir IV for 3 days as alternative. Molnupiravir if other options unavailable. Updated COVID-19 vaccine (XBB or later variant) for all ages ≥6 months. Pre-exposure prophylaxis with tixagevimab-cilgavimab no longer authorized.", "A", "Strong",
         ["covid-19", "sars-cov-2", "coronavirus"], ["nirmatrelvir-ritonavir", "remdesivir", "molnupiravir", "dexamethasone"], ["sars-cov-2 pcr", "rapid antigen test", "spo2"], ["covid-19", "paxlovid", "remdesivir", "antiviral"]),
        ("COVID-19 Inpatient Treatment", "Dexamethasone 6mg × 10 days for hospitalized patients requiring supplemental oxygen. Remdesivir for hospitalized patients. Baricitinib or tocilizumab for patients on high-flow or NIV with rising oxygen needs. Anticoagulation with prophylactic-dose heparin for non-ICU patients. Prone positioning for moderate-severe ARDS.", "A", "Strong",
         ["covid-19", "severe covid", "covid pneumonia"], ["dexamethasone", "remdesivir", "baricitinib", "tocilizumab", "enoxaparin"], ["spo2", "crp", "d-dimer", "ferritin", "chest x-ray", "ct chest"], ["covid-19", "dexamethasone", "baricitinib", "inpatient"]),
    ]),
    ("IDSA Influenza Treatment", "IDSA", 2024, [
        ("Influenza Antiviral Therapy", "Oseltamivir within 48 hours of symptom onset for high-risk patients or severe illness. Baloxavir marboxil as single-dose alternative. Peramivir IV for hospitalized patients unable to take oral. Annual influenza vaccination for all ≥6 months. Empiric treatment while awaiting testing for high-risk or hospitalized.", "A", "Strong",
         ["influenza", "flu", "influenza a", "influenza b"], ["oseltamivir", "baloxavir", "peramivir"], ["rapid influenza test", "influenza pcr", "chest x-ray"], ["influenza", "oseltamivir", "baloxavir", "antiviral"]),
    ]),
    ("IDSA UTI Guidelines (Updated)", "IDSA", 2024, [
        ("Complicated UTI and Pyelonephritis", "Urine culture before antibiotics. Fluoroquinolone (ciprofloxacin, levofloxacin) or TMP-SMX for outpatient pyelonephritis. IV ceftriaxone, fluoroquinolone, or piperacillin-tazobactam for admitted patients. Duration 7-14 days. CT abdomen for suspected abscess or obstruction. Blood cultures for sepsis.", "A", "Strong",
         ["complicated uti", "pyelonephritis", "urinary tract infection"], ["ciprofloxacin", "levofloxacin", "ceftriaxone", "piperacillin-tazobactam", "trimethoprim-sulfamethoxazole"], ["urine culture", "urinalysis", "blood culture", "ct abdomen"], ["pyelonephritis", "complicated uti", "fluoroquinolone", "ceftriaxone"]),
        ("Catheter-Associated UTI", "Remove or replace catheter before initiating antibiotics. Treat symptomatic CAUTI only (fever, suprapubic pain), not asymptomatic bacteriuria. Duration 7 days if prompt resolution, 10-14 days if delayed. Avoid routine urine surveillance cultures. Catheter should be removed as soon as possible.", "A", "Strong",
         ["catheter-associated uti", "cauti", "urinary tract infection"], ["ceftriaxone", "ciprofloxacin", "nitrofurantoin"], ["urine culture", "urinalysis"], ["cauti", "catheter", "bacteriuria", "removal"]),
    ]),
    ("IDSA Prosthetic Joint Infection", "IDSA", 2024, [
        ("PJI Treatment", "Two-stage exchange arthroplasty as standard for chronic PJI. DAIR (debridement, antibiotics, implant retention) for early-onset or acute hematogenous PJI with well-fixed components. IV antibiotics 4-6 weeks followed by oral suppressive therapy. Rifampin combination for staphylococcal PJI with retained implants. Preoperative aspiration for culture.", "A", "Strong",
         ["prosthetic joint infection", "pji", "periprosthetic infection"], ["vancomycin", "cefazolin", "rifampin", "ciprofloxacin", "daptomycin"], ["joint aspiration", "esr", "crp", "synovial fluid wbc", "alpha-defensin"], ["prosthetic joint infection", "two-stage exchange", "dair", "rifampin"]),
    ]),

    # ── ADDITIONAL ENDOCRINOLOGY ──
    ("Endocrine Society Hyperthyroidism", "Endocrine Society/ATA", 2024, [
        ("Graves Disease Treatment", "Antithyroid drugs (methimazole preferred, PTU for first trimester pregnancy) as first-line. Radioactive iodine (RAI) ablation for definitive therapy. Total thyroidectomy for large goiters, ophthalmopathy, or medication non-adherence. Beta-blockers for symptom control. Monitor TSH, free T4 every 4-6 weeks during titration.", "A", "Strong",
         ["graves disease", "hyperthyroidism", "thyrotoxicosis"], ["methimazole", "propylthiouracil", "propranolol", "atenolol", "radioactive iodine"], ["tsh", "free t4", "free t3", "trab", "thyroid uptake scan"], ["graves disease", "methimazole", "radioactive iodine", "hyperthyroidism"]),
    ]),
    ("Endocrine Society Pheochromocytoma", "Endocrine Society", 2024, [
        ("Pheochromocytoma/Paraganglioma", "Alpha-blockade (phenoxybenzamine or doxazosin) for 10-14 days before surgery. Beta-blockade only after adequate alpha-blockade. Surgical resection as definitive treatment. Preoperative volume expansion with high-sodium diet and IV fluids. Genetic testing for SDH, VHL, RET, NF1 mutations. Annual biochemical screening for hereditary syndromes.", "A", "Strong",
         ["pheochromocytoma", "paraganglioma", "catecholamine excess"], ["phenoxybenzamine", "doxazosin", "propranolol", "metyrosine"], ["plasma metanephrines", "24-hour urine catecholamines", "ct adrenals", "mibg scan"], ["pheochromocytoma", "alpha-blockade", "metanephrines", "paraganglioma"]),
    ]),
    ("ADA Diabetic Foot", "ADA/IWGDF", 2024, [
        ("Diabetic Foot Ulcer Management", "Comprehensive foot exam annually for all diabetics. Offloading with total contact cast or removable walker for plantar ulcers. Debridement of necrotic tissue. Antibiotics only for clinically infected ulcers (not colonization). Vascular assessment with ABI and toe pressures. Revascularization for ischemic ulcers. Multidisciplinary limb preservation team.", "A", "Strong",
         ["diabetic foot ulcer", "diabetic foot", "peripheral neuropathy", "limb ischemia"], ["amoxicillin-clavulanate", "piperacillin-tazobactam", "vancomycin"], ["abi", "toe brachial index", "wound culture", "x-ray foot", "mri foot"], ["diabetic foot", "offloading", "wound care", "limb preservation"]),
    ]),

    # ── ADDITIONAL PREVENTIVE MEDICINE ──
    ("ACIP Immunization Schedule", "CDC/ACIP", 2025, [
        ("Adult Immunization Recommendations", "Annual influenza vaccine. Updated COVID-19 vaccine annually. Tdap booster every 10 years. Shingrix (recombinant zoster) 2 doses for adults ≥50. PCV20 or PCV21 for pneumococcal protection. HPV vaccine through age 26 (catch-up to 45). Hepatitis B for unvaccinated adults. RSV vaccine for adults ≥60.", "A", "Strong",
         ["adult immunization", "vaccination", "preventive care"], ["influenza vaccine", "covid-19 vaccine", "shingrix", "pcv20", "hpv vaccine", "tdap"], [], ["immunization", "vaccination", "shingrix", "pneumococcal"]),
    ]),
    ("USPSTF Depression Screening", "USPSTF", 2024, [
        ("Depression Screening in Adults", "Screen for depression in all adults including pregnant and postpartum women. PHQ-2 as initial screen; PHQ-9 for those screening positive. Screen for suicide risk. Ensure adequate systems for diagnosis, treatment, and follow-up. Screening benefits outweigh harms in primary care settings.", "B", "Strong",
         ["depression screening", "major depressive disorder", "postpartum depression"], [], ["phq-2", "phq-9", "edinburgh postnatal depression scale"], ["depression screening", "phq-9", "uspstf", "preventive"]),
    ]),
    ("USPSTF Prediabetes/Diabetes Screening", "USPSTF", 2024, [
        ("Diabetes Screening", "Screen adults aged 35-70 with overweight/obesity for prediabetes and type 2 diabetes. Fasting glucose, HbA1c, or oral glucose tolerance test. Refer patients with prediabetes to lifestyle intervention programs (e.g., DPP). Metformin for prediabetes with high-risk features. Repeat screening every 3 years.", "B", "Strong",
         ["prediabetes", "diabetes screening", "type 2 diabetes prevention"], ["metformin"], ["fasting glucose", "hba1c", "ogtt"], ["diabetes screening", "prediabetes", "dpp", "lifestyle intervention"]),
    ]),
    ("USPSTF Statin Use for CVD Prevention", "USPSTF", 2024, [
        ("Statin for Primary Prevention", "Low-to-moderate dose statin for adults 40-75 with ≥1 CVD risk factor and 10-year ASCVD risk ≥10%. Shared decision-making for risk 7.5-10%. CVD risk factors: dyslipidemia, diabetes, hypertension, smoking. Insufficient evidence for adults ≥76.", "B", "Moderate",
         ["cardiovascular disease prevention", "statin therapy", "primary prevention"], ["atorvastatin", "rosuvastatin", "pravastatin", "simvastatin"], ["ldl", "total cholesterol", "10-year ascvd risk"], ["statin", "primary prevention", "ascvd risk", "uspstf"]),
    ]),
    ("USPSTF Cervical Cancer Screening", "USPSTF", 2024, [
        ("Cervical Cancer Screening", "Ages 21-29: cytology alone every 3 years. Ages 30-65: hrHPV testing alone every 5 years (preferred), co-testing every 5 years, or cytology alone every 3 years. No screening before age 21 or after 65 with adequate prior screening. No screening after hysterectomy with cervix removal for non-cancer indications.", "A", "Strong",
         ["cervical cancer screening", "hpv screening", "pap smear"], [], ["hpv test", "pap smear", "colposcopy"], ["cervical screening", "hpv", "cytology", "uspstf"]),
    ]),

    # ── ADDITIONAL OPHTHALMOLOGY ──
    ("AAO Diabetic Retinopathy", "AAO", 2024, [
        ("Diabetic Retinopathy Management", "Annual dilated eye exam for all diabetics. Anti-VEGF intravitreal injections (aflibercept, ranibizumab, faricimab) as first-line for center-involving diabetic macular edema. Panretinal photocoagulation for proliferative diabetic retinopathy. Anti-VEGF as alternative to PRP for PDR. Optimize glycemic control (A1c <7%) and blood pressure.", "A", "Strong",
         ["diabetic retinopathy", "diabetic macular edema", "proliferative diabetic retinopathy"], ["aflibercept", "ranibizumab", "faricimab"], ["dilated fundoscopy", "oct", "fluorescein angiography", "hba1c"], ["diabetic retinopathy", "anti-vegf", "macular edema", "photocoagulation"]),
    ]),
    ("AAO Cataract Surgery", "AAO", 2024, [
        ("Cataract Surgery Guidelines", "Phacoemulsification with IOL implantation as standard technique. Surgery indicated when visual impairment affects daily activities or impairs other eye care. Biometry for IOL power calculation. Topical NSAIDs and antibiotics perioperatively. Informed consent regarding IOL type (monofocal, multifocal, toric). Post-op visit within 48 hours.", "A", "Strong",
         ["cataract", "cataract surgery", "lens opacity"], [], ["visual acuity", "biometry", "oct", "keratometry"], ["cataract surgery", "phacoemulsification", "iol", "biometry"]),
    ]),

    # ── ADDITIONAL ORTHOPEDICS ──
    ("ACR/AAOS Osteoarthritis Management", "ACR/AAOS", 2024, [
        ("Knee/Hip Osteoarthritis", "Exercise (land-based, aquatic) as first-line for all OA patients. Weight loss of ≥5% for overweight patients. Topical NSAIDs for knee OA. Oral NSAIDs at lowest effective dose with PPI if GI risk. Intra-articular corticosteroid injections for acute flares. Duloxetine as adjunct for OA pain. Total joint replacement for end-stage disease failing conservative management.", "A", "Strong",
         ["osteoarthritis", "knee osteoarthritis", "hip osteoarthritis"], ["diclofenac topical", "naproxen", "ibuprofen", "celecoxib", "duloxetine", "acetaminophen"], ["x-ray", "mri", "bmi"], ["osteoarthritis", "exercise", "nsaid", "joint replacement"]),
    ]),
    ("AAOS Rotator Cuff Guidelines", "AAOS", 2024, [
        ("Rotator Cuff Tear Management", "Physical therapy as first-line for partial tears and small full-thickness tears in low-demand patients. Rotator cuff repair (arthroscopic preferred) for acute full-thickness tears in active patients. Corticosteroid injection for temporary pain relief (limit to 3 per year). Reverse total shoulder arthroplasty for massive irreparable tears with arthropathy.", "A", "Strong",
         ["rotator cuff tear", "shoulder impingement", "shoulder pain"], ["corticosteroid injection", "ketorolac"], ["shoulder mri", "x-ray shoulder", "ultrasound shoulder"], ["rotator cuff", "arthroscopic repair", "physical therapy", "shoulder"]),
    ]),
    ("NASS Lumbar Spinal Stenosis", "NASS", 2024, [
        ("Lumbar Stenosis Management", "Physical therapy and structured exercise as initial treatment. NSAIDs for pain management. Epidural steroid injections for short-term relief. Surgical decompression (laminectomy) for patients failing 3-6 months of conservative treatment with neurogenic claudication or radiculopathy. Fusion added for concurrent instability.", "B", "Strong",
         ["lumbar spinal stenosis", "neurogenic claudication", "lumbar radiculopathy"], ["naproxen", "gabapentin", "epidural corticosteroid"], ["mri lumbar spine", "x-ray lumbar spine", "emg"], ["spinal stenosis", "laminectomy", "epidural injection", "neurogenic claudication"]),
    ]),

    # ── ADDITIONAL UROLOGY ──
    ("AUA BPH/LUTS Guidelines", "AUA", 2024, [
        ("BPH Medical Therapy", "Alpha-blockers (tamsulosin, silodosin) as first-line for moderate LUTS. 5-alpha reductase inhibitors (finasteride, dutasteride) for prostate >30g. Combination therapy (alpha-blocker + 5ARI) for large prostates. PDE5 inhibitor (tadalafil 5mg daily) for concurrent ED and LUTS. Anticholinergics or beta-3 agonist for storage symptoms.", "A", "Strong",
         ["benign prostatic hyperplasia", "bph", "luts", "enlarged prostate"], ["tamsulosin", "silodosin", "finasteride", "dutasteride", "tadalafil", "mirabegron"], ["psa", "uroflowmetry", "post-void residual", "ipss"], ["bph", "alpha-blocker", "5-alpha reductase", "luts"]),
        ("BPH Surgical Options", "Transurethral resection of prostate (TURP) as gold standard for 30-80g prostates. Holmium laser enucleation (HoLEP) for all prostate sizes. Rezum water vapor therapy and UroLift as minimally invasive options preserving sexual function. Simple prostatectomy (open or robotic) for >80-100g prostates. Aquablation for 30-150g.", "A", "Strong",
         ["bph", "benign prostatic hyperplasia", "urinary obstruction"], [], ["uroflowmetry", "pvr", "cystoscopy", "prostate volume"], ["turp", "holep", "urolift", "rezum"]),
    ]),
    ("AUA Erectile Dysfunction", "AUA", 2024, [
        ("ED Evaluation and Treatment", "PDE5 inhibitors (sildenafil, tadalafil, vardenafil, avanafil) as first-line therapy. Testosterone replacement for documented hypogonadism. Vacuum erection devices as non-pharmacologic option. Intracavernosal injections (alprostadil, trimix) for PDE5i failure. Penile prosthesis for refractory ED. Screen for cardiovascular disease.", "A", "Strong",
         ["erectile dysfunction", "ed", "sexual dysfunction"], ["sildenafil", "tadalafil", "vardenafil", "testosterone", "alprostadil"], ["testosterone", "fsh", "lh", "prolactin", "hba1c", "lipid panel"], ["erectile dysfunction", "pde5 inhibitor", "testosterone", "prosthesis"]),
    ]),

    # ── ADDITIONAL DERMATOLOGY ──
    ("AAD Drug Reactions", "AAD", 2024, [
        ("Stevens-Johnson Syndrome / TEN", "Immediate withdrawal of causative drug. Transfer to burn unit for TEN (>30% BSA). Supportive care: wound care, fluid management, temperature regulation, nutritional support. IV immunoglobulin or cyclosporine for severe cases. Common triggers: allopurinol, carbamazepine, lamotrigine, sulfonamides, NSAIDs. HLA-B*5801 testing before allopurinol in at-risk populations.", "A", "Strong",
         ["stevens-johnson syndrome", "toxic epidermal necrolysis", "sjs/ten", "drug reaction"], ["ivig", "cyclosporine"], ["skin biopsy", "bsa assessment", "bmp"], ["sjs", "ten", "drug reaction", "ivig"]),
    ]),
    ("AAD Fungal Skin Infections", "AAD", 2024, [
        ("Onychomycosis Treatment", "Oral terbinafine as first-line for dermatophyte onychomycosis (6 weeks fingernails, 12 weeks toenails). Itraconazole pulse therapy as alternative. Ciclopirox or efinaconazole topical for mild disease or poor oral candidates. Confirm diagnosis with KOH, culture, or PAS stain before systemic treatment. Monitor LFTs with oral terbinafine.", "A", "Strong",
         ["onychomycosis", "fungal nail infection", "dermatophytosis"], ["terbinafine", "itraconazole", "ciclopirox", "efinaconazole"], ["koh preparation", "fungal culture", "liver function"], ["onychomycosis", "terbinafine", "fungal nail", "topical antifungal"]),
    ]),
]


def generate_section_id(guideline_name: str, section_title: str) -> str:
    words = re.sub(r'[^a-z0-9\s]', '', guideline_name.lower()).split()
    stop = {"the", "of", "for", "and", "in", "a", "an", "to", "with", "on"}
    abbr = "-".join(w for w in words[:4] if w not in stop)
    sec_words = re.sub(r'[^a-z0-9\s]', '', section_title.lower()).split()
    sec_abbr = "-".join(w for w in sec_words[:3] if w not in stop)
    return f"{abbr}-{sec_abbr}"


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
    with open(fixture_path, "w") as f:
        json.dump({"guidelines": all_sections}, f, indent=2)
    print(f"Written to {fixture_path}")

if __name__ == "__main__":
    main()
