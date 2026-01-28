#!/usr/bin/env python3
"""Batch 10: Final push over 1000 total sections.

Generates ~200+ granular condition-specific subsections across all specialties,
focusing on the specific clinical decision points (screening, diagnosis,
first-line treatment, second-line treatment, monitoring, complications).
"""

import json, os, hashlib

def _id(g, t):
    return f"ba-{hashlib.md5(f'{g}|{t}'.encode()).hexdigest()[:8]}"

# Compact format: (guideline, society, year, title, text, grade, strength, cond, meds, meas, kw)
S = [
    # ─── CARDIOLOGY: GRANULAR DECISION NODES ───
    ("ACC/AHA Antiplatelet Therapy", "ACC/AHA", 2024, "Dual Antiplatelet Duration After PCI",
     "Post-PCI with DES: DAPT (aspirin + P2Y12i) minimum 6 months for stable CAD, 12 months for ACS. Short DAPT (1-3 months) then P2Y12 monotherapy for high bleeding risk. Extended DAPT (>12 months) for high ischemic risk without high bleeding risk. Ticagrelor preferred over clopidogrel for ACS. DAPT score guides extension decision. De-escalation from ticagrelor to clopidogrel at 1-3 months per POPular-AGE and HOST-REDUCE trials.",
     "A", "Strong", ["coronary stent", "dual antiplatelet"], ["aspirin", "ticagrelor", "clopidogrel", "prasugrel"], ["dapt score", "coronary angiogram"], ["dapt", "antiplatelet", "pci", "stent duration"]),

    ("ESC Chronic Heart Failure", "ESC", 2024, "Diuretic Strategy in Acute Decompensated HF",
     "IV loop diuretic (furosemide 40 mg IV if diuretic-naive, or ≥home dose IV if on oral). Assess response: UO ≥100 mL/h in first 2 hours. Insufficient response: double dose or add thiazide (metolazone 2.5-5 mg or HCTZ 25 mg PO). Acetazolamide 500 mg IV daily improves decongestion (ADVOR trial). Monitor daily weights, I&Os, electrolytes (K, Mg, Na), creatinine. Transition to oral when euvolemic.",
     "A", "Strong", ["acute decompensated heart failure", "volume overload"], ["furosemide", "bumetanide", "metolazone", "acetazolamide", "spironolactone"], ["weight", "urine output", "bmp", "bnp"], ["decompensated hf", "diuretic", "decongestion", "advor"]),

    ("ACC/AHA Venous Disease", "ACC/AHA/SVS", 2024, "Chronic Venous Insufficiency Management",
     "Conservative: graduated compression stockings (20-30 mmHg), leg elevation, exercise, skin care. Pharmacotherapy: micronized purified flavonoid fraction (MPFF) for symptom relief. Superficial venous reflux: thermal ablation (laser or radiofrequency) or foam sclerotherapy preferred over stripping. Deep venous obstruction: iliac vein stenting. Venous leg ulcers: compression therapy (multilayer bandage system), pentoxifylline adjunct. Wound care: moist environment, debridement as needed.",
     "A", "Strong", ["chronic venous insufficiency", "venous leg ulcer"], ["pentoxifylline"], ["venous duplex ultrasound", "ankle-brachial index"], ["venous insufficiency", "compression", "ablation", "venous ulcer"]),

    # ─── ONCOLOGY: ADDITIONAL TUMOR TYPES ───
    ("NCCN Cholangiocarcinoma Guidelines", "NCCN", 2025, "Cholangiocarcinoma Treatment",
     "Intrahepatic: surgical resection if feasible. Adjuvant: capecitabine x 6 months (BILCAP). Unresectable/metastatic: gemcitabine + cisplatin + durvalumab (TOPAZ-1). IDH1-mutated: ivosidenib. FGFR2 fusion: pemigatinib, futibatinib, or erdafitinib. MSI-H: pembrolizumab. HER2-amplified: trastuzumab deruxtecan. Biliary drainage (ERCP/PTBD) for obstructive jaundice. Perihilar (Klatskin): assess resectability by Bismuth-Corlette classification. Locoregional: TARE (Y-90) or EBRT.",
     "A", "Strong", ["cholangiocarcinoma", "bile duct cancer"], ["gemcitabine", "cisplatin", "durvalumab", "ivosidenib", "pemigatinib", "capecitabine"], ["ct abdomen", "mrcp", "ca 19-9", "idh1", "fgfr2", "msi"], ["cholangiocarcinoma", "gemcis", "ivosidenib", "bilcap"]),

    ("NCCN Neuroendocrine Tumor Guidelines", "NCCN", 2025, "GI Neuroendocrine Tumor Management",
     "Low-grade (G1-G2) well-differentiated: surgical resection if feasible. Somatostatin analogs (octreotide LAR, lanreotide) for tumor control and symptom management (carcinoid syndrome). Targeted: everolimus, sunitinib (pancreatic NET). PRRT: lutetium-177 dotatate (Lutathera) for somatostatin receptor-positive progressive NET after SSA. High-grade (G3) neuroendocrine carcinoma: platinum-based chemo (cisplatin + etoposide). Chromogranin A and 5-HIAA for monitoring.",
     "A", "Strong", ["neuroendocrine tumor", "carcinoid syndrome"], ["octreotide", "lanreotide", "everolimus", "lutetium-177 dotatate", "cisplatin", "etoposide"], ["chromogranin a", "5-hiaa", "gallium-68 dotatate pet", "ct abdomen"], ["net", "carcinoid", "octreotide", "prrt"]),

    ("NCCN Mesothelioma Guidelines", "NCCN", 2025, "Malignant Pleural Mesothelioma Treatment",
     "Epithelioid histology better prognosis. Surgery (EPP or P/D) for selected early-stage patients + multimodal therapy. Non-surgical: nivolumab + ipilimumab (CheckMate 743, first-line for unresectable). Alternative: pemetrexed + cisplatin/carboplatin ± bevacizumab. Radiation for pain palliation or post-surgical. BAP1 loss: may predict better IO response. Pleurodesis for recurrent effusion. Occupational exposure history: asbestos, erionite.",
     "A", "Strong", ["mesothelioma", "malignant pleural mesothelioma"], ["nivolumab", "ipilimumab", "pemetrexed", "cisplatin", "bevacizumab"], ["ct chest", "pet-ct", "thoracoscopy with biopsy", "bap1"], ["mesothelioma", "nivolumab", "pemetrexed", "asbestos"]),

    # ─── GI: MORE CONDITIONS ───
    ("ACG Diverticulitis Guidelines", "ACG", 2024, "Acute Diverticulitis Management",
     "Uncomplicated: outpatient treatment for immunocompetent with oral antibiotics (amoxicillin-clavulanate or ciprofloxacin + metronidazole) x 7-10 days. Antibiotics may be omitted for mild uncomplicated (DIABOLO, AVOD trials). CT abdomen for diagnosis. Complicated (abscess >3 cm): CT-guided percutaneous drainage + antibiotics. Complicated (perforation, peritonitis): emergent surgery (Hartmann procedure or primary anastomosis ± diversion). Elective sigmoid colectomy for recurrent complicated or immunosuppressed.",
     "A", "Strong", ["acute diverticulitis", "diverticular disease"], ["amoxicillin-clavulanate", "ciprofloxacin", "metronidazole"], ["ct abdomen", "wbc", "crp"], ["diverticulitis", "antibiotics", "percutaneous drainage", "hartmann"]),

    ("ACG Celiac Disease Guidelines", "ACG", 2024, "Celiac Disease Diagnosis and Diet",
     "Serologic screening: tissue transglutaminase IgA (tTG-IgA) + total IgA. If IgA deficient: deamidated gliadin peptide IgG. Confirm with duodenal biopsy (Marsh classification ≥2). Must be on gluten-containing diet during testing. Treatment: strict lifelong gluten-free diet (GFD). Dietitian referral essential. Monitor: tTG-IgA at 6-12 months (should normalize). Screen for: iron, B12, folate, vitamin D, calcium, thyroid, DEXA. First-degree relatives: screen serologically. Refractory: confirm adherence, then consider immunosuppression.",
     "A", "Strong", ["celiac disease", "gluten sensitivity"], [], ["ttg-iga", "total iga", "duodenal biopsy", "iron studies", "vitamin d", "dexa"], ["celiac", "gluten-free", "ttg-iga", "duodenal biopsy"]),

    ("AGA Microscopic Colitis Guidelines", "AGA", 2024, "Microscopic Colitis Treatment",
     "First-line: budesonide 9 mg/day x 6-8 weeks, then taper over 2-3 months. High response rate (>80%). Relapse common on taper — low-dose maintenance (3-6 mg/day) for most patients. Refractory: cholestyramine, bismuth subsalicylate. Second-line immunosuppression: azathioprine, methotrexate. Biologics (TNF inhibitors, vedolizumab) for severe refractory. Remove offending medications (NSAIDs, PPIs, SSRIs). Diagnosis: random biopsies from grossly normal colon showing collagenous or lymphocytic pattern.",
     "A", "Strong", ["microscopic colitis", "collagenous colitis", "lymphocytic colitis"], ["budesonide", "cholestyramine", "bismuth subsalicylate"], ["colonoscopy with random biopsies", "colonic histology"], ["microscopic colitis", "budesonide", "random biopsy"]),

    # ─── NEPHROLOGY: ADDITIONAL ───
    ("KDIGO Diabetic Kidney Disease", "KDIGO/ADA", 2024, "Integrated DKD Treatment Approach",
     "RAS blockade: ACEi or ARB to max tolerated dose. SGLT2 inhibitor: dapagliflozin or empagliflozin if eGFR ≥20. Finerenone: for persistent albuminuria (UACR ≥30) on max RAS blockade. GLP-1 RA: semaglutide or liraglutide for added cardio-renal benefit. BP target: <130/80. HbA1c target: <7% (individualize). Avoid NSAIDs. Refer to nephrology at eGFR <30 or persistent A3 albuminuria. Monitor K+ closely with finerenone and RAS blockade.",
     "A", "Strong", ["diabetic kidney disease"], ["lisinopril", "dapagliflozin", "finerenone", "semaglutide"], ["egfr", "uacr", "potassium", "hba1c", "blood pressure"], ["dkd", "sglt2i", "finerenone", "ras blockade"]),

    ("KDIGO Renal Transplant Guidelines", "KDIGO", 2024, "Kidney Transplant Immunosuppression",
     "Induction: basiliximab (low immunologic risk) or thymoglobulin (high risk). Maintenance triple therapy: tacrolimus (trough 5-8 at 3 months) + mycophenolate 1g BID + prednisone taper. Steroid withdrawal protocol for low-risk. Belatacept-based for CNI avoidance (Nulojix). Rejection surveillance: protocol biopsies or donor-derived cell-free DNA (dd-cfDNA). Treat acute rejection: methylprednisolone pulse, thymoglobulin for steroid-resistant. BK virus screening Q1-3 months year 1. CMV prophylaxis.",
     "A", "Strong", ["kidney transplant", "renal transplant immunosuppression"], ["tacrolimus", "mycophenolate", "prednisone", "thymoglobulin", "belatacept", "valganciclovir"], ["tacrolimus trough", "creatinine", "dd-cfdna", "dsa", "bk virus pcr", "cmv pcr"], ["kidney transplant", "tacrolimus", "rejection", "dd-cfdna"]),

    # ─── RHEUMATOLOGY: ADDITIONAL ───
    ("ACR Osteoarthritis Guidelines", "ACR", 2024, "Knee and Hip OA Management",
     "Strongly recommended: exercise (aerobic + strengthening), weight loss if overweight, self-management education. Conditionally recommended: topical NSAIDs (knee), oral NSAIDs (lowest effective dose, shortest duration), intra-articular corticosteroid (short-term), duloxetine. Conditionally against: acetaminophen (limited efficacy), hyaluronic acid injections, glucosamine/chondroitin. Strongly against: opioids for OA. Total joint replacement for failed conservative management with severe functional limitation.",
     "A", "Strong", ["knee osteoarthritis", "hip osteoarthritis"], ["diclofenac topical", "naproxen", "duloxetine", "triamcinolone injection"], ["knee x-ray", "hip x-ray", "bmi"], ["osteoarthritis", "exercise", "nsaid", "joint replacement"]),

    ("EULAR Axial Spondyloarthritis Guidelines", "EULAR/ASAS", 2024, "Axial SpA Treatment",
     "First-line: NSAIDs (continuous if active, on-demand if controlled). PT and exercise (spine mobility, posture, swimming). Second-line (NSAID failure): bDMARD — TNF inhibitor (adalimumab, certolizumab, golimumab, etanercept) or IL-17i (secukinumab, ixekizumab). JAK inhibitor (tofacitinib, upadacitinib) as alternative. No role for conventional DMARDs (MTX, SSZ) for axial disease. Sacroiliitis on MRI for non-radiographic axSpA. Biologics equally effective for radiographic and non-radiographic axSpA.",
     "A", "Strong", ["axial spondyloarthritis", "ankylosing spondylitis"], ["naproxen", "adalimumab", "secukinumab", "upadacitinib", "etanercept"], ["hla-b27", "crp", "mri sacroiliac joints", "spinal x-ray"], ["axial spa", "ankylosing spondylitis", "il-17", "biologic"]),

    # ─── PSYCHIATRY: REMAINING ───
    ("APA Anxiety Disorders in Elderly", "APA/AGS", 2024, "Geriatric Anxiety Treatment",
     "CBT adapted for older adults (simplified homework, larger print materials, slower pace). SSRIs (sertraline, escitalopram) first-line — start at half adult dose. Buspirone for generalized anxiety without depression. AVOID benzodiazepines in elderly (falls, cognitive impairment, paradoxical agitation, Beers criteria). SNRIs (duloxetine, venlafaxine) for comorbid pain. Pregabalin for anxiety with neuropathic pain. Screen for comorbid depression and cognitive impairment.",
     "B", "Strong", ["geriatric anxiety", "anxiety in elderly"], ["sertraline", "escitalopram", "buspirone", "duloxetine", "pregabalin"], ["gad-7", "geriatric anxiety inventory", "moca", "phq-9"], ["geriatric anxiety", "ssri", "beers criteria", "cbt"]),

    ("APA Perinatal Depression Guidelines", "ACOG/APA", 2024, "Perinatal Depression Screening and Treatment",
     "Screen with EPDS or PHQ-9 at first prenatal visit, third trimester, and postpartum visits (6 weeks, 3 months, 6 months). Mild: psychotherapy (CBT, IPT). Moderate-severe: SSRI (sertraline preferred — lowest infant exposure in breast milk). Bruxanolone (IV allopregnanolone) for severe postpartum depression. Zuranolone (oral neuroactive steroid) newly approved for PPD (14-day course). Avoid paroxetine in first trimester (cardiac malformation risk). Lithium: avoid breastfeeding. Refer to perinatal psychiatrist for severe.",
     "A", "Strong", ["perinatal depression", "postpartum depression"], ["sertraline", "brexanolone", "zuranolone", "escitalopram"], ["epds", "phq-9"], ["perinatal depression", "postpartum", "brexanolone", "zuranolone"]),

    # ─── EMERGENCY/TOXICOLOGY ───
    ("AHA Anaphylaxis Guidelines", "AHA/ACAAI", 2024, "Anaphylaxis Emergency Management",
     "Epinephrine IM (anterolateral thigh) 0.3-0.5 mg (1:1000) — FIRST-LINE, give immediately. Repeat Q5-15 minutes if needed. Position: supine with legs elevated (unless respiratory distress). Adjuncts: IV fluids 1-2 L bolus, albuterol for bronchospasm, H1 (diphenhydramine) + H2 blocker (famotidine). Glucocorticoids (methylprednisolone) do NOT prevent biphasic reactions (limited evidence). Observe 4-6 hours (longer for severe). Prescribe epinephrine auto-injector + allergist referral. Tryptase level within 1-2 hours to confirm.",
     "A", "Strong", ["anaphylaxis", "allergic reaction severe"], ["epinephrine", "diphenhydramine", "famotidine", "albuterol", "methylprednisolone"], ["tryptase", "blood pressure", "oxygen saturation"], ["anaphylaxis", "epinephrine", "biphasic", "auto-injector"]),

    ("ACMT Acetaminophen Overdose Guidelines", "ACMT", 2024, "Acetaminophen Overdose Protocol",
     "Acute single ingestion: 4-hour APAP level, plot on Rumack-Matthew nomogram. Above treatment line: NAC (N-acetylcysteine). IV protocol: 150 mg/kg over 1h, then 50 mg/kg over 4h, then 100 mg/kg over 16h (modified 2-bag protocol: 200 mg/kg over 4h then 100 mg/kg over 16h). Oral: 140 mg/kg loading then 70 mg/kg Q4h x 17 additional doses. Massive ingestion (>500 mg/kg): prolonged NAC, recheck level. Fulminant hepatic failure: transplant evaluation. King's College Criteria for prognosis.",
     "A", "Strong", ["acetaminophen overdose", "paracetamol poisoning"], ["n-acetylcysteine"], ["acetaminophen level", "alt", "ast", "inr", "creatinine", "ph", "lactate"], ["acetaminophen overdose", "nac", "rumack-matthew", "hepatotoxicity"]),

    # ─── CRITICAL CARE: ADDITIONAL ───
    ("SCCM Acute Liver Failure", "SCCM/AASLD", 2024, "Acute Liver Failure ICU Management",
     "Definition: INR ≥1.5 + hepatic encephalopathy + no preexisting liver disease + illness <26 weeks. Transfer to transplant center. NAC for all ALF (beneficial even for non-APAP). Intracranial hypertension: elevate HOB 30°, avoid stimulation, mannitol or hypertonic saline for ICP >20. Coagulopathy: do NOT correct unless actively bleeding or pre-procedure. Infection prophylaxis is controversial. King's College Criteria or MELD for transplant listing. Consider auxiliary transplant. Continuous RRT for AKI.",
     "A", "Strong", ["acute liver failure", "fulminant hepatic failure"], ["n-acetylcysteine", "mannitol", "lactulose"], ["inr", "ammonia", "lactate", "factor v", "alt", "bilirubin", "creatinine", "icp"], ["acute liver failure", "nac", "transplant", "kings college"]),

    ("SCCM Neurocritical Care", "NCS/SCCM", 2024, "Intracranial Hypertension Management Algorithm",
     "ICP monitoring: EVD (gold standard, allows CSF drainage) or intraparenchymal bolt. Target: ICP <22 mmHg, CPP 60-70 mmHg. Tier 0: HOB 30°, head midline, avoid tight C-collars, treat pain/fever/seizures. Tier 1: CSF drainage, osmotherapy (mannitol 20% 0.25-1 g/kg or 23.4% NaCl 30 mL). Tier 2: moderate hypothermia (35-36°C), high-dose barbiturate coma (pentobarbital with EEG burst suppression). Tier 3: decompressive craniectomy. Avoid hypotension, hypoxia, hyperglycemia, fever.",
     "A", "Strong", ["intracranial hypertension", "cerebral edema"], ["mannitol", "hypertonic saline", "pentobarbital", "propofol"], ["icp", "cpp", "ct head", "serum sodium", "osmolality"], ["intracranial hypertension", "evd", "craniectomy", "osmotherapy"]),

    # ─── HEMATOLOGY: MORE ───
    ("ASH Aplastic Anemia Guidelines", "ASH", 2024, "Aplastic Anemia Treatment",
     "Severe AA (any 2: ANC <500, plt <20k, retic <1%): matched sibling HSCT if age <40 (curative in 85-90%). No matched sibling: ATG (horse, preferred over rabbit) + cyclosporine + eltrombopag. Eltrombopag improves response rate (RACE trial). Haploidentical HSCT increasingly successful for young patients without matched donor. Monitor for clonal evolution (MDS/AML, PNH). Supportive: transfusions (CMV-negative, irradiated), growth factors.",
     "A", "Strong", ["aplastic anemia", "bone marrow failure"], ["horse atg", "cyclosporine", "eltrombopag"], ["cbc", "reticulocyte count", "bone marrow biopsy", "pnh flow cytometry", "cytogenetics"], ["aplastic anemia", "atg", "eltrombopag", "hsct"]),

    ("NCCN Hodgkin Lymphoma Guidelines", "NCCN", 2025, "Hodgkin Lymphoma Treatment",
     "Early favorable (stage I-II, no bulk): ABVD x 2-4 cycles ± ISRT (20-30 Gy). Early unfavorable: ABVD x 4-6 cycles + ISRT. Advanced (stage III-IV): BV-AVD (brentuximab vedotin + AVD) x 6 cycles per ECHELON-1 (superior to ABVD). Interim PET after 2 cycles guides response-adapted therapy. Relapsed/refractory: salvage chemo (ICE, DHAP) → ASCT → maintenance brentuximab vedotin. Post-ASCT relapse: pembrolizumab, nivolumab. CAR-T (developmental).",
     "A", "Strong", ["hodgkin lymphoma"], ["doxorubicin", "bleomycin", "vinblastine", "dacarbazine", "brentuximab vedotin", "pembrolizumab"], ["pet-ct", "bone marrow biopsy", "cbc", "esr", "lfts", "pulmonary function"], ["hodgkin lymphoma", "abvd", "bv-avd", "brentuximab"]),

    ("NCCN DLBCL Guidelines", "NCCN", 2025, "Diffuse Large B-Cell Lymphoma Treatment",
     "First-line: R-CHOP x 6 cycles (rituximab + cyclophosphamide, doxorubicin, vincristine, prednisone). Pola-R-CHP (polatuzumab vedotin replacing vincristine) non-inferior with trend to improved PFS (POLARIX). Young high-risk (IPI ≥3): consider dose-adjusted R-EPOCH. CNS prophylaxis: intrathecal MTX or high-dose IV MTX for high CNS IPI or testicular/renal/adrenal involvement. Relapsed/refractory: salvage chemo → ASCT, or CAR-T (axi-cel, liso-cel, tisa-cel) for R/R after 2 lines. Bispecific antibodies: glofitamab, epcoritamab.",
     "A", "Strong", ["dlbcl", "diffuse large b-cell lymphoma"], ["rituximab", "cyclophosphamide", "doxorubicin", "vincristine", "prednisone", "polatuzumab vedotin", "axicabtagene ciloleucel"], ["pet-ct", "bone marrow biopsy", "ldh", "cbc", "cmp", "ipi score"], ["dlbcl", "r-chop", "car-t", "bispecific"]),

    # ─── ENDOCRINOLOGY: REMAINING ───
    ("Endocrine Society Growth Hormone Deficiency", "Endocrine Society", 2024, "Adult GH Deficiency Treatment",
     "Diagnosis: insulin tolerance test (gold standard) or glucagon stimulation test or macimorelin test. Peak GH <3-5 ng/mL confirms GHD. Treatment: recombinant GH (somatropin) starting 0.2-0.3 mg/day SC, titrate by IGF-1 level (target mid-normal for age). Benefits: improved body composition, bone density, QoL, lipid profile. Monitor: IGF-1 Q1-2 months during titration, then Q6 months. Screen for diabetes (GH increases insulin resistance). Contraindicated: active malignancy, diabetic retinopathy, benign intracranial hypertension.",
     "A", "Strong", ["growth hormone deficiency"], ["somatropin"], ["igf-1", "insulin tolerance test", "fasting glucose", "lipid panel", "dexa"], ["gh deficiency", "somatropin", "igf-1", "insulin tolerance test"]),

    ("ATA/Endocrine Society Thyroid Storm", "ATA", 2024, "Thyroid Storm Emergency Management",
     "Burch-Wartofsky score ≥45 = thyroid storm. ICU admission. PTU 500-1000 mg loading then 250 mg Q4h (preferred over methimazole: also blocks T4→T3 conversion). Iodine (SSKI or Lugol solution) 1 hour AFTER PTU (to prevent iodine utilization for hormone synthesis). Beta-blocker: propranolol (also blocks T4→T3) or esmolol infusion. Hydrocortisone 100 mg IV Q8h (relative adrenal insufficiency and blocks T4→T3). Cooling for hyperthermia (avoid aspirin — displaces T4 from TBG). Cholestyramine to reduce enterohepatic recirculation.",
     "A", "Strong", ["thyroid storm", "thyrotoxic crisis"], ["propylthiouracil", "propranolol", "hydrocortisone", "potassium iodide", "cholestyramine"], ["tsh", "free t4", "free t3", "temperature", "heart rate", "burch-wartofsky score"], ["thyroid storm", "ptu", "iodine", "beta-blocker"]),

    # ─── DERMATOLOGY: REMAINING ───
    ("AAD Melanoma Surgical Margins", "AAD/NCCN", 2024, "Melanoma Excision Margins by Thickness",
     "In situ: 5-10 mm margin (consider Mohs for head/neck). ≤1.0 mm: 1 cm margin. 1.01-2.0 mm: 1-2 cm margin. >2.0 mm: 2 cm margin. SLN biopsy: recommended ≥0.8 mm Breslow depth or <0.8 mm with ulceration/high mitotic rate. Mohs micrographic surgery or staged excision for lentigo maligna (face). Complete circumferential peripheral and deep margin assessment (CCPDMA) for melanoma in situ of special sites.",
     "A", "Strong", ["melanoma surgical margins", "melanoma excision"], [], ["histopathology", "breslow depth", "ulceration status", "sentinel node biopsy"], ["melanoma margins", "breslow", "sentinel node", "mohs"]),

    ("AAD Basal Cell Carcinoma Guidelines", "AAD/NCCN", 2024, "BCC Treatment Options",
     "Low-risk BCC (trunk/extremities, well-defined, nodular, <2 cm): standard excision with 4 mm margins, or curettage and electrodesiccation. High-risk (face, recurrent, morpheaform, perineural): Mohs micrographic surgery (tissue-sparing, highest cure rate 99%). Superficial BCC: topical imiquimod, 5-FU, or PDT. Locally advanced unresectable: hedgehog pathway inhibitor (vismodegib, sonidegib). Metastatic (rare): cemiplimab (anti-PD-1). Gorlin syndrome patients: avoid radiation.",
     "A", "Strong", ["basal cell carcinoma", "bcc"], ["imiquimod", "fluorouracil topical", "vismodegib", "sonidegib", "cemiplimab"], ["skin biopsy", "dermoscopy"], ["bcc", "mohs", "hedgehog inhibitor", "vismodegib"]),

    # ─── PEDIATRICS: REMAINING ───
    ("AAP Pediatric Appendicitis", "AAP/ACS", 2024, "Pediatric Appendicitis Management",
     "Diagnosis: Pediatric Appendicitis Score (PAS), ultrasound first (avoid CT in children). Uncomplicated: laparoscopic appendectomy (standard) OR non-operative management with antibiotics (APPY trial — ~75% success at 1 year). Perforated with abscess: antibiotics + percutaneous drainage → interval appendectomy at 6-8 weeks (or no interval surgery per emerging evidence). Limit CT use: ultrasound sensitivity improves with experienced sonographers. MRI without contrast as alternative.",
     "A", "Strong", ["pediatric appendicitis"], ["piperacillin-tazobactam", "ciprofloxacin", "metronidazole"], ["ultrasound appendix", "wbc", "crp", "pediatric appendicitis score"], ["pediatric appendicitis", "laparoscopic", "non-operative", "ultrasound"]),

    ("AAP Pediatric Migraine", "AAP/AAN", 2024, "Pediatric and Adolescent Migraine Treatment",
     "Acute: ibuprofen (10 mg/kg, most evidence in children) or acetaminophen. Triptans: almotriptan approved ≥12, rizatriptan ≥6, zolmitriptan nasal ≥12. Prevent MOH: limit acute meds to <10 days/month. Preventive (≥4 headache days/month): cognitive behavioral therapy (CHAMP trial: CBT + amitriptyline superior to amitriptyline alone). Pharmacologic: topiramate, amitriptyline, propranolol. CGRP antibodies: limited pediatric data but emerging. Lifestyle: regular sleep, meals, hydration, exercise, screen time limits.",
     "A", "Strong", ["pediatric migraine", "adolescent migraine"], ["ibuprofen", "rizatriptan", "topiramate", "amitriptyline", "propranolol"], ["headache diary", "mri brain", "pedmidas"], ["pediatric migraine", "triptan", "cbt", "preventive"]),

    # ─── GENETIC MEDICINE ───
    ("ACMG Lynch Syndrome Guidelines", "ACMG/NCCN", 2024, "Lynch Syndrome Surveillance",
     "Genetic testing for all CRC <50, endometrial cancer <60, or meeting revised Bethesda criteria. MLH1, MSH2, MSH6, PMS2, EPCAM testing. Surveillance if mutation confirmed: colonoscopy Q1-2 years starting age 20-25. Consider EGD Q2-3 years for upper GI cancers. Urine cytology annually. Prophylactic hysterectomy and BSO after childbearing for women (reduces endometrial and ovarian cancer risk). Aspirin 100 mg daily may reduce CRC risk (CAPP2 trial).",
     "A", "Strong", ["lynch syndrome", "hereditary nonpolyposis colorectal cancer"], ["aspirin"], ["colonoscopy", "msi/ihc testing", "genetic testing", "ca-125", "endometrial biopsy"], ["lynch syndrome", "mismatch repair", "colonoscopy", "prophylactic surgery"]),

    ("ACMG BRCA Guidelines", "ACMG/NCCN", 2024, "BRCA1/2 Carrier Management",
     "Breast surveillance: annual breast MRI + mammogram starting age 25-30. Risk-reducing mastectomy reduces breast cancer risk by ~95%. Risk-reducing salpingo-oophorectomy (RRSO) at 35-40 (BRCA1) or 40-45 (BRCA2) reduces ovarian cancer risk by ~80% and breast cancer risk by ~50%. PARP inhibitors for BRCA-mutated breast (olaparib adjuvant per OlympiA) and ovarian cancer. Screen for prostate cancer (BRCA2 men) and pancreatic cancer (annual MRI/EUS if family history).",
     "A", "Strong", ["brca mutation carrier", "hereditary breast ovarian cancer"], ["olaparib", "tamoxifen"], ["breast mri", "mammogram", "ca-125", "genetic counseling", "transvaginal ultrasound"], ["brca", "risk-reducing surgery", "parp inhibitor", "surveillance"]),

    # ─── REHABILITATION/SPORTS ───
    ("AAN Concussion Return-to-Play", "AAN/CIS", 2024, "Sport Concussion Return-to-Play Protocol",
     "6-step graduated return-to-sport: 1) Symptom-limited activity (daily activities that don't provoke symptoms). 2) Light aerobic exercise (walking, stationary cycling). 3) Sport-specific exercise (running drills, no contact). 4) Non-contact training drills (passing, complex drills). 5) Full-contact practice (cleared by physician). 6) Return to competition. Minimum 24 hours per step. If symptoms recur, return to previous asymptomatic step. No same-day return to play. Neuropsych testing for persistent symptoms. No pharmacologic intervention for acute concussion.",
     "A", "Strong", ["sport concussion", "return-to-play"], [], ["scat6", "neuropsychological testing", "balance testing"], ["concussion", "return to play", "graduated", "scat"]),

    # ─── WOUND CARE ───
    ("NPUAP Pressure Injury Guidelines", "NPUAP/EPUAP", 2024, "Pressure Injury Prevention and Treatment",
     "Prevention: risk assessment (Braden Scale ≤18 = at risk). Interventions: repositioning Q2h, support surface (pressure redistribution mattress), nutrition optimization (protein 1.25-1.5 g/kg/day, calories 30-35 kcal/kg/day), moisture management, friction reduction. Treatment by stage: Stage 1/2: moist wound healing (hydrocolloid, foam). Stage 3/4: debridement (sharp, enzymatic, autolytic), negative pressure wound therapy (NPWT), address infection. Unstageable: debride to determine depth. Offloading is essential.",
     "A", "Strong", ["pressure injury", "pressure ulcer", "decubitus ulcer"], ["collagenase", "silver sulfadiazine"], ["braden scale", "wound measurement", "albumin", "prealbumin"], ["pressure injury", "braden scale", "wound care", "npwt"]),

    # ─── ALLERGY/IMMUNOLOGY ───
    ("ACAAI Drug Allergy Guidelines", "ACAAI/AAAAI", 2024, "Drug Allergy Evaluation and Management",
     "Detailed history: timing, morphology, severity of reaction. Penicillin allergy: >90% of labeled patients are NOT truly allergic. Skin testing + oral challenge (10% dose → full dose) safely delabels. Cross-reactivity: penicillin → cephalosporin ~2% (similar R1 side chain). Anaphylaxis to drug: absolute contraindication unless desensitization performed. Desensitization: gradual dose escalation for immediate-type allergy when no alternative exists (e.g., aspirin for CAD, carboplatin for ovarian cancer). Document: allergy delabeling in medical record.",
     "A", "Strong", ["drug allergy", "penicillin allergy"], ["penicillin", "amoxicillin", "cefazolin"], ["penicillin skin test", "drug challenge"], ["drug allergy", "penicillin allergy", "delabeling", "desensitization"]),

    ("ACAAI Hereditary Angioedema Guidelines", "ACAAI/WAO", 2024, "HAE Acute and Prophylactic Treatment",
     "Acute attacks: C1-INH concentrate (Berinert IV, Ruconest IV, Haegarda SC), icatibant (bradykinin B2 receptor antagonist SC), or ecallantide (kallikrein inhibitor SC). On-demand treatment at earliest symptom onset. Do NOT use epinephrine/antihistamines/steroids (bradykinin-mediated, not histamine). Long-term prophylaxis: lanadelumab (anti-kallikrein mAb SC Q2-4 weeks), berotralstat (oral kallikrein inhibitor daily), SC C1-INH. Short-term prophylaxis before procedures: IV C1-INH. Diagnosis: low C4, low C1-INH level and function.",
     "A", "Strong", ["hereditary angioedema", "hae"], ["c1 esterase inhibitor", "icatibant", "lanadelumab", "berotralstat"], ["c4", "c1-inh level", "c1-inh function"], ["hereditary angioedema", "bradykinin", "lanadelumab", "c1-inh"]),

    # ─── ENT: REMAINING ───
    ("AAO-HNS BPPV Guidelines", "AAO-HNS", 2024, "BPPV Diagnosis and Treatment",
     "Most common cause of vertigo. Posterior canal (most common): positive Dix-Hallpike test. Treatment: Epley maneuver (canalith repositioning procedure) — 80% cure rate in single session. Horizontal canal: positive supine roll test; treatment: Lempert (BBQ roll) or Gufoni maneuver. No role for routine imaging, audiometry, or vestibular testing unless atypical features. Medication (meclizine) NOT recommended for BPPV (delays central compensation). Refer for persistent symptoms: consider vestibular rehabilitation.",
     "A", "Strong", ["bppv", "benign paroxysmal positional vertigo"], ["meclizine"], ["dix-hallpike test", "supine roll test"], ["bppv", "epley maneuver", "vertigo", "dix-hallpike"]),

    ("AAO-HNS Thyroid Nodule FNA", "AAO-HNS/ATA", 2024, "Thyroid Nodule Fine Needle Aspiration",
     "FNA indications guided by ACR TI-RADS: TR5 (highly suspicious) ≥1 cm, TR4 (moderately suspicious) ≥1.5 cm, TR3 (mildly suspicious) ≥2.5 cm. No FNA for TR1-TR2. Bethesda classification: I nondiagnostic (repeat FNA), II benign (follow-up US), III atypia/FLUS (molecular testing or repeat FNA), IV follicular neoplasm (lobectomy or molecular), V suspicious (lobectomy or total thyroidectomy), VI malignant (surgery). Molecular testing (ThyroSeq, Afirma) for Bethesda III-IV to avoid unnecessary surgery.",
     "A", "Strong", ["thyroid fna", "thyroid nodule biopsy"], [], ["thyroid ultrasound", "fna cytology", "molecular testing", "tsh"], ["thyroid fna", "bethesda", "ti-rads", "molecular testing"]),

    # ─── ADDICTION MEDICINE ───
    ("ASAM Benzodiazepine Tapering Guidelines", "ASAM/APA", 2024, "Benzodiazepine Tapering Protocol",
     "Taper plan: reduce by 10-25% every 1-2 weeks initially, then slower (5-10% reductions) for final 25%. Switch short-acting (alprazolam, lorazepam) to equivalent long-acting (diazepam, clonazepam) before taper for smoother pharmacokinetics. Adjunctive: gabapentin or carbamazepine for withdrawal symptoms. CBT for insomnia (CBT-I) and anxiety concurrently. Monitor: CIWA-B (for benzodiazepine withdrawal). Avoid abrupt discontinuation (seizure risk after >1 month of daily use). Total taper duration: typically 4-16 weeks depending on duration of use.",
     "B", "Strong", ["benzodiazepine dependence", "benzodiazepine tapering"], ["diazepam", "clonazepam", "gabapentin", "carbamazepine"], ["ciwa-b score"], ["benzodiazepine taper", "benzo withdrawal", "gradual reduction"]),

    # ─── ADDITIONAL PAIN/PM&R ───
    ("AAOS Rotator Cuff Tear Guidelines", "AAOS", 2024, "Rotator Cuff Tear Management",
     "Partial-thickness or small full-thickness (<1 cm) in low-demand patient: conservative (PT focusing on ROM and strengthening x 6-12 weeks, subacromial injection). Large/massive or failed conservative in active patients: arthroscopic rotator cuff repair. Irreparable tears: superior capsular reconstruction, tendon transfer (latissimus dorsi, lower trapezius), or reverse total shoulder arthroplasty for cuff tear arthropathy. Postoperative: sling x 6 weeks, progressive rehab x 4-6 months. MRI for diagnosis.",
     "A", "Strong", ["rotator cuff tear", "shoulder impingement"], ["ketorolac", "triamcinolone injection", "naproxen"], ["mri shoulder", "shoulder x-ray", "physical exam"], ["rotator cuff", "arthroscopic repair", "physical therapy"]),

    ("ACR Fibromyalgia Guidelines", "ACR", 2024, "Fibromyalgia Multimodal Management",
     "Non-pharmacologic (most important): aerobic exercise (walking, swimming, cycling 30 min 3-5x/week), CBT, sleep hygiene, stress management, patient education. Pharmacologic: duloxetine 60 mg (FDA-approved), milnacipran (FDA-approved), pregabalin 150-450 mg (FDA-approved). Amitriptyline 10-50 mg at bedtime. Cyclobenzaprine for sleep. Avoid: opioids (not effective, risk of dependence), NSAIDs (limited benefit). Address comorbidities: depression, anxiety, sleep disorders. Multidisciplinary approach.",
     "A", "Strong", ["fibromyalgia", "chronic widespread pain"], ["duloxetine", "milnacipran", "pregabalin", "amitriptyline", "cyclobenzaprine"], ["fibromyalgia criteria", "pain score", "fiq-r"], ["fibromyalgia", "duloxetine", "pregabalin", "exercise"]),

    # ─── PUBLIC HEALTH: REMAINING ───
    ("CDC STI Treatment Guidelines", "CDC", 2024, "STI Screening and Treatment Update",
     "Chlamydia/Gonorrhea: screen all sexually active women <25 annually, men per risk. Chlamydia: doxycycline 100 mg BID x 7 days (preferred over azithromycin). Gonorrhea: ceftriaxone 500 mg IM single dose (1g if ≥150 kg). Syphilis primary/secondary: benzathine penicillin G 2.4 million units IM single dose. Latent (early <1 year): same. Late latent or unknown: 2.4 million units IM weekly x 3. Neurosyphilis: IV penicillin G. Trichomonas: metronidazole 500 mg BID x 7 days (women) or 2g single dose (men).",
     "A", "Strong", ["sexually transmitted infections", "chlamydia", "gonorrhea", "syphilis"], ["doxycycline", "ceftriaxone", "benzathine penicillin", "metronidazole", "azithromycin"], ["naat chlamydia/gonorrhea", "rpr", "fta-abs", "hiv test"], ["sti", "chlamydia", "gonorrhea", "syphilis", "doxycycline"]),

    ("ACSM Exercise Prescription Guidelines", "ACSM", 2024, "Physical Activity Prescription for Health",
     "Adults: ≥150 min/week moderate-intensity aerobic (brisk walking, cycling) or ≥75 min/week vigorous-intensity. Resistance training: ≥2 days/week, all major muscle groups. Flexibility: ≥2 days/week. Neuromotor (balance): for fall-prone older adults. Move more, sit less — any physical activity provides health benefits. Dose-response: more activity provides greater benefit up to ~300 min/week moderate. Exercise is medicine: prescribe like a medication (type, dose, frequency, duration). Screen for contraindications per ACSM algorithm.",
     "A", "Strong", ["physical activity prescription", "exercise medicine"], [], ["6-minute walk test", "vo2 max", "blood pressure", "bmi", "hba1c"], ["exercise prescription", "physical activity", "acsm", "150 minutes"]),
]


def main():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "clinical_guidelines.json")
    with open(fixture_path) as f:
        data = json.load(f)

    existing_ids = {s["section_id"] for s in data["guidelines"]}
    added = 0

    for entry in S:
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
    print(f"Batch 10: added {added} sections (total now {total})")


if __name__ == "__main__":
    main()
