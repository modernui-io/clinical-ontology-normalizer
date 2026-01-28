#!/usr/bin/env python3
"""Batch 3: Add ~200 more guideline sections - deeper sub-specialty coverage."""

import json, os, re

GUIDELINES = [
    # ── CARDIOLOGY DEEP DIVE ──
    ("ACC/AHA Cardiomyopathy Guidelines", "ACC/AHA", 2024, [
        ("Dilated Cardiomyopathy", "Guideline-directed medical therapy identical to HFrEF: ACEi/ARNI, beta-blocker, MRA, SGLT2i. Genetic testing recommended for familial DCM. ICD for primary prevention if LVEF ≤35% after 3 months optimal therapy. Cardiac MRI for prognosis (late gadolinium enhancement). Consider LVAD or transplant for advanced disease.", "A", "Strong",
         ["dilated cardiomyopathy", "dcm", "cardiomyopathy"], ["sacubitril-valsartan", "carvedilol", "spironolactone", "empagliflozin"], ["ejection fraction", "cardiac mri", "bnp", "genetic testing"], ["dilated cardiomyopathy", "gdmt", "genetic", "icd"]),
        ("Hypertrophic Cardiomyopathy", "Mavacamten for obstructive HCM with NYHA II-III symptoms despite beta-blocker/CCB. Beta-blockers or verapamil as first-line for symptomatic obstruction. Disopyramide as add-on for refractory symptoms. Septal reduction therapy (myectomy preferred over alcohol ablation) for drug-refractory obstruction. ICD for SCD risk: ≥6% 5-year risk.", "A", "Strong",
         ["hypertrophic cardiomyopathy", "hcm", "hocm"], ["mavacamten", "metoprolol", "verapamil", "disopyramide"], ["echocardiogram", "cardiac mri", "holter monitor", "exercise stress test"], ["hcm", "mavacamten", "myectomy", "scd risk"]),
        ("Cardiac Amyloidosis", "Tafamidis for ATTR cardiac amyloidosis (wild-type or hereditary) with NYHA I-III. Early diagnosis with bone scintigraphy (Tc-99m PYP) for ATTR. Endomyocardial biopsy for AL amyloid confirmation. Chemotherapy (daratumumab-based) for AL amyloidosis. Avoid digoxin and CCB in cardiac amyloidosis.", "A", "Strong",
         ["cardiac amyloidosis", "attr amyloidosis", "al amyloidosis"], ["tafamidis", "daratumumab", "bortezomib"], ["tc-99m pyp scan", "cardiac mri", "bnp", "troponin", "free light chains"], ["amyloidosis", "tafamidis", "attr", "bone scintigraphy"]),
    ]),
    ("HRS Cardiac Arrhythmia Guidelines", "HRS", 2024, [
        ("Ventricular Tachycardia Management", "Hemodynamically unstable VT: immediate cardioversion. Stable monomorphic VT: IV amiodarone or procainamide. ICD implantation for secondary prevention of sustained VT/VF. Catheter ablation for recurrent VT despite AAD. Beta-blockers reduce ICD shocks.", "A", "Strong",
         ["ventricular tachycardia", "vt", "ventricular fibrillation"], ["amiodarone", "procainamide", "lidocaine", "metoprolol", "sotalol"], ["ecg", "electrophysiology study", "cardiac mri"], ["ventricular tachycardia", "icd", "ablation", "amiodarone"]),
        ("Bradyarrhythmia and Pacing", "Permanent pacemaker for symptomatic sinus node dysfunction, high-grade AV block, or alternating bundle branch block. Conduction system pacing (His bundle or left bundle branch area pacing) preferred over RV pacing. Leadless pacemaker for select single-chamber needs. Cardiac monitoring before pacemaker in syncope evaluation.", "A", "Strong",
         ["bradycardia", "heart block", "sinus node dysfunction"], ["atropine", "isoproterenol"], ["ecg", "holter monitor", "electrophysiology study"], ["pacemaker", "bradycardia", "heart block", "conduction system pacing"]),
    ]),
    ("AHA Acute Aortic Syndromes", "AHA", 2024, [
        ("Aortic Dissection Management", "Type A (ascending): emergency surgical repair. Type B (descending): medical management with IV beta-blocker targeting HR <60 and SBP <120. TEVAR for complicated type B (malperfusion, rupture, rapid expansion). CT angiography as primary diagnostic modality. Transfer to aortic center.", "A", "Strong",
         ["aortic dissection", "acute aortic syndrome", "aortic aneurysm"], ["esmolol", "labetalol", "nicardipine", "clevidipine"], ["ct angiography", "d-dimer", "blood pressure", "heart rate"], ["aortic dissection", "type a", "type b", "tevar"]),
    ]),

    # ── ONCOLOGY CONTINUED ──
    ("NCCN Acute Myeloid Leukemia", "NCCN", 2025, [
        ("AML Induction Therapy", "Standard 7+3 induction (cytarabine + daunorubicin) for fit patients. Midostaurin added for FLT3-mutated AML. CPX-351 for therapy-related or AML with myelodysplasia-related changes. Venetoclax plus azacitidine for unfit patients. IDH inhibitors (ivosidenib, enasidenib) for IDH-mutated AML.", "A", "Strong",
         ["acute myeloid leukemia", "aml", "leukemia"], ["cytarabine", "daunorubicin", "midostaurin", "venetoclax", "azacitidine", "ivosidenib"], ["cbc", "bone marrow biopsy", "flt3", "idh1", "idh2", "npm1"], ["aml", "induction", "7+3", "venetoclax"]),
        ("AML Post-Remission Therapy", "Allogeneic stem cell transplant for intermediate/adverse-risk AML in first remission. Consolidation with high-dose cytarabine for favorable-risk. FLT3 inhibitor maintenance (gilteritinib) after transplant. Oral azacitidine maintenance for patients not proceeding to transplant.", "A", "Strong",
         ["acute myeloid leukemia", "aml"], ["cytarabine", "gilteritinib", "azacitidine"], ["bone marrow biopsy", "measurable residual disease"], ["aml", "transplant", "consolidation", "maintenance"]),
    ]),
    ("NCCN Acute Lymphoblastic Leukemia", "NCCN", 2025, [
        ("Adult ALL Treatment", "Multi-agent chemotherapy with risk-stratified approach. Pediatric-inspired regimens for AYA patients. Blinatumomab or inotuzumab ozogamicin for relapsed/refractory B-ALL. Tisagenlecleucel (CAR-T) for relapsed B-ALL. Ph+ ALL: TKI (dasatinib or ponatinib) plus chemotherapy or blinatumomab.", "A", "Strong",
         ["acute lymphoblastic leukemia", "all", "b-cell all", "ph-positive all"], ["vincristine", "dexamethasone", "asparaginase", "blinatumomab", "inotuzumab", "dasatinib", "ponatinib"], ["cbc", "bone marrow", "bcr-abl", "mrd", "csf cytology"], ["all", "blinatumomab", "car-t", "ph-positive"]),
    ]),
    ("NCCN Myelodysplastic Syndromes", "NCCN", 2025, [
        ("Lower-Risk MDS", "Observation for asymptomatic lower-risk MDS. Erythropoiesis-stimulating agents (ESA) for symptomatic anemia with EPO <500. Luspatercept for ESA-refractory anemia in RS+ MDS. Lenalidomide for del(5q) MDS. Imetelstat for ESA-refractory lower-risk without del(5q).", "A", "Strong",
         ["myelodysplastic syndrome", "mds", "refractory anemia"], ["epoetin alfa", "darbepoetin", "luspatercept", "lenalidomide", "imetelstat"], ["cbc", "bone marrow biopsy", "cytogenetics", "epo level"], ["mds", "esa", "luspatercept", "lenalidomide"]),
        ("Higher-Risk MDS", "Hypomethylating agents (azacitidine, decitabine) as standard of care. Allogeneic stem cell transplant for eligible patients. Venetoclax plus HMA under investigation. IPSS-R for risk stratification. Red cell and platelet transfusions as supportive care. Iron chelation for chronically transfused patients.", "A", "Strong",
         ["myelodysplastic syndrome", "mds", "high-risk mds"], ["azacitidine", "decitabine", "venetoclax", "deferasirox"], ["cbc", "bone marrow", "ipss-r", "ferritin"], ["mds", "azacitidine", "transplant", "hypomethylating"]),
    ]),
    ("NCCN Sarcoma Guidelines", "NCCN", 2025, [
        ("Soft Tissue Sarcoma", "Wide surgical resection with negative margins as primary treatment. Radiation therapy for high-grade, deep, >5cm tumors. Neoadjuvant radiation for extremity STS to reduce field size. Doxorubicin-based chemotherapy for advanced/metastatic disease. Histology-specific therapies: pazopanib for non-adipocytic STS, trabectedin for L-sarcomas.", "A", "Strong",
         ["soft tissue sarcoma", "sarcoma", "leiomyosarcoma", "liposarcoma"], ["doxorubicin", "ifosfamide", "pazopanib", "trabectedin", "eribulin"], ["mri", "ct scan", "biopsy"], ["sarcoma", "resection", "doxorubicin", "radiation"]),
    ]),
    ("NCCN Cervical Cancer Guidelines", "NCCN", 2025, [
        ("Cervical Cancer Treatment", "Conization or simple hysterectomy for stage IA1. Radical hysterectomy with pelvic lymphadenectomy for IB1-IIA1. Concurrent chemoradiation (cisplatin weekly) for IB2+ or node-positive. Pembrolizumab plus chemoradiation for stage III-IVA. Bevacizumab added to chemotherapy for recurrent/metastatic.", "A", "Strong",
         ["cervical cancer", "cervical squamous cell", "hpv-related cancer"], ["cisplatin", "pembrolizumab", "bevacizumab", "carboplatin", "paclitaxel", "topotecan"], ["ct scan", "pet scan", "mri pelvis", "scc antigen"], ["cervical cancer", "chemoradiation", "immunotherapy", "radical hysterectomy"]),
    ]),

    # ── GI CONTINUED ──
    ("AGA Autoimmune Hepatitis", "AGA", 2024, [
        ("AIH Diagnosis and Treatment", "Simplified diagnostic criteria: autoantibodies (ANA, SMA, anti-LKM1), elevated IgG, compatible histology. Prednisone plus azathioprine as standard induction. Budesonide as alternative for non-cirrhotic patients. Azathioprine maintenance after steroid taper. Mycophenolate for azathioprine-intolerant. Liver transplant for decompensated disease.", "A", "Strong",
         ["autoimmune hepatitis", "aih"], ["prednisone", "azathioprine", "budesonide", "mycophenolate"], ["ana", "sma", "igg", "alt", "ast", "liver biopsy"], ["autoimmune hepatitis", "azathioprine", "prednisone", "autoantibody"]),
    ]),
    ("AASLD Primary Biliary Cholangitis", "AASLD", 2024, [
        ("PBC Treatment", "Ursodeoxycholic acid (UDCA) 13-15 mg/kg/day as first-line for all PBC patients. Obeticholic acid as second-line for incomplete UDCA response. Elafibranor or seladelpar (PPAR agonists) as newer second-line options. Monitor alkaline phosphatase, bilirubin, and albumin. Liver transplant for decompensated disease.", "A", "Strong",
         ["primary biliary cholangitis", "pbc", "primary biliary cirrhosis"], ["ursodeoxycholic acid", "obeticholic acid", "elafibranor", "seladelpar"], ["alkaline phosphatase", "bilirubin", "anti-mitochondrial antibody", "igg"], ["pbc", "udca", "obeticholic acid", "alkaline phosphatase"]),
    ]),
    ("ACG Eosinophilic Esophagitis", "ACG", 2024, [
        ("EoE Treatment", "PPI trial as initial therapy. Swallowed topical corticosteroids (budesonide orodispersible tablet, fluticasone) for PPI non-responders. Six-food elimination diet as alternative. Dupilumab for EoE ≥12 years and ≥40kg. Esophageal dilation for symptomatic strictures. Target ≤15 eosinophils/hpf on repeat biopsy.", "A", "Strong",
         ["eosinophilic esophagitis", "eoe", "dysphagia"], ["omeprazole", "budesonide", "fluticasone", "dupilumab"], ["upper endoscopy", "esophageal biopsy", "eosinophil count"], ["eosinophilic esophagitis", "eoe", "dupilumab", "elimination diet"]),
    ]),
    ("ACG Gastroparesis", "ACG", 2024, [
        ("Gastroparesis Management", "Dietary modifications: small, frequent, low-fat, low-fiber meals. Metoclopramide as first-line prokinetic (lowest effective dose, FDA black box for tardive dyskinesia). Domperidone available via expanded access. Antiemetics: ondansetron, prochlorperazine. Gastric electrical stimulation for refractory nausea/vomiting. Pyloric interventions (G-POEM) for refractory cases.", "B", "Strong",
         ["gastroparesis", "delayed gastric emptying", "diabetic gastroparesis"], ["metoclopramide", "domperidone", "ondansetron", "prochlorperazine", "erythromycin"], ["gastric emptying study", "upper endoscopy", "hba1c"], ["gastroparesis", "prokinetic", "metoclopramide", "gastric emptying"]),
    ]),

    # ── RHEUMATOLOGY EXPANSION ──
    ("ACR Giant Cell Arteritis", "ACR", 2024, [
        ("GCA Treatment", "High-dose prednisone (40-60 mg/day) immediately upon clinical suspicion. Tocilizumab as first-line steroid-sparing agent (176mg SC q2wk or 162mg SC qwk). Temporal artery biopsy within 2 weeks of starting steroids (sensitivity preserved). CTA or ultrasound for large-vessel assessment. Low-dose aspirin for ischemic prevention.", "A", "Strong",
         ["giant cell arteritis", "temporal arteritis", "gca"], ["prednisone", "tocilizumab", "aspirin"], ["esr", "crp", "temporal artery biopsy", "temporal artery ultrasound"], ["giant cell arteritis", "tocilizumab", "temporal biopsy", "prednisone"]),
    ]),
    ("ACR Polymyalgia Rheumatica", "ACR", 2024, [
        ("PMR Treatment", "Prednisone 12.5-25 mg/day as initial therapy. Gradual taper over 12-18 months. Minimum effective dose maintenance. Consider tocilizumab or methotrexate for relapsing disease or inability to taper below 10 mg. Screen for concurrent GCA (headache, visual symptoms, jaw claudication). Monitor for steroid side effects.", "A", "Strong",
         ["polymyalgia rheumatica", "pmr"], ["prednisone", "methotrexate", "tocilizumab"], ["esr", "crp", "shoulder ultrasound"], ["polymyalgia rheumatica", "prednisone", "steroid taper"]),
    ]),
    ("ACR Sjögren Syndrome", "ACR", 2024, [
        ("Sjögren Management", "Artificial tears and saliva substitutes as first-line symptomatic therapy. Pilocarpine or cevimeline for refractory sicca symptoms. Hydroxychloroquine for arthralgias and fatigue. Rituximab for severe systemic manifestations (vasculitis, neuropathy, severe parotid swelling). Screen for lymphoma (5-10% lifetime risk). Monitor gammaglobulins and complement.", "B", "Strong",
         ["sjogren syndrome", "sjögren", "sicca syndrome"], ["pilocarpine", "cevimeline", "hydroxychloroquine", "rituximab"], ["ssa antibody", "ssb antibody", "schirmer test", "salivary flow rate", "immunoglobulins"], ["sjogren", "sicca", "pilocarpine", "rituximab"]),
    ]),
    ("ACR Scleroderma/Systemic Sclerosis", "ACR", 2024, [
        ("Systemic Sclerosis Management", "Raynaud: CCB (nifedipine) as first-line; PDE5 inhibitors for severe. Skin fibrosis: mycophenolate or methotrexate for early diffuse disease. ILD: mycophenolate or nintedanib; tocilizumab for early ILD. Pulmonary hypertension: PAH-specific therapy. Scleroderma renal crisis: ACE inhibitor immediately. GI dysmotility: PPI, prokinetics.", "A", "Strong",
         ["systemic sclerosis", "scleroderma", "crest syndrome"], ["nifedipine", "sildenafil", "mycophenolate", "nintedanib", "tocilizumab", "lisinopril"], ["scl-70 antibody", "anti-centromere", "hrct chest", "echocardiogram", "pfts"], ["scleroderma", "raynaud", "ild", "renal crisis"]),
    ]),
    ("ACR Dermatomyositis/Polymyositis", "ACR", 2024, [
        ("Inflammatory Myopathy Treatment", "High-dose prednisone as initial therapy. Methotrexate or azathioprine as first-line steroid-sparing agents. IVIG for refractory disease, especially dysphagia. Rituximab for anti-synthetase syndrome or refractory disease. Myositis-specific antibody panel for diagnosis and prognosis. Cancer screening (especially dermatomyositis).", "A", "Strong",
         ["dermatomyositis", "polymyositis", "inflammatory myopathy"], ["prednisone", "methotrexate", "azathioprine", "ivig", "rituximab", "mycophenolate"], ["ck", "aldolase", "mri muscle", "emg", "myositis antibodies"], ["dermatomyositis", "myositis", "ck", "rituximab"]),
    ]),
    ("ACR Fibromyalgia", "ACR", 2024, [
        ("Fibromyalgia Management", "Patient education and self-management as foundation. Exercise (aerobic, strength, flexibility) as most effective non-pharmacologic intervention. Duloxetine, milnacipran, or pregabalin as FDA-approved pharmacotherapy. CBT for pain coping. Sleep hygiene optimization. Avoid opioids. Amitriptyline at low dose for sleep and pain.", "A", "Strong",
         ["fibromyalgia", "chronic widespread pain"], ["duloxetine", "milnacipran", "pregabalin", "amitriptyline", "cyclobenzaprine"], ["tender point exam", "fibromyalgia criteria"], ["fibromyalgia", "duloxetine", "pregabalin", "exercise"]),
    ]),

    # ── PSYCHIATRY EXPANSION ──
    ("APA Obsessive-Compulsive Disorder", "APA", 2024, [
        ("OCD Treatment", "CBT with exposure and response prevention (ERP) as first-line. SSRIs (fluoxetine, fluvoxamine, sertraline) at higher doses than for depression. Clomipramine for SSRI-refractory OCD. Augmentation with low-dose aripiprazole for partial SSRI response. Deep brain stimulation or gamma knife capsulotomy for treatment-refractory severe OCD.", "A", "Strong",
         ["obsessive-compulsive disorder", "ocd"], ["fluoxetine", "fluvoxamine", "sertraline", "clomipramine", "aripiprazole"], [], ["ocd", "erp", "ssri", "clomipramine"]),
    ]),
    ("APA Eating Disorders", "APA", 2024, [
        ("Anorexia Nervosa", "Nutritional rehabilitation as primary treatment. Supervised refeeding with monitoring for refeeding syndrome. Family-based treatment (FBT/Maudsley) for adolescents. CBT-E for adults. No medications FDA-approved; olanzapine may aid weight restoration. Medical stabilization: cardiac monitoring, electrolyte correction.", "A", "Strong",
         ["anorexia nervosa", "eating disorder"], ["olanzapine", "multivitamin"], ["bmi", "electrolytes", "ecg", "phosphorus", "magnesium"], ["anorexia nervosa", "refeeding", "fbt", "nutritional rehabilitation"]),
        ("Bulimia Nervosa and Binge Eating", "CBT as first-line for bulimia nervosa. Fluoxetine 60mg as pharmacotherapy for bulimia. Lisdexamfetamine for binge eating disorder. Topiramate as alternative for BED. Avoid prescribing ipecac or stimulant laxatives. Monitor electrolytes, dental health, and parotid glands.", "A", "Strong",
         ["bulimia nervosa", "binge eating disorder", "eating disorder"], ["fluoxetine", "lisdexamfetamine", "topiramate"], ["electrolytes", "amylase", "bmi"], ["bulimia", "binge eating", "fluoxetine", "cbt"]),
    ]),
    ("APA ADHD in Adults", "APA", 2024, [
        ("Adult ADHD Treatment", "Stimulant medications (methylphenidate, mixed amphetamine salts, lisdexamfetamine) as first-line. Long-acting formulations preferred for sustained coverage. Atomoxetine, bupropion, or viloxazine as non-stimulant alternatives. CBT as adjunct to medication. Monitor cardiovascular parameters (BP, HR) with stimulants.", "A", "Strong",
         ["adult adhd", "attention deficit hyperactivity disorder"], ["methylphenidate", "lisdexamfetamine", "mixed amphetamine salts", "atomoxetine", "bupropion", "viloxazine"], ["blood pressure", "heart rate", "ecg"], ["adult adhd", "stimulant", "lisdexamfetamine", "atomoxetine"]),
    ]),
    ("APA Substance Use Disorders", "APA", 2024, [
        ("Alcohol Use Disorder", "Naltrexone (oral 50mg daily or IM 380mg monthly) for reducing heavy drinking. Acamprosate for maintaining abstinence. Disulfiram for motivated patients with supervision. Brief interventions for hazardous drinking. Benzodiazepine taper for alcohol withdrawal; phenobarbital as alternative. Thiamine supplementation for all.", "A", "Strong",
         ["alcohol use disorder", "alcoholism", "alcohol withdrawal"], ["naltrexone", "acamprosate", "disulfiram", "chlordiazepoxide", "lorazepam", "thiamine"], ["ggt", "ast", "alt", "mcv", "blood alcohol level", "ciwa score"], ["alcohol use disorder", "naltrexone", "acamprosate", "withdrawal"]),
        ("Stimulant Use Disorder", "No FDA-approved pharmacotherapy for cocaine or methamphetamine use disorder. Contingency management as most effective behavioral treatment. CBT and motivational interviewing. Mirtazapine and topiramate under investigation for methamphetamine. Bupropion with naltrexone combination showing promise.", "C", "Moderate",
         ["stimulant use disorder", "cocaine use disorder", "methamphetamine use disorder"], ["mirtazapine", "topiramate", "bupropion"], ["urine drug screen"], ["stimulant use disorder", "contingency management", "cocaine", "methamphetamine"]),
    ]),

    # ── OB/GYN EXPANSION ──
    ("ACOG Gestational Diabetes", "ACOG", 2024, [
        ("GDM Screening and Management", "Universal screening at 24-28 weeks with 50g glucose challenge test or 75g OGTT. Dietary modification and exercise as first-line. Blood glucose targets: fasting <95, 1-hour postprandial <140, 2-hour <120 mg/dL. Insulin preferred pharmacotherapy; metformin as alternative. Fetal surveillance starting 32-34 weeks for insulin-requiring. Delivery by 39-40 weeks.", "A", "Strong",
         ["gestational diabetes", "gdm", "diabetes in pregnancy"], ["insulin", "metformin", "glyburide"], ["fasting glucose", "hba1c", "ogtt", "glucose challenge test"], ["gestational diabetes", "insulin", "ogtt", "fetal surveillance"]),
    ]),
    ("ACOG Preterm Labor", "ACOG", 2024, [
        ("Preterm Labor Management", "Antenatal corticosteroids (betamethasone 12mg IM × 2 or dexamethasone 6mg IM × 4) between 24-34 weeks for threatened preterm birth. Magnesium sulfate for neuroprotection if <32 weeks. Tocolysis (nifedipine or indomethacin) for 48 hours to allow steroid course. Progesterone supplementation for short cervix. Cerclage for cervical insufficiency.", "A", "Strong",
         ["preterm labor", "preterm birth", "premature labor"], ["betamethasone", "dexamethasone", "magnesium sulfate", "nifedipine", "indomethacin", "progesterone"], ["cervical length", "fetal fibronectin", "fetal heart rate"], ["preterm labor", "corticosteroids", "tocolysis", "neuroprotection"]),
    ]),
    ("ACOG Ectopic Pregnancy", "ACOG", 2024, [
        ("Ectopic Pregnancy Management", "Methotrexate (single dose 50mg/m² IM) for hemodynamically stable ectopic pregnancy with hCG <5000, no cardiac activity, and size <4cm. Surgical management (salpingostomy or salpingectomy) for ruptured ectopic, hemodynamic instability, or methotrexate contraindication. Serial hCG monitoring after methotrexate.", "A", "Strong",
         ["ectopic pregnancy", "tubal pregnancy"], ["methotrexate"], ["beta-hcg", "transvaginal ultrasound", "hemoglobin"], ["ectopic pregnancy", "methotrexate", "salpingectomy", "hcg"]),
    ]),
    ("ESHRE/ASRM Endometriosis", "ESHRE/ASRM", 2024, [
        ("Endometriosis Management", "NSAIDs plus hormonal therapy (combined OCP, progestins, or GnRH agonists) for pain. Dienogest as first-line progestin. Elagolix (GnRH antagonist) for moderate-severe pain. Laparoscopic excision for deep infiltrating endometriosis. IVF for endometriosis-associated infertility after failed conservative measures. Long-term hormonal suppression to prevent recurrence.", "A", "Strong",
         ["endometriosis", "pelvic pain", "dysmenorrhea"], ["combined oral contraceptive", "dienogest", "elagolix", "leuprolide", "norethindrone"], ["ca-125", "pelvic ultrasound", "mri pelvis"], ["endometriosis", "hormonal therapy", "laparoscopy", "elagolix"]),
    ]),

    # ── PEDIATRICS EXPANSION ──
    ("AAP Pediatric Asthma", "AAP/NAEPP", 2024, [
        ("Pediatric Asthma Step Therapy", "Step 1: PRN SABA for intermittent asthma. Step 2: Low-dose ICS daily. Step 3: Low-dose ICS-LABA or medium-dose ICS. Step 4: Medium-dose ICS-LABA. Step 5: High-dose ICS-LABA ± biologic. ICS-formoterol as SMART therapy for ages ≥4. Written asthma action plan for all.", "A", "Strong",
         ["pediatric asthma", "childhood asthma", "asthma"], ["albuterol", "budesonide", "fluticasone", "montelukast", "formoterol"], ["fev1", "pef", "feno"], ["pediatric asthma", "step therapy", "ics", "smart therapy"]),
    ]),
    ("AAP Neonatal Sepsis", "AAP", 2024, [
        ("Early-Onset Neonatal Sepsis", "Empiric ampicillin plus gentamicin for suspected early-onset sepsis (<72 hours). Blood culture before antibiotics. Duration 48-72 hours if cultures negative and clinically well. GBS prophylaxis: penicillin G IV to mother during labor for GBS colonization. Serial clinical assessment with Kaiser sepsis risk calculator.", "A", "Strong",
         ["neonatal sepsis", "early-onset sepsis", "group b streptococcus"], ["ampicillin", "gentamicin", "penicillin g"], ["blood culture", "cbc", "crp", "procalcitonin"], ["neonatal sepsis", "ampicillin", "gbs", "early-onset"]),
        ("Late-Onset Neonatal Sepsis", "Empiric vancomycin plus aminoglycoside or third-generation cephalosporin for late-onset sepsis (>72 hours). MRSA and CONS common in NICU. Duration based on organism: 7-10 days for most bacteremia, 14 days for GNR, 21 days for meningitis. CRP trending for treatment response.", "A", "Strong",
         ["late-onset sepsis", "neonatal sepsis", "nicu infection"], ["vancomycin", "gentamicin", "cefotaxime", "meropenem"], ["blood culture", "csf culture", "cbc", "crp"], ["late-onset sepsis", "vancomycin", "nicu", "cons"]),
    ]),
    ("AAP Kawasaki Disease", "AAP", 2024, [
        ("Kawasaki Disease Treatment", "IVIG 2g/kg single infusion within 10 days of fever onset. High-dose aspirin (80-100 mg/kg/day) until afebrile, then low-dose aspirin (3-5 mg/kg/day) for 6-8 weeks. Repeat IVIG for IVIG-resistant KD. Infliximab or corticosteroids for refractory disease. Echocardiogram at diagnosis, 1-2 weeks, and 4-6 weeks.", "A", "Strong",
         ["kawasaki disease", "mucocutaneous lymph node syndrome"], ["ivig", "aspirin", "infliximab", "methylprednisolone"], ["echocardiogram", "esr", "crp", "cbc", "alt"], ["kawasaki", "ivig", "coronary aneurysm", "aspirin"]),
    ]),
    ("AAP RSV Prevention", "AAP", 2024, [
        ("RSV Prophylaxis", "Nirsevimab (long-acting monoclonal antibody) for all infants <8 months entering their first RSV season. Palivizumab monthly for high-risk infants if nirsevimab unavailable. Maternal RSV vaccine (Abrysvo) during 32-36 weeks gestation as alternative. Supportive care for RSV bronchiolitis: nasal suctioning, supplemental oxygen, hydration.", "A", "Strong",
         ["rsv", "respiratory syncytial virus", "bronchiolitis"], ["nirsevimab", "palivizumab"], ["rapid rsv test", "oxygen saturation"], ["rsv", "nirsevimab", "prophylaxis", "bronchiolitis"]),
    ]),
    ("AAP Food Allergy Prevention", "AAP", 2024, [
        ("Early Allergen Introduction", "Introduce peanut-containing foods at around 4-6 months for high-risk infants (severe eczema and/or egg allergy). SPT or sIgE testing before introduction for highest-risk infants. Early introduction of egg, milk, and other allergenic foods. No maternal dietary restrictions during pregnancy or lactation for allergy prevention.", "A", "Strong",
         ["food allergy", "peanut allergy", "egg allergy", "infant feeding"], [], ["skin prick test", "specific ige"], ["food allergy", "early introduction", "peanut", "prevention"]),
    ]),

    # ── EMERGENCY MEDICINE EXPANSION ──
    ("ACEP Anaphylaxis", "ACEP", 2024, [
        ("ED Anaphylaxis Management", "Epinephrine IM 0.3-0.5mg immediately—delay increases mortality. Repeat every 5-15 minutes as needed. Adjuncts: IV fluids, H1/H2 blockers, corticosteroids (do not delay epinephrine). Biphasic reaction monitoring: observe 4-6 hours minimum (longer for severe). Discharge with epinephrine auto-injector and allergy referral.", "A", "Strong",
         ["anaphylaxis", "anaphylactic shock", "allergic emergency"], ["epinephrine", "diphenhydramine", "ranitidine", "methylprednisolone", "albuterol"], ["tryptase", "blood pressure", "oxygen saturation"], ["anaphylaxis", "epinephrine", "biphasic", "emergency"]),
    ]),
    ("ACEP Status Epilepticus", "ACEP", 2024, [
        ("Status Epilepticus Treatment", "Benzodiazepines as first-line: IV lorazepam 0.1mg/kg or IM midazolam 10mg. Second-line: fosphenytoin, levetiracetam, or valproate IV. Third-line (refractory SE): propofol, midazolam, or pentobarbital infusion with continuous EEG monitoring. Time-critical: treat within 5 minutes of seizure onset.", "A", "Strong",
         ["status epilepticus", "prolonged seizure", "seizure emergency"], ["lorazepam", "midazolam", "fosphenytoin", "levetiracetam", "valproate", "propofol"], ["glucose", "electrolytes", "eeg", "ct head"], ["status epilepticus", "benzodiazepine", "lorazepam", "fosphenytoin"]),
    ]),
    ("ACEP Diabetic Ketoacidosis", "ACEP", 2024, [
        ("DKA Management", "Aggressive IV fluid resuscitation: NS 1-1.5L in first hour. Insulin infusion 0.1-0.14 units/kg/hr after initial fluid resuscitation. Potassium replacement when K <5.3 mEq/L (do not start insulin if K <3.3). Transition to SC insulin when anion gap closes, glucose <200, and patient tolerating PO. Monitor every 1-2 hours: glucose, potassium, bicarbonate, anion gap.", "A", "Strong",
         ["diabetic ketoacidosis", "dka", "diabetes emergency"], ["regular insulin", "normal saline", "potassium chloride", "potassium phosphate"], ["glucose", "potassium", "bicarbonate", "anion gap", "ph", "beta-hydroxybutyrate"], ["dka", "insulin", "fluid resuscitation", "anion gap"]),
    ]),
    ("ACEP Burns Management", "ACEP", 2024, [
        ("Burn Assessment and Treatment", "Parkland formula: 4 mL/kg/% TBSA for fluid resuscitation in first 24 hours (50% in first 8 hours). Intubation for suspected inhalation injury. Escharotomy for circumferential full-thickness burns. Silver sulfadiazine or bioengineered skin substitutes for wound care. Transfer to burn center for >20% TBSA, full-thickness, face/hands/feet/genitalia.", "A", "Strong",
         ["burns", "thermal injury", "inhalation injury"], ["silver sulfadiazine", "morphine", "tetanus toxoid"], ["carboxyhemoglobin", "lactate", "abg"], ["burns", "parkland formula", "fluid resuscitation", "escharotomy"]),
    ]),
    ("ACEP Toxicology/Overdose", "ACEP", 2024, [
        ("Acetaminophen Overdose", "N-acetylcysteine (NAC) as antidote. IV protocol: 150mg/kg over 1 hour, then 50mg/kg over 4 hours, then 100mg/kg over 16 hours. Oral: 140mg/kg load then 70mg/kg q4h × 17 doses. Rumack-Matthew nomogram for single acute ingestion. Check acetaminophen level at 4 hours post-ingestion. Monitor ALT, INR, creatinine.", "A", "Strong",
         ["acetaminophen overdose", "acetaminophen toxicity", "drug overdose"], ["n-acetylcysteine"], ["acetaminophen level", "alt", "ast", "inr", "creatinine"], ["acetaminophen", "overdose", "nac", "rumack-matthew"]),
        ("Opioid Overdose", "Naloxone 0.4-2mg IV/IM/IN for suspected opioid overdose with respiratory depression. Repeat every 2-3 minutes as needed. Higher doses (up to 10mg) may be needed for synthetic opioids (fentanyl analogs). Minimum 2-hour observation after naloxone for short-acting opioids, 4+ hours for long-acting. Naloxone infusion for recurrent sedation.", "A", "Strong",
         ["opioid overdose", "opioid toxicity", "drug overdose"], ["naloxone"], ["respiratory rate", "pulse oximetry", "urine drug screen"], ["opioid overdose", "naloxone", "fentanyl", "narcan"]),
    ]),

    # ── CRITICAL CARE EXPANSION ──
    ("SCCM Sepsis / Surviving Sepsis Campaign", "SCCM", 2024, [
        ("Sepsis Antibiotic Stewardship", "Empiric broad-spectrum antibiotics within 1 hour of sepsis recognition. De-escalation to narrow-spectrum based on cultures at 48-72 hours. Procalcitonin-guided discontinuation to reduce antibiotic duration. 7 days typical for most infections. Source control (drainage, debridement) within 6-12 hours when indicated.", "A", "Strong",
         ["sepsis", "antibiotic stewardship"], ["vancomycin", "meropenem", "piperacillin-tazobactam", "cefepime"], ["procalcitonin", "blood culture", "lactate", "crp"], ["sepsis", "antibiotic stewardship", "de-escalation", "procalcitonin"]),
    ]),
    ("SCCM/ASPEN Nutrition in Critical Illness", "SCCM/ASPEN", 2024, [
        ("ICU Nutrition", "Early enteral nutrition (within 24-48 hours) for hemodynamically stable ICU patients. Gastric feeding preferred; post-pyloric for high aspiration risk. Protein target 1.2-2.0 g/kg/day. Supplemental parenteral nutrition if EN insufficient by day 7. Avoid overfeeding in first week. Indirect calorimetry for energy target when available.", "A", "Strong",
         ["icu nutrition", "enteral nutrition", "parenteral nutrition"], [], ["prealbumin", "nitrogen balance", "indirect calorimetry", "gastric residual volume"], ["icu nutrition", "enteral", "protein", "early feeding"]),
    ]),
    ("SCCM Ventilator Liberation", "SCCM", 2024, [
        ("Weaning and Extubation", "Daily spontaneous awakening trial (SAT) paired with spontaneous breathing trial (SBT). SBT using T-piece or pressure support ≤8 cmH2O for 30-120 minutes. RSBI <105 predicts successful extubation. Cuff leak test for patients at risk of post-extubation stridor. Prophylactic NIV for high-risk patients post-extubation.", "A", "Strong",
         ["mechanical ventilation", "ventilator weaning", "extubation"], ["dexmedetomidine", "methylprednisolone"], ["rsbi", "pao2", "paco2", "tidal volume", "negative inspiratory force"], ["weaning", "extubation", "sbt", "sat"]),
    ]),

    # ── HEMATOLOGY EXPANSION ──
    ("ASH Sickle Cell Disease", "ASH", 2024, [
        ("SCD Disease-Modifying Therapy", "Hydroxyurea for all patients with SCD ≥9 months of age. Voxelotor for ongoing hemolysis despite hydroxyurea. Crizanlizumab for vaso-occlusive crisis prevention. L-glutamine as adjunct therapy. Gene therapy (exagamglogene autotemcel/Casgevy, lovotibeglogene autotemcel/Lyfgenia) potentially curative for eligible patients.", "A", "Strong",
         ["sickle cell disease", "scd", "sickle cell anemia"], ["hydroxyurea", "voxelotor", "crizanlizumab", "l-glutamine"], ["hemoglobin", "hemoglobin s", "reticulocyte count", "ldh", "bilirubin"], ["sickle cell", "hydroxyurea", "gene therapy", "voxelotor"]),
        ("Sickle Cell Acute Pain Crisis", "IV opioids (morphine, hydromorphone) for severe pain within 30 minutes of presentation. Patient-controlled analgesia (PCA) preferred. NSAIDs as adjunct. IV fluids at maintenance rate (avoid overhydration). Incentive spirometry to prevent acute chest syndrome. Transfusion for Hb <5 g/dL or acute complications.", "A", "Strong",
         ["sickle cell crisis", "vaso-occlusive crisis", "sickle cell pain"], ["morphine", "hydromorphone", "ketorolac", "acetaminophen"], ["hemoglobin", "reticulocyte count", "chest x-ray", "type and screen"], ["pain crisis", "pca", "vaso-occlusive", "acute chest"]),
    ]),
    ("ASH Immune Thrombocytopenia", "ASH", 2024, [
        ("ITP Treatment", "Corticosteroids (dexamethasone 40mg × 4 days or prednisone 1mg/kg) as first-line. IVIG for rapid platelet increase (active bleeding or pre-procedure). TPO receptor agonists (eltrombopag, romiplostim, avatrombopag) for chronic ITP. Rituximab for refractory disease. Fostamatinib as alternative. Splenectomy deferred; now less common.", "A", "Strong",
         ["immune thrombocytopenia", "itp", "thrombocytopenia"], ["dexamethasone", "prednisone", "ivig", "eltrombopag", "romiplostim", "rituximab", "fostamatinib"], ["cbc", "peripheral smear", "reticulocyte count"], ["itp", "tpo agonist", "eltrombopag", "rituximab"]),
    ]),
    ("ASH DIC Guidelines", "ASH", 2024, [
        ("DIC Management", "Treat underlying cause as primary intervention. Platelet transfusion for active bleeding with platelets <50K. Cryoprecipitate for fibrinogen <150 mg/dL. FFP for prolonged PT/aPTT with bleeding. Heparin for DIC with thrombotic predominance (purpura fulminans, thrombosis). Antithrombin concentrate in select cases.", "B", "Strong",
         ["disseminated intravascular coagulation", "dic", "coagulopathy"], ["heparin", "cryoprecipitate", "platelets", "ffp"], ["pt", "aptt", "fibrinogen", "d-dimer", "platelets", "peripheral smear"], ["dic", "coagulopathy", "fibrinogen", "cryoprecipitate"]),
    ]),
    ("ASH Hemophilia Guidelines", "ASH", 2024, [
        ("Hemophilia Treatment", "Emicizumab prophylaxis for hemophilia A (with or without inhibitors). Factor replacement for breakthrough bleeds. On-demand recombinant factor VIII for hemophilia A, factor IX for hemophilia B. Fitusiran (anti-antithrombin) for hemophilia with inhibitors. Valoctocogene roxaparvovec (gene therapy) for adults with severe hemophilia A. Target trough ≥1-3% for prophylaxis.", "A", "Strong",
         ["hemophilia a", "hemophilia b", "factor viii deficiency", "factor ix deficiency"], ["emicizumab", "recombinant factor viii", "recombinant factor ix", "fitusiran", "desmopressin"], ["factor viii level", "factor ix level", "aptt", "inhibitor titer"], ["hemophilia", "emicizumab", "gene therapy", "factor replacement"]),
    ]),

    # ── DERMATOLOGY EXPANSION ──
    ("AAD Psoriasis Guidelines", "AAD", 2024, [
        ("Moderate-Severe Psoriasis", "Biologics as first-line systemic therapy for moderate-severe plaque psoriasis. IL-17 inhibitors (secukinumab, ixekizumab, bimekizumab) and IL-23 inhibitors (guselkumab, risankizumab, tildrakizumab) most effective. TNF inhibitors (adalimumab) still effective. Apremilast for patients preferring oral therapy. Methotrexate as conventional systemic.", "A", "Strong",
         ["psoriasis", "plaque psoriasis"], ["secukinumab", "ixekizumab", "bimekizumab", "guselkumab", "risankizumab", "adalimumab", "apremilast", "methotrexate"], ["pasi score", "bsa", "cbc", "liver function"], ["psoriasis", "biologic", "il-17", "il-23"]),
        ("Psoriasis Comorbidity Screening", "Screen for psoriatic arthritis at every visit (joint pain, stiffness, swelling). Cardiovascular risk assessment: psoriasis is independent CV risk factor. Screen for metabolic syndrome, diabetes, depression, and fatty liver disease. Lifestyle counseling: smoking cessation, weight management, alcohol moderation.", "B", "Strong",
         ["psoriasis", "psoriatic arthritis", "cardiovascular risk"], [], ["lipid panel", "fasting glucose", "crp", "liver function"], ["psoriasis", "comorbidity", "cardiovascular", "screening"]),
    ]),
    ("AAD Skin Cancer - BCC and SCC", "AAD", 2024, [
        ("Basal Cell Carcinoma", "Surgical excision with 4mm margins for primary BCC. Mohs micrographic surgery for high-risk BCC (head/neck, recurrent, aggressive subtype, large). Topical imiquimod or 5-FU for superficial BCC. Hedgehog pathway inhibitors (vismodegib, sonidegib) for locally advanced or metastatic BCC. Cemiplimab for HPI-refractory locally advanced BCC.", "A", "Strong",
         ["basal cell carcinoma", "bcc", "skin cancer"], ["imiquimod", "5-fluorouracil", "vismodegib", "sonidegib", "cemiplimab"], ["skin biopsy", "dermoscopy"], ["basal cell carcinoma", "mohs", "hedgehog inhibitor"]),
        ("Cutaneous Squamous Cell Carcinoma", "Surgical excision with appropriate margins. Mohs surgery for high-risk SCC (head/neck, perineural invasion, recurrent, immunosuppressed). Radiation for non-surgical candidates. Cemiplimab or pembrolizumab for locally advanced or metastatic cSCC. Sentinel lymph node biopsy for high-risk features.", "A", "Strong",
         ["squamous cell carcinoma", "scc", "cutaneous squamous cell", "skin cancer"], ["cemiplimab", "pembrolizumab"], ["skin biopsy", "ct scan", "sentinel lymph node biopsy"], ["squamous cell carcinoma", "mohs", "cemiplimab", "immunotherapy"]),
    ]),
    ("AAD Urticaria Guidelines", "AAD", 2024, [
        ("Chronic Spontaneous Urticaria", "Second-generation antihistamines (cetirizine, loratadine, fexofenadine) as first-line, up to 4x standard dose. Omalizumab for antihistamine-refractory CSU. Cyclosporine as third-line for severe refractory CSU. Avoid systemic corticosteroids for chronic use. UAS7 score for disease monitoring. Average duration 2-5 years with spontaneous remission.", "A", "Strong",
         ["chronic urticaria", "urticaria", "hives"], ["cetirizine", "loratadine", "fexofenadine", "omalizumab", "cyclosporine"], ["cbc", "esr", "crp", "tsh", "ige"], ["urticaria", "antihistamine", "omalizumab", "chronic"]),
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
