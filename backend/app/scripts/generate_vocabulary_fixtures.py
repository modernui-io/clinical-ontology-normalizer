"""Generate vocabulary fixtures from Athena CSV files.

This script processes the OMOP vocabulary CSV files from Athena and generates
JSON fixtures that can be used without a database.

Usage:
    python -m app.scripts.generate_vocabulary_fixtures --path /Users/alexstinard/Downloads/vocab

Output:
    - backend/fixtures/icd10_codes.json (ICD-10 codes for conditions)
    - backend/fixtures/cpt_codes.json (CPT codes for procedures)
    - backend/fixtures/snomed_concepts.json (SNOMED clinical findings)
    - backend/fixtures/rxnorm_drugs.json (RxNorm drug concepts)
    - backend/fixtures/loinc_measurements.json (LOINC lab codes)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fixture output directory
FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures"

# Vocabulary mappings
VOCAB_CONFIG = {
    "ICD10CM": {
        "output_file": "icd10_codes.json",
        "domain_filter": ["Condition"],
        "max_records": 10000,
        "include_synonyms": True,
    },
    "CPT4": {
        "output_file": "cpt_codes.json",
        "domain_filter": ["Procedure", "Measurement"],
        "max_records": 5000,
        "include_synonyms": True,
    },
    "SNOMED": {
        "output_file": "snomed_concepts.json",
        "domain_filter": ["Condition", "Procedure", "Observation"],
        "max_records": 50000,
        "include_synonyms": True,
    },
    "RxNorm": {
        "output_file": "rxnorm_drugs.json",
        "domain_filter": ["Drug"],
        "max_records": 20000,
        "include_synonyms": True,
    },
    "LOINC": {
        "output_file": "loinc_measurements.json",
        "domain_filter": ["Measurement", "Observation"],
        "max_records": 10000,
        "include_synonyms": True,
    },
}


def load_synonyms(synonym_file: Path) -> dict[int, list[str]]:
    """Load concept synonyms into a dictionary."""
    logger.info(f"Loading synonyms from {synonym_file}")
    synonyms = defaultdict(list)

    with open(synonym_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            concept_id = int(row["concept_id"])
            synonym = row["concept_synonym_name"].strip()
            if synonym and len(synonym) < 500:
                synonyms[concept_id].append(synonym)

    logger.info(f"Loaded synonyms for {len(synonyms):,} concepts")
    return dict(synonyms)


def process_concepts(
    concept_file: Path,
    vocabulary_id: str,
    config: dict,
    synonyms: dict[int, list[str]] | None = None,
) -> list[dict]:
    """Process concepts for a specific vocabulary."""
    logger.info(f"Processing {vocabulary_id} concepts...")

    domain_filter = set(config["domain_filter"])
    max_records = config["max_records"]
    include_synonyms = config.get("include_synonyms", False)

    concepts = []

    with open(concept_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            # Filter by vocabulary
            if row["vocabulary_id"] != vocabulary_id:
                continue

            # Filter by domain
            if row["domain_id"] not in domain_filter:
                continue

            # Only include standard/classification concepts
            standard = row.get("standard_concept", "")
            if standard not in ("S", "C", ""):
                continue

            concept_id = int(row["concept_id"])
            concept = {
                "concept_id": concept_id,
                "concept_code": row.get("concept_code", ""),
                "concept_name": row["concept_name"][:500],
                "domain_id": row["domain_id"],
                "vocabulary_id": vocabulary_id,
                "concept_class_id": row["concept_class_id"],
                "standard_concept": standard if standard else None,
            }

            # Add synonyms if available
            if include_synonyms and synonyms and concept_id in synonyms:
                concept["synonyms"] = synonyms[concept_id][:10]  # Limit to 10 synonyms

            concepts.append(concept)

            if len(concepts) >= max_records:
                break

    logger.info(f"Processed {len(concepts):,} {vocabulary_id} concepts")
    return concepts


def generate_combined_vocabulary(
    concept_file: Path,
    synonyms: dict[int, list[str]] | None = None,
) -> dict:
    """Generate a combined vocabulary file with key concepts from all sources."""
    logger.info("Generating combined vocabulary...")

    combined = {
        "conditions": [],
        "procedures": [],
        "drugs": [],
        "measurements": [],
        "observations": [],
    }

    # Track concept counts by vocabulary and domain
    counts = defaultdict(lambda: defaultdict(int))

    # Target counts per category
    targets = {
        "conditions": 15000,
        "procedures": 5000,
        "drugs": 15000,
        "measurements": 8000,
        "observations": 2000,
    }

    # Priority vocabularies for each domain
    priority = {
        "Condition": ["ICD10CM", "SNOMED"],
        "Procedure": ["CPT4", "SNOMED", "HCPCS"],
        "Drug": ["RxNorm", "RxNorm Extension"],
        "Measurement": ["LOINC", "SNOMED"],
        "Observation": ["LOINC", "SNOMED"],
    }

    with open(concept_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            vocab = row["vocabulary_id"]
            domain = row["domain_id"]

            # Map domain to category
            if domain == "Condition":
                category = "conditions"
            elif domain == "Procedure":
                category = "procedures"
            elif domain == "Drug":
                category = "drugs"
            elif domain == "Measurement":
                category = "measurements"
            elif domain == "Observation":
                category = "observations"
            else:
                continue

            # Check if we need more of this category
            if len(combined[category]) >= targets[category]:
                continue

            # Prefer priority vocabularies
            if vocab not in priority.get(domain, []):
                # Still include some non-priority vocabs
                if counts[category][vocab] > 1000:
                    continue

            # Only include standard concepts
            standard = row.get("standard_concept", "")
            if standard not in ("S", "C", ""):
                continue

            concept_id = int(row["concept_id"])
            concept = {
                "concept_id": concept_id,
                "concept_code": row.get("concept_code", ""),
                "concept_name": row["concept_name"][:500],
                "domain_id": domain,
                "vocabulary_id": vocab,
                "concept_class_id": row["concept_class_id"],
                "standard_concept": standard if standard else None,
            }

            # Add synonyms
            if synonyms and concept_id in synonyms:
                concept["synonyms"] = synonyms[concept_id][:5]

            combined[category].append(concept)
            counts[category][vocab] += 1

    # Log summary
    for category, concepts in combined.items():
        logger.info(f"  {category}: {len(concepts):,} concepts")
        for vocab, count in counts[category].items():
            logger.info(f"    - {vocab}: {count:,}")

    return combined


def generate_drug_interactions_from_rxnorm(concept_file: Path) -> list[dict]:
    """Generate expanded drug interactions based on RxNorm drug classes."""
    logger.info("Generating drug interactions...")

    # Common drug classes and their interactions
    drug_class_interactions = {
        "Anticoagulant": {
            "interacts_with": ["NSAID", "Antiplatelet", "SSRI", "Fibrinolytic"],
            "severity": "high",
            "effect": "Increased bleeding risk",
        },
        "NSAID": {
            "interacts_with": ["Anticoagulant", "ACE Inhibitor", "Diuretic", "Lithium"],
            "severity": "moderate",
            "effect": "Reduced efficacy or increased toxicity",
        },
        "ACE Inhibitor": {
            "interacts_with": ["Potassium-sparing Diuretic", "ARB", "NSAID", "Lithium"],
            "severity": "moderate",
            "effect": "Hyperkalemia or reduced efficacy",
        },
        "Beta Blocker": {
            "interacts_with": ["Calcium Channel Blocker", "Clonidine", "Insulin"],
            "severity": "moderate",
            "effect": "Bradycardia or masked hypoglycemia",
        },
        "Statin": {
            "interacts_with": ["Fibrate", "Macrolide", "Azole Antifungal", "Grapefruit"],
            "severity": "moderate",
            "effect": "Increased myopathy risk",
        },
        "SSRI": {
            "interacts_with": ["MAOI", "Triptan", "Tramadol", "Anticoagulant"],
            "severity": "high",
            "effect": "Serotonin syndrome or bleeding risk",
        },
        "Opioid": {
            "interacts_with": ["Benzodiazepine", "CNS Depressant", "MAOI", "Muscle Relaxant"],
            "severity": "high",
            "effect": "Respiratory depression",
        },
        "Fluoroquinolone": {
            "interacts_with": ["NSAID", "Theophylline", "Antacid", "Warfarin"],
            "severity": "moderate",
            "effect": "Seizure risk or altered drug levels",
        },
        "Metformin": {
            "interacts_with": ["Contrast Dye", "Alcohol", "Carbonic Anhydrase Inhibitor"],
            "severity": "high",
            "effect": "Lactic acidosis risk",
        },
        "Digoxin": {
            "interacts_with": ["Amiodarone", "Verapamil", "Diuretic", "Quinidine"],
            "severity": "high",
            "effect": "Digoxin toxicity",
        },
    }

    # Common drugs in each class (for mapping)
    drug_class_members = {
        "Anticoagulant": ["warfarin", "heparin", "enoxaparin", "rivaroxaban", "apixaban", "dabigatran", "edoxaban"],
        "NSAID": ["ibuprofen", "naproxen", "aspirin", "celecoxib", "meloxicam", "diclofenac", "ketorolac", "indomethacin"],
        "ACE Inhibitor": ["lisinopril", "enalapril", "ramipril", "benazepril", "captopril", "quinapril", "fosinopril"],
        "ARB": ["losartan", "valsartan", "olmesartan", "irbesartan", "candesartan", "telmisartan"],
        "Beta Blocker": ["metoprolol", "atenolol", "carvedilol", "propranolol", "bisoprolol", "labetalol", "nebivolol"],
        "Calcium Channel Blocker": ["amlodipine", "diltiazem", "verapamil", "nifedipine", "felodipine"],
        "Statin": ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin", "lovastatin", "fluvastatin"],
        "SSRI": ["sertraline", "fluoxetine", "paroxetine", "citalopram", "escitalopram", "fluvoxamine"],
        "Opioid": ["morphine", "oxycodone", "hydrocodone", "fentanyl", "tramadol", "codeine", "hydromorphone", "methadone"],
        "Benzodiazepine": ["lorazepam", "diazepam", "alprazolam", "clonazepam", "midazolam", "temazepam"],
        "Fluoroquinolone": ["ciprofloxacin", "levofloxacin", "moxifloxacin", "ofloxacin"],
        "Diuretic": ["furosemide", "hydrochlorothiazide", "spironolactone", "bumetanide", "torsemide", "chlorthalidone"],
        "Potassium-sparing Diuretic": ["spironolactone", "eplerenone", "amiloride", "triamterene"],
        "Antiplatelet": ["clopidogrel", "ticagrelor", "prasugrel", "aspirin", "dipyridamole"],
        "Macrolide": ["azithromycin", "clarithromycin", "erythromycin"],
        "Azole Antifungal": ["fluconazole", "itraconazole", "ketoconazole", "voriconazole", "posaconazole"],
        "MAOI": ["phenelzine", "tranylcypromine", "selegiline", "isocarboxazid"],
        "Triptan": ["sumatriptan", "rizatriptan", "zolmitriptan", "eletriptan", "almotriptan"],
        "CNS Depressant": ["alcohol", "barbiturate", "sedative", "antihistamine"],
        "Fibrinolytic": ["alteplase", "tenecteplase", "reteplase", "streptokinase"],
        "Fibrate": ["gemfibrozil", "fenofibrate", "bezafibrate"],
    }

    interactions = []
    interaction_id = 1

    # Generate pairwise interactions
    for drug_class, info in drug_class_interactions.items():
        drugs = drug_class_members.get(drug_class, [])

        for interacting_class in info["interacts_with"]:
            interacting_drugs = drug_class_members.get(interacting_class, [interacting_class.lower()])

            # Generate specific drug-drug interactions
            for drug1 in drugs[:5]:  # Limit to top 5 per class
                for drug2 in interacting_drugs[:5]:
                    if drug1 != drug2:
                        interactions.append({
                            "id": interaction_id,
                            "drug1": drug1,
                            "drug1_class": drug_class,
                            "drug2": drug2,
                            "drug2_class": interacting_class,
                            "severity": info["severity"],
                            "effect": info["effect"],
                            "mechanism": f"{drug_class} + {interacting_class} interaction",
                            "recommendation": f"Monitor closely when combining {drug_class.lower()} with {interacting_class.lower()}",
                        })
                        interaction_id += 1

    logger.info(f"Generated {len(interactions):,} drug interactions")
    return interactions


def generate_drug_safety_profiles() -> list[dict]:
    """Generate comprehensive drug safety profiles with contraindications."""
    logger.info("Generating drug safety profiles...")

    safety_profiles = [
        # Cardiovascular drugs
        {
            "drug_name": "warfarin",
            "drug_class": "Anticoagulant",
            "black_box_warning": True,
            "black_box_text": "Can cause major or fatal bleeding. Regular INR monitoring required.",
            "contraindications": ["active bleeding", "hemorrhagic stroke", "severe hypertension", "pregnancy"],
            "pregnancy_category": "X",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["INR", "signs of bleeding", "hemoglobin"],
        },
        {
            "drug_name": "metoprolol",
            "drug_class": "Beta Blocker",
            "black_box_warning": True,
            "black_box_text": "Do not discontinue abruptly - risk of exacerbation of angina and MI.",
            "contraindications": ["sinus bradycardia", "heart block > first degree", "cardiogenic shock", "decompensated heart failure"],
            "pregnancy_category": "C",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["heart rate", "blood pressure", "ECG"],
        },
        {
            "drug_name": "lisinopril",
            "drug_class": "ACE Inhibitor",
            "black_box_warning": True,
            "black_box_text": "Can cause fetal injury/death when used during pregnancy.",
            "contraindications": ["pregnancy", "angioedema history", "bilateral renal artery stenosis"],
            "pregnancy_category": "D",
            "renal_adjustment": True,
            "hepatic_adjustment": False,
            "monitoring_required": ["potassium", "creatinine", "blood pressure"],
        },
        {
            "drug_name": "amlodipine",
            "drug_class": "Calcium Channel Blocker",
            "black_box_warning": False,
            "contraindications": ["severe aortic stenosis", "cardiogenic shock"],
            "pregnancy_category": "C",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["blood pressure", "heart rate", "edema"],
        },
        {
            "drug_name": "atorvastatin",
            "drug_class": "Statin",
            "black_box_warning": False,
            "contraindications": ["active liver disease", "pregnancy", "breastfeeding"],
            "pregnancy_category": "X",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["LFTs", "lipid panel", "CK if symptomatic"],
        },
        {
            "drug_name": "digoxin",
            "drug_class": "Cardiac Glycoside",
            "black_box_warning": False,
            "contraindications": ["ventricular fibrillation", "hypertrophic cardiomyopathy with outflow obstruction"],
            "pregnancy_category": "C",
            "renal_adjustment": True,
            "hepatic_adjustment": False,
            "monitoring_required": ["digoxin level", "potassium", "creatinine", "heart rate"],
        },
        # Diabetes medications
        {
            "drug_name": "metformin",
            "drug_class": "Biguanide",
            "black_box_warning": True,
            "black_box_text": "Lactic acidosis risk, especially with renal impairment, hepatic impairment, or iodinated contrast.",
            "contraindications": ["eGFR < 30", "metabolic acidosis", "acute heart failure"],
            "pregnancy_category": "B",
            "renal_adjustment": True,
            "hepatic_adjustment": True,
            "monitoring_required": ["creatinine", "eGFR", "B12 levels annually"],
        },
        {
            "drug_name": "insulin",
            "drug_class": "Insulin",
            "black_box_warning": False,
            "contraindications": ["hypoglycemia"],
            "pregnancy_category": "B",
            "renal_adjustment": True,
            "hepatic_adjustment": True,
            "monitoring_required": ["blood glucose", "HbA1c", "hypoglycemia signs"],
        },
        {
            "drug_name": "glipizide",
            "drug_class": "Sulfonylurea",
            "black_box_warning": False,
            "contraindications": ["DKA", "type 1 diabetes", "severe renal impairment"],
            "pregnancy_category": "C",
            "renal_adjustment": True,
            "hepatic_adjustment": True,
            "monitoring_required": ["blood glucose", "HbA1c", "hypoglycemia"],
        },
        {
            "drug_name": "empagliflozin",
            "drug_class": "SGLT2 Inhibitor",
            "black_box_warning": False,
            "contraindications": ["severe renal impairment", "dialysis", "DKA"],
            "pregnancy_category": "C",
            "renal_adjustment": True,
            "hepatic_adjustment": False,
            "monitoring_required": ["eGFR", "blood glucose", "ketones", "UTI symptoms"],
        },
        # Pain medications
        {
            "drug_name": "oxycodone",
            "drug_class": "Opioid",
            "black_box_warning": True,
            "black_box_text": "Risk of addiction, abuse, and misuse. Life-threatening respiratory depression. Neonatal opioid withdrawal syndrome.",
            "contraindications": ["respiratory depression", "acute/severe asthma", "GI obstruction", "MAOIs within 14 days"],
            "pregnancy_category": "C",
            "renal_adjustment": True,
            "hepatic_adjustment": True,
            "monitoring_required": ["pain level", "respiratory rate", "sedation", "bowel function"],
        },
        {
            "drug_name": "morphine",
            "drug_class": "Opioid",
            "black_box_warning": True,
            "black_box_text": "Risk of addiction, abuse, and misuse. Life-threatening respiratory depression.",
            "contraindications": ["respiratory depression", "acute/severe asthma", "GI obstruction"],
            "pregnancy_category": "C",
            "renal_adjustment": True,
            "hepatic_adjustment": True,
            "monitoring_required": ["pain level", "respiratory rate", "sedation"],
        },
        {
            "drug_name": "tramadol",
            "drug_class": "Opioid",
            "black_box_warning": True,
            "black_box_text": "Risk of addiction. Respiratory depression. Serotonin syndrome with SSRIs/SNRIs. Seizure risk.",
            "contraindications": ["seizure disorder", "MAOIs", "severe respiratory depression"],
            "pregnancy_category": "C",
            "renal_adjustment": True,
            "hepatic_adjustment": True,
            "monitoring_required": ["pain level", "seizure risk", "serotonin syndrome signs"],
        },
        {
            "drug_name": "ibuprofen",
            "drug_class": "NSAID",
            "black_box_warning": True,
            "black_box_text": "Increased risk of serious cardiovascular thrombotic events, MI, and stroke. GI bleeding, ulceration, perforation risk.",
            "contraindications": ["aspirin-sensitive asthma", "CABG surgery", "active GI bleeding", "severe renal impairment"],
            "pregnancy_category": "C/D",
            "renal_adjustment": True,
            "hepatic_adjustment": True,
            "monitoring_required": ["renal function", "GI symptoms", "blood pressure"],
        },
        # Psychiatric medications
        {
            "drug_name": "sertraline",
            "drug_class": "SSRI",
            "black_box_warning": True,
            "black_box_text": "Suicidality risk in children, adolescents, and young adults.",
            "contraindications": ["MAOIs within 14 days", "pimozide use", "concurrent linezolid/IV methylene blue"],
            "pregnancy_category": "C",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["suicidal ideation", "serotonin syndrome", "bleeding"],
        },
        {
            "drug_name": "fluoxetine",
            "drug_class": "SSRI",
            "black_box_warning": True,
            "black_box_text": "Suicidality risk in children, adolescents, and young adults.",
            "contraindications": ["MAOIs within 14 days", "thioridazine use", "pimozide use"],
            "pregnancy_category": "C",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["suicidal ideation", "serotonin syndrome", "weight"],
        },
        {
            "drug_name": "quetiapine",
            "drug_class": "Atypical Antipsychotic",
            "black_box_warning": True,
            "black_box_text": "Increased mortality in elderly dementia patients. Suicidality in young adults.",
            "contraindications": ["dementia-related psychosis in elderly"],
            "pregnancy_category": "C",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["metabolic parameters", "tardive dyskinesia", "suicidal ideation", "orthostatic hypotension"],
        },
        {
            "drug_name": "lithium",
            "drug_class": "Mood Stabilizer",
            "black_box_warning": True,
            "black_box_text": "Lithium toxicity can occur at doses close to therapeutic levels. Serum lithium monitoring required.",
            "contraindications": ["severe renal impairment", "severe cardiovascular disease", "dehydration"],
            "pregnancy_category": "D",
            "renal_adjustment": True,
            "hepatic_adjustment": False,
            "monitoring_required": ["lithium level", "renal function", "thyroid function", "ECG"],
        },
        {
            "drug_name": "alprazolam",
            "drug_class": "Benzodiazepine",
            "black_box_warning": True,
            "black_box_text": "Concomitant use with opioids may result in profound sedation, respiratory depression, and death.",
            "contraindications": ["acute narrow-angle glaucoma", "concurrent ketoconazole/itraconazole"],
            "pregnancy_category": "D",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["respiratory rate", "sedation", "dependence", "fall risk"],
        },
        # Antibiotics
        {
            "drug_name": "ciprofloxacin",
            "drug_class": "Fluoroquinolone",
            "black_box_warning": True,
            "black_box_text": "Risk of tendinitis, tendon rupture, peripheral neuropathy, CNS effects, and myasthenia gravis exacerbation.",
            "contraindications": ["myasthenia gravis", "concurrent tizanidine"],
            "pregnancy_category": "C",
            "renal_adjustment": True,
            "hepatic_adjustment": False,
            "monitoring_required": ["tendon pain", "neurological symptoms", "QT interval"],
        },
        {
            "drug_name": "amoxicillin",
            "drug_class": "Penicillin",
            "black_box_warning": False,
            "contraindications": ["penicillin allergy", "infectious mononucleosis"],
            "pregnancy_category": "B",
            "renal_adjustment": True,
            "hepatic_adjustment": False,
            "monitoring_required": ["allergic reaction", "C. diff symptoms", "rash"],
        },
        {
            "drug_name": "vancomycin",
            "drug_class": "Glycopeptide",
            "black_box_warning": False,
            "contraindications": ["known hypersensitivity"],
            "pregnancy_category": "C",
            "renal_adjustment": True,
            "hepatic_adjustment": False,
            "monitoring_required": ["vancomycin trough", "creatinine", "audiometry", "red man syndrome"],
        },
        {
            "drug_name": "azithromycin",
            "drug_class": "Macrolide",
            "black_box_warning": False,
            "contraindications": ["history of cholestatic jaundice with prior azithromycin", "QT prolongation"],
            "pregnancy_category": "B",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["QT interval", "LFTs", "hearing"],
        },
        # GI medications
        {
            "drug_name": "omeprazole",
            "drug_class": "PPI",
            "black_box_warning": False,
            "contraindications": ["rilpivirine use"],
            "pregnancy_category": "C",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["magnesium", "B12", "bone density with long-term use"],
        },
        {
            "drug_name": "ondansetron",
            "drug_class": "5-HT3 Antagonist",
            "black_box_warning": False,
            "contraindications": ["congenital long QT syndrome", "concurrent apomorphine"],
            "pregnancy_category": "B",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["QT interval", "electrolytes"],
        },
        # Respiratory
        {
            "drug_name": "albuterol",
            "drug_class": "Beta-2 Agonist",
            "black_box_warning": False,
            "contraindications": ["hypersensitivity to albuterol"],
            "pregnancy_category": "C",
            "renal_adjustment": False,
            "hepatic_adjustment": False,
            "monitoring_required": ["heart rate", "potassium", "blood pressure"],
        },
        {
            "drug_name": "prednisone",
            "drug_class": "Corticosteroid",
            "black_box_warning": False,
            "contraindications": ["systemic fungal infections", "live vaccines"],
            "pregnancy_category": "C",
            "renal_adjustment": False,
            "hepatic_adjustment": False,
            "monitoring_required": ["blood glucose", "blood pressure", "bone density", "adrenal function"],
        },
        # Anticoagulants
        {
            "drug_name": "rivaroxaban",
            "drug_class": "Factor Xa Inhibitor",
            "black_box_warning": True,
            "black_box_text": "Premature discontinuation increases thrombosis risk. Spinal/epidural hematoma risk with neuraxial anesthesia.",
            "contraindications": ["active pathological bleeding", "severe renal impairment with A-fib indication"],
            "pregnancy_category": "C",
            "renal_adjustment": True,
            "hepatic_adjustment": True,
            "monitoring_required": ["renal function", "signs of bleeding", "hemoglobin"],
        },
        {
            "drug_name": "apixaban",
            "drug_class": "Factor Xa Inhibitor",
            "black_box_warning": True,
            "black_box_text": "Premature discontinuation increases thrombosis risk. Spinal/epidural hematoma risk.",
            "contraindications": ["active pathological bleeding", "severe hepatic impairment"],
            "pregnancy_category": "B",
            "renal_adjustment": True,
            "hepatic_adjustment": True,
            "monitoring_required": ["renal function", "hepatic function", "signs of bleeding"],
        },
        {
            "drug_name": "enoxaparin",
            "drug_class": "LMWH",
            "black_box_warning": True,
            "black_box_text": "Spinal/epidural hematomas can occur with neuraxial anesthesia or spinal puncture.",
            "contraindications": ["active major bleeding", "thrombocytopenia with positive test for antiplatelet antibody"],
            "pregnancy_category": "B",
            "renal_adjustment": True,
            "hepatic_adjustment": False,
            "monitoring_required": ["anti-Xa levels in renal impairment", "platelet count", "signs of bleeding"],
        },
        # More cardiovascular
        {
            "drug_name": "losartan",
            "drug_class": "ARB",
            "black_box_warning": True,
            "black_box_text": "Can cause fetal injury/death when used during pregnancy.",
            "contraindications": ["pregnancy", "concurrent aliskiren in diabetes"],
            "pregnancy_category": "D",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["potassium", "creatinine", "blood pressure"],
        },
        {
            "drug_name": "furosemide",
            "drug_class": "Loop Diuretic",
            "black_box_warning": True,
            "black_box_text": "Can lead to profound diuresis with water and electrolyte depletion if given in excess.",
            "contraindications": ["anuria", "severe electrolyte depletion"],
            "pregnancy_category": "C",
            "renal_adjustment": True,
            "hepatic_adjustment": False,
            "monitoring_required": ["electrolytes", "renal function", "blood pressure", "hearing"],
        },
        {
            "drug_name": "spironolactone",
            "drug_class": "Potassium-sparing Diuretic",
            "black_box_warning": True,
            "black_box_text": "Shown to be tumorigenic in chronic rat toxicity studies.",
            "contraindications": ["anuria", "acute renal insufficiency", "hyperkalemia", "Addison's disease"],
            "pregnancy_category": "C",
            "renal_adjustment": True,
            "hepatic_adjustment": False,
            "monitoring_required": ["potassium", "creatinine", "blood pressure"],
        },
        {
            "drug_name": "amiodarone",
            "drug_class": "Antiarrhythmic",
            "black_box_warning": True,
            "black_box_text": "Pulmonary toxicity, hepatotoxicity, and proarrhythmia can occur.",
            "contraindications": ["cardiogenic shock", "sick sinus syndrome", "second/third degree AV block without pacemaker"],
            "pregnancy_category": "D",
            "renal_adjustment": False,
            "hepatic_adjustment": True,
            "monitoring_required": ["thyroid function", "LFTs", "pulmonary function", "ECG", "ophthalmologic exam"],
        },
    ]

    logger.info(f"Generated {len(safety_profiles)} drug safety profiles")
    return safety_profiles


def main():
    parser = argparse.ArgumentParser(description="Generate vocabulary fixtures from Athena CSV files")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("/Users/alexstinard/Downloads/vocab"),
        help="Path to Athena vocabulary directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=FIXTURE_DIR,
        help="Output directory for fixtures",
    )

    args = parser.parse_args()
    vocab_path = args.path
    output_dir = args.output

    output_dir.mkdir(parents=True, exist_ok=True)

    concept_file = vocab_path / "CONCEPT.csv"
    synonym_file = vocab_path / "CONCEPT_SYNONYM.csv"

    if not concept_file.exists():
        logger.error(f"CONCEPT.csv not found in {vocab_path}")
        return

    # Load synonyms
    synonyms = None
    if synonym_file.exists():
        synonyms = load_synonyms(synonym_file)

    # Process each vocabulary
    for vocab_id, config in VOCAB_CONFIG.items():
        concepts = process_concepts(concept_file, vocab_id, config, synonyms)

        output_file = output_dir / config["output_file"]
        with open(output_file, "w") as f:
            json.dump({"concepts": concepts, "vocabulary_id": vocab_id}, f, indent=2)

        logger.info(f"Wrote {len(concepts):,} {vocab_id} concepts to {output_file}")

    # Generate combined vocabulary
    combined = generate_combined_vocabulary(concept_file, synonyms)
    combined_file = output_dir / "omop_vocabulary_comprehensive.json"
    with open(combined_file, "w") as f:
        json.dump(combined, f, indent=2)

    total = sum(len(v) for v in combined.values())
    logger.info(f"Wrote {total:,} total concepts to {combined_file}")

    # Generate drug interactions
    interactions = generate_drug_interactions_from_rxnorm(concept_file)
    interactions_file = output_dir / "drug_interactions_expanded.json"
    with open(interactions_file, "w") as f:
        json.dump({"interactions": interactions}, f, indent=2)
    logger.info(f"Wrote {len(interactions):,} drug interactions to {interactions_file}")

    # Generate drug safety profiles
    safety_profiles = generate_drug_safety_profiles()
    safety_file = output_dir / "drug_safety_profiles_expanded.json"
    with open(safety_file, "w") as f:
        json.dump({"profiles": safety_profiles}, f, indent=2)
    logger.info(f"Wrote {len(safety_profiles)} drug safety profiles to {safety_file}")

    logger.info("Fixture generation complete!")


if __name__ == "__main__":
    main()
