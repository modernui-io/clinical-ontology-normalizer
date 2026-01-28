#!/usr/bin/env python3
"""Batch 12: Final top-off to reach 1000+ sections.
Adds ~30 remaining niche/sub-specialty sections.
"""

import hashlib
import json
import os


def _id(guideline: str, title: str) -> str:
    raw = f"{guideline}|{title}"
    h = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"bc-{h}"


SECTIONS = [
    # ── Interventional Cardiology ─────────────────────────────────────
    (
        "SCAI Cardiogenic Shock",
        "SCAI", 2024,
        "Cardiogenic Shock Classification and Management",
        "SCAI stages A-E for cardiogenic shock classification. Stage C (classic shock): IV inotropes/vasopressors + consideration of mechanical circulatory support (Impella, IABP, ECMO). Stage D (deteriorating): escalate MCS. Early cardiac catheterization for acute MI with shock. Multidisciplinary shock team activation.",
        "B", "Strong",
        ["cardiogenic shock", "acute myocardial infarction"],
        ["dobutamine", "milrinone", "norepinephrine"],
        ["cardiac output", "lactate", "map", "cvp", "pcwp"],
        ["cardiogenic shock", "scai", "mcs", "impella", "ecmo"],
    ),
    (
        "ACC/SCAI TAVR Patient Selection",
        "ACC/SCAI", 2024,
        "TAVR vs SAVR Decision-Making",
        "TAVR is standard for inoperable and high-surgical-risk patients with severe aortic stenosis. For intermediate risk, both TAVR and SAVR are acceptable (shared decision-making). For low-risk patients, TAVR is an option with demonstrated non-inferior outcomes at 5 years. Heart team evaluation is essential. Age and durability considerations for younger patients.",
        "A", "Strong",
        ["aortic stenosis", "aortic valve replacement"],
        [],
        ["echocardiogram", "aortic valve area", "mean gradient", "ct aorta"],
        ["tavr", "aortic stenosis", "valve replacement", "heart team"],
    ),
    # ── Interventional Radiology ──────────────────────────────────────
    (
        "SIR IR Procedures",
        "SIR", 2024,
        "Transjugular Intrahepatic Portosystemic Shunt",
        "TIPS is indicated for refractory ascites, recurrent variceal bleeding unresponsive to endoscopic therapy, and Budd-Chiari syndrome. MELD score guides patient selection; generally avoided if MELD >18. Covered stents (PTFE-covered) preferred for improved patency. Monitor for hepatic encephalopathy post-procedure.",
        "B", "Strong",
        ["portal hypertension", "variceal bleeding", "refractory ascites"],
        ["lactulose", "rifaximin"],
        ["meld score", "portal pressure gradient", "doppler ultrasound"],
        ["tips", "portal hypertension", "ascites", "variceal bleeding"],
    ),
    (
        "SIR Uterine Fibroid Embolization",
        "SIR/ACOG", 2024,
        "UFE for Symptomatic Fibroids",
        "Uterine artery embolization is effective for symptomatic fibroids (menorrhagia, bulk symptoms) in patients who want to avoid hysterectomy. Not recommended for patients actively seeking pregnancy. MRI before procedure to characterize fibroids. Post-embolization syndrome (pain, fever, nausea) is common and self-limited.",
        "B", "Moderate",
        ["uterine fibroids", "leiomyoma", "menorrhagia"],
        ["nsaids", "ketorolac"],
        ["pelvic mri", "pelvic ultrasound"],
        ["uterine fibroid embolization", "ufe", "fibroids", "interventional radiology"],
    ),
    # ── Nuclear Medicine ──────────────────────────────────────────────
    (
        "SNMMI Thyroid Disease",
        "SNMMI/ATA", 2024,
        "Radioactive Iodine Therapy for Hyperthyroidism",
        "RAI (I-131) is first-line definitive therapy for Graves disease in the US. Calculate dose based on gland size and uptake. Contraindicated in pregnancy and breastfeeding. Hypothyroidism is expected outcome; start levothyroxine when TSH elevates. Pre-treatment with methimazole for severe hyperthyroidism; discontinue 3-5 days before RAI.",
        "A", "Strong",
        ["graves disease", "hyperthyroidism", "toxic nodular goiter"],
        ["radioactive iodine", "methimazole", "levothyroxine"],
        ["tsh", "free t4", "radioiodine uptake scan"],
        ["rai", "radioactive iodine", "graves disease", "i-131"],
    ),
    # ── Toxicology ────────────────────────────────────────────────────
    (
        "ACMT Poisoning Guidelines",
        "ACMT", 2024,
        "Acute Poisoning General Approach",
        "Stabilize ABCs. Activated charcoal if ingestion within 1-2 hours and intact airway. Whole bowel irrigation for sustained-release or enteric-coated preparations. Specific antidotes when indicated (naloxone, acetylcysteine, fomepizole, flumazenil with caution). Consult poison control center. Enhanced elimination (hemodialysis) for specific toxins.",
        "B", "Strong",
        ["poisoning", "drug overdose", "toxic ingestion"],
        ["activated charcoal", "naloxone", "acetylcysteine", "fomepizole"],
        ["drug levels", "anion gap", "osmol gap", "ecg"],
        ["poisoning", "antidote", "activated charcoal", "toxicology"],
    ),
    (
        "ACMT Toxic Alcohol Poisoning",
        "ACMT", 2024,
        "Methanol and Ethylene Glycol Poisoning",
        "Fomepizole (preferred) or ethanol to inhibit alcohol dehydrogenase. Hemodialysis for severe poisoning (high osmol gap, metabolic acidosis, renal failure, visual symptoms for methanol). Folic acid/leucovorin adjunct for methanol. Thiamine/pyridoxine adjunct for ethylene glycol. Do not wait for confirmatory levels if high clinical suspicion.",
        "A", "Strong",
        ["methanol poisoning", "ethylene glycol poisoning", "toxic alcohol"],
        ["fomepizole", "ethanol", "folic acid", "thiamine", "pyridoxine"],
        ["osmol gap", "anion gap", "ethylene glycol level", "methanol level"],
        ["toxic alcohol", "fomepizole", "methanol", "ethylene glycol", "hemodialysis"],
    ),
    # ── Infectious Disease – Travel Medicine ──────────────────────────
    (
        "CDC Traveler Health",
        "CDC", 2024,
        "Malaria Chemoprophylaxis",
        "Atovaquone-proguanil, doxycycline, or mefloquine based on destination resistance patterns. Begin before travel (varies by drug). Atovaquone-proguanil: start 1-2 days before, continue 7 days after return. Doxycycline: start 1-2 days before, continue 28 days after. Mefloquine: start 2 weeks before, continue 4 weeks after.",
        "A", "Strong",
        ["malaria prevention", "travel medicine"],
        ["atovaquone-proguanil", "doxycycline", "mefloquine"],
        [],
        ["malaria prophylaxis", "travel medicine", "atovaquone", "doxycycline"],
    ),
    (
        "CDC Traveler Health",
        "CDC", 2024,
        "Traveler's Diarrhea Management",
        "Prevention: hand hygiene, food/water precautions. Self-treatment for moderate-severe: azithromycin (preferred for Southeast Asia due to fluoroquinolone resistance) or fluoroquinolone. Loperamide as adjunct for adults without dysentery. Rifaximin for non-invasive disease. Oral rehydration for all cases.",
        "B", "Strong",
        ["travelers diarrhea", "infectious diarrhea"],
        ["azithromycin", "ciprofloxacin", "rifaximin", "loperamide"],
        ["stool culture", "stool pcr panel"],
        ["travelers diarrhea", "azithromycin", "ciprofloxacin", "oral rehydration"],
    ),
    # ── Rehabilitation Medicine ───────────────────────────────────────
    (
        "AAN Stroke Rehabilitation",
        "AAN/ACRM", 2024,
        "Post-Stroke Rehabilitation",
        "Begin rehabilitation as early as clinically appropriate (within 24-48 hours for mobilization). Intensive task-specific training improves motor recovery. Constraint-induced movement therapy for upper extremity. Speech-language pathology for aphasia and dysphagia. Screen and treat post-stroke depression. Spasticity management with botulinum toxin.",
        "A", "Strong",
        ["stroke rehabilitation", "hemiparesis", "aphasia"],
        ["botulinum toxin", "sertraline"],
        ["nihss", "barthel index", "modified rankin scale", "fim"],
        ["stroke rehab", "constraint-induced", "task-specific", "motor recovery"],
    ),
    # ── Infectious Disease – Fungal ───────────────────────────────────
    (
        "IDSA Fungal Infections Guidelines",
        "IDSA", 2024,
        "Coccidioidomycosis Treatment",
        "Mild pulmonary: observation with serial serology and imaging (many self-resolve). Moderate-severe or immunocompromised: fluconazole or itraconazole. Disseminated disease: amphotericin B induction followed by azole maintenance. CNS involvement: fluconazole (lifelong) ± intrathecal amphotericin B for refractory cases.",
        "B", "Strong",
        ["coccidioidomycosis", "valley fever"],
        ["fluconazole", "itraconazole", "amphotericin b"],
        ["coccidioides antibody", "complement fixation titer", "chest ct"],
        ["coccidioidomycosis", "valley fever", "fluconazole", "amphotericin"],
    ),
    (
        "IDSA Fungal Infections Guidelines",
        "IDSA", 2024,
        "Histoplasmosis Treatment",
        "Mild-moderate pulmonary: observation or itraconazole for >4 weeks of symptoms. Moderate-severe: liposomal amphotericin B induction (1-2 weeks) then itraconazole (12 months). Disseminated disease: same approach as moderate-severe. Monitor itraconazole levels and Histoplasma antigen for treatment response.",
        "B", "Strong",
        ["histoplasmosis"],
        ["itraconazole", "amphotericin b liposomal"],
        ["histoplasma antigen", "chest ct", "itraconazole level"],
        ["histoplasmosis", "itraconazole", "amphotericin", "endemic mycosis"],
    ),
    # ── Neonatology ───────────────────────────────────────────────────
    (
        "AAP Neonatal Resuscitation",
        "AAP/NRP", 2024,
        "Neonatal Resuscitation Algorithm",
        "Initial steps: warm, dry, stimulate, clear airway if needed. PPV if HR <100 or apneic/gasping at 30 seconds. CPAP for spontaneous breathing with labored respirations. Intubation if PPV ineffective. Epinephrine if HR <60 despite effective ventilation and chest compressions. Delayed cord clamping (30-60 seconds) for vigorous term and preterm infants.",
        "A", "Strong",
        ["neonatal resuscitation", "birth asphyxia"],
        ["epinephrine"],
        ["apgar score", "heart rate", "oxygen saturation", "umbilical blood gas"],
        ["neonatal resuscitation", "nrp", "ppv", "apgar"],
    ),
    (
        "AAP Necrotizing Enterocolitis",
        "AAP", 2024,
        "NEC Prevention and Management",
        "Human milk feeding is the most effective NEC prevention strategy. Probiotics may reduce NEC risk in VLBW infants (institutional protocols vary). Medical management: NPO, gastric decompression, broad-spectrum antibiotics (ampicillin + gentamicin + metronidazole). Surgical consultation for pneumoperitoneum, clinical deterioration, or fixed loops.",
        "B", "Strong",
        ["necrotizing enterocolitis", "nec"],
        ["ampicillin", "gentamicin", "metronidazole"],
        ["abdominal x-ray", "cbc", "blood culture", "blood gas"],
        ["nec", "necrotizing enterocolitis", "human milk", "premature"],
    ),
    (
        "AAP Respiratory Distress Syndrome",
        "AAP", 2024,
        "Neonatal RDS Management",
        "Surfactant replacement therapy for intubated preterm infants with RDS. Less invasive surfactant administration (LISA) via thin catheter during CPAP. Early CPAP as initial respiratory support for spontaneously breathing preterm infants. Target SpO2 90-95% in preterm infants. Caffeine for apnea of prematurity.",
        "A", "Strong",
        ["respiratory distress syndrome", "hyaline membrane disease"],
        ["surfactant", "caffeine citrate"],
        ["chest x-ray", "blood gas", "fio2", "spo2"],
        ["rds", "surfactant", "cpap", "preterm", "lisa"],
    ),
    # ── Additional Rare/Specialty topics ──────────────────────────────
    (
        "ACR Imaging in Pregnancy",
        "ACR", 2024,
        "Imaging Safety During Pregnancy",
        "Ultrasound and MRI (without gadolinium) are safe at any gestational age. Ionizing radiation: dose-dependent risk; most diagnostic studies are below harmful threshold (<50 mGy). CT with informed consent when clinically indicated. Gadolinium crosses placenta — avoid unless essential. Iodinated contrast: use if indicated; check neonatal thyroid function.",
        "B", "Moderate",
        ["pregnancy imaging", "radiation in pregnancy"],
        [],
        ["ultrasound", "mri", "ct"],
        ["pregnancy imaging", "radiation safety", "gadolinium", "mri safety"],
    ),
    (
        "AAN Idiopathic Intracranial Hypertension",
        "AAN", 2024,
        "IIH Management",
        "Weight loss (5-10% body weight) is the most effective treatment. Acetazolamide is first-line pharmacotherapy. Topiramate as alternative (also promotes weight loss). Therapeutic LP for acute vision-threatening papilledema. CSF shunting or optic nerve sheath fenestration for refractory cases with progressive vision loss.",
        "B", "Strong",
        ["idiopathic intracranial hypertension", "pseudotumor cerebri"],
        ["acetazolamide", "topiramate"],
        ["lumbar puncture opening pressure", "visual field testing", "oct"],
        ["iih", "pseudotumor cerebri", "acetazolamide", "papilledema"],
    ),
    (
        "ESC Chronic Heart Failure",
        "ESC/AHA", 2024,
        "HFrEF Quadruple Therapy",
        "All four pillars should be initiated for HFrEF (EF ≤40%): ACEi/ARNi (sacubitril-valsartan preferred), beta-blocker (carvedilol, bisoprolol, metoprolol succinate), MRA (spironolactone/eplerenone), and SGLT2i (dapagliflozin/empagliflozin). Rapid sequencing: start all four within weeks, uptitrate to target doses. Each class independently reduces mortality.",
        "A", "Strong",
        ["heart failure with reduced ejection fraction", "hfref"],
        ["sacubitril-valsartan", "carvedilol", "spironolactone", "dapagliflozin"],
        ["ejection fraction", "nt-probnp", "potassium", "creatinine"],
        ["hfref", "quadruple therapy", "arni", "sglt2 inhibitor", "gdmt"],
    ),
    (
        "ISTH DIC Guidelines",
        "ISTH", 2024,
        "DIC Diagnosis and Management",
        "ISTH DIC scoring system: platelets, fibrin markers, PT, fibrinogen. Treat underlying cause. Supportive: platelets if <10K (or <50K with bleeding), FFP/cryoprecipitate for fibrinogen <100 mg/dL with bleeding. Heparin for DIC with thrombotic predominance (e.g., malignancy-associated). Antifibrinolytics generally avoided unless hyperfibrinolysis confirmed.",
        "B", "Strong",
        ["disseminated intravascular coagulation", "dic"],
        ["platelets", "ffp", "cryoprecipitate", "heparin"],
        ["platelet count", "pt", "fibrinogen", "d-dimer", "peripheral smear"],
        ["dic", "coagulopathy", "fibrinogen", "d-dimer"],
    ),
    (
        "AGA Microscopic Colitis",
        "AGA", 2024,
        "Microscopic Colitis Treatment",
        "Budesonide is the preferred first-line treatment for active microscopic colitis. Maintenance budesonide for relapse prevention. Cholestyramine as adjunct for associated bile acid malabsorption. Immunomodulators (azathioprine) or biologics for budesonide-refractory cases. Discontinue potential offending medications (NSAIDs, PPIs, SSRIs).",
        "A", "Strong",
        ["microscopic colitis", "collagenous colitis", "lymphocytic colitis"],
        ["budesonide", "cholestyramine", "azathioprine"],
        ["colonoscopy with biopsy"],
        ["microscopic colitis", "budesonide", "collagenous", "lymphocytic"],
    ),
    (
        "AGA Bile Acid Diarrhea",
        "AGA", 2024,
        "Bile Acid Diarrhea Diagnosis and Treatment",
        "Consider BAD in patients with chronic watery diarrhea, especially post-cholecystectomy or ileal disease. SeHCAT scan (where available) or empiric trial of bile acid sequestrant (cholestyramine, colesevelam) is diagnostic/therapeutic. Response to sequestrant supports diagnosis. Colesevelam may be better tolerated than cholestyramine.",
        "B", "Moderate",
        ["bile acid diarrhea", "bile acid malabsorption"],
        ["cholestyramine", "colesevelam", "colestipol"],
        ["sehcat scan", "fgf-19 level", "7-alpha-c4"],
        ["bile acid diarrhea", "bad", "cholestyramine", "colesevelam"],
    ),
    (
        "AAN Trigeminal Neuralgia",
        "AAN", 2024,
        "Trigeminal Neuralgia Treatment",
        "Carbamazepine or oxcarbazepine are first-line pharmacotherapy. Lamotrigine, baclofen, or gabapentin as second-line. MRI to exclude secondary causes (tumor, MS). Microvascular decompression for medically refractory TN with neurovascular compression on MRI. Stereotactic radiosurgery or percutaneous procedures as alternatives.",
        "A", "Strong",
        ["trigeminal neuralgia", "tic douloureux"],
        ["carbamazepine", "oxcarbazepine", "lamotrigine", "baclofen"],
        ["brain mri", "ciss sequence"],
        ["trigeminal neuralgia", "carbamazepine", "microvascular decompression"],
    ),
    (
        "ATS Pulmonary Rehabilitation",
        "ATS/ERS", 2024,
        "Pulmonary Rehabilitation Program",
        "Recommended for symptomatic COPD patients (MRC dyspnea grade ≥2). Minimum 6-8 weeks, ≥2 sessions/week. Components: endurance training, resistance training, education, psychosocial support, nutritional counseling. Improves exercise capacity, dyspnea, and quality of life. Reduces hospitalizations. Maintenance exercise program after completion.",
        "A", "Strong",
        ["copd", "chronic lung disease", "exercise intolerance"],
        [],
        ["6-minute walk test", "shuttle walk test", "cat score", "mrc dyspnea scale"],
        ["pulmonary rehabilitation", "copd", "exercise training", "dyspnea"],
    ),
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
    print(f"Batch 12: added {added} sections (total now {total})")


if __name__ == "__main__":
    main()
