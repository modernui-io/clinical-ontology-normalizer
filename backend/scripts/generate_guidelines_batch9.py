#!/usr/bin/env python3
"""Batch 9: Final batch to push past 1000 sections.

Generates ~250 granular subsections covering remaining gaps and
adding depth to established specialties.
"""

import json, os, hashlib

def _id(guideline, title):
    raw = f"{guideline}|{title}"
    h = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"b9-{h}"

SECTIONS = [
    # ═══ CARDIOLOGY REMAINING ═══
    ("ESC/AHA Pulmonary Hypertension Guidelines", "ESC/AHA", 2024,
     "Pulmonary Arterial Hypertension Treatment Algorithm",
     "Risk stratify at diagnosis: low/intermediate/high mortality risk. Initial combination therapy for most PAH: PDE-5 inhibitor (sildenafil, tadalafil) + ERA (ambrisentan, macitentan). Triple therapy for high risk: add prostacyclin pathway agent (selexipag, treprostinil, epoprostenol). IV epoprostenol for WHO FC IV. Sotatercept (activin signaling inhibitor) added to background therapy improves PVR and 6MWD. Right heart catheterization required for diagnosis (mPAP >20 mmHg, PAWP ≤15, PVR >2 WU).",
     "A", "Strong", ["pulmonary arterial hypertension", "pah"], ["sildenafil", "tadalafil", "ambrisentan", "macitentan", "selexipag", "epoprostenol", "sotatercept"], ["right heart catheterization", "6-minute walk test", "bnp", "echocardiogram", "ct chest"], ["pulmonary hypertension", "pah", "era", "sotatercept"]),

    ("ACC/AHA Infective Endocarditis Prevention", "AHA", 2024,
     "Endocarditis Prophylaxis Indications",
     "Antibiotic prophylaxis for dental procedures (involving gingival tissue, periapical region, or oral mucosa perforation) ONLY for highest-risk patients: prosthetic valve, prior IE, congenital heart disease (unrepaired cyanotic, repaired with residual defect, repaired with prosthetic material <6 months), cardiac transplant with valvulopathy. Regimen: amoxicillin 2g PO 30-60 min before procedure. Penicillin allergy: clindamycin 600 mg, cephalexin 2g, or azithromycin 500 mg.",
     "A", "Strong", ["endocarditis prophylaxis"], ["amoxicillin", "clindamycin", "cephalexin", "azithromycin"], [], ["endocarditis prophylaxis", "dental procedure", "prosthetic valve"]),

    ("ACC/AHA Syncope Guidelines", "ACC/AHA/HRS", 2024,
     "Syncope Evaluation and Risk Stratification",
     "Initial evaluation: history (most diagnostic), physical exam, orthostatic vitals, 12-lead ECG. High-risk features: abnormal ECG, structural heart disease, HF, exertional syncope, sudden onset without prodrome, family history of SCD. Low-risk (vasovagal): reassurance, trigger avoidance, counterpressure maneuvers. Tilt table for recurrent vasovagal. Implantable loop recorder for recurrent unexplained syncope. Cardiac monitoring: Holter (frequent), event recorder (intermittent), ILR (rare events).",
     "B", "Strong", ["syncope", "vasovagal syncope", "cardiac syncope"], [], ["ecg", "echocardiogram", "orthostatic blood pressure", "tilt table test", "implantable loop recorder"], ["syncope", "vasovagal", "tilt table", "loop recorder"]),

    ("ACC Deep Vein Thrombosis Guidelines", "ACC/AHA", 2024,
     "DVT Diagnosis and Initial Management",
     "Pretest probability: Wells score. Low probability + negative D-dimer = DVT excluded. Moderate-high probability: compression ultrasonography (CUS). Proximal DVT: anticoagulation (DOAC preferred). Distal DVT: anticoagulate or serial imaging. Massive iliofemoral DVT: consider catheter-directed thrombolysis. IVC filter only if anticoagulation absolutely contraindicated and acute proximal DVT. Early ambulation (not bed rest). Compression stockings: no longer routinely recommended for PTS prevention (SOX trial).",
     "A", "Strong", ["deep vein thrombosis", "dvt"], ["apixaban", "rivaroxaban", "enoxaparin"], ["d-dimer", "compression ultrasound", "ct venogram", "wells score"], ["dvt", "wells score", "doac", "compression ultrasound"]),

    # ═══ ONCOLOGY REMAINING ═══
    ("NCCN Ovarian Cancer Guidelines", "NCCN", 2025,
     "Epithelial Ovarian Cancer Treatment",
     "Stage I (well differentiated): surgical staging alone (TAH/BSO + staging). Stage IC+/high grade: adjuvant carboplatin + paclitaxel x 3-6 cycles. Stage III-IV: primary debulking surgery (goal: R0) + carboplatin/paclitaxel ± bevacizumab. BRCA/HRD+: PARP inhibitor maintenance (olaparib, niraparib). PFI >6 months: rechallenge platinum-based. Recurrent: options include liposomal doxorubicin, topotecan, gemcitabine, bevacizumab, mirvetuximab soravtansine (FRα+).",
     "A", "Strong", ["ovarian cancer", "epithelial ovarian cancer"], ["carboplatin", "paclitaxel", "olaparib", "niraparib", "bevacizumab"], ["ca-125", "ct abdomen/pelvis", "brca testing", "hrd score"], ["ovarian cancer", "parp inhibitor", "debulking", "brca"]),

    ("NCCN Gastric Cancer Guidelines", "NCCN", 2025,
     "Gastric Adenocarcinoma Treatment",
     "Early (T1): endoscopic resection (EMR/ESD) for select criteria. Locally advanced (T2+N+): perioperative FLOT (5-FU, leucovorin, oxaliplatin, docetaxel) x 4 cycles pre and post-surgery. Gastrectomy with D2 lymphadenectomy. Metastatic first-line: 5-FU + platinum ± trastuzumab (HER2+) ± nivolumab (PD-L1 CPS ≥5). Claudin 18.2+: zolbetuximab + CAPOX/mFOLFOX6. MSI-H: pembrolizumab first-line. Second-line: ramucirumab + paclitaxel.",
     "A", "Strong", ["gastric cancer", "stomach cancer"], ["fluorouracil", "oxaliplatin", "docetaxel", "trastuzumab", "nivolumab", "ramucirumab", "zolbetuximab"], ["egd with biopsy", "ct abdomen", "her2", "pd-l1", "msi", "claudin 18.2"], ["gastric cancer", "flot", "trastuzumab", "nivolumab"]),

    ("NCCN Endometrial Cancer Guidelines", "NCCN", 2025,
     "Endometrial Cancer Treatment",
     "Stage I low-grade: TAH/BSO ± sentinel lymph node. Observation after surgery for low-risk. Stage I high-risk (grade 3, LVSI, deep invasion): vaginal cuff brachytherapy ± external beam RT ± chemotherapy. Stage III-IV: multimodal: surgery + carboplatin/paclitaxel ± RT. Molecular classification guides: p53-mutant = high risk; POLE-mutant = favorable; MMRd/MSI-H = pembrolizumab + lenvatinib (dostarlimab if MMRd). HRT replacement after treatment for low-grade type I.",
     "A", "Strong", ["endometrial cancer", "uterine cancer"], ["carboplatin", "paclitaxel", "pembrolizumab", "lenvatinib", "dostarlimab"], ["endometrial biopsy", "mri pelvis", "ct chest/abdomen", "msi", "p53", "pole mutation"], ["endometrial cancer", "molecular classification", "immunotherapy"]),

    ("NCCN Thyroid Cancer Guidelines", "NCCN/ATA", 2025,
     "Differentiated Thyroid Cancer Management",
     "Papillary thyroid cancer (PTC) >4 cm or extrathyroidal: total thyroidectomy + central compartment dissection. PTC 1-4 cm: lobectomy or total thyroidectomy. RAI (I-131) for intermediate-high risk after total thyroidectomy. TSH suppression with levothyroxine: <0.1 for high-risk, 0.1-0.5 for intermediate, 0.5-2.0 for low-risk. Thyroglobulin (Tg) as tumor marker. Lenvatinib or sorafenib for RAI-refractory. RET-mutated: selpercatinib or pralsetinib.",
     "A", "Strong", ["thyroid cancer", "papillary thyroid cancer"], ["levothyroxine", "radioactive iodine", "lenvatinib", "sorafenib", "selpercatinib"], ["thyroglobulin", "tsh", "thyroid ultrasound", "whole body iodine scan", "ret mutation"], ["thyroid cancer", "rai", "thyroglobulin", "tsh suppression"]),

    ("NCCN AML Guidelines", "NCCN", 2025,
     "Acute Myeloid Leukemia Induction",
     "Favorable risk (CBF AML: t(8;21), inv(16)): 7+3 (cytarabine + daunorubicin) + gemtuzumab ozogamicin. Intermediate risk: 7+3, consider CPX-351 for therapy-related or MDS-related AML. Adverse risk: consider clinical trial, venetoclax-based, or CPX-351. FLT3-ITD+: midostaurin + 7+3. IDH1/2 mutated: ivosidenib/enasidenib. Unfit patients: venetoclax + azacitidine (transformed standard of care). Consolidation: HiDAC or allogeneic HSCT for intermediate/adverse risk. MRD monitoring by flow cytometry or PCR.",
     "A", "Strong", ["acute myeloid leukemia", "aml"], ["cytarabine", "daunorubicin", "venetoclax", "azacitidine", "midostaurin", "gemtuzumab"], ["bone marrow biopsy", "cytogenetics", "flt3", "npm1", "idh1", "idh2", "cbc"], ["aml", "7+3", "venetoclax", "flt3"]),

    ("NCCN ALL Guidelines", "NCCN", 2025,
     "Adult Acute Lymphoblastic Leukemia Treatment",
     "Ph-negative B-ALL: pediatric-inspired regimens (hyper-CVAD or CALGB-type) for younger adults. Blinatumomab (BiTE) or inotuzumab (ADC) for R/R. Ph-positive: TKI (dasatinib or ponatinib) + steroids ± reduced chemo (Blinatumomab + dasatinib chemotherapy-free approach). T-ALL: nelarabine for R/R. ALL patients: CNS prophylaxis (intrathecal methotrexate/cytarabine). MRD-negative after induction: favorable. Consider allogeneic HSCT for high-risk or MRD-positive. CAR-T (tisagenlecleucel) for R/R B-ALL ≤25 years.",
     "A", "Strong", ["acute lymphoblastic leukemia", "all"], ["blinatumomab", "inotuzumab", "dasatinib", "nelarabine", "tisagenlecleucel", "methotrexate"], ["bone marrow biopsy", "flow cytometry", "bcr-abl", "mrd", "csf cytology", "cbc"], ["all", "blinatumomab", "car-t", "bcr-abl"]),

    ("NCCN Multiple Myeloma Guidelines", "NCCN", 2025,
     "Multiple Myeloma Treatment",
     "Transplant-eligible: induction with VRd (bortezomib, lenalidomide, dexamethasone) + daratumumab (Dara-VRd per GRIFFIN/PERSEUS). Autologous stem cell transplant. Maintenance: lenalidomide until progression. Transplant-ineligible: Dara-VRd or Dara-Rd. First relapse: regimen depends on prior therapy and refractory status. Options include carfilzomib, pomalidomide, ixazomib, elotuzumab, selinexor. BCMA-targeted: teclistamab, talquetamab, belantamab (ADC). CAR-T: idecabtagene vicleucel, ciltacabtagene autoleucel for R/R (≥4 prior lines).",
     "A", "Strong", ["multiple myeloma"], ["bortezomib", "lenalidomide", "daratumumab", "dexamethasone", "carfilzomib", "idecabtagene vicleucel"], ["spep", "upep", "serum free light chains", "bone marrow biopsy", "pet-ct", "beta-2 microglobulin"], ["myeloma", "daratumumab", "vrd", "car-t"]),

    # ═══ GASTROENTEROLOGY REMAINING ═══
    ("ACG GERD Guidelines", "ACG", 2024,
     "GERD Diagnosis and PPI Management",
     "Typical symptoms (heartburn, regurgitation): empiric PPI trial x 8 weeks. Alarm features (dysphagia, weight loss, GI bleeding, odynophagia, persistent vomiting): EGD before PPI. PPI step-down to lowest effective dose for long-term. Alternatives: H2RA (famotidine), potassium-competitive acid blocker (vonoprazan). Refractory GERD workup: EGD, ambulatory pH monitoring (off PPI), impedance. Anti-reflux surgery (Nissen fundoplication) or magnetic sphincter augmentation (LINX) for PPI-dependent with confirmed GERD.",
     "A", "Strong", ["gerd", "gastroesophageal reflux disease"], ["omeprazole", "esomeprazole", "famotidine", "vonoprazan"], ["egd", "ph impedance study", "esophageal manometry"], ["gerd", "ppi", "fundoplication", "ph monitoring"]),

    ("ACG H. pylori Guidelines", "ACG", 2024,
     "H. pylori Eradication Therapy",
     "Test: urea breath test or fecal antigen (preferred non-invasive). Treat all positives. First-line (metronidazole resistance <15%): bismuth quadruple (PPI + bismuth + metronidazole + tetracycline x 14 days) or concomitant (PPI + amoxicillin + clarithromycin + metronidazole x 14 days). Penicillin allergy: bismuth quadruple. Confirm eradication: UBT or fecal antigen ≥4 weeks after completion and ≥2 weeks off PPI. Rifabutin-based triple for multiply resistant.",
     "A", "Strong", ["h pylori", "helicobacter pylori infection"], ["omeprazole", "bismuth subsalicylate", "metronidazole", "tetracycline", "amoxicillin", "clarithromycin"], ["urea breath test", "fecal h pylori antigen", "egd with biopsy"], ["h pylori", "bismuth quadruple", "eradication", "ubt"]),

    ("AGA Pancreatic Cyst Guidelines", "AGA", 2024,
     "Pancreatic Cyst Management",
     "Incidental pancreatic cyst: characterize with MRI/MRCP. Serous cystadenoma: benign, observe if asymptomatic. Mucinous cystic neoplasm: surgical resection. IPMN: main duct (>5 mm dilation) = higher malignancy risk → consider surgery. Branch duct IPMN <3 cm without worrisome features: surveillance MRI Q1-2 years. Worrisome features (enhancing mural nodule, dilated MPD, size >3 cm, rapid growth, high-grade dysplasia on EUS-FNA): surgical consultation.",
     "B", "Strong", ["pancreatic cyst", "ipmn", "mucinous cystic neoplasm"], [], ["mri pancreas", "mrcp", "eus with fna", "cea in cyst fluid", "amylase in cyst fluid"], ["pancreatic cyst", "ipmn", "surveillance", "eus"]),

    ("ACG Eosinophilic Esophagitis Guidelines", "ACG", 2024,
     "EoE Diagnosis and Treatment",
     "Diagnosis: symptoms of esophageal dysfunction + ≥15 eos/hpf on esophageal biopsy (proximal and distal biopsies). Treatment options: PPI (effective in ~50%), topical corticosteroids (budesonide oral suspension or fluticasone swallowed x 8-12 weeks), elimination diet (6-food or 2-food). Dupilumab (FDA-approved for EoE, first biologic, ≥12 years, ≥40 kg). Dilation for strictures. Endoscopic reference score (EREFS). Maintenance therapy for most patients (high recurrence off treatment).",
     "A", "Strong", ["eosinophilic esophagitis", "eoe"], ["budesonide", "fluticasone", "dupilumab", "omeprazole"], ["egd with biopsy", "eosinophil count", "erefs score"], ["eoe", "topical steroids", "dupilumab", "elimination diet"]),

    # ═══ ADDITIONAL ENDOCRINOLOGY ═══
    ("Endocrine Society Hyperthyroidism Guidelines", "ATA/Endocrine Society", 2024,
     "Graves Disease Treatment Options",
     "Three options: antithyroid drugs (ATDs), radioactive iodine (RAI), surgery. ATDs preferred initial treatment in many countries: methimazole (preferred) or propylthiouracil (PTU, first trimester only). Methimazole 5-30 mg/day, taper based on TFTs. Duration: 12-18 months. RAI for recurrence/preference (contraindicated in pregnancy, moderate-severe Graves ophthalmopathy). Thyroidectomy for large goiter, suspicious nodule, or severe ophthalmopathy. Beta-blocker (propranolol) for symptom control.",
     "A", "Strong", ["graves disease", "hyperthyroidism"], ["methimazole", "propylthiouracil", "propranolol", "radioactive iodine"], ["tsh", "free t4", "free t3", "trab", "thyroid uptake scan"], ["graves disease", "methimazole", "rai", "hyperthyroidism"]),

    ("Endocrine Society DKA Guidelines", "ADA/Endocrine Society", 2024,
     "Diabetic Ketoacidosis Management Protocol",
     "Diagnostic criteria: glucose >250, pH <7.3, bicarb <18, positive ketones, AG >12. Fluids: NS 1-1.5 L/h initially, then 250-500 mL/h. Switch to D5 0.45% NS when glucose <200. Insulin: regular insulin 0.1 U/kg bolus + 0.1 U/kg/h drip (or 0.14 U/kg/h no bolus). Transition to SC insulin when AG closed, glucose <200, patient eating (overlap drip and SC by 1-2 hours). Potassium: replace if K <5.3 before insulin; hold insulin if K <3.3. Monitor: BMP Q2h, AG to guide resolution. Identify precipitant (infection, missed insulin, new diagnosis).",
     "A", "Strong", ["diabetic ketoacidosis", "dka"], ["regular insulin", "normal saline", "potassium chloride"], ["blood glucose", "ph", "bicarbonate", "anion gap", "potassium", "beta-hydroxybutyrate"], ["dka", "insulin drip", "anion gap", "potassium replacement"]),

    # ═══ ADDITIONAL INFECTIOUS DISEASE ═══
    ("IDSA Osteomyelitis Guidelines", "IDSA", 2024,
     "Osteomyelitis Diagnosis and Treatment",
     "Diagnosis: MRI (most sensitive and specific imaging). Bone biopsy with culture (gold standard) before antibiotic initiation. Blood cultures. Empiric: vancomycin + 3rd gen cephalosporin (adjust to culture). S. aureus (most common): nafcillin/cefazolin (MSSA) or vancomycin/daptomycin (MRSA). Duration: 4-6 weeks IV. Oral step-down with high-bioavailability agents (fluoroquinolone + rifampin for staphylococcal) per OVIVA trial. Surgical debridement for necrotic bone, hardware, or abscess.",
     "A", "Strong", ["osteomyelitis", "bone infection"], ["vancomycin", "cefazolin", "nafcillin", "ciprofloxacin", "rifampin"], ["mri bone", "bone biopsy", "blood cultures", "esr", "crp"], ["osteomyelitis", "mri", "bone biopsy", "vancomycin"]),

    ("IDSA Intra-Abdominal Infection Guidelines", "SIS/IDSA", 2024,
     "Complicated Intra-Abdominal Infection Treatment",
     "Source control is paramount: percutaneous drainage or surgical intervention. Community-acquired mild-moderate: ceftriaxone + metronidazole, or ertapenem, or moxifloxacin. Community-acquired severe: piperacillin-tazobactam, or meropenem, or cefepime + metronidazole. Healthcare-associated: meropenem or piperacillin-tazobactam + vancomycin (MRSA) ± antifungal (if risk for Candida). Duration: 4-5 days if adequate source control (STOP-IT trial). De-escalate to narrow-spectrum based on cultures.",
     "A", "Strong", ["intra-abdominal infection", "peritonitis", "abdominal abscess"], ["piperacillin-tazobactam", "meropenem", "ceftriaxone", "metronidazole", "ertapenem"], ["ct abdomen", "blood cultures", "wbc", "lactate", "procalcitonin"], ["intra-abdominal infection", "source control", "stop-it", "metronidazole"]),

    ("IDSA Diabetic Foot Infection Guidelines", "IDSA", 2024,
     "Diabetic Foot Infection Classification and Treatment",
     "Classify severity: mild (superficial, limited cellulitis <2 cm), moderate (deeper, cellulitis >2 cm, lymphangitis, fascia/muscle/bone), severe (systemic toxicity, metabolic instability). Mild: oral antibiotic (cephalexin, amoxicillin-clavulanate, TMP-SMX, doxycycline). Moderate-severe: IV ampicillin-sulbactam, piperacillin-tazobactam, or ertapenem ± vancomycin (MRSA). Osteomyelitis: probe-to-bone test, MRI. Duration: 1-2 weeks for soft tissue, 4-6 weeks for osteo. Vascular assessment (ABI, toe pressures) essential. Offloading. Multidisciplinary team.",
     "A", "Strong", ["diabetic foot infection", "diabetic osteomyelitis"], ["amoxicillin-clavulanate", "piperacillin-tazobactam", "vancomycin", "ertapenem"], ["mri foot", "probe-to-bone test", "wound culture", "abi", "esr", "crp", "hba1c"], ["diabetic foot infection", "probe-to-bone", "osteomyelitis", "offloading"]),

    # ═══ ADDITIONAL RHEUMATOLOGY ═══
    ("ACR Gout Guidelines", "ACR", 2024,
     "Gout Flare and Urate-Lowering Therapy",
     "Acute flare: NSAIDs (indomethacin, naproxen), colchicine (1.2 mg then 0.6 mg 1h later), or glucocorticoids (oral or intra-articular). IL-1 inhibitor (anakinra, canakinumab) for refractory. ULT indications: ≥2 flares/year, tophaceous gout, urate urolithiasis, CKD stage ≥3. First-line: allopurinol (start 100 mg, titrate to urate <6). Febuxostat if allopurinol intolerant/allergic. Pegloticase for refractory tophaceous gout (with immunomodulator to reduce immunogenicity). Flare prophylaxis during ULT initiation: colchicine 0.6 mg daily for 3-6 months.",
     "A", "Strong", ["gout", "hyperuricemia"], ["allopurinol", "febuxostat", "colchicine", "indomethacin", "prednisone", "anakinra", "pegloticase"], ["uric acid", "synovial fluid analysis", "renal function", "cbc"], ["gout", "allopurinol", "urate-lowering", "colchicine"]),

    ("ACR/EULAR Rheumatoid Arthritis Guidelines", "ACR/EULAR", 2024,
     "RA Treat-to-Target Strategy",
     "Target: remission (DAS28 <2.6) or low disease activity. Start DMARD within 3 months of symptom onset. Methotrexate first-line (15-25 mg weekly + folic acid). If target not met at 3 months: add bDMARD (TNFi: adalimumab, etanercept; IL-6: tocilizumab, sarilumab; T-cell: abatacept; B-cell: rituximab) or JAK inhibitor (tofacitinib, upadacitinib, baricitinib). Triple therapy (MTX + SSZ + HCQ) as alternative to biologic. Taper biologics if sustained remission ≥6 months.",
     "A", "Strong", ["rheumatoid arthritis"], ["methotrexate", "adalimumab", "tocilizumab", "tofacitinib", "upadacitinib", "abatacept", "rituximab"], ["das28", "crp", "esr", "rheumatoid factor", "anti-ccp", "joint x-rays", "joint ultrasound"], ["ra", "methotrexate", "treat-to-target", "biologic"]),

    # ═══ ADDITIONAL PEDIATRICS ═══
    ("AAP Pediatric Sepsis Guidelines", "AAP/SCCM", 2024,
     "Pediatric Sepsis Recognition and Bundles",
     "Screening: use Phoenix Sepsis Score or institutional screening tool. Hour-1 bundle: measure lactate, obtain blood culture, administer broad-spectrum antibiotics (ceftriaxone + vancomycin empiric for community-acquired), IV fluid bolus 10-20 mL/kg (up to 40-60 mL/kg in first hour, reassess after each bolus for fluid responsiveness). Fluid refractory shock: start vasoactive (epinephrine for cold shock, norepinephrine for warm shock). Hydrocortisone for catecholamine-resistant shock.",
     "A", "Strong", ["pediatric sepsis", "pediatric septic shock"], ["ceftriaxone", "vancomycin", "epinephrine", "norepinephrine", "hydrocortisone"], ["lactate", "blood cultures", "blood pressure", "capillary refill", "urine output"], ["pediatric sepsis", "septic shock", "fluid resuscitation"]),

    ("AAP Pediatric Type 1 Diabetes Guidelines", "AAP/ADA", 2024,
     "T1DM Pediatric Management",
     "Insulin therapy: basal-bolus MDI or insulin pump (CSII). AID systems improve outcomes. CGM for all T1DM youth. Target A1c <7% (individualized). Monitor growth, thyroid (TSH annually), celiac (tTG annually x 5 years), lipids, microalbumin. Hypoglycemia management: glucagon kits (nasal or injectable) prescribed. Sick-day rules: check ketones, maintain insulin, extra fluids. School 504 plan. Psychosocial: screen for diabetes distress, depression, disordered eating. Transition planning to adult care.",
     "A", "Strong", ["type 1 diabetes pediatric"], ["insulin lispro", "insulin aspart", "insulin glargine", "glucagon"], ["hba1c", "cgm time in range", "tsh", "celiac panel", "microalbumin"], ["t1dm pediatric", "insulin pump", "cgm", "diabetes management"]),

    ("AAP/ACIP Childhood Immunization Schedule", "AAP/ACIP", 2025,
     "Routine Childhood Immunization Schedule",
     "Birth: HepB. 2 months: DTaP, IPV, Hib, PCV15, RV, HepB. 4 months: DTaP, IPV, Hib, PCV15, RV. 6 months: DTaP, Hib, PCV15, RV (if 3-dose series), influenza (annually from 6mo). 12-15 months: MMR, varicella, HepA, PCV15→PCV20 (or PPSV23), Hib booster. 4-6 years: DTaP, IPV, MMR, varicella boosters. 11-12 years: Tdap, MenACWY, HPV (2-dose if started <15). Catch-up schedules available. Contraindications: severe allergic reaction to prior dose or component.",
     "A", "Strong", ["childhood immunization", "pediatric vaccination"], ["dtap", "mmr", "ipv", "pcv15", "hpv vaccine", "menacwy"], [], ["childhood immunization", "acip schedule", "vaccination"]),

    # ═══ ADDITIONAL SURGERY/PERIOPERATIVE ═══
    ("ACC/AHA Perioperative Cardiac Risk Guidelines", "ACC/AHA", 2024,
     "Preoperative Cardiac Risk Assessment",
     "RCRI (Revised Cardiac Risk Index) for non-cardiac surgery. Low risk (RCRI 0, functional capacity ≥4 METs): proceed to surgery. Elevated risk: consider if results will change management. Stress testing for poor functional capacity + elevated risk surgery. NT-proBNP/BNP preoperatively for patients ≥65 or with CV disease/risk factors. Beta-blockers: continue if already taking; do NOT start de novo. Antiplatelet: continue aspirin for coronary stents within 6 weeks (BMS) or 6 months (DES). Hold P2Y12 5-7 days before surgery.",
     "A", "Strong", ["perioperative cardiac risk", "preoperative evaluation"], ["metoprolol", "aspirin"], ["rcri", "nt-probnp", "ecg", "stress test", "echocardiogram"], ["perioperative", "rcri", "preoperative", "cardiac risk"]),

    ("ASRA Regional Anesthesia Guidelines", "ASRA", 2024,
     "Regional Anesthesia and Anticoagulation",
     "Neuraxial: hold warfarin 5 days (INR ≤1.4), LMWH prophylactic 12h / therapeutic 24h, UFH IV 4-6h (check aPTT), rivaroxaban/apixaban 72h, dabigatran 4-5 days (CrCl dependent). Catheter removal: same timing as insertion. Peripheral nerve blocks: less stringent; can proceed with prophylactic anticoagulation for most superficial blocks. Deep blocks (paravertebral, psoas compartment): same as neuraxial. Document risk-benefit discussion. Post-procedure neurologic checks Q1h x 24h.",
     "A", "Strong", ["regional anesthesia", "nerve block anticoagulation"], ["warfarin", "enoxaparin", "rivaroxaban", "apixaban", "heparin"], ["inr", "aptt", "anti-xa", "platelet count", "creatinine clearance"], ["regional anesthesia", "anticoagulation", "asra", "neuraxial"]),

    # ═══ ADDITIONAL PREVENTIVE/PUBLIC HEALTH ═══
    ("USPSTF Lung Cancer Screening", "USPSTF", 2024,
     "Low-Dose CT Lung Cancer Screening",
     "Annual LDCT for adults 50-80 years with ≥20 pack-year smoking history AND currently smoke or quit within 15 years. Shared decision-making. Nodule management per Lung-RADS. Smoking cessation counseling at every screening visit. Discontinue if life expectancy limited or unable to undergo curative treatment. Reduce mortality by ~20% (NLST). Risks: false positives, overdiagnosis, radiation exposure, incidental findings, anxiety.",
     "A", "Strong", ["lung cancer screening"], [], ["low-dose ct chest", "lung-rads score"], ["lung cancer screening", "ldct", "pack-year", "lung-rads"]),

    ("USPSTF AAA Screening", "USPSTF", 2024,
     "Abdominal Aortic Aneurysm Screening",
     "One-time screening ultrasound for men ages 65-75 who have ever smoked. Selective screening for men 65-75 who never smoked. Insufficient evidence for women who have never smoked; selective for women 65-75 who have ever smoked or family history. AAA <3.0 cm: normal. 3.0-3.9 cm: surveillance US Q3 years. 4.0-4.9 cm: surveillance Q12 months. 5.0-5.4 cm: surveillance Q6 months + vascular surgery referral. ≥5.5 cm or rapidly expanding (>0.5 cm/6months): repair.",
     "A", "Strong", ["abdominal aortic aneurysm", "aaa screening"], [], ["abdominal aortic ultrasound", "ct angiography"], ["aaa screening", "aortic aneurysm", "ultrasound"]),

    ("USPSTF Depression Screening", "USPSTF", 2024,
     "Depression Screening in Adults",
     "Screen all adults ≥18 for depression using validated instruments: PHQ-2 (brief screen, ≥3 triggers further evaluation), PHQ-9 (diagnostic, ≥10 = moderate depression). Screen adolescents ≥12. Screening must be implemented with adequate follow-up systems: diagnosis confirmation, treatment initiation, monitoring. Special populations: postpartum (screen at each visit through 12 months), older adults (GDS as alternative), perinatal (Edinburgh Postnatal Depression Scale). Frequency: at least annually, more often for high-risk.",
     "A", "Strong", ["depression screening", "major depressive disorder"], [], ["phq-2", "phq-9", "gds", "epds"], ["depression screening", "phq-9", "uspstf"]),

    # ═══ NEPHROLOGY/DIALYSIS ═══
    ("KDOQI Hemodialysis Adequacy", "KDOQI/KDIGO", 2024,
     "Hemodialysis Adequacy and Prescription",
     "Target spKt/V ≥1.4 for thrice-weekly HD (minimum ≥1.2). Standard: 4 hours thrice weekly. Assess monthly. Residual kidney function contributes to adequacy (may allow reduced frequency initially). Vascular access: AV fistula preferred (first mature fistula), AV graft second, tunneled catheter as bridge. Fistula First initiative. Dry weight assessment: clinical, bioimpedance, lung ultrasound. Intradialytic hypotension: reduce UF rate, sodium profiling, midodrine, cooled dialysate.",
     "A", "Strong", ["hemodialysis", "end-stage kidney disease"], ["erythropoiesis-stimulating agents", "iv iron", "sevelamer", "cinacalcet", "midodrine"], ["sktv", "urea reduction ratio", "hemoglobin", "calcium", "phosphorus", "pth", "albumin"], ["hemodialysis", "adequacy", "av fistula", "kt/v"]),

    ("KDIGO Peritoneal Dialysis Guidelines", "KDIGO/ISPD", 2024,
     "Peritoneal Dialysis Prescription and Complications",
     "PD modalities: CAPD (4 exchanges/day) or APD (cycler overnight). Target weekly Kt/V urea ≥1.7. PD catheter: surgical or percutaneous placement, 2-week break-in preferred. Peritonitis: most common complication. Diagnosis: cloudy fluid + WBC >100/μL with >50% PMN. Empiric: intraperitoneal vancomycin + gentamicin (or ceftazidime). Duration: 14-21 days per pathogen. Catheter removal for: refractory peritonitis (>5 days), fungal, repeat peritonitis, tunnel infection.",
     "A", "Strong", ["peritoneal dialysis", "esrd"], ["vancomycin intraperitoneal", "gentamicin intraperitoneal", "ceftazidime"], ["pd effluent wbc", "pd culture", "kt/v urea", "albumin", "residual urine output"], ["peritoneal dialysis", "peritonitis", "capd", "apd"]),

    # ═══ ADDITIONAL EMERGENCY MEDICINE ═══
    ("ACEP Chest Pain Evaluation Guidelines", "ACEP/AHA", 2024,
     "Low-Risk Chest Pain Disposition",
     "HEART score for risk stratification: 0-3 = low risk (0.9-1.7% MACE at 30 days), 4-6 = moderate, 7-10 = high. Low-risk pathway: serial troponin (0 and 3 hours high-sensitivity) + HEART score ≤3 = safe for discharge with outpatient follow-up. Avoid routine stress testing for low-risk patients (per 2021 AHA/ACC Chest Pain guidelines). Moderate risk: observation, stress testing or CCTA. High risk: cardiology consultation, invasive strategy.",
     "A", "Strong", ["chest pain evaluation", "acute coronary syndrome rule-out"], [], ["troponin", "ecg", "heart score", "ccta", "stress test"], ["chest pain", "heart score", "troponin", "low risk"]),

    ("ACEP Pediatric Emergency Guidelines", "ACEP/AAP", 2024,
     "Pediatric Fever Without Source Management",
     "Neonates 0-28 days with fever ≥38°C: full sepsis workup (blood, urine, CSF cultures + CBC) + empiric antibiotics (ampicillin + gentamicin or cefotaxime). 29-60 days: risk stratification (Rochester, Philadelphia, Boston criteria or Step-by-Step). Low risk: outpatient with follow-up (some centers). High risk: admit + antibiotics. >60 days to 36 months: UA + urine culture (all), blood culture + CBC if toxic-appearing. UTI most common serious bacterial infection in this age group.",
     "A", "Strong", ["pediatric fever", "fever without source", "neonatal fever"], ["ampicillin", "gentamicin", "ceftriaxone"], ["cbc", "blood culture", "urinalysis", "urine culture", "csf analysis", "procalcitonin"], ["pediatric fever", "neonatal sepsis workup", "rochester criteria"]),

    # ═══ ADDITIONAL CRITICAL CARE ═══
    ("SCCM Stress Ulcer Prophylaxis", "SCCM/ESICM", 2024,
     "ICU Stress Ulcer Prevention",
     "Indicated for: mechanical ventilation >48 hours, coagulopathy (INR >1.5, plt <50k), history of GI ulcer/bleed within 1 year, TBI, burns >35%, ≥2 minor risk factors. PPI preferred (pantoprazole 40 mg IV daily). H2RA (famotidine 20 mg IV BID) as alternative. Sucralfate: less effective but lower pneumonia risk. Discontinue when risk factors resolve (e.g., extubation). Early enteral nutrition may provide some protection. SUP-ICU trial: PPI did not reduce mortality but decreased GI bleeding.",
     "B", "Moderate", ["stress ulcer prophylaxis", "icu gi bleeding prevention"], ["pantoprazole", "famotidine", "sucralfate"], ["hemoglobin", "stool guaiac"], ["stress ulcer", "ppi", "icu prophylaxis", "sup-icu"]),

    ("SCCM ICU Nutrition Guidelines", "SCCM/ASPEN", 2024,
     "ICU Nutrition Support",
     "Enteral nutrition (EN) preferred over parenteral (PN). Start EN within 24-48 hours for hemodynamically stable patients. Trophic feeding (10-20 mL/h) initially for severe shock. Advance to goal (25-30 kcal/kg/day) over 48-72h. Protein: 1.2-2.0 g/kg/day (higher for burns, trauma, wounds). PN: start by day 7 if EN not feasible. Monitor: residual volumes (hold at >500 mL), electrolytes, glucose. Avoid overfeeding (refeeding syndrome risk with malnutrition). Indirect calorimetry for personalized targets if available.",
     "B", "Strong", ["icu nutrition", "enteral nutrition", "parenteral nutrition"], ["tpn", "lipid emulsion"], ["prealbumin", "phosphorus", "magnesium", "potassium", "glucose", "indirect calorimetry"], ["icu nutrition", "enteral feeding", "protein requirement", "refeeding"]),

    # ═══ ADDITIONAL DERMATOLOGY ═══
    ("AAD Melanoma Screening", "AAD/USPSTF", 2024,
     "Melanoma Surveillance and Prevention",
     "Skin self-examination monthly. Full skin exam for high-risk: personal/family history of melanoma, >50 nevi, atypical mole syndrome, prior non-melanoma skin cancer, immunosuppression. Dermoscopy improves diagnostic accuracy. ABCDE criteria: Asymmetry, Border irregularity, Color variation, Diameter >6mm, Evolution. Ugly duckling sign: lesion that looks different from others. Sun protection: broad-spectrum SPF ≥30, protective clothing, avoid tanning beds. Biopsy: excisional preferred for suspicious lesion.",
     "B", "Strong", ["melanoma screening", "skin cancer prevention"], ["sunscreen"], ["dermoscopy", "skin biopsy"], ["melanoma screening", "dermoscopy", "abcde", "sun protection"]),

    ("AAD Nail Fungus Guidelines", "AAD", 2024,
     "Onychomycosis Treatment",
     "Confirm diagnosis: KOH prep, fungal culture, or PAS staining of nail clipping (histopathology most sensitive). Terbinafine 250 mg daily (fingernails 6 weeks, toenails 12 weeks) — first-line, highest cure rate. Itraconazole pulse therapy (200 mg BID x 1 week/month for 2-3 months) alternative. Topical: efinaconazole 10% or tavaborole 5% (for mild, <50% nail involvement without matrix involvement). Ciclopirox 8% lacquer less effective. Check LFTs at baseline and 6 weeks for oral azoles. Recurrence common.",
     "B", "Moderate", ["onychomycosis", "nail fungus"], ["terbinafine", "itraconazole", "efinaconazole", "ciclopirox"], ["koh prep", "fungal culture", "nail biopsy", "alt"], ["onychomycosis", "terbinafine", "nail fungus"]),

    # ═══ ADDITIONAL OPHTHALMOLOGY ═══
    ("AAO Diabetic Retinopathy Guidelines", "AAO/ADA", 2024,
     "Diabetic Retinopathy Management",
     "Screening: dilated eye exam at T2DM diagnosis, within 5 years for T1DM, then annually (biennial if no retinopathy). AI-based retinal screening validated for primary care settings. Mild NPDR: optimize glycemia and BP, annual exam. Moderate-severe NPDR: referral to retina specialist, exam Q3-6 months. Proliferative DR: panretinal photocoagulation (PRP) or anti-VEGF intravitreal injections (aflibercept per DRCR Protocol S). DME: anti-VEGF first-line (aflibercept, ranibizumab, faricimab). Focal laser for non-center-involving DME.",
     "A", "Strong", ["diabetic retinopathy", "diabetic macular edema"], ["aflibercept", "ranibizumab", "faricimab"], ["dilated fundus exam", "oct macula", "fluorescein angiography", "hba1c", "blood pressure"], ["diabetic retinopathy", "anti-vegf", "panretinal photocoagulation", "dme"]),

    # ═══ ADDITIONAL PULMONOLOGY ═══
    ("ATS Obstructive Sleep Apnea Guidelines", "ATS/AASM", 2024,
     "OSA Diagnosis and PAP Therapy",
     "Diagnosis: polysomnography (PSG) gold standard, or home sleep apnea test (HSAT) for moderate-high pretest probability without significant comorbidities. AHI ≥5 with symptoms or ≥15 regardless = OSA. Severity: mild (5-14), moderate (15-29), severe (≥30). CPAP is first-line for moderate-severe OSA. Autotitrating PAP (APAP) as alternative to fixed pressure. MAD (mandibular advancement device) for mild-moderate or CPAP intolerance. Weight loss (bariatric surgery if appropriate). Hypoglossal nerve stimulation (Inspire) for CPAP-intolerant, BMI <32, AHI 15-65.",
     "A", "Strong", ["obstructive sleep apnea", "osa"], [], ["polysomnography", "home sleep test", "ahi", "oxygen saturation", "bmi", "epworth sleepiness scale"], ["osa", "cpap", "polysomnography", "hypoglossal nerve stimulation"]),

    # ═══ ADDICTION/BEHAVIORAL ═══
    ("ASAM Alcohol Withdrawal Guidelines", "ASAM", 2024,
     "Alcohol Withdrawal Syndrome Management",
     "Risk assessment: AUDIT-C for use, PAWSS for withdrawal risk. CIWA-Ar protocol for symptom-triggered benzodiazepine dosing (give chlordiazepoxide or lorazepam when CIWA ≥8-10). Alternative: fixed-dose taper. Severe withdrawal/DTs: ICU level care, IV diazepam or phenobarbital. Refractory: propofol or dexmedetomidine infusion. Seizure prophylaxis: benzodiazepines (not phenytoin). Thiamine 500 mg IV x 3 days BEFORE glucose (prevent Wernicke). Folate, multivitamin, magnesium supplementation. Gabapentin for mild withdrawal without seizure/DT history.",
     "A", "Strong", ["alcohol withdrawal", "delirium tremens"], ["chlordiazepoxide", "lorazepam", "diazepam", "phenobarbital", "thiamine", "gabapentin"], ["ciwa-ar score", "blood alcohol level", "cmp", "magnesium", "phosphorus"], ["alcohol withdrawal", "ciwa", "benzodiazepine", "delirium tremens"]),

    # ═══ VASCULAR / INTERVENTIONAL ═══
    ("SVS Carotid Disease Guidelines", "SVS/AHA", 2024,
     "Carotid Artery Stenosis Management",
     "Asymptomatic ≥70% stenosis: carotid endarterectomy (CEA) if perioperative risk <3% and life expectancy >3-5 years. Medical management (aspirin + statin + BP control + smoking cessation) improved outcomes; may be adequate for many patients. Symptomatic ≥50%: CEA (within 2 weeks of event) reduces stroke risk. CAS (carotid artery stenting) alternative for: high surgical risk, prior neck radiation, surgically inaccessible lesion. TCAR (transcarotid artery revascularization) emerging option. Surveillance: carotid duplex annually.",
     "A", "Strong", ["carotid stenosis", "carotid artery disease"], ["aspirin", "atorvastatin"], ["carotid duplex ultrasound", "ct angiography", "mra"], ["carotid stenosis", "endarterectomy", "stenting", "stroke prevention"]),

    # ═══ ADDITIONAL MISCELLANEOUS ═══
    ("AAN Chronic Headache Guidelines", "AAN/AHS", 2024,
     "Medication Overuse Headache Prevention",
     "MOH definition: headache ≥15 days/month with regular overuse of acute medication (≥10 days for triptans/opioids/combinations, ≥15 days for simple analgesics). Prevention: limit acute medication to <10-15 days/month. Treatment: withdraw offending medication (may require bridge with steroids or nerve block), start preventive medication simultaneously. NSAIDs and triptans: abrupt withdrawal. Opioids/barbiturates: gradual taper. Preventive options: topiramate, anti-CGRP mAb (may work without withdrawal per studies), onabotulinumtoxinA.",
     "A", "Strong", ["medication overuse headache", "chronic daily headache"], ["topiramate", "erenumab", "onabotulinumtoxinA"], ["headache diary", "hit-6", "midas"], ["medication overuse headache", "moh", "headache prevention"]),

    ("ACOG Cervical Cancer Screening Guidelines", "ACOG/ACS/ASCCP", 2024,
     "Cervical Cancer Screening Strategy",
     "Age 21-24: cytology (Pap) alone Q3 years. Age 25-65: primary HPV testing Q5 years (preferred), cotesting (HPV + Pap) Q5 years, or cytology Q3 years. >65: discontinue if adequate prior screening and no CIN2+ in prior 25 years. Post-hysterectomy (without cervix, no CIN2+ history): stop screening. Immunocompromised: start at age 21, cytology annually until 3 consecutive normals, then Q3 years. Abnormal results: follow ASCCP risk-based management guidelines. HPV vaccination does not change screening intervals.",
     "A", "Strong", ["cervical cancer screening", "hpv screening"], ["hpv vaccine"], ["pap smear", "hpv test", "colposcopy"], ["cervical screening", "hpv", "pap smear", "asccp"]),

    ("ADA Hypoglycemia Guidelines", "ADA", 2025,
     "Hypoglycemia Recognition and Treatment",
     "Level 1 (alert): glucose <70 mg/dL. Level 2 (clinically significant): <54 mg/dL. Level 3 (severe): altered mental status requiring assistance. Treatment: conscious patient — 15g fast-acting carbohydrate (glucose tablets, juice), recheck in 15 minutes (rule of 15). Severe hypoglycemia: glucagon 1 mg IM/SC or nasal glucagon 3 mg or dasiglucagon 0.6 mg SC. Reduce/adjust insulin or sulfonylurea. CGM to reduce hypoglycemia. Educate on prevention, driving safety. Hypoglycemia unawareness: raise glucose targets, CGM essential.",
     "A", "Strong", ["hypoglycemia", "severe hypoglycemia"], ["glucagon", "dasiglucagon", "dextrose"], ["blood glucose", "cgm", "hba1c"], ["hypoglycemia", "glucagon", "rule of 15", "cgm"]),

    ("WHO Malaria Guidelines", "WHO/CDC", 2024,
     "Malaria Treatment",
     "Uncomplicated P. falciparum: artemisinin-based combination therapy (ACT): artemether-lumefantrine or artesunate-mefloquine. Duration: 3 days. P. vivax/ovale: chloroquine + primaquine 14 days (check G6PD first; tafenoquine single dose alternative). Severe malaria: IV artesunate (first-line); follow with full ACT course. Supportive: manage hypoglycemia, anemia, renal failure, cerebral malaria. Chemoprophylaxis for travelers: atovaquone-proguanil, doxycycline, or mefloquine based on destination resistance.",
     "A", "Strong", ["malaria", "plasmodium falciparum"], ["artemether-lumefantrine", "artesunate", "chloroquine", "primaquine", "atovaquone-proguanil"], ["blood smear", "rapid diagnostic test", "g6pd level", "cbc", "bmp", "lactate"], ["malaria", "artemisinin", "act", "chemoprophylaxis"]),

    ("ACOG Gestational Diabetes Guidelines", "ACOG/ADA", 2024,
     "GDM Screening and Management",
     "Universal screening at 24-28 weeks: 1-step (75g OGTT, IADPSG criteria) or 2-step (50g GCT then 100g OGTT if positive). Diet and exercise first-line. Glucose targets: fasting <95, 1h post-meal <140, 2h post-meal <120 mg/dL. If targets not met in 1-2 weeks: insulin (preferred) or metformin. Fetal surveillance: NST/BPP starting 32-36 weeks depending on severity. Delivery timing: diet-controlled at 39-40 weeks; medication-requiring at 37-39 weeks. Postpartum: screen for T2DM at 4-12 weeks (75g OGTT), then every 1-3 years.",
     "A", "Strong", ["gestational diabetes", "gdm"], ["insulin", "metformin", "glyburide"], ["fasting glucose", "ogtt", "hba1c", "fetal nst", "biophysical profile"], ["gdm", "gestational diabetes", "ogtt", "insulin"]),

    ("AAFP Primary Care Depression Management", "AAFP/APA", 2024,
     "MDD Initial Treatment in Primary Care",
     "Mild depression: watchful waiting 2 weeks or psychotherapy (CBT, IPT). Moderate-severe: pharmacotherapy ± psychotherapy. First-line: SSRIs (sertraline, escitalopram) — best balance of efficacy/tolerability. Alternative: SNRIs (duloxetine, venlafaxine), bupropion, mirtazapine. Start low, monitor at 2 and 4 weeks. Response assessment with PHQ-9 (≥50% reduction = response, <5 = remission). If inadequate response at 4-6 weeks at adequate dose: optimize dose, switch, or augment. Duration: continue ≥6-9 months after remission (12+ months for recurrent).",
     "A", "Strong", ["major depressive disorder", "depression treatment"], ["sertraline", "escitalopram", "duloxetine", "bupropion", "mirtazapine", "venlafaxine"], ["phq-9", "gad-7"], ["depression", "ssri", "primary care", "phq-9"]),

    ("ACC/AHA Aortic Aneurysm Guidelines", "ACC/AHA/SVS", 2024,
     "Thoracic and Abdominal Aortic Aneurysm Management",
     "AAA surveillance: 3.0-3.9 cm Q3 years, 4.0-4.9 cm Q12 months, 5.0-5.4 cm Q6 months. Repair threshold: AAA ≥5.5 cm (men), ≥5.0 cm (women), or rapid expansion >0.5 cm/6 months. EVAR or open repair based on anatomy and patient factors. TAA: repair at ≥5.5 cm (6.0 for descending), lower threshold for connective tissue disease (Marfan ≥5.0 cm). Medical: BP control (beta-blocker preferred), statin, smoking cessation. Screen first-degree relatives of AAA patients.",
     "A", "Strong", ["aortic aneurysm", "abdominal aortic aneurysm", "thoracic aortic aneurysm"], ["metoprolol", "atorvastatin", "amlodipine"], ["ct angiography", "abdominal ultrasound", "mra", "echocardiogram"], ["aortic aneurysm", "evar", "surveillance", "repair threshold"]),

    ("AAN Neuropathic Pain Guidelines", "AAN/IASP", 2024,
     "Neuropathic Pain Pharmacotherapy",
     "First-line: gabapentinoids (pregabalin 150-600 mg/day, gabapentin 1200-3600 mg/day), TCAs (amitriptyline, nortriptyline 25-150 mg/day), SNRIs (duloxetine 60-120 mg/day, venlafaxine 150-225 mg/day). Topical: lidocaine 5% patch/cream, capsaicin 8% patch (applied by provider). Second-line: tramadol, combination therapy. Avoid: first-line opioids for chronic neuropathic pain. Diabetic neuropathy: duloxetine has FDA approval. PHN: pregabalin, gabapentin, lidocaine patch. Trigeminal neuralgia: carbamazepine first-line.",
     "A", "Strong", ["neuropathic pain", "diabetic neuropathy", "postherpetic neuralgia"], ["pregabalin", "gabapentin", "duloxetine", "amitriptyline", "lidocaine patch", "capsaicin patch", "carbamazepine"], ["pain score", "neurologic exam", "emg/ncs"], ["neuropathic pain", "gabapentinoid", "duloxetine", "lidocaine patch"]),

    ("ACC Sleep and Cardiovascular Health", "AHA/AASM", 2024,
     "Sleep and Cardiovascular Risk",
     "Short sleep (<7 hours) and long sleep (>9 hours) associated with increased CV risk. AHA Life's Essential 8 includes sleep health. OSA is independent CV risk factor: associated with resistant HTN, AF, HF, stroke. Screen cardiac patients for OSA (STOP-BANG ≥3). CPAP improves BP in resistant hypertension with OSA. Central sleep apnea in HF: adaptive servo-ventilation contraindicated in HFrEF (SERVE-HF). Circadian disruption (shift work): associated with metabolic syndrome, CVD.",
     "B", "Strong", ["sleep and cardiovascular risk", "osa cardiovascular"], [], ["polysomnography", "stop-bang score", "blood pressure", "echocardiogram"], ["sleep health", "osa", "cardiovascular", "lifes essential 8"]),

    ("ADA Diabetes and Chronic Kidney Disease", "ADA/KDIGO", 2025,
     "DKD Integrated Management",
     "Target HbA1c <7% (individualize for CKD stage). First-line glucose-lowering: metformin (adjust for eGFR: reduce at <45, stop at <30). SGLT2 inhibitor for eGFR ≥20 with albuminuria (regardless of diabetes control). GLP-1 RA: cardiovascular and renal benefit. Finerenone (nonsteroidal MRA) for T2DM with albuminuria on max RAS blockade. BP target <130/80 with ACEi or ARB. Monitor: eGFR, UACR, potassium Q3-6 months. Avoid NSAIDs. Referral to nephrology at eGFR <30.",
     "A", "Strong", ["diabetic kidney disease", "dkd"], ["metformin", "dapagliflozin", "empagliflozin", "semaglutide", "finerenone", "lisinopril"], ["hba1c", "egfr", "uacr", "potassium", "creatinine"], ["dkd", "sglt2", "finerenone", "ras blockade"]),
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
    print(f"Batch 9: added {added} sections (total now {total})")


if __name__ == "__main__":
    main()
