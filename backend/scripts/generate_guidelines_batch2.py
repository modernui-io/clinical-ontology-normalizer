#!/usr/bin/env python3
"""Batch 2: Add ~200 more guideline sections across expanded specialties."""

import json, os, re

GUIDELINES = [
    # ── CARDIOLOGY EXPANSION ──
    ("ESC Atrial Fibrillation Guidelines", "ESC", 2024, [
        ("AF Stroke Prevention", "Anticoagulation with DOACs (apixaban, rivaroxaban, edoxaban, dabigatran) is recommended for AF patients with CHA2DS2-VASc ≥2 (men) or ≥3 (women). DOACs are preferred over warfarin. Left atrial appendage occlusion for patients with contraindications to long-term anticoagulation.", "A", "Strong",
         ["atrial fibrillation", "af", "stroke prevention"], ["apixaban", "rivaroxaban", "edoxaban", "dabigatran", "warfarin"], ["cha2ds2-vasc", "inr", "creatinine clearance"], ["atrial fibrillation", "anticoagulation", "doac", "stroke prevention"]),
        ("AF Rate vs Rhythm Control", "Rhythm control with catheter ablation or antiarrhythmic drugs is preferred for early AF and symptomatic patients. Rate control with beta-blockers or diltiazem/verapamil for permanent AF. Lenient rate control (resting HR <110) acceptable for asymptomatic patients.", "A", "Strong",
         ["atrial fibrillation", "af"], ["flecainide", "amiodarone", "metoprolol", "diltiazem", "sotalol"], ["ecg", "heart rate", "holter monitor"], ["af", "rate control", "rhythm control", "ablation"]),
        ("AF Catheter Ablation", "Pulmonary vein isolation is the cornerstone of AF ablation. Recommended for symptomatic paroxysmal AF refractory to antiarrhythmic drugs. May be considered as first-line therapy. Left atrial posterior wall isolation for persistent AF. Success rates 70-80% at 1 year.", "A", "Strong",
         ["atrial fibrillation", "paroxysmal af", "persistent af"], [], ["ecg", "cardiac mri", "ct angiography"], ["ablation", "pulmonary vein isolation", "catheter ablation"]),
    ]),
    ("ACC/AHA Hypertension Guidelines", "ACC/AHA", 2024, [
        ("Hypertension Diagnosis and Goals", "Hypertension defined as BP ≥130/80 mmHg. Target BP <130/80 for most adults. Target <120/80 for high cardiovascular risk. Out-of-office BP monitoring (ABPM or home BP) recommended to confirm diagnosis. Screen for secondary causes if resistant or early-onset.", "A", "Strong",
         ["hypertension", "high blood pressure"], [], ["blood pressure", "ambulatory bp monitoring", "creatinine", "potassium"], ["hypertension", "blood pressure", "target", "diagnosis"]),
        ("First-Line Antihypertensive Agents", "ACE inhibitors, ARBs, calcium channel blockers, and thiazide diuretics as first-line options. ACEi/ARB preferred for diabetes, CKD, or heart failure. CCB or thiazide for Black patients. Combination therapy for stage 2 hypertension (BP ≥140/90).", "A", "Strong",
         ["hypertension"], ["lisinopril", "losartan", "amlodipine", "chlorthalidone", "hydrochlorothiazide"], ["blood pressure", "creatinine", "potassium"], ["antihypertensive", "ace inhibitor", "arb", "ccb", "diuretic"]),
        ("Resistant Hypertension", "Defined as BP above goal despite 3 agents including a diuretic at optimal doses. Confirm adherence and exclude white-coat effect. Add spironolactone as fourth agent. Evaluate for secondary causes: renal artery stenosis, primary aldosteronism, pheochromocytoma, OSA.", "B", "Strong",
         ["resistant hypertension", "secondary hypertension"], ["spironolactone", "minoxidil", "hydralazine"], ["aldosterone", "renin", "renal artery doppler", "metanephrines"], ["resistant hypertension", "spironolactone", "secondary causes"]),
    ]),
    ("ACC/AHA Lipid Management Guidelines", "ACC/AHA", 2024, [
        ("Statin Therapy for Primary Prevention", "High-intensity statin for LDL ≥190 mg/dL. Moderate-to-high intensity statin for diabetes aged 40-75. Risk-enhancing factors and CAC score to guide therapy for borderline/intermediate risk. Shared decision-making for patients 40-75 with 10-year ASCVD risk 7.5-20%.", "A", "Strong",
         ["hyperlipidemia", "atherosclerosis prevention"], ["atorvastatin", "rosuvastatin", "pravastatin"], ["ldl", "total cholesterol", "triglycerides", "cac score"], ["statin", "primary prevention", "ldl", "ascvd risk"]),
        ("LDL Lowering Beyond Statins", "Ezetimibe as first add-on therapy for patients not at LDL goal on maximally tolerated statin. PCSK9 inhibitors (evolocumab, alirocumab) for very high-risk ASCVD patients with LDL ≥70 on statin plus ezetimibe. Bempedoic acid for statin-intolerant patients. Inclisiran as alternative PCSK9 pathway inhibitor.", "A", "Strong",
         ["hyperlipidemia", "atherosclerosis"], ["ezetimibe", "evolocumab", "alirocumab", "bempedoic acid", "inclisiran"], ["ldl", "total cholesterol", "lipoprotein a"], ["ezetimibe", "pcsk9", "ldl lowering", "statin intolerance"]),
        ("Hypertriglyceridemia Management", "Lifestyle modifications and statin therapy as foundation. Icosapent ethyl (EPA) for triglycerides 135-499 with ASCVD or diabetes plus additional risk factors. Fibrates for severe hypertriglyceridemia (TG ≥500) to reduce pancreatitis risk. Omega-3 fatty acids as adjunct.", "A", "Strong",
         ["hypertriglyceridemia", "dyslipidemia"], ["icosapent ethyl", "fenofibrate", "gemfibrozil"], ["triglycerides", "hdl", "ldl"], ["triglycerides", "icosapent ethyl", "fibrate", "vascepa"]),
    ]),
    ("AHA/ACC Infective Endocarditis", "AHA/ACC", 2024, [
        ("Endocarditis Diagnosis", "Modified Duke criteria for diagnosis. Blood cultures (3 sets from different sites) before antibiotics. Echocardiography: TTE first, TEE if TTE negative with high suspicion or prosthetic valve. PET/CT for prosthetic valve endocarditis when Duke criteria inconclusive.", "A", "Strong",
         ["infective endocarditis", "endocarditis"], [], ["blood culture", "echocardiogram", "tee", "crp", "esr"], ["endocarditis", "duke criteria", "blood culture", "echocardiogram"]),
        ("Endocarditis Treatment", "IV antibiotics for 4-6 weeks. Native valve S. aureus: nafcillin or cefazolin; MRSA: vancomycin or daptomycin. Streptococcal: penicillin G or ceftriaxone. Surgical intervention for heart failure, uncontrolled infection, or large vegetations with embolic risk.", "A", "Strong",
         ["infective endocarditis"], ["nafcillin", "cefazolin", "vancomycin", "daptomycin", "ceftriaxone", "gentamicin"], ["blood culture", "echocardiogram", "crp"], ["endocarditis", "antibiotic", "surgery", "vegetation"]),
    ]),
    ("ESC Pericardial Disease", "ESC", 2024, [
        ("Acute Pericarditis", "NSAIDs (ibuprofen, aspirin) plus colchicine as first-line for acute pericarditis. Colchicine for 3 months to reduce recurrence. Low-dose corticosteroids only if NSAIDs/colchicine contraindicated. Restrict exercise until symptom resolution and CRP normalization.", "A", "Strong",
         ["pericarditis", "acute pericarditis", "pericardial effusion"], ["ibuprofen", "aspirin", "colchicine", "prednisone"], ["crp", "echocardiogram", "ecg", "troponin"], ["pericarditis", "colchicine", "nsaid", "recurrence"]),
        ("Pericardial Effusion and Tamponade", "Echocardiography-guided pericardiocentesis for tamponade or large effusions with hemodynamic compromise. Urgent drainage for cardiac tamponade. Pericardial fluid analysis: cell count, protein, LDH, glucose, cytology, cultures. Pericardial window for recurrent effusions.", "A", "Strong",
         ["pericardial effusion", "cardiac tamponade"], [], ["echocardiogram", "ct chest", "pericardial fluid"], ["tamponade", "pericardiocentesis", "effusion", "pericardial"]),
    ]),

    # ── ONCOLOGY EXPANSION ──
    ("NCCN Gastric Cancer Guidelines", "NCCN", 2025, [
        ("Gastric Cancer Treatment", "Perioperative FLOT (docetaxel, oxaliplatin, 5-FU/leucovorin) for resectable gastric cancer. Subtotal or total gastrectomy with D2 lymphadenectomy. Trastuzumab plus chemotherapy for HER2-positive metastatic disease. Nivolumab for PD-L1 CPS ≥5 in combination with chemotherapy.", "A", "Strong",
         ["gastric cancer", "stomach cancer"], ["docetaxel", "oxaliplatin", "5-fluorouracil", "trastuzumab", "nivolumab"], ["her2", "pd-l1", "ct abdomen", "endoscopy"], ["gastric cancer", "flot", "gastrectomy", "her2"]),
        ("Gastric Cancer Screening in High-Risk", "Endoscopic surveillance recommended for high-risk populations (intestinal metaplasia, pernicious anemia, familial risk). H. pylori eradication reduces gastric cancer risk. No routine screening for average-risk populations in Western countries.", "B", "Moderate",
         ["gastric cancer screening", "intestinal metaplasia"], [], ["upper endoscopy", "h pylori test"], ["gastric cancer", "screening", "h pylori", "intestinal metaplasia"]),
    ]),
    ("NCCN Esophageal Cancer Guidelines", "NCCN", 2025, [
        ("Esophageal Cancer Treatment", "Neoadjuvant chemoradiation (carboplatin/paclitaxel with radiation) followed by surgery for resectable disease. Nivolumab adjuvant for residual disease after neoadjuvant CRT. Pembrolizumab plus chemotherapy for metastatic esophageal SCC or adenocarcinoma with PD-L1 CPS ≥10.", "A", "Strong",
         ["esophageal cancer", "esophageal adenocarcinoma", "esophageal squamous cell"], ["carboplatin", "paclitaxel", "nivolumab", "pembrolizumab", "5-fluorouracil"], ["ct scan", "pet scan", "pd-l1", "endoscopy"], ["esophageal cancer", "chemoradiation", "immunotherapy"]),
    ]),
    ("NCCN Ovarian Cancer Guidelines", "NCCN", 2025, [
        ("Ovarian Cancer Primary Treatment", "Optimal debulking surgery followed by carboplatin/paclitaxel chemotherapy. Neoadjuvant chemotherapy for patients not candidates for primary cytoreduction. BRCA and HRD testing for all epithelial ovarian cancers. Olaparib or niraparib maintenance for BRCA-mutated or HRD-positive tumors.", "A", "Strong",
         ["ovarian cancer", "epithelial ovarian cancer"], ["carboplatin", "paclitaxel", "olaparib", "niraparib", "bevacizumab"], ["ca-125", "ct abdomen pelvis", "brca", "hrd"], ["ovarian cancer", "parp inhibitor", "debulking", "carboplatin"]),
        ("Ovarian Cancer Recurrence", "Platinum-sensitive recurrence: platinum-based rechallenge with PARP inhibitor maintenance. Platinum-resistant: weekly paclitaxel, pegylated liposomal doxorubicin, topotecan, or gemcitabine. Mirvetuximab soravtansine for FRα-positive platinum-resistant disease.", "A", "Strong",
         ["recurrent ovarian cancer", "ovarian cancer"], ["carboplatin", "paclitaxel", "olaparib", "pegylated liposomal doxorubicin", "mirvetuximab"], ["ca-125", "ct scan", "fra"], ["ovarian", "recurrence", "platinum-resistant", "parp"]),
    ]),
    ("NCCN Endometrial Cancer", "NCCN", 2025, [
        ("Endometrial Cancer Treatment", "Total hysterectomy with bilateral salpingo-oophorectomy as primary surgery. Sentinel lymph node mapping preferred for staging. Adjuvant therapy based on risk stratification: observation for low-risk, vaginal cuff brachytherapy for intermediate, chemoradiation for high-risk. Dostarlimab-gxly for dMMR/MSI-H advanced disease.", "A", "Strong",
         ["endometrial cancer", "uterine cancer"], ["carboplatin", "paclitaxel", "dostarlimab", "pembrolizumab", "lenvatinib"], ["ct scan", "msi", "mmr", "ca-125"], ["endometrial cancer", "hysterectomy", "immunotherapy"]),
    ]),
    ("NCCN Bladder Cancer", "NCCN", 2025, [
        ("Non-Muscle Invasive Bladder Cancer", "Transurethral resection of bladder tumor (TURBT) with re-resection at 2-6 weeks for high-grade tumors. Intravesical BCG for high-risk NMIBC. Pembrolizumab for BCG-unresponsive CIS. Radical cystectomy for BCG-refractory or highest-risk disease.", "A", "Strong",
         ["bladder cancer", "urothelial carcinoma", "non-muscle invasive bladder cancer"], ["bcg", "mitomycin c", "pembrolizumab"], ["cystoscopy", "urine cytology", "ct urogram"], ["bladder cancer", "turbt", "bcg", "intravesical"]),
        ("Muscle-Invasive Bladder Cancer", "Neoadjuvant cisplatin-based chemotherapy followed by radical cystectomy. Nivolumab adjuvant for high-risk after neoadjuvant chemo. Trimodal therapy (TURBT + chemoradiation) for bladder preservation candidates. Enfortumab vedotin plus pembrolizumab for metastatic first-line.", "A", "Strong",
         ["muscle-invasive bladder cancer", "metastatic bladder cancer"], ["cisplatin", "gemcitabine", "nivolumab", "enfortumab vedotin", "pembrolizumab"], ["ct scan", "pet scan", "creatinine"], ["bladder cancer", "cystectomy", "neoadjuvant", "enfortumab"]),
    ]),
    ("NCCN Head and Neck Cancer", "NCCN", 2025, [
        ("Oropharyngeal Cancer", "HPV status is critical for prognosis and treatment decisions. Surgery or radiation for early-stage. Concurrent cisplatin-radiation for locally advanced. De-escalation strategies under investigation for HPV-positive. Pembrolizumab plus chemotherapy for recurrent/metastatic.", "A", "Strong",
         ["oropharyngeal cancer", "head and neck cancer", "hpv-related cancer"], ["cisplatin", "pembrolizumab", "cetuximab", "carboplatin"], ["hpv p16", "ct scan", "pet scan"], ["oropharyngeal", "hpv", "cisplatin", "radiation"]),
        ("Laryngeal Cancer", "Radiation or surgery for early-stage larynx cancer. Concurrent chemoradiation for organ preservation in advanced disease. Total laryngectomy for salvage or T4a disease. Voice rehabilitation after laryngectomy.", "A", "Strong",
         ["laryngeal cancer", "head and neck cancer"], ["cisplatin"], ["ct neck", "laryngoscopy", "pet scan"], ["laryngeal cancer", "organ preservation", "chemoradiation"]),
    ]),
    ("NCCN Thyroid Cancer", "NCCN", 2025, [
        ("Differentiated Thyroid Cancer", "Total thyroidectomy or lobectomy based on risk stratification. RAI ablation for intermediate and high-risk patients. TSH suppression with levothyroxine. Lenvatinib or sorafenib for RAI-refractory progressive disease. Selpercatinib for RET-mutated, larotrectinib for NTRK-fusion thyroid cancer.", "A", "Strong",
         ["thyroid cancer", "papillary thyroid cancer", "follicular thyroid cancer"], ["levothyroxine", "lenvatinib", "sorafenib", "selpercatinib"], ["tsh", "thyroglobulin", "thyroid ultrasound", "rai scan"], ["thyroid cancer", "thyroidectomy", "rai", "tsh suppression"]),
        ("Medullary Thyroid Cancer", "Total thyroidectomy with central neck dissection. RET mutation testing for all patients. Vandetanib or cabozantinib for progressive metastatic MTC. Selpercatinib or pralsetinib for RET-mutated MTC. Calcitonin and CEA monitoring for recurrence.", "A", "Strong",
         ["medullary thyroid cancer", "men2"], ["vandetanib", "cabozantinib", "selpercatinib", "pralsetinib"], ["calcitonin", "cea", "ret mutation"], ["medullary thyroid", "ret", "vandetanib", "calcitonin"]),
    ]),
    ("NCCN Hepatocellular Carcinoma", "NCCN", 2025, [
        ("HCC Treatment Algorithm", "Surgical resection for early-stage HCC with preserved liver function. Liver transplant within Milan criteria. Locoregional therapy (TACE, ablation) for intermediate-stage. Atezolizumab/bevacizumab or durvalumab/tremelimumab as first-line systemic for advanced HCC. Sorafenib or lenvatinib as alternatives.", "A", "Strong",
         ["hepatocellular carcinoma", "liver cancer", "hcc"], ["atezolizumab", "bevacizumab", "sorafenib", "lenvatinib", "durvalumab"], ["afp", "ct abdomen", "mri liver", "child-pugh"], ["hcc", "liver cancer", "transplant", "immunotherapy"]),
        ("HCC Surveillance", "Surveillance with ultrasound and AFP every 6 months for cirrhosis patients. MRI may be used for inadequate ultrasound visualization. Diagnostic criteria: arterial hyperenhancement with washout on CT or MRI (LI-RADS). Biopsy for indeterminate lesions.", "A", "Strong",
         ["hepatocellular carcinoma surveillance", "cirrhosis"], [], ["ultrasound", "afp", "ct abdomen", "mri liver"], ["hcc screening", "surveillance", "li-rads", "cirrhosis"]),
    ]),
    ("NCCN Hodgkin Lymphoma", "NCCN", 2025, [
        ("Classical Hodgkin Lymphoma", "ABVD (doxorubicin, bleomycin, vinblastine, dacarbazine) as standard first-line. Brentuximab vedotin plus AVD for advanced-stage. PET-adapted therapy: de-escalation for PET-negative after 2 cycles. Pembrolizumab for relapsed/refractory after ASCT and brentuximab.", "A", "Strong",
         ["hodgkin lymphoma", "classical hodgkin"], ["doxorubicin", "bleomycin", "vinblastine", "brentuximab vedotin", "pembrolizumab"], ["pet scan", "ct scan", "cbc", "esr"], ["hodgkin", "abvd", "brentuximab", "pet-adapted"]),
    ]),
    ("NCCN Diffuse Large B-Cell Lymphoma", "NCCN", 2025, [
        ("DLBCL First-Line Treatment", "R-CHOP (rituximab, cyclophosphamide, doxorubicin, vincristine, prednisone) for 6 cycles as standard. Polatuzumab vedotin-R-CHP for previously untreated. CNS prophylaxis for high-risk patients. PET/CT for response assessment.", "A", "Strong",
         ["diffuse large b-cell lymphoma", "dlbcl", "non-hodgkin lymphoma"], ["rituximab", "cyclophosphamide", "doxorubicin", "vincristine", "polatuzumab vedotin"], ["pet scan", "ldh", "cbc", "bone marrow biopsy"], ["dlbcl", "r-chop", "rituximab", "lymphoma"]),
        ("Relapsed DLBCL", "CAR-T cell therapy (axicabtagene ciloleucel, lisocabtagene maraleucel, tisagenlecleucel) for relapsed/refractory after 2+ lines. Bispecific antibodies (glofitamab, epcoritamab) as alternatives. Salvage chemotherapy and ASCT for chemo-sensitive relapse. Polatuzumab-BR for transplant-ineligible.", "A", "Strong",
         ["relapsed dlbcl", "refractory lymphoma"], ["axicabtagene", "tisagenlecleucel", "glofitamab", "epcoritamab"], ["pet scan", "ldh", "cbc"], ["car-t", "bispecific", "relapsed lymphoma"]),
    ]),
    ("NCCN Multiple Myeloma", "NCCN", 2025, [
        ("Newly Diagnosed Myeloma", "Transplant-eligible: VRd induction (bortezomib, lenalidomide, dexamethasone) followed by ASCT and lenalidomide maintenance. Transplant-ineligible: VRd or DRd (daratumumab, lenalidomide, dexamethasone) until progression. Isatuximab-VRd for high-risk cytogenetics.", "A", "Strong",
         ["multiple myeloma", "myeloma"], ["bortezomib", "lenalidomide", "dexamethasone", "daratumumab", "isatuximab"], ["spep", "upep", "free light chains", "bone marrow biopsy", "pet scan"], ["myeloma", "vrd", "transplant", "lenalidomide"]),
        ("Relapsed Myeloma", "Carfilzomib, pomalidomide, or elotuzumab-based regimens for first relapse. Teclistamab or talquetamab (bispecific antibodies) for heavily pretreated. Ide-cel or cilta-cel (BCMA CAR-T) for 4+ prior lines. Belantamab mafodotin, selinexor as additional options.", "A", "Strong",
         ["relapsed myeloma", "refractory myeloma"], ["carfilzomib", "pomalidomide", "teclistamab", "ide-cel", "cilta-cel", "belantamab"], ["spep", "free light chains", "bone marrow"], ["relapsed myeloma", "car-t", "bispecific", "bcma"]),
    ]),

    # ── PULMONOLOGY EXPANSION ──
    ("GOLD COPD Guidelines", "GOLD", 2025, [
        ("COPD Initial Pharmacotherapy", "LAMA monotherapy for Group A (low symptoms, low exacerbation risk). LABA/LAMA combination for Group B (more symptoms). LABA/LAMA/ICS triple therapy for Group E (frequent exacerbations). Blood eosinophils ≥300 favors ICS-containing regimens.", "A", "Strong",
         ["copd", "chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis"], ["tiotropium", "umeclidinium", "formoterol", "salmeterol", "fluticasone", "budesonide"], ["fev1", "fev1/fvc", "eosinophils", "chest x-ray"], ["copd", "gold", "lama", "laba", "triple therapy"]),
        ("COPD Exacerbation Management", "Short-acting bronchodilators (SABA +/- SAMA) for immediate relief. Systemic corticosteroids (prednisone 40mg × 5 days) for moderate-severe exacerbations. Antibiotics for purulent sputum with increased dyspnea/volume. NIV for respiratory acidosis. Reassess maintenance therapy after exacerbation.", "A", "Strong",
         ["copd exacerbation", "copd"], ["albuterol", "ipratropium", "prednisone", "azithromycin", "amoxicillin-clavulanate"], ["fev1", "abg", "chest x-ray", "sputum culture"], ["copd exacerbation", "corticosteroid", "niv", "antibiotic"]),
        ("COPD Non-Pharmacologic Management", "Pulmonary rehabilitation for all symptomatic patients. Smoking cessation is the single most effective intervention. Supplemental oxygen for resting PaO2 ≤55 mmHg or SpO2 ≤88%. Influenza, pneumococcal, COVID-19, and RSV vaccination. Lung volume reduction surgery for select emphysema patients.", "A", "Strong",
         ["copd", "emphysema"], ["varenicline", "bupropion", "nicotine replacement"], ["pao2", "spo2", "6-minute walk test", "ct chest"], ["copd", "pulmonary rehabilitation", "oxygen therapy", "smoking cessation"]),
    ]),
    ("GINA Asthma Guidelines", "GINA", 2025, [
        ("Asthma Step Therapy", "Step 1-2: As-needed low-dose ICS-formoterol (preferred) or as-needed SABA with low-dose ICS. Step 3: Low-dose ICS-LABA maintenance. Step 4: Medium-dose ICS-LABA. Step 5: High-dose ICS-LABA, add LAMA, or biologic therapy. Assess control, inhaler technique, and adherence before stepping up.", "A", "Strong",
         ["asthma", "bronchial asthma"], ["budesonide", "formoterol", "fluticasone", "salmeterol", "montelukast", "tiotropium"], ["fev1", "pef", "feno", "eosinophils"], ["asthma", "step therapy", "ics", "controller"]),
        ("Asthma Action Plans", "Written asthma action plan for all patients. Green zone: well-controlled, continue regular therapy. Yellow zone: increasing symptoms, increase controller or add reliever. Red zone: severe exacerbation, seek emergency care. PEF monitoring for moderate-severe asthma.", "A", "Strong",
         ["asthma", "asthma management"], ["albuterol", "prednisone", "budesonide"], ["pef", "fev1"], ["asthma", "action plan", "self-management", "pef"]),
    ]),
    ("ESC/ERS Pulmonary Hypertension", "ESC/ERS", 2024, [
        ("PAH Diagnosis and Classification", "Right heart catheterization required for definitive diagnosis (mPAP >20 mmHg, PCWP ≤15, PVR >2 WU). Echocardiography for screening. V/Q scan to exclude CTEPH. Functional class assessment with 6MWT. Risk stratification guides treatment intensity.", "A", "Strong",
         ["pulmonary arterial hypertension", "pulmonary hypertension", "pah"], [], ["right heart catheterization", "echocardiogram", "bnp", "6-minute walk test", "v/q scan"], ["pulmonary hypertension", "right heart catheterization", "pah", "diagnosis"]),
        ("PAH Treatment", "Initial combination therapy for intermediate-high risk PAH: PDE5 inhibitor or sGC stimulator plus ERA. IV/SC prostacyclin for high-risk patients. Sotatercept as add-on for inadequate response. Referral for lung transplant for refractory disease.", "A", "Strong",
         ["pulmonary arterial hypertension", "pah"], ["sildenafil", "tadalafil", "ambrisentan", "macitentan", "epoprostenol", "treprostinil", "sotatercept", "riociguat"], ["bnp", "6-minute walk test", "right heart catheterization"], ["pah", "combination therapy", "prostacyclin", "sotatercept"]),
    ]),
    ("AASM Obstructive Sleep Apnea", "AASM", 2024, [
        ("OSA Diagnosis and Treatment", "Polysomnography or home sleep apnea testing for diagnosis. CPAP as first-line for moderate-severe OSA (AHI ≥15). Mandibular advancement device for mild-moderate OSA or CPAP-intolerant. Weight loss, positional therapy, and myofunctional therapy as adjuncts. Hypoglossal nerve stimulation for select CPAP-intolerant patients.", "A", "Strong",
         ["obstructive sleep apnea", "sleep apnea", "osa"], [], ["polysomnography", "ahi", "odi", "epworth sleepiness scale"], ["sleep apnea", "cpap", "ahi", "polysomnography"]),
    ]),
    ("CFF Cystic Fibrosis Guidelines", "CFF", 2024, [
        ("CFTR Modulator Therapy", "Elexacaftor/tezacaftor/ivacaftor (Trikafta) for patients ≥2 years with at least one F508del mutation. Dramatic improvement in FEV1, BMI, pulmonary exacerbations, and sweat chloride. Monitoring: LFTs, ophthalmologic exam, mental health screening. Lung transplant remains option for advanced disease.", "A", "Strong",
         ["cystic fibrosis", "cf"], ["elexacaftor", "tezacaftor", "ivacaftor", "dornase alfa", "hypertonic saline", "azithromycin"], ["fev1", "sweat chloride", "sputum culture", "bmi"], ["cystic fibrosis", "cftr modulator", "trikafta", "f508del"]),
    ]),

    # ── GI EXPANSION ──
    ("AGA NAFLD/NASH Guidelines", "AGA", 2024, [
        ("NAFLD Assessment and Treatment", "FIB-4 score as initial non-invasive fibrosis assessment. Vibration-controlled transient elastography (FibroScan) for further evaluation if FIB-4 indeterminate/high. Resmetirom for NASH with moderate fibrosis (F2-F3). Weight loss ≥7-10% body weight improves steatohepatitis. GLP-1 RAs (semaglutide) for NASH with diabetes or obesity.", "A", "Strong",
         ["nafld", "nash", "fatty liver disease", "metabolic dysfunction-associated steatotic liver disease"], ["resmetirom", "semaglutide", "pioglitazone", "vitamin e"], ["alt", "ast", "fib-4", "fibroscan", "mri-pdff"], ["nafld", "nash", "fibrosis", "resmetirom"]),
    ]),
    ("ACG Inflammatory Bowel Disease - Ulcerative Colitis", "ACG", 2024, [
        ("UC Induction Therapy", "Oral and topical 5-ASA for mild-moderate UC. Oral budesonide MMX for mild-moderate left-sided/extensive disease. Systemic corticosteroids for moderate-severe flares. Biologics (infliximab, vedolizumab, ustekinumab) or tofacitinib for moderate-severe or steroid-dependent UC.", "A", "Strong",
         ["ulcerative colitis", "uc", "inflammatory bowel disease"], ["mesalamine", "budesonide", "prednisone", "infliximab", "vedolizumab", "tofacitinib"], ["calprotectin", "colonoscopy", "crp", "hemoglobin"], ["ulcerative colitis", "5-asa", "biologic", "induction"]),
        ("UC Maintenance and Monitoring", "5-ASA maintenance for mild-moderate UC. Biologic or small molecule maintenance for moderate-severe. Mucosal healing as treatment target. Colonoscopic surveillance for dysplasia starting 8 years after diagnosis. Colectomy for refractory disease or dysplasia.", "A", "Strong",
         ["ulcerative colitis", "uc"], ["mesalamine", "infliximab", "vedolizumab", "ustekinumab", "ozanimod", "tofacitinib"], ["calprotectin", "colonoscopy"], ["uc maintenance", "mucosal healing", "surveillance", "colectomy"]),
    ]),
    ("ACG Crohn's Disease", "ACG", 2024, [
        ("Crohn's Disease Induction", "Oral budesonide for mild ileal/right colonic Crohn's. Systemic corticosteroids for moderate-severe flares. Early biologic therapy (anti-TNF, vedolizumab, ustekinumab, risankizumab) for moderate-severe or high-risk disease. Combination therapy (infliximab + azathioprine) more effective than monotherapy.", "A", "Strong",
         ["crohn's disease", "crohn disease", "inflammatory bowel disease"], ["budesonide", "prednisone", "infliximab", "adalimumab", "ustekinumab", "risankizumab", "vedolizumab"], ["calprotectin", "crp", "colonoscopy", "mre"], ["crohn disease", "biologic", "anti-tnf", "induction"]),
        ("Crohn's Perianal Disease", "MRI pelvis for assessment of perianal fistulas. Seton placement for complex fistulas. Infliximab or adalimumab as first-line medical therapy. Combined surgical and medical approach. Ustekinumab or vedolizumab as second-line. Stem cell therapy under investigation.", "B", "Strong",
         ["perianal crohn's", "crohn disease", "perianal fistula"], ["infliximab", "adalimumab", "metronidazole", "ciprofloxacin"], ["mri pelvis", "exam under anesthesia"], ["perianal", "fistula", "seton", "infliximab"]),
    ]),
    ("ACG Celiac Disease", "ACG", 2024, [
        ("Celiac Disease Diagnosis and Management", "Tissue transglutaminase IgA (tTG-IgA) as initial screening test. Total IgA to exclude IgA deficiency. Duodenal biopsy for confirmation. Strict lifelong gluten-free diet as primary treatment. Monitor tTG-IgA for dietary adherence. Screen for nutritional deficiencies (iron, calcium, vitamin D, B12).", "A", "Strong",
         ["celiac disease", "gluten sensitivity"], [], ["ttg-iga", "total iga", "duodenal biopsy", "iron", "vitamin d"], ["celiac disease", "gluten-free", "ttg", "biopsy"]),
    ]),
    ("ACG Irritable Bowel Syndrome", "ACG", 2024, [
        ("IBS Diagnosis and Treatment", "Rome IV criteria for diagnosis. Limited testing: CBC, CRP, celiac serology, calprotectin. Low FODMAP diet for symptom management. Linaclotide or plecanatide for IBS-C. Rifaximin for IBS-D without constipation. Eluxadoline for IBS-D. Antispasmodics, peppermint oil for abdominal pain. CBT and gut-directed hypnotherapy.", "B", "Strong",
         ["irritable bowel syndrome", "ibs", "ibs-c", "ibs-d"], ["linaclotide", "plecanatide", "rifaximin", "eluxadoline", "lubiprostone", "amitriptyline"], ["cbc", "crp", "calprotectin", "celiac serology"], ["ibs", "fodmap", "linaclotide", "rifaximin"]),
    ]),
    ("AGA Barrett's Esophagus", "AGA", 2024, [
        ("Barrett's Surveillance and Management", "Endoscopic surveillance every 3-5 years for non-dysplastic Barrett's. Annual surveillance for low-grade dysplasia. Endoscopic eradication therapy (RFA, cryotherapy) for confirmed low-grade or high-grade dysplasia. Esophagectomy for invasive adenocarcinoma. PPI therapy for all Barrett's patients.", "A", "Strong",
         ["barrett's esophagus", "esophageal adenocarcinoma", "gerd"], ["omeprazole", "esomeprazole", "pantoprazole"], ["upper endoscopy", "biopsy"], ["barrett's", "surveillance", "ablation", "dysplasia"]),
    ]),
    ("ACG Diverticular Disease", "ACG", 2024, [
        ("Diverticulitis Management", "Uncomplicated diverticulitis: antibiotics may be selectively avoided for mild cases. Oral antibiotics (metronidazole + fluoroquinolone or amoxicillin-clavulanate) for mild-moderate. IV antibiotics for complicated cases. CT abdomen for diagnosis. Elective sigmoid colectomy after multiple episodes or complicated disease.", "A", "Strong",
         ["diverticulitis", "diverticular disease"], ["metronidazole", "ciprofloxacin", "amoxicillin-clavulanate", "piperacillin-tazobactam"], ["ct abdomen", "wbc", "crp"], ["diverticulitis", "antibiotic", "colectomy", "ct scan"]),
    ]),
    ("ACG GI Bleeding", "ACG", 2024, [
        ("Upper GI Bleeding", "Resuscitation and hemodynamic stabilization. Restrictive transfusion strategy (Hb threshold 7 g/dL). PPI infusion before endoscopy. Early upper endoscopy within 24 hours. Endoscopic hemostasis for high-risk stigmata. PPI infusion for 72 hours after endoscopic therapy for high-risk ulcers.", "A", "Strong",
         ["upper gi bleeding", "peptic ulcer bleeding", "variceal bleeding"], ["pantoprazole", "octreotide", "terlipressin"], ["hemoglobin", "inr", "bun", "creatinine", "endoscopy"], ["gi bleeding", "endoscopy", "ppi", "transfusion"]),
        ("Lower GI Bleeding", "Hemodynamic stabilization. CT angiography for active bleeding localization. Colonoscopy within 24 hours after bowel prep for stable patients. Urgent angiographic embolization for hemodynamically significant bleeding. Surgery for refractory bleeding.", "B", "Strong",
         ["lower gi bleeding", "colonic bleeding", "diverticular bleeding"], [], ["hemoglobin", "ct angiography", "colonoscopy", "tagged rbc scan"], ["lower gi bleed", "colonoscopy", "ct angiography", "embolization"]),
    ]),

    # ── NEPHROLOGY EXPANSION ──
    ("KDIGO Diabetic Kidney Disease", "KDIGO", 2024, [
        ("DKD Management", "SGLT2 inhibitors (dapagliflozin, empagliflozin) for eGFR ≥20 with albuminuria. Finerenone (nonsteroidal MRA) for type 2 diabetes with albuminuria and eGFR ≥25. RAS blockade with ACEi or ARB titrated to maximum tolerated dose. GLP-1 RA for cardiovascular and renal benefit. Glycemic target A1c ~7% with individualization.", "A", "Strong",
         ["diabetic kidney disease", "diabetic nephropathy", "ckd", "diabetes"], ["dapagliflozin", "empagliflozin", "finerenone", "lisinopril", "losartan", "semaglutide"], ["egfr", "uacr", "hba1c", "potassium", "creatinine"], ["diabetic kidney disease", "sglt2", "finerenone", "ras blockade"]),
    ]),
    ("KDIGO Dialysis Guidelines", "KDIGO", 2024, [
        ("Hemodialysis Adequacy", "Minimum spKt/V 1.4 per session for thrice-weekly HD. Vascular access: arteriovenous fistula preferred, AV graft second choice, catheter as last resort. Volume assessment and dry weight targeting. Phosphate binder and ESA therapy as indicated. Dialysis initiation based on symptoms, not eGFR threshold.", "A", "Strong",
         ["hemodialysis", "dialysis", "esrd", "ckd stage 5"], ["epoetin alfa", "darbepoetin", "sevelamer", "cinacalcet"], ["kt/v", "hemoglobin", "phosphorus", "pth", "albumin"], ["hemodialysis", "adequacy", "vascular access", "fistula"]),
        ("Peritoneal Dialysis", "PD as valid modality choice equal to HD. Continuous ambulatory PD or automated PD based on patient preference and lifestyle. Weekly Kt/V ≥1.7 target. Peritonitis prevention with exit-site care and touch contamination protocols. Icodextrin for long dwell to improve ultrafiltration.", "B", "Strong",
         ["peritoneal dialysis", "pd", "esrd"], ["icodextrin", "heparin"], ["kt/v", "peritoneal equilibration test", "albumin"], ["peritoneal dialysis", "capd", "apd", "peritonitis"]),
    ]),
    ("KDIGO Kidney Transplant", "KDIGO", 2024, [
        ("Post-Transplant Immunosuppression", "Induction with basiliximab or anti-thymocyte globulin. Maintenance triple therapy: tacrolimus, mycophenolate mofetil, and corticosteroids. Tacrolimus trough target 5-8 ng/mL long-term. Steroid minimization or withdrawal after 1 year in low-risk. Monitor for donor-specific antibodies.", "A", "Strong",
         ["kidney transplant", "renal transplant"], ["tacrolimus", "mycophenolate", "prednisone", "basiliximab", "anti-thymocyte globulin"], ["creatinine", "tacrolimus level", "bk virus pcr", "dsa"], ["kidney transplant", "immunosuppression", "tacrolimus", "rejection"]),
    ]),

    # ── NEUROLOGY EXPANSION ──
    ("AAN Epilepsy Guidelines", "AAN", 2024, [
        ("Epilepsy First-Line Therapy", "Levetiracetam or lamotrigine as broad-spectrum first-line for focal and generalized epilepsy. Carbamazepine or oxcarbazepine for focal epilepsy. Valproate for generalized epilepsy (avoid in women of childbearing potential). Ethosuximide for childhood absence epilepsy. Monotherapy preferred initially.", "A", "Strong",
         ["epilepsy", "seizure disorder", "focal epilepsy", "generalized epilepsy"], ["levetiracetam", "lamotrigine", "carbamazepine", "valproate", "oxcarbazepine", "ethosuximide"], ["eeg", "mri brain", "drug levels"], ["epilepsy", "antiseizure", "levetiracetam", "lamotrigine"]),
        ("Drug-Resistant Epilepsy", "Defined as failure of 2 adequate ASM trials. Refer for epilepsy surgery evaluation. Temporal lobectomy for mesial temporal sclerosis. Vagus nerve stimulation or responsive neurostimulation for non-surgical candidates. Dietary therapy (ketogenic, modified Atkins) as adjunct.", "A", "Strong",
         ["drug-resistant epilepsy", "refractory epilepsy"], ["clobazam", "cenobamate", "brivaracetam"], ["eeg video monitoring", "mri brain", "pet scan"], ["drug-resistant epilepsy", "surgery", "vns", "ketogenic diet"]),
    ]),
    ("AAN Peripheral Neuropathy", "AAN", 2024, [
        ("Diabetic Peripheral Neuropathy", "Glycemic control as foundation to prevent progression. Duloxetine, pregabalin, or gabapentin as first-line for neuropathic pain. TCAs (amitriptyline, nortriptyline) as alternatives. Topical capsaicin or lidocaine for localized symptoms. Avoid opioids as first-line. Annual monofilament foot exam.", "A", "Strong",
         ["diabetic neuropathy", "peripheral neuropathy", "neuropathic pain"], ["duloxetine", "pregabalin", "gabapentin", "amitriptyline", "capsaicin"], ["nerve conduction study", "emg", "hba1c", "vitamin b12"], ["diabetic neuropathy", "neuropathic pain", "duloxetine", "pregabalin"]),
    ]),
    ("AAN Myasthenia Gravis", "AAN", 2024, [
        ("Myasthenia Gravis Treatment", "Pyridostigmine as initial symptomatic therapy. Corticosteroids for inadequate response. Steroid-sparing agents: azathioprine, mycophenolate. Rituximab for refractory MG. Efgartigimod and rozanolixizumab (FcRn inhibitors) for generalized MG. Thymectomy for thymoma and non-thymomatous AChR+ generalized MG.", "A", "Strong",
         ["myasthenia gravis", "mg", "neuromuscular junction disorder"], ["pyridostigmine", "prednisone", "azathioprine", "mycophenolate", "rituximab", "efgartigimod"], ["achr antibody", "musk antibody", "ct chest", "repetitive nerve stimulation"], ["myasthenia gravis", "pyridostigmine", "thymectomy", "fcrn"]),
    ]),

    # ── INFECTIOUS DISEASE EXPANSION ──
    ("IDSA/ATS Tuberculosis", "IDSA/ATS", 2024, [
        ("Latent TB Treatment", "Rifampin 4 months or isoniazid/rifapentine 3 months (12 weekly doses) preferred over 9-month isoniazid. IGRA or TST for screening. Target testing for high-risk groups. Rule out active TB before treatment. Monitor LFTs monthly for hepatotoxicity.", "A", "Strong",
         ["latent tuberculosis", "ltbi", "tuberculosis screening"], ["isoniazid", "rifampin", "rifapentine"], ["igra", "tuberculin skin test", "chest x-ray", "sputum afb"], ["latent tb", "isoniazid", "rifampin", "igra"]),
        ("Active TB Treatment", "RIPE regimen: rifampin, isoniazid, pyrazinamide, ethambutol for 2 months induction, followed by rifampin and isoniazid for 4 months continuation. DOT recommended. Pyridoxine with isoniazid. Drug susceptibility testing for all initial isolates. Extended treatment for CNS, bone, or MDR-TB.", "A", "Strong",
         ["active tuberculosis", "pulmonary tuberculosis", "tb"], ["rifampin", "isoniazid", "pyrazinamide", "ethambutol", "pyridoxine"], ["sputum afb", "sputum culture", "chest x-ray", "genexpert"], ["tuberculosis", "ripe", "dot", "drug susceptibility"]),
    ]),
    ("IDSA Invasive Fungal Infections", "IDSA", 2024, [
        ("Invasive Aspergillosis", "Voriconazole as first-line for invasive aspergillosis. Isavuconazole as alternative with fewer drug interactions. Liposomal amphotericin B for azole-intolerant or refractory cases. CT chest: halo sign early, air crescent sign late. Galactomannan and beta-D-glucan for diagnosis.", "A", "Strong",
         ["invasive aspergillosis", "aspergillosis", "fungal infection"], ["voriconazole", "isavuconazole", "amphotericin b", "caspofungin"], ["galactomannan", "beta-d-glucan", "ct chest", "bai"], ["aspergillosis", "voriconazole", "halo sign", "galactomannan"]),
        ("Invasive Candidiasis", "Echinocandin (micafungin, caspofungin, anidulafungin) as first-line for candidemia. Remove central venous catheters when feasible. Fluconazole step-down for susceptible Candida species after clinical improvement. Ophthalmologic exam for all candidemia. Minimum 14 days of therapy after blood culture clearance.", "A", "Strong",
         ["candidemia", "invasive candidiasis", "fungal infection"], ["micafungin", "caspofungin", "anidulafungin", "fluconazole", "amphotericin b"], ["blood culture", "beta-d-glucan", "creatinine"], ["candidemia", "echinocandin", "candida", "catheter removal"]),
    ]),
    ("IDSA Osteomyelitis", "IDSA", 2024, [
        ("Osteomyelitis Treatment", "Culture-directed antibiotic therapy for 6 weeks for native vertebral osteomyelitis. Surgical debridement for prosthetic joint infection or chronic osteomyelitis. MRSA: vancomycin or daptomycin IV then oral linezolid or TMP-SMX. Gram-negative: fluoroquinolone or beta-lactam. MRI as preferred imaging.", "A", "Strong",
         ["osteomyelitis", "bone infection", "prosthetic joint infection"], ["vancomycin", "daptomycin", "cefazolin", "ciprofloxacin", "linezolid"], ["mri", "bone biopsy culture", "esr", "crp"], ["osteomyelitis", "debridement", "vancomycin", "prosthetic joint"]),
    ]),

    # ── ENDOCRINOLOGY EXPANSION ──
    ("ADA Type 2 Diabetes Standards of Care", "ADA", 2025, [
        ("T2DM Glycemic Management", "Metformin as first-line pharmacotherapy. SGLT2 inhibitor or GLP-1 RA for patients with established ASCVD, heart failure, or CKD regardless of A1c. Tirzepatide or semaglutide for patients needing weight loss. Insulin therapy when A1c >10% or symptomatic hyperglycemia. A1c target <7% for most adults; individualize for elderly/comorbid.", "A", "Strong",
         ["type 2 diabetes", "diabetes mellitus", "t2dm"], ["metformin", "semaglutide", "tirzepatide", "empagliflozin", "dapagliflozin", "insulin glargine", "liraglutide"], ["hba1c", "fasting glucose", "egfr", "uacr"], ["type 2 diabetes", "metformin", "glp-1", "sglt2"]),
        ("T2DM Cardiovascular Risk Reduction", "Statin therapy for all adults with diabetes aged 40-75. High-intensity statin for diabetes with ASCVD. ACE inhibitor or ARB for hypertension and albuminuria. Aspirin for secondary prevention. GLP-1 RA with proven CV benefit (liraglutide, semaglutide, dulaglutide) for established ASCVD.", "A", "Strong",
         ["type 2 diabetes", "cardiovascular risk", "atherosclerosis"], ["atorvastatin", "rosuvastatin", "lisinopril", "losartan", "aspirin", "liraglutide", "semaglutide"], ["hba1c", "ldl", "uacr", "blood pressure"], ["diabetes", "cardiovascular", "statin", "aspirin"]),
        ("T2DM Technology and Monitoring", "CGM recommended for patients on intensive insulin therapy. Time in range (70-180 mg/dL) >70% as target. CGM can be considered for patients on basal insulin or non-insulin therapies. Insulin pump therapy for select patients with T2DM. Regular A1c monitoring every 3 months if not at goal.", "B", "Strong",
         ["type 2 diabetes", "glucose monitoring"], ["insulin lispro", "insulin aspart", "insulin glargine"], ["cgm", "hba1c", "time in range"], ["cgm", "continuous glucose monitoring", "time in range", "insulin pump"]),
    ]),
    ("ADA/EASD Type 1 Diabetes", "ADA/EASD", 2025, [
        ("T1DM Insulin Therapy", "Basal-bolus insulin or insulin pump as standard of care. Rapid-acting analogs (lispro, aspart, glulisine) for bolus. Long-acting analogs (glargine U300, degludec) for basal. Hybrid closed-loop (HCL) insulin pump systems for improved time in range. Carbohydrate counting for flexible dosing.", "A", "Strong",
         ["type 1 diabetes", "t1dm"], ["insulin glargine", "insulin degludec", "insulin lispro", "insulin aspart", "pramlintide"], ["hba1c", "cgm", "c-peptide", "gad antibodies"], ["type 1 diabetes", "insulin pump", "closed loop", "basal-bolus"]),
        ("T1DM Screening and Prevention", "Screen first-degree relatives with islet autoantibodies (GAD65, IA-2, ZnT8, IAA). Teplizumab for stage 2 T1DM (2+ autoantibodies + dysglycemia) to delay stage 3 onset. Regular OGTT monitoring for antibody-positive individuals. DKA prevention education.", "A", "Strong",
         ["type 1 diabetes prevention", "presymptomatic t1dm"], ["teplizumab"], ["gad antibodies", "ia-2 antibodies", "ogtt", "c-peptide"], ["type 1 diabetes", "autoantibody", "teplizumab", "screening"]),
    ]),
    ("Endocrine Society Cushing Syndrome", "Endocrine Society", 2024, [
        ("Cushing Syndrome Diagnosis", "Screen with 24-hour urinary free cortisol, late-night salivary cortisol, or 1mg overnight dexamethasone suppression test. At least two positive first-line tests needed. ACTH level to differentiate ACTH-dependent from independent. MRI pituitary for ACTH-dependent. CT adrenals for ACTH-independent.", "A", "Strong",
         ["cushing syndrome", "cushing disease", "hypercortisolism"], ["dexamethasone"], ["24-hour urine cortisol", "late-night salivary cortisol", "acth", "mri pituitary", "ct adrenals"], ["cushing syndrome", "cortisol", "dexamethasone suppression", "acth"]),
    ]),
    ("Endocrine Society PCOS", "Endocrine Society", 2024, [
        ("PCOS Diagnosis and Management", "Rotterdam criteria: 2 of 3 (oligo/anovulation, hyperandrogenism, polycystic ovaries). Combined OCP as first-line for menstrual regulation and hyperandrogenism. Metformin for metabolic features. Spironolactone for hirsutism. Letrozole as first-line ovulation induction. Screen for diabetes, dyslipidemia, OSA, depression.", "A", "Strong",
         ["polycystic ovary syndrome", "pcos", "hyperandrogenism"], ["combined oral contraceptive", "metformin", "spironolactone", "letrozole"], ["testosterone", "dheas", "lh", "fsh", "ogtt", "pelvic ultrasound"], ["pcos", "hyperandrogenism", "metformin", "ovulation induction"]),
    ]),

    # ── ADDITIONAL SPECIALTIES ──
    # Allergy/Immunology
    ("EAACI/WAO Anaphylaxis Guidelines", "EAACI/WAO", 2024, [
        ("Anaphylaxis Management", "Intramuscular epinephrine (0.3-0.5mg adult, 0.01mg/kg pediatric) in mid-anterolateral thigh as first-line treatment. Position supine with legs elevated unless respiratory distress. IV fluids for hypotension. Second dose epinephrine if no improvement in 5-15 minutes. Observation for 4-6 hours minimum. Prescribe epinephrine auto-injector at discharge.", "A", "Strong",
         ["anaphylaxis", "allergic reaction", "anaphylactic shock"], ["epinephrine", "diphenhydramine", "methylprednisolone", "albuterol"], ["tryptase"], ["anaphylaxis", "epinephrine", "auto-injector", "allergic reaction"]),
        ("Food Allergy Management", "Strict allergen avoidance as cornerstone. Epinephrine auto-injector for all patients with IgE-mediated food allergy. Oral immunotherapy (OIT) for peanut allergy in select patients aged 4-17. Component-resolved diagnostics for risk stratification. Annual re-evaluation for possible tolerance development.", "A", "Strong",
         ["food allergy", "peanut allergy", "ige-mediated allergy"], ["epinephrine", "omalizumab"], ["specific ige", "skin prick test", "component testing", "oral food challenge"], ["food allergy", "oral immunotherapy", "peanut", "epinephrine"]),
    ]),

    # Geriatrics
    ("AGS Geriatric Guidelines", "AGS", 2024, [
        ("Falls Prevention in Older Adults", "Multifactorial assessment for fall risk: gait and balance, medications, vision, orthostatic hypotension, home hazards. Exercise programs (balance, strength training) reduce falls by 23%. Vitamin D supplementation if deficient. Deprescribing fall-risk medications (benzodiazepines, anticholinergics, opioids). Home safety modifications.", "A", "Strong",
         ["falls prevention", "geriatric falls", "elderly falls"], ["vitamin d", "calcium"], ["25-hydroxyvitamin d", "orthostatic vitals", "gait assessment"], ["falls prevention", "exercise", "deprescribing", "geriatric"]),
        ("Polypharmacy Management", "Regular medication review at every clinical encounter. Deprescribe medications without clear indication. Use STOPP/START criteria or Beers criteria to identify potentially inappropriate medications. Consider drug-drug interactions, renal dosing, and anticholinergic burden. Prioritize medications aligned with goals of care.", "A", "Strong",
         ["polypharmacy", "medication management", "geriatric prescribing"], [], ["creatinine clearance", "medication list"], ["polypharmacy", "deprescribing", "beers criteria", "medication review"]),
        ("Delirium Prevention in Hospitalized Elderly", "HELP (Hospital Elder Life Program) reduces delirium by 40%. Non-pharmacologic interventions: reorientation, sleep protocols, early mobilization, hydration, vision/hearing aids. Avoid precipitants: benzodiazepines, anticholinergics, urinary catheters, physical restraints. Screen with CAM or 4AT.", "A", "Strong",
         ["delirium", "acute confusion", "geriatric delirium"], [], ["cam", "4at", "metabolic panel", "urinalysis"], ["delirium", "prevention", "help program", "non-pharmacologic"]),
    ]),

    # Pain Medicine
    ("CDC Opioid Prescribing Guidelines", "CDC", 2024, [
        ("Chronic Non-Cancer Pain", "Non-opioid therapies preferred as first-line for chronic pain: NSAIDs, acetaminophen, duloxetine, gabapentinoids, topical agents. If opioids initiated, start at lowest effective dose. Avoid >90 MME/day. Re-evaluate within 1-4 weeks. Naloxone co-prescribing for ≥50 MME/day or concurrent benzodiazepine use.", "A", "Strong",
         ["chronic pain", "non-cancer pain", "opioid prescribing"], ["ibuprofen", "acetaminophen", "duloxetine", "gabapentin", "naloxone", "buprenorphine"], ["pain score", "urine drug screen", "pdmp"], ["chronic pain", "opioid", "non-opioid", "naloxone"]),
        ("Opioid Use Disorder Treatment", "Buprenorphine or methadone as first-line medications for OUD. Buprenorphine can be initiated in office-based setting. Extended-release naltrexone for patients who have completed detoxification. Psychosocial support as adjunct. Harm reduction including naloxone distribution.", "A", "Strong",
         ["opioid use disorder", "opioid addiction", "substance use disorder"], ["buprenorphine", "methadone", "naltrexone", "naloxone"], ["urine drug screen"], ["opioid use disorder", "buprenorphine", "methadone", "mat"]),
    ]),

    # Palliative Care
    ("NCCN Palliative Care Guidelines", "NCCN", 2025, [
        ("Cancer Pain Management", "WHO analgesic ladder: non-opioids → weak opioids → strong opioids. Oral morphine, oxycodone, or hydromorphone for moderate-severe cancer pain. Breakthrough dosing: 10-20% of total daily opioid dose. Adjuvants: gabapentin for neuropathic pain, dexamethasone for bone pain, bisphosphonates/denosumab for bone metastases. Palliative radiation for painful bone metastases.", "A", "Strong",
         ["cancer pain", "palliative care", "bone metastases"], ["morphine", "oxycodone", "hydromorphone", "fentanyl patch", "gabapentin", "dexamethasone", "denosumab"], ["pain score", "performance status"], ["cancer pain", "opioid", "palliative", "who ladder"]),
        ("Symptom Management in Advanced Cancer", "Nausea: ondansetron, metoclopramide, dexamethasone, olanzapine based on etiology. Dyspnea: low-dose opioids, oxygen for hypoxemia, fan therapy. Fatigue: address reversible causes, methylphenidate for selected patients. Malignant bowel obstruction: octreotide, dexamethasone, and antiemetics for inoperable.", "B", "Strong",
         ["advanced cancer", "palliative care", "end-of-life"], ["ondansetron", "metoclopramide", "dexamethasone", "olanzapine", "morphine", "methylphenidate", "octreotide"], ["performance status", "electrolytes"], ["palliative", "symptom management", "nausea", "dyspnea"]),
    ]),

    # Sleep Medicine
    ("AASM Insomnia Guidelines", "AASM", 2024, [
        ("Chronic Insomnia Treatment", "Cognitive behavioral therapy for insomnia (CBT-I) as first-line treatment. Pharmacotherapy if CBT-I unavailable or insufficient: suvorexant, lemborexant (orexin receptor antagonists), or low-dose doxepin. Short-term use of benzodiazepine receptor agonists (zolpidem, eszopiclone). Avoid long-term benzodiazepine use.", "A", "Strong",
         ["insomnia", "chronic insomnia", "sleep disorder"], ["suvorexant", "lemborexant", "doxepin", "zolpidem", "eszopiclone", "melatonin"], ["sleep diary", "actigraphy", "polysomnography"], ["insomnia", "cbt-i", "orexin", "sleep hygiene"]),
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
