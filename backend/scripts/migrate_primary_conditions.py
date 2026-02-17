#!/usr/bin/env python3
"""Migrate clinical_guidelines.json to add primary_conditions field.

Parses guideline names to extract the primary disease/condition each guideline
is fundamentally about. This prevents false matches where a secondary condition
(e.g., "anemia") in a sickle-cell guideline matches a patient who has anemia
from a completely different etiology.

Usage:
    python backend/scripts/migrate_primary_conditions.py [--dry-run]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "clinical_guidelines.json"

# ---------------------------------------------------------------------------
# Explicit mapping: guideline name substring → primary conditions.
# Checked first (case-insensitive). Order matters: more specific patterns first.
# ---------------------------------------------------------------------------
EXPLICIT_MAP: list[tuple[str, list[str]]] = [
    # Cardiovascular
    ("high blood pressure", ["hypertension"]),
    ("hypertension", ["hypertension"]),
    ("blood cholesterol", ["hyperlipidemia", "dyslipidemia"]),
    ("cholesterol", ["hyperlipidemia", "dyslipidemia"]),
    ("lipid management", ["hyperlipidemia", "dyslipidemia"]),
    ("heart failure", ["heart failure"]),
    ("atrial fibrillation", ["atrial fibrillation"]),
    ("chest pain", ["chest pain", "acute coronary syndrome"]),
    ("coronary artery revascularization", ["coronary artery disease"]),
    ("coronary artery disease", ["coronary artery disease"]),
    ("acute coronary syndrome", ["acute coronary syndrome"]),
    ("acute coronary", ["acute coronary syndrome"]),
    ("peripheral artery disease", ["peripheral artery disease"]),
    ("peripheral arterial disease", ["peripheral artery disease"]),
    ("pad guidelines", ["peripheral artery disease"]),
    ("venous thromboembolism", ["venous thromboembolism"]),
    ("vte", ["venous thromboembolism"]),
    ("deep vein thrombosis", ["deep vein thrombosis"]),
    ("dvt", ["deep vein thrombosis"]),
    ("pulmonary embolism", ["pulmonary embolism"]),
    ("aortic disease", ["aortic disease"]),
    ("aortic stenosis", ["aortic stenosis"]),
    ("aortic aneurysm", ["aortic aneurysm"]),
    ("valvular heart", ["valvular heart disease"]),
    ("infective endocarditis", ["infective endocarditis"]),
    ("endocarditis", ["infective endocarditis"]),
    ("cardiomyopathy", ["cardiomyopathy"]),
    ("cardiac arrest", ["cardiac arrest"]),
    ("cardiopulmonary resuscitation", ["cardiac arrest"]),
    ("cpr", ["cardiac arrest"]),
    ("arrhythmia", ["arrhythmia"]),
    ("bradycardia", ["bradycardia"]),
    ("supraventricular tachycardia", ["supraventricular tachycardia"]),
    ("ventricular tachycardia", ["ventricular tachycardia"]),
    ("sudden cardiac death", ["sudden cardiac death"]),
    ("pericardial disease", ["pericardial disease"]),
    ("pericarditis", ["pericarditis"]),
    ("myocarditis", ["myocarditis"]),
    ("pulmonary hypertension", ["pulmonary hypertension"]),
    ("stable ischemic heart", ["coronary artery disease"]),
    ("syncope", ["syncope"]),
    ("cardiovascular prevention", ["cardiovascular disease"]),
    ("cardiovascular risk", ["cardiovascular disease"]),

    # Diabetes / endocrine
    ("standards of care in diabetes", ["diabetes"]),
    ("diabetes management", ["diabetes"]),
    ("type 2 diabetes", ["type 2 diabetes"]),
    ("type 1 diabetes", ["type 1 diabetes"]),
    ("gestational diabetes", ["gestational diabetes"]),
    ("thyroid", ["thyroid disease"]),
    ("hypothyroidism", ["hypothyroidism"]),
    ("hyperthyroidism", ["hyperthyroidism"]),
    ("thyroid cancer", ["thyroid cancer"]),
    ("thyroid nodule", ["thyroid nodules"]),
    ("adrenal", ["adrenal disorders"]),
    ("cushing", ["cushing syndrome"]),
    ("pheochromocytoma", ["pheochromocytoma"]),
    ("hyperaldosteronism", ["hyperaldosteronism"]),
    ("osteoporosis", ["osteoporosis"]),
    ("obesity", ["obesity"]),
    ("pituitary", ["pituitary disorders"]),
    ("acromegaly", ["acromegaly"]),
    ("prolactinoma", ["prolactinoma"]),
    ("hypogonadism", ["hypogonadism"]),
    ("testosterone deficiency", ["hypogonadism"]),
    ("polycystic ovary", ["polycystic ovary syndrome"]),
    ("pcos", ["polycystic ovary syndrome"]),
    ("hyperparathyroidism", ["hyperparathyroidism"]),
    ("hypoparathyroidism", ["hypoparathyroidism"]),
    ("vitamin d deficiency", ["vitamin d deficiency"]),

    # Hematology
    ("sickle cell", ["sickle cell disease"]),
    ("scd ", ["sickle cell disease"]),
    ("iron deficiency", ["iron deficiency anemia"]),
    ("anemia management", ["anemia"]),
    ("hemophilia", ["hemophilia"]),
    ("von willebrand", ["von willebrand disease"]),
    ("thrombocytopenia", ["thrombocytopenia"]),
    ("immune thrombocytopenia", ["immune thrombocytopenia"]),
    ("itp", ["immune thrombocytopenia"]),
    ("heparin-induced thrombocytopenia", ["heparin-induced thrombocytopenia"]),
    ("hit guidelines", ["heparin-induced thrombocytopenia"]),
    ("anticoagulation", ["anticoagulation management"]),
    ("antithrombotic", ["anticoagulation management"]),
    ("myelodysplastic", ["myelodysplastic syndrome"]),
    ("mds guidelines", ["myelodysplastic syndrome"]),
    ("myeloproliferative", ["myeloproliferative neoplasm"]),
    ("polycythemia vera", ["polycythemia vera"]),
    ("essential thrombocythemia", ["essential thrombocythemia"]),
    ("myelofibrosis", ["myelofibrosis"]),
    ("thalassemia", ["thalassemia"]),
    ("aplastic anemia", ["aplastic anemia"]),
    ("neutropenia", ["neutropenia"]),
    ("transfusion", ["transfusion medicine"]),
    ("blood management", ["transfusion medicine"]),

    # Oncology
    ("colorectal cancer", ["colorectal cancer"]),
    ("colon cancer", ["colorectal cancer"]),
    ("rectal cancer", ["rectal cancer"]),
    ("breast cancer", ["breast cancer"]),
    ("lung cancer", ["lung cancer"]),
    ("non-small cell lung", ["non-small cell lung cancer"]),
    ("small cell lung", ["small cell lung cancer"]),
    ("nsclc", ["non-small cell lung cancer"]),
    ("sclc", ["small cell lung cancer"]),
    ("prostate cancer", ["prostate cancer"]),
    ("pancreatic cancer", ["pancreatic cancer"]),
    ("ovarian cancer", ["ovarian cancer"]),
    ("cervical cancer", ["cervical cancer"]),
    ("endometrial cancer", ["endometrial cancer"]),
    ("uterine cancer", ["endometrial cancer"]),
    ("bladder cancer", ["bladder cancer"]),
    ("kidney cancer", ["kidney cancer"]),
    ("renal cell carcinoma", ["renal cell carcinoma"]),
    ("hepatocellular", ["hepatocellular carcinoma"]),
    ("liver cancer", ["hepatocellular carcinoma"]),
    ("gastric cancer", ["gastric cancer"]),
    ("stomach cancer", ["gastric cancer"]),
    ("esophageal cancer", ["esophageal cancer"]),
    ("melanoma", ["melanoma"]),
    ("basal cell carcinoma", ["basal cell carcinoma"]),
    ("squamous cell carcinoma", ["squamous cell carcinoma"]),
    ("skin cancer", ["skin cancer"]),
    ("lymphoma", ["lymphoma"]),
    ("hodgkin", ["hodgkin lymphoma"]),
    ("non-hodgkin", ["non-hodgkin lymphoma"]),
    ("leukemia", ["leukemia"]),
    ("acute myeloid leukemia", ["acute myeloid leukemia"]),
    ("aml guidelines", ["acute myeloid leukemia"]),
    ("chronic myeloid leukemia", ["chronic myeloid leukemia"]),
    ("cml guidelines", ["chronic myeloid leukemia"]),
    ("acute lymphoblastic", ["acute lymphoblastic leukemia"]),
    ("all guidelines", ["acute lymphoblastic leukemia"]),
    ("chronic lymphocytic", ["chronic lymphocytic leukemia"]),
    ("cll guidelines", ["chronic lymphocytic leukemia"]),
    ("multiple myeloma", ["multiple myeloma"]),
    ("glioblastoma", ["glioblastoma"]),
    ("brain tumor", ["brain tumor"]),
    ("brain cancer", ["brain tumor"]),
    ("head and neck cancer", ["head and neck cancer"]),
    ("testicular cancer", ["testicular cancer"]),
    ("thymic", ["thymic malignancy"]),
    ("sarcoma", ["sarcoma"]),
    ("gastrointestinal stromal", ["gastrointestinal stromal tumor"]),
    ("gist", ["gastrointestinal stromal tumor"]),
    ("neuroendocrine", ["neuroendocrine tumor"]),
    ("cholangiocarcinoma", ["cholangiocarcinoma"]),
    ("mesothelioma", ["mesothelioma"]),
    ("cancer screening", ["cancer screening"]),
    ("oncologic emergency", ["oncologic emergency"]),
    ("febrile neutropenia", ["febrile neutropenia"]),
    ("cancer pain", ["cancer pain"]),
    ("palliative care", ["palliative care"]),
    ("survivorship", ["cancer survivorship"]),

    # Pulmonary
    ("asthma", ["asthma"]),
    ("copd", ["chronic obstructive pulmonary disease"]),
    ("chronic obstructive pulmonary", ["chronic obstructive pulmonary disease"]),
    ("pneumonia", ["pneumonia"]),
    ("community-acquired pneumonia", ["community-acquired pneumonia"]),
    ("hospital-acquired pneumonia", ["hospital-acquired pneumonia"]),
    ("ventilator-associated pneumonia", ["ventilator-associated pneumonia"]),
    ("tuberculosis", ["tuberculosis"]),
    ("cystic fibrosis", ["cystic fibrosis"]),
    ("interstitial lung disease", ["interstitial lung disease"]),
    ("pulmonary fibrosis", ["pulmonary fibrosis"]),
    ("idiopathic pulmonary fibrosis", ["idiopathic pulmonary fibrosis"]),
    ("obstructive sleep apnea", ["obstructive sleep apnea"]),
    ("sleep apnea", ["obstructive sleep apnea"]),
    ("pleural effusion", ["pleural effusion"]),
    ("pneumothorax", ["pneumothorax"]),
    ("sarcoidosis", ["sarcoidosis"]),
    ("pulmonary rehabilitation", ["pulmonary rehabilitation"]),
    ("bronchiectasis", ["bronchiectasis"]),

    # GI / Hepatology
    ("inflammatory bowel disease", ["inflammatory bowel disease"]),
    ("ibd guidelines", ["inflammatory bowel disease"]),
    ("crohn", ["crohn disease"]),
    ("ulcerative colitis", ["ulcerative colitis"]),
    ("irritable bowel", ["irritable bowel syndrome"]),
    ("ibs guidelines", ["irritable bowel syndrome"]),
    ("celiac", ["celiac disease"]),
    ("gerd", ["gastroesophageal reflux disease"]),
    ("gastroesophageal reflux", ["gastroesophageal reflux disease"]),
    ("peptic ulcer", ["peptic ulcer disease"]),
    ("h. pylori", ["helicobacter pylori infection"]),
    ("helicobacter pylori", ["helicobacter pylori infection"]),
    ("hepatitis b", ["hepatitis b"]),
    ("hepatitis c", ["hepatitis c"]),
    ("cirrhosis", ["cirrhosis"]),
    ("liver disease", ["liver disease"]),
    ("nonalcoholic fatty liver", ["nonalcoholic fatty liver disease"]),
    ("nafld", ["nonalcoholic fatty liver disease"]),
    ("nash", ["nonalcoholic steatohepatitis"]),
    ("pancreatitis", ["pancreatitis"]),
    ("acute pancreatitis", ["acute pancreatitis"]),
    ("chronic pancreatitis", ["chronic pancreatitis"]),
    ("gallstone", ["gallstone disease"]),
    ("cholecystitis", ["cholecystitis"]),
    ("diverticular", ["diverticular disease"]),
    ("diverticulitis", ["diverticulitis"]),
    ("gi bleed", ["gastrointestinal bleeding"]),
    ("gastrointestinal bleed", ["gastrointestinal bleeding"]),
    ("upper gi", ["gastrointestinal disease"]),
    ("lower gi", ["gastrointestinal disease"]),
    ("colorectal screening", ["colorectal cancer screening"]),
    ("constipation", ["constipation"]),
    ("diarrhea", ["diarrhea"]),
    ("nausea", ["nausea and vomiting"]),
    ("barrett", ["barrett esophagus"]),
    ("achalasia", ["achalasia"]),
    ("eosinophilic esophagitis", ["eosinophilic esophagitis"]),

    # Nephrology
    ("chronic kidney disease", ["chronic kidney disease"]),
    ("ckd guidelines", ["chronic kidney disease"]),
    ("acute kidney injury", ["acute kidney injury"]),
    ("aki guidelines", ["acute kidney injury"]),
    ("dialysis", ["end-stage renal disease"]),
    ("hemodialysis", ["end-stage renal disease"]),
    ("peritoneal dialysis", ["end-stage renal disease"]),
    ("kidney transplant", ["kidney transplantation"]),
    ("renal transplant", ["kidney transplantation"]),
    ("glomerulonephritis", ["glomerulonephritis"]),
    ("nephrotic syndrome", ["nephrotic syndrome"]),
    ("polycystic kidney", ["polycystic kidney disease"]),
    ("renal artery stenosis", ["renal artery stenosis"]),
    ("hyperkalemia", ["hyperkalemia"]),
    ("hyponatremia", ["hyponatremia"]),
    ("electrolyte", ["electrolyte disorders"]),

    # Neurology
    ("stroke", ["stroke"]),
    ("ischemic stroke", ["ischemic stroke"]),
    ("hemorrhagic stroke", ["hemorrhagic stroke"]),
    ("tia", ["transient ischemic attack"]),
    ("epilepsy", ["epilepsy"]),
    ("status epilepticus", ["status epilepticus"]),
    ("seizure", ["seizure disorders"]),
    ("migraine", ["migraine"]),
    ("headache", ["headache"]),
    ("multiple sclerosis", ["multiple sclerosis"]),
    ("parkinson", ["parkinson disease"]),
    ("alzheimer", ["alzheimer disease"]),
    ("dementia", ["dementia"]),
    ("als guidelines", ["amyotrophic lateral sclerosis"]),
    ("amyotrophic lateral sclerosis", ["amyotrophic lateral sclerosis"]),
    ("myasthenia gravis", ["myasthenia gravis"]),
    ("guillain-barré", ["guillain-barre syndrome"]),
    ("guillain-barre", ["guillain-barre syndrome"]),
    ("bell palsy", ["bell palsy"]),
    ("trigeminal neuralgia", ["trigeminal neuralgia"]),
    ("neuropathic pain", ["neuropathic pain"]),
    ("peripheral neuropathy", ["peripheral neuropathy"]),
    ("essential tremor", ["essential tremor"]),
    ("concussion", ["concussion"]),
    ("tbi", ["traumatic brain injury"]),
    ("traumatic brain injury", ["traumatic brain injury"]),
    ("brain death", ["brain death determination"]),
    ("spasticity", ["spasticity"]),
    ("normal pressure hydrocephalus", ["normal pressure hydrocephalus"]),
    ("intracranial hypertension", ["intracranial hypertension"]),
    ("narcolepsy", ["narcolepsy"]),
    ("restless legs", ["restless legs syndrome"]),

    # Infectious disease
    ("hiv", ["hiv infection"]),
    ("covid", ["covid-19"]),
    ("influenza", ["influenza"]),
    ("sepsis", ["sepsis"]),
    ("meningitis", ["meningitis"]),
    ("urinary tract infection", ["urinary tract infection"]),
    ("uti guidelines", ["urinary tract infection"]),
    ("cellulitis", ["cellulitis"]),
    ("osteomyelitis", ["osteomyelitis"]),
    ("endocarditis", ["infective endocarditis"]),
    ("malaria", ["malaria"]),
    ("lyme disease", ["lyme disease"]),
    ("clostridium difficile", ["clostridioides difficile infection"]),
    ("c. difficile", ["clostridioides difficile infection"]),
    ("c diff", ["clostridioides difficile infection"]),
    ("mrsa", ["mrsa infection"]),
    ("fungal infection", ["fungal infection"]),
    ("candidiasis", ["candidiasis"]),
    ("aspergillosis", ["aspergillosis"]),
    ("antimicrobial stewardship", ["antimicrobial stewardship"]),

    # Rheumatology
    ("rheumatoid arthritis", ["rheumatoid arthritis"]),
    ("systemic lupus", ["systemic lupus erythematosus"]),
    ("lupus", ["systemic lupus erythematosus"]),
    ("sle guidelines", ["systemic lupus erythematosus"]),
    ("gout", ["gout"]),
    ("ankylosing spondylitis", ["ankylosing spondylitis"]),
    ("axial spondyloarthritis", ["axial spondyloarthritis"]),
    ("psoriatic arthritis", ["psoriatic arthritis"]),
    ("scleroderma", ["scleroderma"]),
    ("systemic sclerosis", ["systemic sclerosis"]),
    ("vasculitis", ["vasculitis"]),
    ("giant cell arteritis", ["giant cell arteritis"]),
    ("polymyalgia rheumatica", ["polymyalgia rheumatica"]),
    ("fibromyalgia", ["fibromyalgia"]),
    ("osteoarthritis", ["osteoarthritis"]),
    ("juvenile idiopathic arthritis", ["juvenile idiopathic arthritis"]),
    ("antiphospholipid", ["antiphospholipid syndrome"]),
    ("sjögren", ["sjogren syndrome"]),
    ("sjogren", ["sjogren syndrome"]),
    ("dermatomyositis", ["dermatomyositis"]),
    ("polymyositis", ["polymyositis"]),
    ("reactive arthritis", ["reactive arthritis"]),

    # Dermatology
    ("psoriasis", ["psoriasis"]),
    ("atopic dermatitis", ["atopic dermatitis"]),
    ("eczema", ["atopic dermatitis"]),
    ("acne", ["acne vulgaris"]),
    ("rosacea", ["rosacea"]),
    ("urticaria", ["urticaria"]),
    ("vitiligo", ["vitiligo"]),
    ("alopecia", ["alopecia"]),
    ("hidradenitis suppurativa", ["hidradenitis suppurativa"]),
    ("drug reactions", ["drug reactions"]),

    # Orthopedics / MSK
    ("low back pain", ["low back pain"]),
    ("back pain", ["back pain"]),
    ("osteoarthritis", ["osteoarthritis"]),
    ("hip fracture", ["hip fracture"]),
    ("rotator cuff", ["rotator cuff injury"]),
    ("acl", ["acl injury"]),
    ("knee osteoarthritis", ["knee osteoarthritis"]),
    ("carpal tunnel", ["carpal tunnel syndrome"]),
    ("spinal stenosis", ["spinal stenosis"]),

    # Psychiatry
    ("depression", ["depression"]),
    ("major depressive", ["major depressive disorder"]),
    ("bipolar", ["bipolar disorder"]),
    ("schizophrenia", ["schizophrenia"]),
    ("anxiety", ["anxiety disorders"]),
    ("generalized anxiety", ["generalized anxiety disorder"]),
    ("panic disorder", ["panic disorder"]),
    ("ptsd", ["post-traumatic stress disorder"]),
    ("post-traumatic stress", ["post-traumatic stress disorder"]),
    ("ocd", ["obsessive-compulsive disorder"]),
    ("obsessive-compulsive", ["obsessive-compulsive disorder"]),
    ("adhd", ["attention-deficit hyperactivity disorder"]),
    ("attention-deficit", ["attention-deficit hyperactivity disorder"]),
    ("eating disorder", ["eating disorders"]),
    ("anorexia", ["anorexia nervosa"]),
    ("bulimia", ["bulimia nervosa"]),
    ("substance use", ["substance use disorder"]),
    ("alcohol use disorder", ["alcohol use disorder"]),
    ("opioid use disorder", ["opioid use disorder"]),
    ("insomnia", ["insomnia"]),
    ("autism", ["autism spectrum disorder"]),
    ("personality disorder", ["personality disorders"]),
    ("suicid", ["suicide prevention"]),

    # Urology
    ("benign prostatic", ["benign prostatic hyperplasia"]),
    ("bph", ["benign prostatic hyperplasia"]),
    ("kidney stone", ["nephrolithiasis"]),
    ("nephrolithiasis", ["nephrolithiasis"]),
    ("urolithiasis", ["nephrolithiasis"]),
    ("erectile dysfunction", ["erectile dysfunction"]),
    ("overactive bladder", ["overactive bladder"]),
    ("urinary incontinence", ["urinary incontinence"]),

    # OB/GYN
    ("preeclampsia", ["preeclampsia"]),
    ("gestational", ["gestational complications"]),
    ("prenatal", ["prenatal care"]),
    ("postpartum", ["postpartum care"]),
    ("menopause", ["menopause"]),
    ("contraception", ["contraception"]),
    ("endometriosis", ["endometriosis"]),
    ("uterine fibroid", ["uterine fibroids"]),
    ("ectopic pregnancy", ["ectopic pregnancy"]),

    # Ophthalmology
    ("macular degeneration", ["age-related macular degeneration"]),
    ("diabetic retinopathy", ["diabetic retinopathy"]),
    ("glaucoma", ["glaucoma"]),
    ("cataract", ["cataract"]),
    ("retinal detachment", ["retinal detachment"]),
    ("uveitis", ["uveitis"]),
    ("dry eye", ["dry eye disease"]),

    # ENT
    ("sinusitis", ["sinusitis"]),
    ("chronic sinusitis", ["chronic sinusitis"]),
    ("epistaxis", ["epistaxis"]),
    ("hearing loss", ["hearing loss"]),
    ("sudden sensorineural hearing loss", ["sudden sensorineural hearing loss"]),
    ("bppv", ["benign paroxysmal positional vertigo"]),
    ("vertigo", ["vertigo"]),
    ("tonsillitis", ["tonsillitis"]),
    ("otitis media", ["otitis media"]),
    ("allergic rhinitis", ["allergic rhinitis"]),

    # Critical care / Emergency
    ("sepsis", ["sepsis"]),
    ("ards", ["acute respiratory distress syndrome"]),
    ("acute respiratory distress", ["acute respiratory distress syndrome"]),
    ("mechanical ventilation", ["respiratory failure"]),
    ("shock", ["shock"]),
    ("trauma", ["trauma"]),
    ("burn", ["burn injury"]),
    ("anaphylaxis", ["anaphylaxis"]),
    ("poisoning", ["poisoning"]),
    ("overdose", ["drug overdose"]),

    # Pediatrics
    ("pediatric", ["pediatric conditions"]),
    ("neonatal", ["neonatal conditions"]),
    ("childhood", ["pediatric conditions"]),

    # Specific unmapped guidelines
    ("hcc guidelines", ["hepatocellular carcinoma"]),
    ("hcv guidelines", ["hepatitis c"]),
    ("ect guidelines", ["electroconvulsive therapy"]),
    ("ash dic", ["disseminated intravascular coagulation"]),
    ("isth dic", ["disseminated intravascular coagulation"]),
    ("ash ttp", ["thrombotic thrombocytopenic purpura"]),
    ("icd guidelines", ["implantable cardioverter-defibrillator"]),

    # General / procedural
    ("perioperative", ["perioperative care"]),
    ("surgical site infection", ["surgical site infection"]),
    ("pain management", ["pain management"]),
    ("chronic pain", ["chronic pain"]),
    ("wound care", ["wound care"]),
    ("nutrition support", ["nutritional support"]),
    ("parenteral nutrition", ["parentional nutrition"]),
    ("enteral nutrition", ["enteral nutrition"]),
    ("fall prevention", ["fall prevention"]),
    ("delirium", ["delirium"]),
    ("pressure ulcer", ["pressure ulcer"]),
    ("pressure injury", ["pressure injury"]),
    ("goals of care", ["goals of care"]),
    ("advance directive", ["advance directives"]),
    ("immunization", ["immunization"]),
    ("vaccination", ["vaccination"]),
    ("allergy", ["allergic conditions"]),
    ("drug allergy", ["drug allergy"]),
    ("hereditary angioedema", ["hereditary angioedema"]),
    ("angioedema", ["angioedema"]),
    ("chronic disease management", ["chronic disease management"]),
]


def extract_primary_conditions(guideline_name: str) -> list[str]:
    """Extract primary conditions from a guideline name using the explicit map."""
    name_lower = guideline_name.lower()

    # Try explicit map (more specific patterns first)
    for pattern, conditions in EXPLICIT_MAP:
        if pattern.lower() in name_lower:
            return conditions

    # Fallback: try to extract condition from the name after the organization prefix
    # Pattern: "ORG Disease/Condition rest (year)"
    # Strip year suffix
    cleaned = re.sub(r"\s*\(\d{4}(?:/\d{4})?\)\s*$", "", guideline_name)
    # Strip organization prefix (typically uppercase acronym + optional slash-separated)
    cleaned = re.sub(r"^[A-Z/]+\s+", "", cleaned)
    # Remove trailing "Guidelines", "Management", etc.
    cleaned = re.sub(
        r"\s+(?:Guidelines?|Management|Recommendations?|Standards?|Guideline|Statement|"
        r"Comprehensive|Clinical Practice|Consensus|Update|Review|Position Paper|"
        r"Practice Guidelines?)$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.strip()

    if cleaned and len(cleaned) > 3:
        return [cleaned.lower()]

    return []


def migrate(dry_run: bool = False) -> None:
    """Add primary_conditions to all guideline sections."""
    with open(FIXTURE_PATH) as f:
        data = json.load(f)

    sections = data["guidelines"]
    stats = {"total": len(sections), "mapped": 0, "unmapped": 0}
    unmapped_names: set[str] = set()

    for section in sections:
        if section.get("primary_conditions"):
            stats["mapped"] += 1
            continue  # already has primary_conditions

        primary = extract_primary_conditions(section["guideline"])
        if primary:
            section["primary_conditions"] = primary
            stats["mapped"] += 1
        else:
            section["primary_conditions"] = []
            stats["unmapped"] += 1
            unmapped_names.add(section["guideline"])

    print(f"Total sections: {stats['total']}")
    print(f"Mapped: {stats['mapped']}")
    print(f"Unmapped: {stats['unmapped']}")

    if unmapped_names:
        print(f"\nUnmapped guideline names ({len(unmapped_names)}):")
        for name in sorted(unmapped_names):
            print(f"  - {name}")

    if not dry_run:
        with open(FIXTURE_PATH, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\nWrote updated fixture to {FIXTURE_PATH}")
    else:
        print("\n[DRY RUN] No changes written.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    migrate(dry_run=dry_run)
