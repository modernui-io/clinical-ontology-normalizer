#!/usr/bin/env python3
"""Bulk guideline generator using structured templates to reach ~1000 total sections.

Generates condition-specific screening, diagnosis, treatment, and monitoring sections
from structured clinical data templates.
"""

import json, os, hashlib

# Each entry: (guideline_name, society, year, section_title, rec_text, grade, strength,
#              conditions, meds, measurements, keywords)
BULK_SECTIONS = [
    # ── COMPREHENSIVE DIABETES CARE ──
    ("ADA Standards of Medical Care in Diabetes", "ADA", 2025, "Diabetic Retinopathy Screening",
     "Dilated eye exam at diagnosis for T2DM, within 5 years for T1DM, then annually. AI-based retinal imaging acceptable for screening in primary care. Optimize glycemia (A1c <7%) and blood pressure to reduce retinopathy risk. Prompt referral for proliferative or severe NPDR.",
     "A", "Strong", ["diabetic retinopathy", "diabetes eye disease"], [], ["dilated eye exam", "hba1c", "blood pressure"], ["retinopathy", "eye exam", "screening"]),
    ("ADA Standards of Medical Care in Diabetes", "ADA", 2025, "Diabetic Neuropathy Screening",
     "Screen for distal symmetric polyneuropathy at diagnosis for T2DM and 5 years after T1DM diagnosis. Annual 10g monofilament plus one additional test. Duloxetine, pregabalin, or gabapentin for painful neuropathy. Optimize glycemic control to prevent progression.",
     "A", "Strong", ["diabetic neuropathy", "peripheral neuropathy"], ["duloxetine", "pregabalin", "gabapentin"], ["monofilament test", "nerve conduction", "hba1c"], ["neuropathy", "monofilament", "screening"]),
    ("ADA Standards of Medical Care in Diabetes", "ADA", 2025, "Diabetic Kidney Disease Screening",
     "Annual UACR and eGFR for all patients with diabetes. SGLT2 inhibitor for UACR ≥30 and eGFR ≥20. Finerenone for T2DM with albuminuria on max RAS blockade. Refer to nephrology for eGFR <30 or rapidly declining function.",
     "A", "Strong", ["diabetic kidney disease", "diabetic nephropathy"], ["dapagliflozin", "empagliflozin", "finerenone", "lisinopril"], ["uacr", "egfr", "creatinine", "hba1c"], ["diabetic nephropathy", "sglt2", "uacr", "screening"]),
    ("ADA Standards of Medical Care in Diabetes", "ADA", 2025, "Diabetes and Pregnancy",
     "Preconception counseling for women with preexisting diabetes. A1c <6.5% before conception. Switch to insulin if on oral agents. Screen for gestational diabetes at 24-28 weeks. Tight glycemic control: fasting <95, 1h post <140, 2h post <120 mg/dL.",
     "A", "Strong", ["diabetes in pregnancy", "preexisting diabetes", "gestational diabetes"], ["insulin", "metformin"], ["hba1c", "fasting glucose", "ogtt"], ["diabetes pregnancy", "preconception", "insulin"]),
    ("ADA Standards of Medical Care in Diabetes", "ADA", 2025, "Diabetes Foot Care",
     "Comprehensive foot exam annually. Assess pulses, sensation (monofilament), skin integrity. Patient education on foot self-care. Refer to podiatry for high-risk feet (prior ulcer, neuropathy, deformity, PAD). Therapeutic footwear for all high-risk patients.",
     "A", "Strong", ["diabetic foot", "diabetes complications"], [], ["monofilament", "abi", "pedal pulses"], ["foot care", "monofilament", "podiatry"]),
    ("ADA Standards of Medical Care in Diabetes", "ADA", 2025, "Diabetes Lipid Management",
     "Moderate-intensity statin for all diabetic adults 40-75. High-intensity statin if ASCVD or 10-year risk ≥20%. Add ezetimibe if LDL ≥70 on max statin for ASCVD. PCSK9 inhibitor for very high-risk with LDL ≥70 on statin+ezetimibe.",
     "A", "Strong", ["diabetes lipid management", "diabetic dyslipidemia"], ["atorvastatin", "rosuvastatin", "ezetimibe", "evolocumab"], ["ldl", "total cholesterol", "triglycerides"], ["diabetes", "statin", "ldl", "lipid"]),
    ("ADA Standards of Medical Care in Diabetes", "ADA", 2025, "Diabetes Hypertension Management",
     "Target BP <130/80 mmHg. ACEi or ARB first-line if albuminuria present. Second-line: thiazide-like diuretic or CCB. Home BP monitoring encouraged. Avoid dual RAS blockade.",
     "A", "Strong", ["diabetes hypertension", "diabetic hypertension"], ["lisinopril", "losartan", "amlodipine", "chlorthalidone"], ["blood pressure", "uacr", "potassium"], ["diabetes", "hypertension", "ace inhibitor", "bp target"]),
    ("ADA Standards of Medical Care in Diabetes", "ADA", 2025, "Diabetes Vaccination",
     "Annual influenza vaccine. COVID-19 series and boosters. PCV20 for adults. Hepatitis B series for unvaccinated 19-59. Tdap booster every 10 years. Shingrix for ≥50 years.",
     "A", "Strong", ["diabetes vaccination", "immunization"], [], [], ["diabetes", "vaccination", "influenza", "pneumococcal"]),

    # ── HEART FAILURE COMPREHENSIVE ──
    ("ACC/AHA Heart Failure Guidelines", "ACC/AHA", 2024, "Stage A Heart Failure Prevention",
     "Control hypertension, diabetes, obesity, and dyslipidemia to prevent heart failure. SGLT2 inhibitors for type 2 diabetes reduce HF risk. ACE inhibitors for patients with ASCVD. BNP-based screening for asymptomatic at-risk patients.",
     "A", "Strong", ["heart failure prevention", "stage a heart failure"], ["dapagliflozin", "empagliflozin", "lisinopril", "atorvastatin"], ["bnp", "nt-probnp", "echocardiogram"], ["heart failure prevention", "stage a", "sglt2"]),
    ("ACC/AHA Heart Failure Guidelines", "ACC/AHA", 2024, "Stage B Heart Failure",
     "ACEi or ARB for patients with structural heart disease but no HF symptoms. Beta-blocker if reduced LVEF or prior MI. Avoid cardiotoxic substances. ICD consideration for LVEF ≤30% and MI ≥40 days prior.",
     "A", "Strong", ["stage b heart failure", "asymptomatic lv dysfunction"], ["lisinopril", "carvedilol", "metoprolol"], ["ejection fraction", "echocardiogram", "bnp"], ["stage b", "structural heart disease", "prevention"]),
    ("ACC/AHA Heart Failure Guidelines", "ACC/AHA", 2024, "Heart Failure Palliative Care",
     "Palliative care consultation for patients with advanced HF and persistent symptoms. Goals-of-care discussions regarding ICD deactivation. Hospice referral for patients with NYHA IV despite optimal therapy. Symptom management: diuretics for congestion, opioids for dyspnea, anxiolytics for anxiety.",
     "B", "Strong", ["advanced heart failure", "palliative care", "end-stage heart failure"], ["morphine", "furosemide", "lorazepam"], ["bnp", "6-minute walk test", "vo2 max"], ["heart failure", "palliative", "hospice", "goals of care"]),
    ("ACC/AHA Heart Failure Guidelines", "ACC/AHA", 2024, "Heart Failure Cardiac Rehabilitation",
     "Exercise-based cardiac rehabilitation for all stable HF patients (NYHA I-III). Improves functional capacity, quality of life, and reduces hospitalizations. Supervised exercise 3-5 times/week for 12+ weeks. Home-based rehabilitation as alternative.",
     "A", "Strong", ["heart failure rehabilitation", "cardiac rehabilitation"], [], ["vo2 max", "6-minute walk test", "ejection fraction"], ["cardiac rehabilitation", "exercise", "heart failure"]),

    # ── CHRONIC PAIN CONDITIONS ──
    ("ACR Chronic Low Back Pain", "ACR/ACP", 2024, "Chronic Low Back Pain Management",
     "Non-pharmacologic therapies first: exercise, physical therapy, CBT, spinal manipulation, acupuncture, yoga, tai chi. First-line pharmacologic: NSAIDs, duloxetine. Second-line: tramadol (limited role). Avoid opioids for chronic non-cancer pain when possible. Imaging only for red flags.",
     "A", "Strong", ["chronic low back pain", "lumbar pain", "back pain"], ["naproxen", "ibuprofen", "duloxetine", "cyclobenzaprine"], ["mri lumbar spine", "x-ray lumbar"], ["back pain", "nsaid", "physical therapy", "exercise"]),
    ("ACR Neck Pain", "ACR", 2024, "Chronic Neck Pain",
     "Exercise and physical therapy as first-line. Manual therapy and mobilization. NSAIDs or acetaminophen for mild-moderate pain. Duloxetine or nortriptyline for persistent pain. Cervical epidural steroid injection for radiculopathy. Surgery for progressive neurologic deficit.",
     "B", "Strong", ["neck pain", "cervical radiculopathy", "cervical spondylosis"], ["naproxen", "duloxetine", "nortriptyline", "gabapentin"], ["mri cervical spine", "x-ray cervical"], ["neck pain", "cervical", "physical therapy", "radiculopathy"]),
    ("ACR Complex Regional Pain Syndrome", "ACR", 2024, "CRPS Treatment",
     "Graded motor imagery and mirror therapy. Physical and occupational therapy as foundation. Bisphosphonates (pamidronate) for early CRPS. Gabapentin or pregabalin for neuropathic pain. Sympathetic nerve blocks for refractory cases. Spinal cord stimulation for chronic CRPS.",
     "B", "Moderate", ["complex regional pain syndrome", "crps", "reflex sympathetic dystrophy"], ["gabapentin", "pregabalin", "pamidronate", "nortriptyline"], ["bone scan", "thermography"], ["crps", "mirror therapy", "sympathetic block", "neuropathic"]),

    # ── ADDITIONAL SCREENING (more detail) ──
    ("ACS Cancer Screening - Breast", "ACS", 2024, "Breast Cancer Risk Assessment",
     "Formal risk assessment for all women by age 30. Use validated tools (Tyrer-Cuzick, Gail, BRCAPro). High-risk (≥20% lifetime): annual mammogram + breast MRI starting at age 25-30. Average risk: annual mammogram starting at 40. Consider risk-reducing strategies for very high risk.",
     "A", "Strong", ["breast cancer risk", "breast cancer screening"], [], ["mammogram", "breast mri", "genetic testing"], ["breast cancer", "risk assessment", "tyrer-cuzick", "screening"]),
    ("USPSTF Abdominal Aortic Aneurysm Screening", "USPSTF", 2024, "AAA Screening Detailed",
     "One-time screening ultrasonography for men 65-75 who have ever smoked. Selective screening for men who have never smoked. Insufficient evidence for women without family history. Refer for vascular surgery if ≥5.5 cm or rapid expansion (>0.5 cm in 6 months). Surveillance every 6-12 months for 3.0-5.4 cm.",
     "B", "Moderate", ["abdominal aortic aneurysm", "aaa screening"], [], ["abdominal ultrasound", "ct angiography"], ["aaa", "screening", "ultrasound", "surveillance"]),

    # ── ALLERGY EXPANSION ──
    ("AAAAI Allergic Rhinitis", "AAAAI", 2024, "Allergic Rhinitis Treatment",
     "Intranasal corticosteroids (fluticasone, mometasone) as most effective monotherapy. Second-generation antihistamines (cetirizine, loratadine, fexofenadine) for mild symptoms. Intranasal antihistamine (azelastine) for nasal congestion. Allergen immunotherapy (SCIT or SLIT) for inadequate response to pharmacotherapy. Allergen avoidance measures.",
     "A", "Strong", ["allergic rhinitis", "hay fever", "nasal allergy"], ["fluticasone nasal", "mometasone nasal", "cetirizine", "loratadine", "azelastine", "montelukast"], ["skin prick test", "specific ige"], ["allergic rhinitis", "intranasal steroid", "antihistamine", "immunotherapy"]),
    ("AAAAI Chronic Sinusitis", "AAAAI", 2024, "Chronic Rhinosinusitis Management",
     "Nasal saline irrigation and intranasal corticosteroids as foundation. Short-course antibiotics (amoxicillin-clavulanate) for acute exacerbations. Dupilumab for CRSwNP (chronic rhinosinusitis with nasal polyps). Endoscopic sinus surgery for refractory disease. Evaluate for aspirin-exacerbated respiratory disease (AERD), cystic fibrosis, and immunodeficiency.",
     "A", "Strong", ["chronic sinusitis", "nasal polyps", "rhinosinusitis"], ["fluticasone nasal", "amoxicillin-clavulanate", "dupilumab", "prednisone"], ["ct sinus", "nasal endoscopy"], ["chronic sinusitis", "nasal polyps", "dupilumab", "sinus surgery"]),

    # ── VASCULAR SURGERY ──
    ("SVS Varicose Vein Guidelines", "SVS", 2024, "Varicose Vein Management",
     "Compression stockings as initial conservative therapy. Endovenous thermal ablation (laser or radiofrequency) for saphenous vein reflux. Foam sclerotherapy for residual varicosities. Phlebectomy for large varicose veins. Duplex ultrasound for assessment before intervention. CEAP classification for staging.",
     "A", "Strong", ["varicose veins", "venous insufficiency", "chronic venous disease"], [], ["venous duplex ultrasound"], ["varicose veins", "ablation", "compression", "sclerotherapy"]),
    ("SVS Carotid Stenosis", "SVS", 2024, "Carotid Stenosis Management",
     "Carotid endarterectomy (CEA) for symptomatic 50-99% stenosis within 2 weeks of event. CEA for asymptomatic 60-99% stenosis if operative risk <3% and life expectancy >5 years. Carotid artery stenting as alternative for high surgical risk. Optimal medical therapy: antiplatelet, statin, BP control for all patients.",
     "A", "Strong", ["carotid stenosis", "carotid artery disease", "stroke prevention"], ["aspirin", "clopidogrel", "atorvastatin"], ["carotid duplex ultrasound", "ct angiography", "mra"], ["carotid stenosis", "endarterectomy", "stenting", "stroke prevention"]),

    # ── PHYSICAL MEDICINE & REHABILITATION ──
    ("ACRM Stroke Rehabilitation", "ACRM", 2024, "Post-Stroke Rehabilitation",
     "Early rehabilitation within 24-48 hours of hemodynamic stability. Intensive therapy: minimum 3 hours/day of task-specific practice. Constraint-induced movement therapy for upper limb. FES and robotics as adjuncts. Speech-language therapy for aphasia and dysphagia. Secondary prevention compliance.",
     "A", "Strong", ["stroke rehabilitation", "post-stroke", "hemiparesis"], [], ["nihss", "modified rankin scale", "barthel index", "fma"], ["stroke rehabilitation", "early mobility", "cimt", "aphasia"]),
    ("AAN Spasticity Management", "AAN", 2024, "Spasticity Treatment",
     "Baclofen (oral or intrathecal) as first-line. Tizanidine as alternative. Botulinum toxin injections for focal spasticity. Physical therapy and stretching as foundation. Intrathecal baclofen pump for generalized severe spasticity. Avoid rapid withdrawal of antispasmodic agents.",
     "A", "Strong", ["spasticity", "upper motor neuron syndrome", "multiple sclerosis", "spinal cord injury"], ["baclofen", "tizanidine", "botulinum toxin a", "dantrolene", "diazepam"], ["modified ashworth scale"], ["spasticity", "baclofen", "botulinum toxin", "intrathecal"]),

    # ── ADOLESCENT MEDICINE ──
    ("AAP Adolescent Depression", "AAP", 2024, "Adolescent Depression Screening and Treatment",
     "Universal depression screening annually for adolescents 12+ using PHQ-A. Mild depression: active monitoring, supportive counseling, exercise. Moderate-severe: fluoxetine (first-line SSRI for adolescents) or CBT. Combined CBT + fluoxetine most effective. Black box warning: monitor for suicidality in first 1-2 months. Escitalopram as second-line.",
     "A", "Strong", ["adolescent depression", "teen depression", "pediatric depression"], ["fluoxetine", "escitalopram", "sertraline"], ["phq-a", "columbia suicide severity rating scale"], ["adolescent depression", "fluoxetine", "cbt", "screening"]),
    ("AAP Adolescent Substance Use", "AAP", 2024, "Adolescent Substance Use Screening",
     "SBIRT (Screening, Brief Intervention, Referral to Treatment) at all well visits for ages 12+. CRAFFT screening tool validated for adolescents. Brief motivational interviewing for risky use. Referral to specialty treatment for substance use disorder. Buprenorphine/naloxone for adolescent opioid use disorder ≥16 years. Naloxone prescribing for at-risk youth.",
     "A", "Strong", ["adolescent substance use", "teen drug use", "underage drinking"], ["buprenorphine-naloxone", "naloxone"], ["crafft", "urine drug screen"], ["adolescent substance use", "sbirt", "crafft", "motivational interviewing"]),

    # ── RARE DISEASES ──
    ("ACR Wilson Disease", "AASLD", 2024, "Wilson Disease Treatment",
     "Chelation therapy with D-penicillamine or trientine for symptomatic Wilson disease. Zinc acetate for maintenance therapy and presymptomatic patients. Liver transplant for acute liver failure or decompensated cirrhosis unresponsive to chelation. Monitor 24-hour urine copper and free copper levels. Genetic testing for ATP7B mutations. Screen siblings.",
     "A", "Strong", ["wilson disease", "hepatolenticular degeneration"], ["d-penicillamine", "trientine", "zinc acetate"], ["ceruloplasmin", "24-hour urine copper", "slit lamp exam", "liver biopsy copper"], ["wilson disease", "chelation", "ceruloplasmin", "copper"]),
    ("Endocrine Society Acromegaly", "Endocrine Society", 2024, "Acromegaly Treatment",
     "Transsphenoidal surgery as first-line for GH-secreting pituitary adenoma. Somatostatin analogs (octreotide LAR, lanreotide) for residual disease or non-surgical candidates. Pegvisomant (GH receptor antagonist) for somatostatin analog-resistant disease. Cabergoline for mild elevation. Target: normal IGF-1 and GH <1 ng/mL.",
     "A", "Strong", ["acromegaly", "growth hormone excess", "pituitary adenoma"], ["octreotide lar", "lanreotide", "pegvisomant", "cabergoline"], ["igf-1", "growth hormone", "mri pituitary", "glucose suppression test"], ["acromegaly", "transsphenoidal surgery", "somatostatin analog", "igf-1"]),
    ("AASLD Hemochromatosis", "AASLD", 2024, "Hereditary Hemochromatosis",
     "Therapeutic phlebotomy as mainstay of treatment. Target ferritin 50-100 ng/mL. Weekly phlebotomy initially, then maintenance every 2-4 months. Screen first-degree relatives with transferrin saturation and ferritin. HFE gene testing for C282Y homozygosity. Liver biopsy or MRI for fibrosis assessment if ferritin >1000.",
     "A", "Strong", ["hereditary hemochromatosis", "iron overload"], [], ["ferritin", "transferrin saturation", "hfe gene", "liver biopsy", "mri liver iron"], ["hemochromatosis", "phlebotomy", "ferritin", "hfe"]),

    # ── INFECTIOUS - MORE ──
    ("IDSA Urinary Tract Infection - Uncomplicated", "IDSA", 2024, "Uncomplicated Cystitis",
     "Nitrofurantoin 100mg BID × 5 days as first-line. TMP-SMX DS BID × 3 days if local resistance <20%. Fosfomycin 3g single dose as alternative. Avoid fluoroquinolones for uncomplicated cystitis. Urine culture not required for typical uncomplicated cystitis. Recurrent UTI: self-start therapy, post-coital prophylaxis, or daily low-dose prophylaxis.",
     "A", "Strong", ["uncomplicated cystitis", "urinary tract infection", "acute cystitis"], ["nitrofurantoin", "trimethoprim-sulfamethoxazole", "fosfomycin"], ["urinalysis", "urine culture"], ["cystitis", "nitrofurantoin", "tmp-smx", "uncomplicated"]),
    ("IDSA Bacterial Sinusitis", "IDSA", 2024, "Acute Bacterial Sinusitis",
     "Watchful waiting for 7-10 days for mild symptoms. Amoxicillin-clavulanate as first-line when antibiotics indicated (symptoms ≥10 days, severe onset, or worsening). Doxycycline for penicillin allergy. Duration 5-7 days for adults, 10-14 days for children. Intranasal steroids as adjunct. CT sinus only for recurrent or complicated cases.",
     "A", "Strong", ["acute bacterial sinusitis", "sinusitis"], ["amoxicillin-clavulanate", "doxycycline", "moxifloxacin", "fluticasone nasal"], ["ct sinus"], ["sinusitis", "amoxicillin", "watchful waiting", "acute"]),
    ("IDSA Pharyngitis", "IDSA", 2024, "Group A Streptococcal Pharyngitis",
     "Rapid antigen detection test (RADT) for diagnosis. Culture only if RADT negative in children/adolescents. Penicillin V or amoxicillin as first-line. Single IM benzathine penicillin G as alternative. First-generation cephalosporin for penicillin allergy (non-anaphylactic). Macrolides if anaphylactic penicillin allergy. 10-day course for oral therapy.",
     "A", "Strong", ["streptococcal pharyngitis", "strep throat", "sore throat"], ["amoxicillin", "penicillin v", "benzathine penicillin", "cephalexin", "azithromycin"], ["rapid strep test", "throat culture"], ["strep pharyngitis", "penicillin", "radt", "amoxicillin"]),
    ("IDSA Herpes Zoster", "IDSA/CDC", 2024, "Herpes Zoster Treatment and Prevention",
     "Antiviral therapy within 72 hours of rash onset: valacyclovir 1g TID × 7 days (preferred) or acyclovir 800mg 5x/day × 7 days. Gabapentin or pregabalin for postherpetic neuralgia. Shingrix vaccine (2 doses) for adults ≥50 and immunocompromised ≥19. Ophthalmologic evaluation for herpes zoster ophthalmicus.",
     "A", "Strong", ["herpes zoster", "shingles", "postherpetic neuralgia"], ["valacyclovir", "acyclovir", "gabapentin", "pregabalin", "shingrix"], ["varicella zoster pcr"], ["herpes zoster", "shingles", "valacyclovir", "shingrix"]),

    # ── DENTAL/ORAL MEDICINE ──
    ("AHA Endocarditis Prophylaxis", "AHA", 2024, "Infective Endocarditis Antibiotic Prophylaxis",
     "Prophylaxis for dental procedures involving gingival manipulation or periapical region in highest-risk patients only: prosthetic valve, prior IE, unrepaired cyanotic CHD, transplant with valvulopathy. Amoxicillin 2g PO 30-60 minutes before procedure. Clindamycin 600mg for penicillin allergy. Not recommended for GI/GU procedures.",
     "A", "Strong", ["endocarditis prophylaxis", "dental prophylaxis", "prosthetic valve"], ["amoxicillin", "clindamycin", "ampicillin", "cefazolin"], [], ["endocarditis prophylaxis", "dental", "prosthetic valve", "amoxicillin"]),

    # ── GERIATRICS EXPANSION ──
    ("AGS Beers Criteria", "AGS", 2024, "Potentially Inappropriate Medications in Elderly",
     "Avoid benzodiazepines for insomnia, agitation, or delirium in older adults. Avoid first-generation antihistamines. Avoid long-acting sulfonylureas. Avoid non-COX-selective NSAIDs chronically. Avoid muscle relaxants in elderly. Reduce anticholinergic burden. Use lowest effective statin dose. Avoid prescribing cascade (treating side effect with another drug).",
     "A", "Strong", ["polypharmacy", "inappropriate prescribing", "geriatric pharmacology"], [], ["medication list", "creatinine clearance"], ["beers criteria", "inappropriate medication", "geriatric", "deprescribing"]),
    ("AGS Cognitive Impairment Screening", "AGS", 2024, "Cognitive Screening in Elderly",
     "Annual cognitive screening for adults ≥65 at Medicare wellness visit. Mini-Cog (3-word recall + clock draw) as rapid screening tool. MoCA for more detailed assessment. If positive: evaluate for reversible causes (B12, TSH, depression). Neuroimaging if rapid decline or focal deficits. Early diagnosis enables planning and intervention.",
     "B", "Strong", ["cognitive impairment", "dementia screening", "mild cognitive impairment"], [], ["mini-cog", "moca", "mmse", "vitamin b12", "tsh", "mri brain"], ["cognitive screening", "mini-cog", "moca", "dementia"]),
    ("AGS Urinary Incontinence in Elderly", "AGS", 2024, "Geriatric Urinary Incontinence",
     "Pelvic floor muscle training as first-line for stress and urge incontinence. Bladder training for urge incontinence. Avoid anticholinergics in elderly (cognitive impairment risk). Mirabegron (beta-3 agonist) as preferred pharmacotherapy. Prompted voiding for cognitively impaired. Evaluate for overflow incontinence (post-void residual). Continence products for management.",
     "A", "Strong", ["urinary incontinence", "geriatric incontinence", "overactive bladder"], ["mirabegron", "oxybutynin", "tolterodine"], ["urinalysis", "post-void residual", "voiding diary"], ["geriatric incontinence", "pelvic floor", "mirabegron", "bladder training"]),

    # ── WOMEN'S HEALTH ──
    ("NAMS Menopause Management", "NAMS", 2024, "Menopausal Hormone Therapy",
     "MHT remains most effective treatment for vasomotor symptoms. Initiate within 10 years of menopause or before age 60 for favorable benefit-risk. Estrogen plus progestogen for women with uterus; estrogen alone after hysterectomy. Fezolinetant (NK3R antagonist) as non-hormonal alternative. Low-dose vaginal estrogen for genitourinary syndrome of menopause. Individualized risk assessment.",
     "A", "Strong", ["menopause", "vasomotor symptoms", "hot flashes"], ["conjugated equine estrogen", "estradiol", "progesterone", "medroxyprogesterone", "fezolinetant"], ["fsh", "estradiol", "dexa scan"], ["menopause", "hormone therapy", "vasomotor", "fezolinetant"]),
    ("ACOG Abnormal Uterine Bleeding", "ACOG", 2024, "AUB Evaluation and Treatment",
     "Structural evaluation with transvaginal ultrasound. Endometrial biopsy for age ≥45, risk factors, or failed medical therapy. PALM-COEIN classification. Hormonal management: combined OCP, progestin-only, levonorgestrel IUD. Tranexamic acid for heavy menstrual bleeding. Hysterectomy for refractory cases. GnRH agonist as bridge to surgery.",
     "A", "Strong", ["abnormal uterine bleeding", "menorrhagia", "heavy menstrual bleeding"], ["combined oral contraceptive", "levonorgestrel iud", "tranexamic acid", "medroxyprogesterone", "leuprolide"], ["transvaginal ultrasound", "endometrial biopsy", "cbc", "tsh", "coagulation studies"], ["abnormal uterine bleeding", "palm-coein", "hormonal therapy", "endometrial biopsy"]),

    # ── ENT ──
    ("AAO-HNS Sudden Sensorineural Hearing Loss", "AAO-HNS", 2024, "Sudden Hearing Loss",
     "Audiogram within 14 days of symptom onset. MRI brain with gadolinium to rule out vestibular schwannoma. Oral corticosteroids (prednisone 60mg × 10-14 days with taper) as initial treatment. Intratympanic dexamethasone for salvage therapy or steroid-contraindicated patients. No role for antivirals. Follow-up audiometry in 6 months.",
     "B", "Strong", ["sudden sensorineural hearing loss", "sudden deafness"], ["prednisone", "dexamethasone intratympanic"], ["audiogram", "mri brain", "cbc"], ["sudden hearing loss", "corticosteroid", "intratympanic", "audiogram"]),
    ("AAO-HNS Benign Paroxysmal Positional Vertigo", "AAO-HNS", 2024, "BPPV Treatment",
     "Canalith repositioning maneuver (Epley) as first-line for posterior canal BPPV. Dix-Hallpike test for diagnosis. No routine vestibular testing, imaging, or blood tests needed. Avoid vestibular suppressants for chronic use. Modified Epley for home self-treatment. Refer for refractory cases or atypical presentations.",
     "A", "Strong", ["bppv", "positional vertigo", "vertigo"], ["meclizine"], ["dix-hallpike test"], ["bppv", "epley maneuver", "vertigo", "canalith repositioning"]),

    # ── OCCUPATIONAL MEDICINE ──
    ("ACOEM Occupational Asthma", "ACOEM", 2024, "Occupational Asthma Management",
     "Remove from exposure as primary treatment. Specific inhalation challenge or serial PEF monitoring for diagnosis. Treat as conventional asthma per GINA guidelines. Workers compensation evaluation. Spirometry with bronchodilator response. Immunologic work-up for sensitizer-induced type. Report to occupational health authorities.",
     "B", "Strong", ["occupational asthma", "work-related asthma"], ["albuterol", "budesonide", "fluticasone"], ["spirometry", "pef monitoring", "specific ige", "methacholine challenge"], ["occupational asthma", "workplace exposure", "spirometry", "removal"]),

    # ── TROPICAL/TRAVEL MEDICINE ──
    ("CDC Malaria Prevention", "CDC", 2024, "Malaria Chemoprophylaxis",
     "Atovaquone-proguanil as preferred prophylaxis for most travelers. Doxycycline as alternative (also protects against rickettsial infections). Mefloquine for chloroquine-resistant areas when others contraindicated. Chloroquine for sensitive areas only. Begin before travel (timing varies by drug). Personal protective measures: DEET, permethrin-treated clothing, bed nets.",
     "A", "Strong", ["malaria prevention", "travel medicine", "malaria"], ["atovaquone-proguanil", "doxycycline", "mefloquine", "chloroquine"], [], ["malaria", "chemoprophylaxis", "travel medicine", "atovaquone"]),
    ("CDC Travel Diarrhea", "CDC", 2024, "Travelers' Diarrhea Prevention and Treatment",
     "Dietary precautions: bottled water, cooked foods, avoid raw vegetables/fruits without peeling. Self-treatment with azithromycin (preferred for Asia) or fluoroquinolone (preferred elsewhere). Loperamide as adjunct for mild-moderate symptoms. Bismuth subsalicylate for prophylaxis. Oral rehydration for fluid replacement. Rifaximin for non-invasive, non-febrile diarrhea.",
     "A", "Strong", ["travelers diarrhea", "travel medicine", "infectious diarrhea"], ["azithromycin", "ciprofloxacin", "loperamide", "bismuth", "rifaximin"], ["stool culture", "stool ova and parasites"], ["travelers diarrhea", "azithromycin", "rehydration", "prevention"]),
]


def generate_section_id(guideline_name: str, section_title: str) -> str:
    raw = f"{guideline_name}|{section_title}".lower()
    h = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"bulk-{h}"


def main():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "clinical_guidelines.json")
    fixture_path = os.path.normpath(fixture_path)
    with open(fixture_path) as f:
        existing = json.load(f)
    existing_ids = {s["section_id"] for s in existing["guidelines"]}
    print(f"Before: {len(existing['guidelines'])} sections")
    new_sections = []
    for entry in BULK_SECTIONS:
        (guideline_name, society, year, title, rec_text, grade, strength,
         conditions, meds, measurements, keywords) = entry
        full_guideline = f"{guideline_name} ({year})"
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
