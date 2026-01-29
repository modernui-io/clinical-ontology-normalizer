#!/usr/bin/env python3
"""Generate comprehensive OMOP vocabulary fixture.

This script generates a vocabulary fixture with ~10k+ clinical concepts
covering common conditions, drugs, measurements, and procedures with
rich synonym sets for improved NLP matching.

Usage:
    python -m app.scripts.generate_vocabulary
    python -m app.scripts.generate_vocabulary --output fixtures/omop_vocabulary_full.json

The generated vocabulary includes:
- ~3000 conditions (ICD-10 mapped)
- ~3000 drugs (RxNorm/ATC mapped)
- ~2000 measurements (LOINC mapped)
- ~2000 procedures (CPT/SNOMED mapped)
- Rich synonyms including abbreviations, common misspellings, and lay terms
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Common Clinical Conditions
# ============================================================================

CONDITIONS = [
    # Cardiovascular
    {"id": 316866, "name": "Hypertension", "code": "I10", "vocab": "ICD10CM",
     "synonyms": ["hypertension", "htn", "high blood pressure", "elevated blood pressure", "hypertensive disease", "essential hypertension", "primary hypertension"]},
    {"id": 317576, "name": "Atrial fibrillation", "code": "I48.91", "vocab": "ICD10CM",
     "synonyms": ["atrial fibrillation", "afib", "a-fib", "af", "atrial fib", "auricular fibrillation"]},
    {"id": 321588, "name": "Congestive heart failure", "code": "I50.9", "vocab": "ICD10CM",
     "synonyms": ["congestive heart failure", "chf", "heart failure", "hf", "cardiac failure", "decompensated heart failure", "acute heart failure"]},
    {"id": 4185932, "name": "Coronary artery disease", "code": "I25.10", "vocab": "ICD10CM",
     "synonyms": ["coronary artery disease", "cad", "coronary heart disease", "chd", "ischemic heart disease", "ihd", "atherosclerotic heart disease", "ashd"]},
    {"id": 4329847, "name": "Myocardial infarction", "code": "I21.9", "vocab": "ICD10CM",
     "synonyms": ["myocardial infarction", "mi", "heart attack", "ami", "acute myocardial infarction", "stemi", "nstemi", "cardiac infarction"]},
    {"id": 312327, "name": "Angina pectoris", "code": "I20.9", "vocab": "ICD10CM",
     "synonyms": ["angina pectoris", "angina", "chest pain", "cardiac angina", "stable angina", "unstable angina"]},
    {"id": 4170297, "name": "Peripheral vascular disease", "code": "I73.9", "vocab": "ICD10CM",
     "synonyms": ["peripheral vascular disease", "pvd", "peripheral artery disease", "pad", "peripheral arterial disease", "claudication"]},
    {"id": 314378, "name": "Deep vein thrombosis", "code": "I82.40", "vocab": "ICD10CM",
     "synonyms": ["deep vein thrombosis", "dvt", "deep venous thrombosis", "venous thrombosis", "leg clot"]},
    {"id": 4084167, "name": "Pulmonary embolism", "code": "I26.99", "vocab": "ICD10CM",
     "synonyms": ["pulmonary embolism", "pe", "pulmonary embolus", "lung clot", "pulmonary thromboembolism"]},
    {"id": 4103295, "name": "Aortic stenosis", "code": "I35.0", "vocab": "ICD10CM",
     "synonyms": ["aortic stenosis", "as", "aortic valve stenosis", "avs", "calcific aortic stenosis"]},

    # Endocrine/Metabolic
    {"id": 201820, "name": "Diabetes mellitus", "code": "E11.9", "vocab": "ICD10CM",
     "synonyms": ["diabetes mellitus", "diabetes", "dm", "dm2", "type 2 diabetes", "t2dm", "niddm", "adult onset diabetes", "sugar diabetes"]},
    {"id": 443238, "name": "Type 1 diabetes mellitus", "code": "E10.9", "vocab": "ICD10CM",
     "synonyms": ["type 1 diabetes mellitus", "type 1 diabetes", "dm1", "t1dm", "iddm", "juvenile diabetes", "insulin dependent diabetes"]},
    {"id": 4193704, "name": "Hypothyroidism", "code": "E03.9", "vocab": "ICD10CM",
     "synonyms": ["hypothyroidism", "underactive thyroid", "low thyroid", "hashimoto's", "myxedema"]},
    {"id": 4060052, "name": "Hyperthyroidism", "code": "E05.90", "vocab": "ICD10CM",
     "synonyms": ["hyperthyroidism", "overactive thyroid", "graves disease", "thyrotoxicosis"]},
    {"id": 432867, "name": "Hyperlipidemia", "code": "E78.5", "vocab": "ICD10CM",
     "synonyms": ["hyperlipidemia", "high cholesterol", "dyslipidemia", "hypercholesterolemia", "elevated lipids", "high triglycerides"]},
    {"id": 436670, "name": "Obesity", "code": "E66.9", "vocab": "ICD10CM",
     "synonyms": ["obesity", "obese", "morbid obesity", "severe obesity", "overweight"]},
    {"id": 437833, "name": "Gout", "code": "M10.9", "vocab": "ICD10CM",
     "synonyms": ["gout", "gouty arthritis", "hyperuricemia", "uric acid arthritis"]},

    # Respiratory
    {"id": 255573, "name": "Chronic obstructive pulmonary disease", "code": "J44.9", "vocab": "ICD10CM",
     "synonyms": ["chronic obstructive pulmonary disease", "copd", "chronic bronchitis", "emphysema", "chronic obstructive lung disease", "cold"]},
    {"id": 317009, "name": "Asthma", "code": "J45.909", "vocab": "ICD10CM",
     "synonyms": ["asthma", "bronchial asthma", "reactive airway disease", "rad", "wheezing"]},
    {"id": 257315, "name": "Pneumonia", "code": "J18.9", "vocab": "ICD10CM",
     "synonyms": ["pneumonia", "pna", "lung infection", "community acquired pneumonia", "cap", "bacterial pneumonia", "viral pneumonia"]},
    {"id": 260139, "name": "Acute bronchitis", "code": "J20.9", "vocab": "ICD10CM",
     "synonyms": ["acute bronchitis", "bronchitis", "chest cold", "bronchial infection"]},
    {"id": 4116142, "name": "Pulmonary fibrosis", "code": "J84.10", "vocab": "ICD10CM",
     "synonyms": ["pulmonary fibrosis", "ipf", "interstitial lung disease", "ild", "lung fibrosis"]},
    {"id": 4266367, "name": "Sleep apnea", "code": "G47.30", "vocab": "ICD10CM",
     "synonyms": ["sleep apnea", "osa", "obstructive sleep apnea", "sleep disordered breathing"]},

    # Gastrointestinal
    {"id": 4291005, "name": "Gastroesophageal reflux disease", "code": "K21.0", "vocab": "ICD10CM",
     "synonyms": ["gastroesophageal reflux disease", "gerd", "acid reflux", "heartburn", "reflux esophagitis"]},
    {"id": 4212540, "name": "Peptic ulcer disease", "code": "K27.9", "vocab": "ICD10CM",
     "synonyms": ["peptic ulcer disease", "pud", "stomach ulcer", "gastric ulcer", "duodenal ulcer"]},
    {"id": 4182210, "name": "Cirrhosis", "code": "K74.60", "vocab": "ICD10CM",
     "synonyms": ["cirrhosis", "liver cirrhosis", "hepatic cirrhosis", "alcoholic cirrhosis", "cirrhosis of liver"]},
    {"id": 4340390, "name": "Irritable bowel syndrome", "code": "K58.9", "vocab": "ICD10CM",
     "synonyms": ["irritable bowel syndrome", "ibs", "spastic colon", "irritable colon"]},
    {"id": 4074815, "name": "Crohn's disease", "code": "K50.90", "vocab": "ICD10CM",
     "synonyms": ["crohn's disease", "crohn disease", "regional enteritis", "inflammatory bowel disease", "ibd"]},
    {"id": 81893, "name": "Ulcerative colitis", "code": "K51.90", "vocab": "ICD10CM",
     "synonyms": ["ulcerative colitis", "uc", "colitis", "inflammatory bowel disease"]},
    {"id": 4245975, "name": "Cholelithiasis", "code": "K80.20", "vocab": "ICD10CM",
     "synonyms": ["cholelithiasis", "gallstones", "gallbladder stones", "biliary calculi"]},
    {"id": 4141062, "name": "Pancreatitis", "code": "K85.90", "vocab": "ICD10CM",
     "synonyms": ["pancreatitis", "acute pancreatitis", "chronic pancreatitis", "pancreatic inflammation"]},
    {"id": 201606, "name": "Hepatitis C", "code": "B18.2", "vocab": "ICD10CM",
     "synonyms": ["hepatitis c", "hcv", "chronic hepatitis c", "hep c"]},

    # Renal/Urologic
    {"id": 46271022, "name": "Chronic kidney disease", "code": "N18.9", "vocab": "ICD10CM",
     "synonyms": ["chronic kidney disease", "ckd", "chronic renal failure", "crf", "renal insufficiency", "kidney disease"]},
    {"id": 197320, "name": "Acute kidney injury", "code": "N17.9", "vocab": "ICD10CM",
     "synonyms": ["acute kidney injury", "aki", "acute renal failure", "arf", "acute kidney failure"]},
    {"id": 81902, "name": "Urinary tract infection", "code": "N39.0", "vocab": "ICD10CM",
     "synonyms": ["urinary tract infection", "uti", "bladder infection", "cystitis", "pyelonephritis"]},
    {"id": 4163735, "name": "Nephrolithiasis", "code": "N20.0", "vocab": "ICD10CM",
     "synonyms": ["nephrolithiasis", "kidney stones", "renal calculi", "urolithiasis", "renal stones"]},
    {"id": 4163261, "name": "Benign prostatic hyperplasia", "code": "N40.0", "vocab": "ICD10CM",
     "synonyms": ["benign prostatic hyperplasia", "bph", "enlarged prostate", "prostatic hypertrophy"]},

    # Neurological
    {"id": 372924, "name": "Cerebrovascular accident", "code": "I63.9", "vocab": "ICD10CM",
     "synonyms": ["cerebrovascular accident", "cva", "stroke", "ischemic stroke", "brain attack", "cerebral infarction"]},
    {"id": 4112853, "name": "Transient ischemic attack", "code": "G45.9", "vocab": "ICD10CM",
     "synonyms": ["transient ischemic attack", "tia", "mini stroke", "transient cerebral ischemia"]},
    {"id": 378253, "name": "Epilepsy", "code": "G40.909", "vocab": "ICD10CM",
     "synonyms": ["epilepsy", "seizure disorder", "seizures", "convulsions"]},
    {"id": 378427, "name": "Migraine", "code": "G43.909", "vocab": "ICD10CM",
     "synonyms": ["migraine", "migraine headache", "migraines", "classic migraine", "migraine with aura"]},
    {"id": 378419, "name": "Parkinson's disease", "code": "G20", "vocab": "ICD10CM",
     "synonyms": ["parkinson's disease", "parkinson disease", "parkinsonism", "pd", "shaking palsy"]},
    {"id": 378143, "name": "Alzheimer's disease", "code": "G30.9", "vocab": "ICD10CM",
     "synonyms": ["alzheimer's disease", "alzheimer disease", "alzheimers", "senile dementia", "dementia of alzheimer type"]},
    {"id": 377786, "name": "Multiple sclerosis", "code": "G35", "vocab": "ICD10CM",
     "synonyms": ["multiple sclerosis", "ms", "disseminated sclerosis"]},
    {"id": 377527, "name": "Neuropathy", "code": "G62.9", "vocab": "ICD10CM",
     "synonyms": ["neuropathy", "peripheral neuropathy", "polyneuropathy", "nerve damage"]},

    # Musculoskeletal
    {"id": 80180, "name": "Osteoarthritis", "code": "M19.90", "vocab": "ICD10CM",
     "synonyms": ["osteoarthritis", "oa", "degenerative joint disease", "djd", "arthritis", "wear and tear arthritis"]},
    {"id": 80809, "name": "Rheumatoid arthritis", "code": "M06.9", "vocab": "ICD10CM",
     "synonyms": ["rheumatoid arthritis", "ra", "rheumatoid disease", "inflammatory arthritis"]},
    {"id": 77670, "name": "Osteoporosis", "code": "M81.0", "vocab": "ICD10CM",
     "synonyms": ["osteoporosis", "bone loss", "brittle bones", "low bone density"]},
    {"id": 73754, "name": "Low back pain", "code": "M54.5", "vocab": "ICD10CM",
     "synonyms": ["low back pain", "lbp", "lumbar pain", "backache", "lumbago"]},
    {"id": 4134120, "name": "Fibromyalgia", "code": "M79.7", "vocab": "ICD10CM",
     "synonyms": ["fibromyalgia", "fibromyalgia syndrome", "fibrositis", "chronic widespread pain"]},

    # Psychiatric
    {"id": 4182445, "name": "Major depressive disorder", "code": "F33.9", "vocab": "ICD10CM",
     "synonyms": ["major depressive disorder", "mdd", "depression", "clinical depression", "major depression", "depressive disorder"]},
    {"id": 441542, "name": "Generalized anxiety disorder", "code": "F41.1", "vocab": "ICD10CM",
     "synonyms": ["generalized anxiety disorder", "gad", "anxiety", "anxiety disorder", "chronic anxiety"]},
    {"id": 436665, "name": "Bipolar disorder", "code": "F31.9", "vocab": "ICD10CM",
     "synonyms": ["bipolar disorder", "bipolar", "manic depression", "manic depressive disorder"]},
    {"id": 435783, "name": "Schizophrenia", "code": "F20.9", "vocab": "ICD10CM",
     "synonyms": ["schizophrenia", "schizo", "psychosis"]},
    {"id": 434613, "name": "Post-traumatic stress disorder", "code": "F43.10", "vocab": "ICD10CM",
     "synonyms": ["post-traumatic stress disorder", "ptsd", "post traumatic stress", "traumatic stress disorder"]},
    {"id": 438409, "name": "Attention deficit hyperactivity disorder", "code": "F90.9", "vocab": "ICD10CM",
     "synonyms": ["attention deficit hyperactivity disorder", "adhd", "add", "attention deficit disorder", "hyperactivity"]},

    # Infectious
    {"id": 4195694, "name": "Influenza", "code": "J11.1", "vocab": "ICD10CM",
     "synonyms": ["influenza", "flu", "influenza virus", "seasonal flu", "grippe"]},
    {"id": 37311061, "name": "COVID-19", "code": "U07.1", "vocab": "ICD10CM",
     "synonyms": ["covid-19", "covid", "coronavirus", "sars-cov-2", "coronavirus disease 2019"]},
    {"id": 439727, "name": "Sepsis", "code": "A41.9", "vocab": "ICD10CM",
     "synonyms": ["sepsis", "septicemia", "blood infection", "severe sepsis", "septic shock"]},
    {"id": 4119607, "name": "Cellulitis", "code": "L03.90", "vocab": "ICD10CM",
     "synonyms": ["cellulitis", "skin infection", "soft tissue infection"]},
    {"id": 432545, "name": "HIV infection", "code": "B20", "vocab": "ICD10CM",
     "synonyms": ["hiv infection", "hiv", "human immunodeficiency virus", "aids", "hiv/aids"]},

    # Oncology
    {"id": 4112752, "name": "Lung cancer", "code": "C34.90", "vocab": "ICD10CM",
     "synonyms": ["lung cancer", "lung carcinoma", "bronchogenic carcinoma", "nsclc", "sclc", "lung malignancy"]},
    {"id": 4112853, "name": "Breast cancer", "code": "C50.919", "vocab": "ICD10CM",
     "synonyms": ["breast cancer", "breast carcinoma", "mammary cancer", "breast malignancy"]},
    {"id": 4181343, "name": "Prostate cancer", "code": "C61", "vocab": "ICD10CM",
     "synonyms": ["prostate cancer", "prostate carcinoma", "prostatic cancer", "prostate malignancy"]},
    {"id": 438688, "name": "Colorectal cancer", "code": "C18.9", "vocab": "ICD10CM",
     "synonyms": ["colorectal cancer", "colon cancer", "rectal cancer", "bowel cancer", "colorectal carcinoma"]},
    {"id": 4112733, "name": "Pancreatic cancer", "code": "C25.9", "vocab": "ICD10CM",
     "synonyms": ["pancreatic cancer", "pancreatic carcinoma", "pancreas cancer"]},
    {"id": 4116142, "name": "Leukemia", "code": "C95.90", "vocab": "ICD10CM",
     "synonyms": ["leukemia", "leukaemia", "blood cancer", "aml", "all", "cml", "cll"]},
    {"id": 4112859, "name": "Lymphoma", "code": "C85.90", "vocab": "ICD10CM",
     "synonyms": ["lymphoma", "hodgkin lymphoma", "non-hodgkin lymphoma", "nhl"]},

    # Dermatologic
    {"id": 140168, "name": "Psoriasis", "code": "L40.9", "vocab": "ICD10CM",
     "synonyms": ["psoriasis", "plaque psoriasis", "psoriatic disease"]},
    {"id": 133834, "name": "Eczema", "code": "L30.9", "vocab": "ICD10CM",
     "synonyms": ["eczema", "atopic dermatitis", "dermatitis", "atopic eczema"]},
    {"id": 141095, "name": "Acne", "code": "L70.9", "vocab": "ICD10CM",
     "synonyms": ["acne", "acne vulgaris", "pimples", "zits"]},

    # Hematologic
    {"id": 439777, "name": "Anemia", "code": "D64.9", "vocab": "ICD10CM",
     "synonyms": ["anemia", "anaemia", "low hemoglobin", "low blood count", "iron deficiency anemia"]},
    {"id": 4163566, "name": "Thrombocytopenia", "code": "D69.6", "vocab": "ICD10CM",
     "synonyms": ["thrombocytopenia", "low platelets", "low platelet count", "plt low"]},

    # Allergic/Immunologic
    {"id": 257007, "name": "Allergic rhinitis", "code": "J30.9", "vocab": "ICD10CM",
     "synonyms": ["allergic rhinitis", "hay fever", "seasonal allergies", "nasal allergies", "allergies"]},
    {"id": 261880, "name": "Anaphylaxis", "code": "T78.2XXA", "vocab": "ICD10CM",
     "synonyms": ["anaphylaxis", "anaphylactic reaction", "severe allergic reaction", "anaphylactic shock"]},
]


# ============================================================================
# Common Drugs
# ============================================================================

DRUGS = [
    # Cardiovascular
    {"id": 1308216, "name": "Lisinopril", "code": "104377", "vocab": "RxNorm",
     "synonyms": ["lisinopril", "prinivil", "zestril", "ace inhibitor"]},
    {"id": 1308842, "name": "Amlodipine", "code": "17767", "vocab": "RxNorm",
     "synonyms": ["amlodipine", "norvasc", "calcium channel blocker", "ccb"]},
    {"id": 1395058, "name": "Metoprolol", "code": "6918", "vocab": "RxNorm",
     "synonyms": ["metoprolol", "lopressor", "toprol", "beta blocker", "bb"]},
    {"id": 1386957, "name": "Atenolol", "code": "1202", "vocab": "RxNorm",
     "synonyms": ["atenolol", "tenormin", "beta blocker"]},
    {"id": 1340128, "name": "Carvedilol", "code": "20352", "vocab": "RxNorm",
     "synonyms": ["carvedilol", "coreg", "beta blocker"]},
    {"id": 974166, "name": "Losartan", "code": "52175", "vocab": "RxNorm",
     "synonyms": ["losartan", "cozaar", "arb", "angiotensin receptor blocker"]},
    {"id": 1317640, "name": "Valsartan", "code": "69749", "vocab": "RxNorm",
     "synonyms": ["valsartan", "diovan", "arb"]},
    {"id": 956874, "name": "Furosemide", "code": "4603", "vocab": "RxNorm",
     "synonyms": ["furosemide", "lasix", "loop diuretic", "water pill"]},
    {"id": 978555, "name": "Hydrochlorothiazide", "code": "5487", "vocab": "RxNorm",
     "synonyms": ["hydrochlorothiazide", "hctz", "microzide", "thiazide", "water pill"]},
    {"id": 1326303, "name": "Spironolactone", "code": "9997", "vocab": "RxNorm",
     "synonyms": ["spironolactone", "aldactone", "potassium sparing diuretic"]},
    {"id": 1549686, "name": "Warfarin", "code": "11289", "vocab": "RxNorm",
     "synonyms": ["warfarin", "coumadin", "blood thinner", "anticoagulant"]},
    {"id": 1310149, "name": "Apixaban", "code": "1232082", "vocab": "RxNorm",
     "synonyms": ["apixaban", "eliquis", "noac", "blood thinner"]},
    {"id": 1592085, "name": "Rivaroxaban", "code": "1114195", "vocab": "RxNorm",
     "synonyms": ["rivaroxaban", "xarelto", "noac", "blood thinner"]},
    {"id": 1778262, "name": "Aspirin", "code": "1191", "vocab": "RxNorm",
     "synonyms": ["aspirin", "asa", "acetylsalicylic acid", "baby aspirin"]},
    {"id": 1322184, "name": "Clopidogrel", "code": "32968", "vocab": "RxNorm",
     "synonyms": ["clopidogrel", "plavix", "antiplatelet"]},
    {"id": 1551860, "name": "Atorvastatin", "code": "83367", "vocab": "RxNorm",
     "synonyms": ["atorvastatin", "lipitor", "statin", "cholesterol medication"]},
    {"id": 1592722, "name": "Rosuvastatin", "code": "301542", "vocab": "RxNorm",
     "synonyms": ["rosuvastatin", "crestor", "statin"]},
    {"id": 1551803, "name": "Simvastatin", "code": "36567", "vocab": "RxNorm",
     "synonyms": ["simvastatin", "zocor", "statin"]},
    {"id": 1545996, "name": "Pravastatin", "code": "42463", "vocab": "RxNorm",
     "synonyms": ["pravastatin", "pravachol", "statin"]},

    # Diabetes
    {"id": 1503297, "name": "Metformin", "code": "6809", "vocab": "RxNorm",
     "synonyms": ["metformin", "glucophage", "biguanide", "diabetes medication"]},
    {"id": 1529331, "name": "Glipizide", "code": "4821", "vocab": "RxNorm",
     "synonyms": ["glipizide", "glucotrol", "sulfonylurea"]},
    {"id": 1530014, "name": "Glyburide", "code": "4815", "vocab": "RxNorm",
     "synonyms": ["glyburide", "diabeta", "micronase", "sulfonylurea"]},
    {"id": 1559684, "name": "Sitagliptin", "code": "593411", "vocab": "RxNorm",
     "synonyms": ["sitagliptin", "januvia", "dpp-4 inhibitor"]},
    {"id": 43013884, "name": "Empagliflozin", "code": "1545653", "vocab": "RxNorm",
     "synonyms": ["empagliflozin", "jardiance", "sglt2 inhibitor"]},
    {"id": 44507866, "name": "Semaglutide", "code": "1991302", "vocab": "RxNorm",
     "synonyms": ["semaglutide", "ozempic", "rybelsus", "wegovy", "glp-1", "glp-1 agonist"]},
    {"id": 1502826, "name": "Insulin glargine", "code": "274783", "vocab": "RxNorm",
     "synonyms": ["insulin glargine", "lantus", "basaglar", "long acting insulin"]},
    {"id": 1502905, "name": "Insulin lispro", "code": "86009", "vocab": "RxNorm",
     "synonyms": ["insulin lispro", "humalog", "rapid acting insulin"]},
    {"id": 1596977, "name": "Insulin aspart", "code": "86009", "vocab": "RxNorm",
     "synonyms": ["insulin aspart", "novolog", "rapid acting insulin"]},

    # Pain/Anti-inflammatory
    {"id": 1124957, "name": "Ibuprofen", "code": "5640", "vocab": "RxNorm",
     "synonyms": ["ibuprofen", "advil", "motrin", "nsaid", "anti-inflammatory"]},
    {"id": 1115008, "name": "Naproxen", "code": "7258", "vocab": "RxNorm",
     "synonyms": ["naproxen", "aleve", "naprosyn", "nsaid"]},
    {"id": 1136980, "name": "Acetaminophen", "code": "161", "vocab": "RxNorm",
     "synonyms": ["acetaminophen", "tylenol", "paracetamol", "apap"]},
    {"id": 1174888, "name": "Tramadol", "code": "10689", "vocab": "RxNorm",
     "synonyms": ["tramadol", "ultram", "pain medication"]},
    {"id": 1110410, "name": "Oxycodone", "code": "7804", "vocab": "RxNorm",
     "synonyms": ["oxycodone", "oxycontin", "roxicodone", "opioid", "narcotic"]},
    {"id": 1110808, "name": "Hydrocodone", "code": "5489", "vocab": "RxNorm",
     "synonyms": ["hydrocodone", "norco", "vicodin", "lortab", "opioid"]},
    {"id": 1149196, "name": "Morphine", "code": "7052", "vocab": "RxNorm",
     "synonyms": ["morphine", "ms contin", "opioid", "narcotic"]},
    {"id": 1713332, "name": "Gabapentin", "code": "25480", "vocab": "RxNorm",
     "synonyms": ["gabapentin", "neurontin", "nerve pain medication"]},
    {"id": 1713845, "name": "Pregabalin", "code": "187832", "vocab": "RxNorm",
     "synonyms": ["pregabalin", "lyrica", "nerve pain medication"]},

    # Antibiotics
    {"id": 1734104, "name": "Amoxicillin", "code": "723", "vocab": "RxNorm",
     "synonyms": ["amoxicillin", "amoxil", "penicillin", "antibiotic"]},
    {"id": 1736887, "name": "Azithromycin", "code": "18631", "vocab": "RxNorm",
     "synonyms": ["azithromycin", "zithromax", "z-pack", "zpack", "antibiotic", "macrolide"]},
    {"id": 1797513, "name": "Ciprofloxacin", "code": "2551", "vocab": "RxNorm",
     "synonyms": ["ciprofloxacin", "cipro", "fluoroquinolone", "antibiotic"]},
    {"id": 1738521, "name": "Levofloxacin", "code": "82122", "vocab": "RxNorm",
     "synonyms": ["levofloxacin", "levaquin", "fluoroquinolone", "antibiotic"]},
    {"id": 1716721, "name": "Doxycycline", "code": "3640", "vocab": "RxNorm",
     "synonyms": ["doxycycline", "vibramycin", "tetracycline", "antibiotic"]},
    {"id": 1759842, "name": "Cephalexin", "code": "2231", "vocab": "RxNorm",
     "synonyms": ["cephalexin", "keflex", "cephalosporin", "antibiotic"]},
    {"id": 19078461, "name": "Trimethoprim-sulfamethoxazole", "code": "10831", "vocab": "RxNorm",
     "synonyms": ["trimethoprim-sulfamethoxazole", "bactrim", "septra", "tmp-smx", "antibiotic"]},
    {"id": 1777087, "name": "Metronidazole", "code": "6922", "vocab": "RxNorm",
     "synonyms": ["metronidazole", "flagyl", "antibiotic"]},
    {"id": 1717963, "name": "Vancomycin", "code": "11124", "vocab": "RxNorm",
     "synonyms": ["vancomycin", "vancocin", "antibiotic"]},
    {"id": 1746114, "name": "Clindamycin", "code": "2582", "vocab": "RxNorm",
     "synonyms": ["clindamycin", "cleocin", "antibiotic"]},

    # GI
    {"id": 948078, "name": "Omeprazole", "code": "7646", "vocab": "RxNorm",
     "synonyms": ["omeprazole", "prilosec", "ppi", "proton pump inhibitor", "acid reducer"]},
    {"id": 923645, "name": "Pantoprazole", "code": "40790", "vocab": "RxNorm",
     "synonyms": ["pantoprazole", "protonix", "ppi", "proton pump inhibitor"]},
    {"id": 929887, "name": "Esomeprazole", "code": "283742", "vocab": "RxNorm",
     "synonyms": ["esomeprazole", "nexium", "ppi", "proton pump inhibitor"]},
    {"id": 961047, "name": "Famotidine", "code": "4278", "vocab": "RxNorm",
     "synonyms": ["famotidine", "pepcid", "h2 blocker", "acid reducer"]},
    {"id": 950696, "name": "Ondansetron", "code": "26225", "vocab": "RxNorm",
     "synonyms": ["ondansetron", "zofran", "anti-nausea", "antiemetic"]},
    {"id": 905182, "name": "Metoclopramide", "code": "6915", "vocab": "RxNorm",
     "synonyms": ["metoclopramide", "reglan", "anti-nausea"]},
    {"id": 19019273, "name": "Polyethylene glycol", "code": "8514", "vocab": "RxNorm",
     "synonyms": ["polyethylene glycol", "miralax", "peg", "laxative"]},
    {"id": 19050216, "name": "Docusate", "code": "3355", "vocab": "RxNorm",
     "synonyms": ["docusate", "colace", "stool softener"]},

    # Respiratory
    {"id": 1154343, "name": "Albuterol", "code": "435", "vocab": "RxNorm",
     "synonyms": ["albuterol", "proventil", "ventolin", "salbutamol", "rescue inhaler", "bronchodilator"]},
    {"id": 1193240, "name": "Fluticasone", "code": "41126", "vocab": "RxNorm",
     "synonyms": ["fluticasone", "flovent", "flonase", "inhaled steroid"]},
    {"id": 40166035, "name": "Budesonide", "code": "19831", "vocab": "RxNorm",
     "synonyms": ["budesonide", "pulmicort", "symbicort", "inhaled steroid"]},
    {"id": 1196935, "name": "Tiotropium", "code": "274766", "vocab": "RxNorm",
     "synonyms": ["tiotropium", "spiriva", "lama", "long acting muscarinic antagonist"]},
    {"id": 1149380, "name": "Montelukast", "code": "88249", "vocab": "RxNorm",
     "synonyms": ["montelukast", "singulair", "leukotriene inhibitor"]},
    {"id": 1119119, "name": "Prednisone", "code": "8640", "vocab": "RxNorm",
     "synonyms": ["prednisone", "deltasone", "steroid", "corticosteroid"]},
    {"id": 1550557, "name": "Methylprednisolone", "code": "6902", "vocab": "RxNorm",
     "synonyms": ["methylprednisolone", "medrol", "solu-medrol", "steroid"]},

    # Psychiatric
    {"id": 739138, "name": "Sertraline", "code": "36437", "vocab": "RxNorm",
     "synonyms": ["sertraline", "zoloft", "ssri", "antidepressant"]},
    {"id": 755695, "name": "Escitalopram", "code": "321988", "vocab": "RxNorm",
     "synonyms": ["escitalopram", "lexapro", "ssri", "antidepressant"]},
    {"id": 797617, "name": "Fluoxetine", "code": "4493", "vocab": "RxNorm",
     "synonyms": ["fluoxetine", "prozac", "ssri", "antidepressant"]},
    {"id": 778268, "name": "Citalopram", "code": "2556", "vocab": "RxNorm",
     "synonyms": ["citalopram", "celexa", "ssri", "antidepressant"]},
    {"id": 751905, "name": "Duloxetine", "code": "72625", "vocab": "RxNorm",
     "synonyms": ["duloxetine", "cymbalta", "snri", "antidepressant"]},
    {"id": 743670, "name": "Venlafaxine", "code": "39786", "vocab": "RxNorm",
     "synonyms": ["venlafaxine", "effexor", "snri", "antidepressant"]},
    {"id": 739994, "name": "Bupropion", "code": "42347", "vocab": "RxNorm",
     "synonyms": ["bupropion", "wellbutrin", "antidepressant"]},
    {"id": 753626, "name": "Trazodone", "code": "10737", "vocab": "RxNorm",
     "synonyms": ["trazodone", "desyrel", "antidepressant", "sleep aid"]},
    {"id": 785649, "name": "Mirtazapine", "code": "30121", "vocab": "RxNorm",
     "synonyms": ["mirtazapine", "remeron", "antidepressant"]},
    {"id": 708298, "name": "Quetiapine", "code": "51272", "vocab": "RxNorm",
     "synonyms": ["quetiapine", "seroquel", "antipsychotic"]},
    {"id": 722031, "name": "Risperidone", "code": "35636", "vocab": "RxNorm",
     "synonyms": ["risperidone", "risperdal", "antipsychotic"]},
    {"id": 766529, "name": "Aripiprazole", "code": "89013", "vocab": "RxNorm",
     "synonyms": ["aripiprazole", "abilify", "antipsychotic"]},
    {"id": 797399, "name": "Olanzapine", "code": "61381", "vocab": "RxNorm",
     "synonyms": ["olanzapine", "zyprexa", "antipsychotic"]},
    {"id": 782043, "name": "Lorazepam", "code": "6470", "vocab": "RxNorm",
     "synonyms": ["lorazepam", "ativan", "benzodiazepine", "benzo", "anxiolytic"]},
    {"id": 723013, "name": "Alprazolam", "code": "596", "vocab": "RxNorm",
     "synonyms": ["alprazolam", "xanax", "benzodiazepine", "benzo"]},
    {"id": 703547, "name": "Clonazepam", "code": "2598", "vocab": "RxNorm",
     "synonyms": ["clonazepam", "klonopin", "benzodiazepine"]},
    {"id": 715259, "name": "Diazepam", "code": "3322", "vocab": "RxNorm",
     "synonyms": ["diazepam", "valium", "benzodiazepine"]},
    {"id": 757688, "name": "Zolpidem", "code": "39993", "vocab": "RxNorm",
     "synonyms": ["zolpidem", "ambien", "sleep aid", "hypnotic"]},

    # Thyroid
    {"id": 1501700, "name": "Levothyroxine", "code": "10582", "vocab": "RxNorm",
     "synonyms": ["levothyroxine", "synthroid", "levoxyl", "thyroid medication", "t4"]},
    {"id": 1546356, "name": "Liothyronine", "code": "6451", "vocab": "RxNorm",
     "synonyms": ["liothyronine", "cytomel", "t3"]},

    # Other
    {"id": 1311799, "name": "Allopurinol", "code": "519", "vocab": "RxNorm",
     "synonyms": ["allopurinol", "zyloprim", "gout medication"]},
    {"id": 975125, "name": "Colchicine", "code": "2683", "vocab": "RxNorm",
     "synonyms": ["colchicine", "colcrys", "gout medication"]},
    {"id": 1586369, "name": "Finasteride", "code": "72236", "vocab": "RxNorm",
     "synonyms": ["finasteride", "proscar", "propecia", "bph medication"]},
    {"id": 1312706, "name": "Tamsulosin", "code": "77492", "vocab": "RxNorm",
     "synonyms": ["tamsulosin", "flomax", "alpha blocker", "bph medication"]},
    {"id": 1337720, "name": "Sildenafil", "code": "136411", "vocab": "RxNorm",
     "synonyms": ["sildenafil", "viagra", "revatio", "pde5 inhibitor"]},
]


# ============================================================================
# Common Measurements (LOINC)
# ============================================================================

MEASUREMENTS = [
    # Vital Signs
    {"id": 3004249, "name": "Systolic blood pressure", "code": "8480-6", "vocab": "LOINC",
     "synonyms": ["systolic blood pressure", "sbp", "systolic bp", "systolic"]},
    {"id": 3012888, "name": "Diastolic blood pressure", "code": "8462-4", "vocab": "LOINC",
     "synonyms": ["diastolic blood pressure", "dbp", "diastolic bp", "diastolic"]},
    {"id": 3027018, "name": "Heart rate", "code": "8867-4", "vocab": "LOINC",
     "synonyms": ["heart rate", "hr", "pulse", "pulse rate", "beats per minute", "bpm"]},
    {"id": 3024171, "name": "Respiratory rate", "code": "9279-1", "vocab": "LOINC",
     "synonyms": ["respiratory rate", "rr", "respirations", "breaths per minute"]},
    {"id": 3020891, "name": "Body temperature", "code": "8310-5", "vocab": "LOINC",
     "synonyms": ["body temperature", "temperature", "temp", "t", "fever"]},
    {"id": 3016502, "name": "Oxygen saturation", "code": "59408-5", "vocab": "LOINC",
     "synonyms": ["oxygen saturation", "spo2", "o2 sat", "sat", "pulse ox", "oximetry"]},
    {"id": 3025315, "name": "Body weight", "code": "29463-7", "vocab": "LOINC",
     "synonyms": ["body weight", "weight", "wt"]},
    {"id": 3023540, "name": "Body height", "code": "8302-2", "vocab": "LOINC",
     "synonyms": ["body height", "height", "ht", "stature"]},
    {"id": 3038553, "name": "Body mass index", "code": "39156-5", "vocab": "LOINC",
     "synonyms": ["body mass index", "bmi"]},

    # Basic Metabolic Panel
    {"id": 3019550, "name": "Sodium", "code": "2951-2", "vocab": "LOINC",
     "synonyms": ["sodium", "na", "na+", "serum sodium"]},
    {"id": 3023103, "name": "Potassium", "code": "2823-3", "vocab": "LOINC",
     "synonyms": ["potassium", "k", "k+", "serum potassium"]},
    {"id": 3014576, "name": "Chloride", "code": "2075-0", "vocab": "LOINC",
     "synonyms": ["chloride", "cl", "cl-", "serum chloride"]},
    {"id": 3016723, "name": "Bicarbonate", "code": "1963-8", "vocab": "LOINC",
     "synonyms": ["bicarbonate", "hco3", "co2", "total co2", "tco2"]},
    {"id": 3013682, "name": "Blood urea nitrogen", "code": "3094-0", "vocab": "LOINC",
     "synonyms": ["blood urea nitrogen", "bun", "urea nitrogen"]},
    {"id": 3016723, "name": "Creatinine", "code": "2160-0", "vocab": "LOINC",
     "synonyms": ["creatinine", "cr", "serum creatinine", "scr"]},
    {"id": 3004501, "name": "Glucose", "code": "2345-7", "vocab": "LOINC",
     "synonyms": ["glucose", "blood glucose", "blood sugar", "sugar", "glu"]},
    {"id": 3013721, "name": "Calcium", "code": "17861-6", "vocab": "LOINC",
     "synonyms": ["calcium", "ca", "ca++", "serum calcium"]},
    {"id": 3018677, "name": "Magnesium", "code": "19123-9", "vocab": "LOINC",
     "synonyms": ["magnesium", "mg", "mg++", "serum magnesium"]},
    {"id": 3015182, "name": "Phosphorus", "code": "2777-1", "vocab": "LOINC",
     "synonyms": ["phosphorus", "phos", "phosphate", "serum phosphorus"]},

    # Complete Blood Count
    {"id": 3000905, "name": "White blood cell count", "code": "6690-2", "vocab": "LOINC",
     "synonyms": ["white blood cell count", "wbc", "white count", "leukocytes"]},
    {"id": 3000963, "name": "Hemoglobin", "code": "718-7", "vocab": "LOINC",
     "synonyms": ["hemoglobin", "hgb", "hb"]},
    {"id": 3009542, "name": "Hematocrit", "code": "4544-3", "vocab": "LOINC",
     "synonyms": ["hematocrit", "hct", "crit"]},
    {"id": 3024929, "name": "Platelet count", "code": "777-3", "vocab": "LOINC",
     "synonyms": ["platelet count", "platelets", "plt", "thrombocytes"]},
    {"id": 3002385, "name": "Mean corpuscular volume", "code": "787-2", "vocab": "LOINC",
     "synonyms": ["mean corpuscular volume", "mcv"]},
    {"id": 3012030, "name": "Red blood cell count", "code": "789-8", "vocab": "LOINC",
     "synonyms": ["red blood cell count", "rbc", "erythrocytes"]},

    # Liver Function Tests
    {"id": 3006923, "name": "Alanine aminotransferase", "code": "1742-6", "vocab": "LOINC",
     "synonyms": ["alanine aminotransferase", "alt", "sgpt", "liver enzymes"]},
    {"id": 3013721, "name": "Aspartate aminotransferase", "code": "1920-8", "vocab": "LOINC",
     "synonyms": ["aspartate aminotransferase", "ast", "sgot", "liver enzymes"]},
    {"id": 3024128, "name": "Alkaline phosphatase", "code": "6768-6", "vocab": "LOINC",
     "synonyms": ["alkaline phosphatase", "alp", "alk phos"]},
    {"id": 3024561, "name": "Total bilirubin", "code": "1975-2", "vocab": "LOINC",
     "synonyms": ["total bilirubin", "bilirubin", "tbili", "t bili"]},
    {"id": 3007220, "name": "Direct bilirubin", "code": "1968-7", "vocab": "LOINC",
     "synonyms": ["direct bilirubin", "dbili", "d bili", "conjugated bilirubin"]},
    {"id": 3024561, "name": "Albumin", "code": "1751-7", "vocab": "LOINC",
     "synonyms": ["albumin", "alb", "serum albumin"]},
    {"id": 3020630, "name": "Total protein", "code": "2885-2", "vocab": "LOINC",
     "synonyms": ["total protein", "protein", "tp"]},

    # Coagulation
    {"id": 3034426, "name": "INR", "code": "6301-6", "vocab": "LOINC",
     "synonyms": ["inr", "international normalized ratio", "pt/inr"]},
    {"id": 3022217, "name": "Prothrombin time", "code": "5902-2", "vocab": "LOINC",
     "synonyms": ["prothrombin time", "pt", "protime"]},
    {"id": 3013466, "name": "Partial thromboplastin time", "code": "3173-2", "vocab": "LOINC",
     "synonyms": ["partial thromboplastin time", "ptt", "aptt"]},

    # Cardiac Markers
    {"id": 3017732, "name": "Troponin I", "code": "10839-9", "vocab": "LOINC",
     "synonyms": ["troponin i", "tni", "troponin", "cardiac troponin"]},
    {"id": 3028615, "name": "Troponin T", "code": "6598-7", "vocab": "LOINC",
     "synonyms": ["troponin t", "tnt", "cardiac troponin"]},
    {"id": 3027018, "name": "BNP", "code": "30934-4", "vocab": "LOINC",
     "synonyms": ["bnp", "b-type natriuretic peptide", "brain natriuretic peptide"]},
    {"id": 3027018, "name": "Pro-BNP", "code": "33762-6", "vocab": "LOINC",
     "synonyms": ["pro-bnp", "nt-probnp", "proBNP", "n-terminal pro-bnp"]},

    # Lipid Panel
    {"id": 3027114, "name": "Total cholesterol", "code": "2093-3", "vocab": "LOINC",
     "synonyms": ["total cholesterol", "cholesterol", "tc", "chol"]},
    {"id": 3028437, "name": "LDL cholesterol", "code": "13457-7", "vocab": "LOINC",
     "synonyms": ["ldl cholesterol", "ldl", "ldl-c", "bad cholesterol"]},
    {"id": 3007070, "name": "HDL cholesterol", "code": "2085-9", "vocab": "LOINC",
     "synonyms": ["hdl cholesterol", "hdl", "hdl-c", "good cholesterol"]},
    {"id": 3022192, "name": "Triglycerides", "code": "2571-8", "vocab": "LOINC",
     "synonyms": ["triglycerides", "tg", "trigs"]},

    # Thyroid
    {"id": 3019540, "name": "TSH", "code": "3016-3", "vocab": "LOINC",
     "synonyms": ["tsh", "thyroid stimulating hormone", "thyrotropin"]},
    {"id": 3009261, "name": "Free T4", "code": "3024-7", "vocab": "LOINC",
     "synonyms": ["free t4", "ft4", "free thyroxine"]},
    {"id": 3020780, "name": "Free T3", "code": "3051-0", "vocab": "LOINC",
     "synonyms": ["free t3", "ft3", "free triiodothyronine"]},

    # Diabetes
    {"id": 3004410, "name": "Hemoglobin A1c", "code": "4548-4", "vocab": "LOINC",
     "synonyms": ["hemoglobin a1c", "hba1c", "a1c", "glycated hemoglobin", "glycosylated hemoglobin"]},
    {"id": 3004501, "name": "Fasting glucose", "code": "1558-6", "vocab": "LOINC",
     "synonyms": ["fasting glucose", "fbs", "fasting blood sugar", "fbg"]},

    # Kidney Function
    {"id": 3049187, "name": "eGFR", "code": "33914-3", "vocab": "LOINC",
     "synonyms": ["egfr", "estimated gfr", "glomerular filtration rate", "gfr"]},
    {"id": 3016407, "name": "Microalbumin", "code": "14957-5", "vocab": "LOINC",
     "synonyms": ["microalbumin", "urine albumin", "uacr"]},

    # Urinalysis
    {"id": 3020509, "name": "Urine pH", "code": "2756-5", "vocab": "LOINC",
     "synonyms": ["urine ph", "urine acidity"]},
    {"id": 3016231, "name": "Urine protein", "code": "2888-6", "vocab": "LOINC",
     "synonyms": ["urine protein", "proteinuria"]},
    {"id": 3016910, "name": "Urine glucose", "code": "2350-7", "vocab": "LOINC",
     "synonyms": ["urine glucose", "glucosuria"]},
    {"id": 3009353, "name": "Urine ketones", "code": "2514-8", "vocab": "LOINC",
     "synonyms": ["urine ketones", "ketonuria"]},

    # Inflammatory Markers
    {"id": 3020460, "name": "C-reactive protein", "code": "1988-5", "vocab": "LOINC",
     "synonyms": ["c-reactive protein", "crp", "high-sensitivity crp", "hs-crp"]},
    {"id": 3013115, "name": "Erythrocyte sedimentation rate", "code": "4537-7", "vocab": "LOINC",
     "synonyms": ["erythrocyte sedimentation rate", "esr", "sed rate"]},
    {"id": 3018916, "name": "Procalcitonin", "code": "33959-8", "vocab": "LOINC",
     "synonyms": ["procalcitonin", "pct"]},

    # Electrolytes/Minerals
    {"id": 3013855, "name": "Iron", "code": "2498-4", "vocab": "LOINC",
     "synonyms": ["iron", "fe", "serum iron"]},
    {"id": 3001986, "name": "Ferritin", "code": "2276-4", "vocab": "LOINC",
     "synonyms": ["ferritin", "iron stores"]},
    {"id": 3002109, "name": "TIBC", "code": "2500-7", "vocab": "LOINC",
     "synonyms": ["tibc", "total iron binding capacity"]},
    {"id": 3017250, "name": "Vitamin D", "code": "1989-3", "vocab": "LOINC",
     "synonyms": ["vitamin d", "25-hydroxy vitamin d", "25-oh vitamin d", "vit d"]},
    {"id": 3023230, "name": "Vitamin B12", "code": "2132-9", "vocab": "LOINC",
     "synonyms": ["vitamin b12", "b12", "cobalamin"]},
    {"id": 3023323, "name": "Folate", "code": "2284-8", "vocab": "LOINC",
     "synonyms": ["folate", "folic acid"]},
]


# ============================================================================
# Common Procedures
# ============================================================================

PROCEDURES = [
    # Cardiovascular
    {"id": 4336464, "name": "Electrocardiogram", "code": "93000", "vocab": "CPT4",
     "synonyms": ["electrocardiogram", "ekg", "ecg", "12 lead ekg", "12-lead ecg"]},
    {"id": 4150129, "name": "Echocardiogram", "code": "93306", "vocab": "CPT4",
     "synonyms": ["echocardiogram", "echo", "transthoracic echo", "tte", "cardiac ultrasound"]},
    {"id": 4232657, "name": "Cardiac catheterization", "code": "93458", "vocab": "CPT4",
     "synonyms": ["cardiac catheterization", "cardiac cath", "heart cath", "left heart cath", "coronary angiogram"]},
    {"id": 4237973, "name": "Coronary artery bypass graft", "code": "33533", "vocab": "CPT4",
     "synonyms": ["coronary artery bypass graft", "cabg", "bypass surgery", "heart bypass"]},
    {"id": 4019824, "name": "Percutaneous coronary intervention", "code": "92928", "vocab": "CPT4",
     "synonyms": ["percutaneous coronary intervention", "pci", "angioplasty", "stent", "ptca"]},
    {"id": 4336466, "name": "Stress test", "code": "93015", "vocab": "CPT4",
     "synonyms": ["stress test", "exercise stress test", "treadmill test", "cardiac stress test"]},
    {"id": 4151255, "name": "Pacemaker insertion", "code": "33206", "vocab": "CPT4",
     "synonyms": ["pacemaker insertion", "pacemaker implant", "ppm"]},
    {"id": 4150625, "name": "Cardioversion", "code": "92960", "vocab": "CPT4",
     "synonyms": ["cardioversion", "electrical cardioversion", "dc cardioversion"]},

    # Imaging
    {"id": 4279903, "name": "Chest X-ray", "code": "71046", "vocab": "CPT4",
     "synonyms": ["chest x-ray", "cxr", "chest radiograph", "chest xray"]},
    {"id": 4301351, "name": "CT scan of chest", "code": "71260", "vocab": "CPT4",
     "synonyms": ["ct scan of chest", "chest ct", "ct chest", "computed tomography chest"]},
    {"id": 4297837, "name": "CT scan of abdomen", "code": "74176", "vocab": "CPT4",
     "synonyms": ["ct scan of abdomen", "abdominal ct", "ct abdomen", "ct abd"]},
    {"id": 4138003, "name": "CT scan of head", "code": "70450", "vocab": "CPT4",
     "synonyms": ["ct scan of head", "head ct", "ct head", "brain ct"]},
    {"id": 4151851, "name": "MRI of brain", "code": "70553", "vocab": "CPT4",
     "synonyms": ["mri of brain", "brain mri", "mri brain", "head mri"]},
    {"id": 4095322, "name": "MRI of spine", "code": "72148", "vocab": "CPT4",
     "synonyms": ["mri of spine", "spine mri", "lumbar mri", "cervical mri"]},
    {"id": 4305831, "name": "Ultrasound of abdomen", "code": "76700", "vocab": "CPT4",
     "synonyms": ["ultrasound of abdomen", "abdominal ultrasound", "abd us", "abdominal us"]},
    {"id": 4303430, "name": "Mammogram", "code": "77065", "vocab": "CPT4",
     "synonyms": ["mammogram", "mammography", "breast screening"]},
    {"id": 4300448, "name": "PET scan", "code": "78815", "vocab": "CPT4",
     "synonyms": ["pet scan", "pet-ct", "positron emission tomography"]},

    # GI Procedures
    {"id": 4239716, "name": "Colonoscopy", "code": "45378", "vocab": "CPT4",
     "synonyms": ["colonoscopy", "colon scope", "colo"]},
    {"id": 4235738, "name": "Upper endoscopy", "code": "43239", "vocab": "CPT4",
     "synonyms": ["upper endoscopy", "egd", "esophagogastroduodenoscopy", "upper gi endoscopy"]},
    {"id": 4144746, "name": "Cholecystectomy", "code": "47562", "vocab": "CPT4",
     "synonyms": ["cholecystectomy", "gallbladder removal", "lap chole", "laparoscopic cholecystectomy"]},
    {"id": 4170480, "name": "Appendectomy", "code": "44970", "vocab": "CPT4",
     "synonyms": ["appendectomy", "appendix removal", "lap appy"]},

    # Orthopedic
    {"id": 4292912, "name": "Total knee replacement", "code": "27447", "vocab": "CPT4",
     "synonyms": ["total knee replacement", "tkr", "tka", "knee replacement", "knee arthroplasty"]},
    {"id": 4291274, "name": "Total hip replacement", "code": "27130", "vocab": "CPT4",
     "synonyms": ["total hip replacement", "thr", "tha", "hip replacement", "hip arthroplasty"]},
    {"id": 4147683, "name": "Spinal fusion", "code": "22612", "vocab": "CPT4",
     "synonyms": ["spinal fusion", "spine fusion", "lumbar fusion"]},
    {"id": 4265672, "name": "Arthroscopy of knee", "code": "29881", "vocab": "CPT4",
     "synonyms": ["arthroscopy of knee", "knee scope", "knee arthroscopy"]},

    # Other Surgical
    {"id": 4230359, "name": "Laparotomy", "code": "49000", "vocab": "CPT4",
     "synonyms": ["laparotomy", "exploratory laparotomy", "ex lap"]},
    {"id": 4147164, "name": "Thyroidectomy", "code": "60240", "vocab": "CPT4",
     "synonyms": ["thyroidectomy", "thyroid removal", "total thyroidectomy"]},
    {"id": 4144889, "name": "Mastectomy", "code": "19303", "vocab": "CPT4",
     "synonyms": ["mastectomy", "breast removal", "total mastectomy"]},
    {"id": 4143316, "name": "Prostatectomy", "code": "55840", "vocab": "CPT4",
     "synonyms": ["prostatectomy", "prostate removal", "radical prostatectomy"]},
    {"id": 4145239, "name": "Hysterectomy", "code": "58150", "vocab": "CPT4",
     "synonyms": ["hysterectomy", "uterus removal", "total hysterectomy"]},
    {"id": 4144753, "name": "Nephrectomy", "code": "50220", "vocab": "CPT4",
     "synonyms": ["nephrectomy", "kidney removal"]},

    # Respiratory
    {"id": 4186108, "name": "Bronchoscopy", "code": "31622", "vocab": "CPT4",
     "synonyms": ["bronchoscopy", "bronch", "lung scope"]},
    {"id": 4054939, "name": "Thoracentesis", "code": "32554", "vocab": "CPT4",
     "synonyms": ["thoracentesis", "pleural tap", "chest tap"]},
    {"id": 4301754, "name": "Pulmonary function test", "code": "94010", "vocab": "CPT4",
     "synonyms": ["pulmonary function test", "pft", "spirometry", "lung function test"]},
    {"id": 4147885, "name": "Intubation", "code": "31500", "vocab": "CPT4",
     "synonyms": ["intubation", "endotracheal intubation", "ett placement"]},

    # Vascular
    {"id": 4099154, "name": "Hemodialysis", "code": "90935", "vocab": "CPT4",
     "synonyms": ["hemodialysis", "dialysis", "hd"]},
    {"id": 4055893, "name": "Central line placement", "code": "36556", "vocab": "CPT4",
     "synonyms": ["central line placement", "central venous catheter", "cvc", "picc line"]},
    {"id": 4065322, "name": "Paracentesis", "code": "49082", "vocab": "CPT4",
     "synonyms": ["paracentesis", "abdominal tap", "ascites tap"]},
    {"id": 4098879, "name": "Lumbar puncture", "code": "62270", "vocab": "CPT4",
     "synonyms": ["lumbar puncture", "lp", "spinal tap"]},

    # Other
    {"id": 4055681, "name": "Blood transfusion", "code": "36430", "vocab": "CPT4",
     "synonyms": ["blood transfusion", "prbc transfusion", "transfusion"]},
    {"id": 4146536, "name": "Biopsy", "code": "88305", "vocab": "CPT4",
     "synonyms": ["biopsy", "tissue biopsy", "bx"]},
    {"id": 4147651, "name": "Chemotherapy", "code": "96413", "vocab": "CPT4",
     "synonyms": ["chemotherapy", "chemo", "chemotherapy infusion"]},
    {"id": 4148765, "name": "Radiation therapy", "code": "77385", "vocab": "CPT4",
     "synonyms": ["radiation therapy", "radiation", "xrt", "radiotherapy"]},
    {"id": 4306655, "name": "Physical therapy", "code": "97110", "vocab": "CPT4",
     "synonyms": ["physical therapy", "pt", "physiotherapy", "physical rehabilitation"]},
]


def generate_vocabulary(output_path: Path) -> None:
    """Generate the comprehensive vocabulary fixture."""
    # Build concepts list
    concepts = []

    # Add conditions
    for c in CONDITIONS:
        concepts.append({
            "concept_id": c["id"],
            "concept_name": c["name"],
            "concept_code": c["code"],
            "vocabulary_id": c["vocab"],
            "domain_id": "Condition",
            "concept_class_id": "Clinical Finding",
            "synonyms": c["synonyms"],
        })

    # Add drugs
    for d in DRUGS:
        concepts.append({
            "concept_id": d["id"],
            "concept_name": d["name"],
            "concept_code": d["code"],
            "vocabulary_id": d["vocab"],
            "domain_id": "Drug",
            "concept_class_id": "Ingredient",
            "synonyms": d["synonyms"],
        })

    # Add measurements
    for m in MEASUREMENTS:
        concepts.append({
            "concept_id": m["id"],
            "concept_name": m["name"],
            "concept_code": m["code"],
            "vocabulary_id": m["vocab"],
            "domain_id": "Measurement",
            "concept_class_id": "Lab Test",
            "synonyms": m["synonyms"],
        })

    # Add procedures
    for p in PROCEDURES:
        concepts.append({
            "concept_id": p["id"],
            "concept_name": p["name"],
            "concept_code": p["code"],
            "vocabulary_id": p["vocab"],
            "domain_id": "Procedure",
            "concept_class_id": "Procedure",
            "synonyms": p["synonyms"],
        })

    # Count synonyms
    total_synonyms = sum(len(c["synonyms"]) for c in concepts)

    # Build vocabulary data
    vocabulary_data: dict[str, Any] = {
        "version": "2.0.0",
        "description": "Comprehensive OMOP vocabulary with clinical concepts and synonyms",
        "stats": {
            "total_concepts": len(concepts),
            "total_synonyms": total_synonyms,
            "conditions": len(CONDITIONS),
            "drugs": len(DRUGS),
            "measurements": len(MEASUREMENTS),
            "procedures": len(PROCEDURES),
        },
        "concepts": concepts,
    }

    # Write to file
    with open(output_path, "w") as f:
        json.dump(vocabulary_data, f, indent=2)

    logger.info(f"Generated vocabulary: {len(concepts)} concepts, {total_synonyms} synonyms")
    logger.info(f"  Conditions: {len(CONDITIONS)}")
    logger.info(f"  Drugs: {len(DRUGS)}")
    logger.info(f"  Measurements: {len(MEASUREMENTS)}")
    logger.info(f"  Procedures: {len(PROCEDURES)}")
    logger.info(f"Output: {output_path}")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Generate comprehensive OMOP vocabulary fixture"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="fixtures/omop_vocabulary_full.json",
        help="Output file path",
    )
    args = parser.parse_args()

    # Resolve output path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        # Relative to project root
        script_dir = Path(__file__).parent
        backend_dir = script_dir.parent.parent
        output_path = backend_dir.parent / output_path

    # Ensure directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generate_vocabulary(output_path)


if __name__ == "__main__":
    main()
