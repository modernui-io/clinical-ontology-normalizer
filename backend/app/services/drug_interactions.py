"""Drug Interaction Database Service.

Provides drug-drug interaction checking using a curated database of
known interactions based on FDA and clinical guidelines.

This service integrates with RxNormService for enhanced drug name
normalization and ingredient extraction.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, TYPE_CHECKING

from app.services.graph_database_service import GraphDatabaseService, get_graph_database_service

if TYPE_CHECKING:
    from app.services.rxnorm_service import RxNormService

logger = logging.getLogger(__name__)

FIXTURE_FILE = Path(__file__).parent.parent.parent / "fixtures" / "drug_interactions_expanded.json"


class InteractionSeverity(str, Enum):
    """Severity levels for drug interactions."""

    CONTRAINDICATED = "contraindicated"  # Should never be combined
    MAJOR = "major"  # Serious, avoid combination
    MODERATE = "moderate"  # Use with caution
    MINOR = "minor"  # Usually not significant


class InteractionType(str, Enum):
    """Types of drug interactions."""

    PHARMACOKINETIC = "pharmacokinetic"  # Affects absorption/metabolism/excretion
    PHARMACODYNAMIC = "pharmacodynamic"  # Affects mechanism of action
    DUPLICATE_THERAPY = "duplicate_therapy"  # Same drug class
    QT_PROLONGATION = "qt_prolongation"  # Risk of cardiac arrhythmia
    SEROTONIN_SYNDROME = "serotonin_syndrome"  # Risk of serotonin toxicity
    BLEEDING_RISK = "bleeding_risk"  # Increased bleeding risk
    HYPOTENSION = "hypotension"  # Additive blood pressure lowering
    HYPERKALEMIA = "hyperkalemia"  # Risk of high potassium
    HYPOGLYCEMIA = "hypoglycemia"  # Risk of low blood sugar
    NEPHROTOXICITY = "nephrotoxicity"  # Kidney damage risk
    HEPATOTOXICITY = "hepatotoxicity"  # Liver damage risk


# ============================================================================
# Neo4j Cypher Query Constants
# ============================================================================

# Direct interaction lookup between two drugs
DIRECT_INTERACTION_QUERY = """
MATCH (d1:Drug {name: $drug1})-[r:INTERACTS_WITH|CONTRAINDICATED_WITH]-(d2:Drug {name: $drug2})
RETURN type(r) AS rel_type,
       r.severity AS severity,
       r.interaction_type AS interaction_type,
       r.description AS description,
       r.clinical_effect AS clinical_effect,
       r.management AS management,
       r.references AS references
LIMIT 1
"""

# Concept-based interaction lookup (using OMOP concept IDs)
CONCEPT_INTERACTION_QUERY = """
MATCH (c1:Concept {concept_id: $concept_id_1})-[r:INTERACTS_WITH|CONTRAINDICATED_WITH]-(c2:Concept {concept_id: $concept_id_2})
RETURN type(r) AS rel_type,
       r.severity AS severity,
       r.interaction_type AS interaction_type,
       r.description AS description,
       r.clinical_effect AS clinical_effect,
       r.management AS management,
       r.references AS references
LIMIT 1
"""

# Pathway-based interaction inference via shared metabolic enzymes (CYP450)
# Finds drugs that interact via a common CYP enzyme pathway
PATHWAY_INTERACTION_QUERY = """
MATCH (d1:Drug {name: $drug1})-[:METABOLIZED_BY]->(enzyme:Enzyme)<-[:INHIBITS|INDUCES]-(d2:Drug {name: $drug2})
WHERE enzyme.type = 'CYP450'
RETURN d1.name AS drug1,
       d2.name AS drug2,
       enzyme.name AS enzyme,
       CASE
           WHEN (d2)-[:INHIBITS]->(enzyme) THEN 'inhibitor'
           ELSE 'inducer'
       END AS effect,
       'pharmacokinetic' AS interaction_type,
       'moderate' AS severity,
       'CYP-mediated pathway interaction: ' + d2.name + ' affects metabolism of ' + d1.name + ' via ' + enzyme.name AS description
LIMIT 5
"""

# QT prolongation risk query - finds drugs with additive QT-prolonging effects
QT_PROLONGATION_QUERY = """
MATCH (d1:Drug {name: $drug1})-[:HAS_EFFECT]->(qt1:Effect {type: 'qt_prolongation'})
MATCH (d2:Drug {name: $drug2})-[:HAS_EFFECT]->(qt2:Effect {type: 'qt_prolongation'})
WHERE d1 <> d2
RETURN d1.name AS drug1,
       d2.name AS drug2,
       qt1.risk_level AS drug1_qt_risk,
       qt2.risk_level AS drug2_qt_risk,
       CASE
           WHEN qt1.risk_level = 'known' AND qt2.risk_level = 'known' THEN 'major'
           WHEN qt1.risk_level = 'known' OR qt2.risk_level = 'known' THEN 'moderate'
           ELSE 'minor'
       END AS combined_severity,
       'Both drugs prolong QT interval; additive risk of torsades de pointes' AS clinical_effect
"""

# Find all QT-prolonging drugs in a medication list
QT_DRUGS_IN_LIST_QUERY = """
MATCH (d:Drug)-[:HAS_EFFECT]->(e:Effect {type: 'qt_prolongation'})
WHERE d.name IN $drug_names
RETURN d.name AS drug_name,
       e.risk_level AS risk_level,
       e.mechanism AS mechanism
ORDER BY
    CASE e.risk_level
        WHEN 'known' THEN 1
        WHEN 'possible' THEN 2
        WHEN 'conditional' THEN 3
        ELSE 4
    END
"""


@dataclass
class DrugInteraction:
    """A drug-drug interaction record."""

    drug1: str  # First drug (lowercase normalized)
    drug2: str  # Second drug (lowercase normalized)
    severity: InteractionSeverity
    interaction_type: InteractionType
    description: str
    clinical_effect: str
    management: str
    references: list[str] = field(default_factory=list)

    def __hash__(self) -> int:
        # Order-independent hash
        drugs = tuple(sorted([self.drug1, self.drug2]))
        return hash((drugs, self.severity, self.interaction_type))


@dataclass
class InteractionCheckResult:
    """Result of checking for drug interactions."""

    drugs_checked: list[str]
    interactions_found: list[DrugInteraction]
    total_interactions: int
    by_severity: dict[str, int]
    highest_severity: InteractionSeverity | None
    has_contraindicated: bool
    has_major: bool


# ============================================================================
# Drug Interaction Database
# ============================================================================

# Curated drug interactions based on FDA labels and clinical guidelines
DRUG_INTERACTIONS: list[DrugInteraction] = [
    # ==========================================================================
    # CONTRAINDICATED COMBINATIONS
    # ==========================================================================
    DrugInteraction(
        drug1="methotrexate",
        drug2="trimethoprim",
        severity=InteractionSeverity.CONTRAINDICATED,
        interaction_type=InteractionType.PHARMACOKINETIC,
        description="Trimethoprim inhibits renal excretion of methotrexate",
        clinical_effect="Increased methotrexate levels, severe myelosuppression",
        management="Avoid combination; if unavoidable, monitor closely and reduce methotrexate dose",
        references=["FDA methotrexate label"],
    ),
    DrugInteraction(
        drug1="simvastatin",
        drug2="itraconazole",
        severity=InteractionSeverity.CONTRAINDICATED,
        interaction_type=InteractionType.PHARMACOKINETIC,
        description="Itraconazole strongly inhibits CYP3A4, markedly increasing simvastatin levels",
        clinical_effect="Rhabdomyolysis, myopathy, acute kidney injury",
        management="Contraindicated; use alternative statin (pravastatin, rosuvastatin)",
        references=["FDA simvastatin label"],
    ),
    DrugInteraction(
        drug1="clarithromycin",
        drug2="simvastatin",
        severity=InteractionSeverity.CONTRAINDICATED,
        interaction_type=InteractionType.PHARMACOKINETIC,
        description="Clarithromycin strongly inhibits CYP3A4",
        clinical_effect="10-fold increase in simvastatin levels, rhabdomyolysis risk",
        management="Contraindicated; suspend simvastatin during clarithromycin course",
        references=["FDA clarithromycin label"],
    ),
    DrugInteraction(
        drug1="linezolid",
        drug2="sertraline",
        severity=InteractionSeverity.CONTRAINDICATED,
        interaction_type=InteractionType.SEROTONIN_SYNDROME,
        description="Linezolid is an MAO inhibitor; sertraline is an SSRI",
        clinical_effect="Serotonin syndrome: hyperthermia, rigidity, autonomic instability",
        management="Contraindicated; wait 2 weeks after stopping sertraline before linezolid",
        references=["FDA linezolid label"],
    ),
    DrugInteraction(
        drug1="linezolid",
        drug2="escitalopram",
        severity=InteractionSeverity.CONTRAINDICATED,
        interaction_type=InteractionType.SEROTONIN_SYNDROME,
        description="Linezolid is an MAO inhibitor; escitalopram is an SSRI",
        clinical_effect="Serotonin syndrome: hyperthermia, rigidity, autonomic instability",
        management="Contraindicated; wait 2 weeks after stopping escitalopram before linezolid",
        references=["FDA linezolid label"],
    ),
    DrugInteraction(
        drug1="sildenafil",
        drug2="nitroglycerin",
        severity=InteractionSeverity.CONTRAINDICATED,
        interaction_type=InteractionType.HYPOTENSION,
        description="Both drugs cause vasodilation via nitric oxide pathway",
        clinical_effect="Severe hypotension, syncope, MI, death",
        management="Contraindicated; do not use nitrates within 24h of sildenafil",
        references=["FDA sildenafil label"],
    ),

    # ==========================================================================
    # MAJOR INTERACTIONS
    # ==========================================================================
    DrugInteraction(
        drug1="warfarin",
        drug2="aspirin",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.BLEEDING_RISK,
        description="Additive anticoagulant/antiplatelet effects",
        clinical_effect="Significantly increased bleeding risk, GI hemorrhage",
        management="Avoid unless specifically indicated (mechanical valve); monitor INR closely",
        references=["CHEST guidelines"],
    ),
    DrugInteraction(
        drug1="warfarin",
        drug2="ibuprofen",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.BLEEDING_RISK,
        description="NSAIDs inhibit platelet function and may increase warfarin levels",
        clinical_effect="Increased bleeding risk, GI hemorrhage",
        management="Avoid combination; use acetaminophen for pain",
        references=["FDA warfarin label"],
    ),
    DrugInteraction(
        drug1="warfarin",
        drug2="naproxen",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.BLEEDING_RISK,
        description="NSAIDs inhibit platelet function and may increase warfarin levels",
        clinical_effect="Increased bleeding risk, GI hemorrhage",
        management="Avoid combination; use acetaminophen for pain",
        references=["FDA warfarin label"],
    ),
    DrugInteraction(
        drug1="metformin",
        drug2="contrast dye",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.NEPHROTOXICITY,
        description="Iodinated contrast can cause acute kidney injury",
        clinical_effect="Lactic acidosis in patients with impaired metformin clearance",
        management="Hold metformin 48h before/after contrast; restart when renal function confirmed stable",
        references=["ACR contrast manual"],
    ),
    DrugInteraction(
        drug1="spironolactone",
        drug2="lisinopril",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.HYPERKALEMIA,
        description="Both drugs increase potassium retention",
        clinical_effect="Severe hyperkalemia, cardiac arrhythmia",
        management="Monitor potassium frequently; avoid if K>5.0 or eGFR<30",
        references=["ACC/AHA heart failure guidelines"],
    ),
    DrugInteraction(
        drug1="spironolactone",
        drug2="enalapril",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.HYPERKALEMIA,
        description="Both drugs increase potassium retention",
        clinical_effect="Severe hyperkalemia, cardiac arrhythmia",
        management="Monitor potassium frequently; avoid if K>5.0 or eGFR<30",
        references=["ACC/AHA heart failure guidelines"],
    ),
    DrugInteraction(
        drug1="amiodarone",
        drug2="metoprolol",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.PHARMACODYNAMIC,
        description="Additive effects on cardiac conduction",
        clinical_effect="Severe bradycardia, heart block, cardiac arrest",
        management="Use with caution; monitor ECG and heart rate closely",
        references=["FDA amiodarone label"],
    ),
    DrugInteraction(
        drug1="amiodarone",
        drug2="diltiazem",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.PHARMACODYNAMIC,
        description="Additive effects on AV nodal conduction",
        clinical_effect="Severe bradycardia, heart block",
        management="Avoid combination; if used, continuous cardiac monitoring required",
        references=["FDA amiodarone label"],
    ),
    DrugInteraction(
        drug1="ciprofloxacin",
        drug2="tizanidine",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.PHARMACOKINETIC,
        description="Ciprofloxacin inhibits CYP1A2, which metabolizes tizanidine",
        clinical_effect="10-fold increase in tizanidine levels; severe hypotension, sedation",
        management="Contraindicated; avoid combination",
        references=["FDA ciprofloxacin label"],
    ),
    DrugInteraction(
        drug1="fluconazole",
        drug2="methadone",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.QT_PROLONGATION,
        description="Both drugs prolong QT interval; fluconazole also increases methadone levels",
        clinical_effect="QT prolongation, torsades de pointes, sudden death",
        management="Avoid if possible; monitor ECG, consider methadone dose reduction",
        references=["FDA methadone label"],
    ),
    DrugInteraction(
        drug1="tramadol",
        drug2="sertraline",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.SEROTONIN_SYNDROME,
        description="Both drugs increase serotonin activity",
        clinical_effect="Serotonin syndrome risk; also increased seizure risk",
        management="Avoid combination; use alternative analgesic",
        references=["FDA tramadol label"],
    ),
    DrugInteraction(
        drug1="methotrexate",
        drug2="ibuprofen",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.NEPHROTOXICITY,
        description="NSAIDs reduce methotrexate clearance",
        clinical_effect="Increased methotrexate toxicity, myelosuppression, mucositis",
        management="Avoid NSAIDs with high-dose methotrexate; caution with low-dose",
        references=["FDA methotrexate label"],
    ),
    DrugInteraction(
        drug1="potassium",
        drug2="lisinopril",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.HYPERKALEMIA,
        description="ACE inhibitors reduce aldosterone, impairing potassium excretion",
        clinical_effect="Hyperkalemia, cardiac arrhythmia",
        management="Monitor potassium; avoid potassium supplements unless documented hypokalemia",
        references=["UpToDate"],
    ),

    # ==========================================================================
    # MODERATE INTERACTIONS
    # ==========================================================================
    DrugInteraction(
        drug1="metformin",
        drug2="lisinopril",
        severity=InteractionSeverity.MODERATE,
        interaction_type=InteractionType.HYPOGLYCEMIA,
        description="ACE inhibitors may enhance hypoglycemic effect",
        clinical_effect="Increased risk of hypoglycemia",
        management="Monitor blood glucose; may need to reduce metformin dose",
        references=["UpToDate"],
    ),
    DrugInteraction(
        drug1="amlodipine",
        drug2="simvastatin",
        severity=InteractionSeverity.MODERATE,
        interaction_type=InteractionType.PHARMACOKINETIC,
        description="Amlodipine inhibits CYP3A4, increasing simvastatin levels",
        clinical_effect="Increased risk of myopathy",
        management="Limit simvastatin to 20mg daily with amlodipine",
        references=["FDA simvastatin label"],
    ),
    DrugInteraction(
        drug1="omeprazole",
        drug2="clopidogrel",
        severity=InteractionSeverity.MODERATE,
        interaction_type=InteractionType.PHARMACOKINETIC,
        description="Omeprazole inhibits CYP2C19, reducing clopidogrel activation",
        clinical_effect="Reduced antiplatelet effect, increased cardiovascular events",
        management="Consider pantoprazole instead; or use H2 blocker",
        references=["FDA clopidogrel label"],
    ),
    DrugInteraction(
        drug1="levothyroxine",
        drug2="calcium",
        severity=InteractionSeverity.MODERATE,
        interaction_type=InteractionType.PHARMACOKINETIC,
        description="Calcium binds levothyroxine in GI tract, reducing absorption",
        clinical_effect="Decreased thyroid hormone levels, hypothyroidism symptoms",
        management="Separate doses by at least 4 hours",
        references=["FDA levothyroxine label"],
    ),
    DrugInteraction(
        drug1="levothyroxine",
        drug2="omeprazole",
        severity=InteractionSeverity.MODERATE,
        interaction_type=InteractionType.PHARMACOKINETIC,
        description="PPIs reduce gastric acid needed for levothyroxine dissolution",
        clinical_effect="Decreased levothyroxine absorption",
        management="Monitor TSH; may need higher levothyroxine dose",
        references=["UpToDate"],
    ),
    DrugInteraction(
        drug1="ciprofloxacin",
        drug2="antacids",
        severity=InteractionSeverity.MODERATE,
        interaction_type=InteractionType.PHARMACOKINETIC,
        description="Antacids chelate ciprofloxacin, reducing absorption",
        clinical_effect="Treatment failure due to subtherapeutic antibiotic levels",
        management="Give ciprofloxacin 2h before or 6h after antacids",
        references=["FDA ciprofloxacin label"],
    ),
    DrugInteraction(
        drug1="gabapentin",
        drug2="morphine",
        severity=InteractionSeverity.MODERATE,
        interaction_type=InteractionType.PHARMACODYNAMIC,
        description="Additive CNS depression",
        clinical_effect="Enhanced sedation, respiratory depression",
        management="Start with lower doses; monitor for respiratory depression",
        references=["FDA gabapentin label"],
    ),
    DrugInteraction(
        drug1="alprazolam",
        drug2="oxycodone",
        severity=InteractionSeverity.MAJOR,
        interaction_type=InteractionType.PHARMACODYNAMIC,
        description="Additive CNS and respiratory depression",
        clinical_effect="Profound sedation, respiratory depression, coma, death",
        management="Avoid combination; FDA black box warning",
        references=["FDA black box warning"],
    ),
    DrugInteraction(
        drug1="prednisone",
        drug2="ibuprofen",
        severity=InteractionSeverity.MODERATE,
        interaction_type=InteractionType.BLEEDING_RISK,
        description="Additive GI toxicity; corticosteroids mask inflammation symptoms",
        clinical_effect="Increased risk of GI ulceration and bleeding",
        management="Use PPI for gastroprotection; monitor for GI symptoms",
        references=["UpToDate"],
    ),
    DrugInteraction(
        drug1="hydrochlorothiazide",
        drug2="lithium",
        severity=InteractionSeverity.MODERATE,
        interaction_type=InteractionType.PHARMACOKINETIC,
        description="Thiazides reduce lithium clearance",
        clinical_effect="Lithium toxicity: tremor, confusion, arrhythmia",
        management="Monitor lithium levels closely; may need to reduce dose",
        references=["FDA lithium label"],
    ),
    DrugInteraction(
        drug1="insulin",
        drug2="metoprolol",
        severity=InteractionSeverity.MODERATE,
        interaction_type=InteractionType.HYPOGLYCEMIA,
        description="Beta-blockers mask tachycardia warning sign of hypoglycemia",
        clinical_effect="Delayed recognition of hypoglycemia; prolonged hypoglycemia",
        management="Educate patient on hypoglycemia symptoms; monitor glucose closely",
        references=["UpToDate"],
    ),
]

# Build lookup indexes for fast access
_DRUG_INDEX: dict[str, set[int]] = {}
_PAIR_INDEX: dict[tuple[str, str], int] = {}

for i, interaction in enumerate(DRUG_INTERACTIONS):
    # Index by individual drugs
    d1 = interaction.drug1.lower()
    d2 = interaction.drug2.lower()

    if d1 not in _DRUG_INDEX:
        _DRUG_INDEX[d1] = set()
    if d2 not in _DRUG_INDEX:
        _DRUG_INDEX[d2] = set()

    _DRUG_INDEX[d1].add(i)
    _DRUG_INDEX[d2].add(i)

    # Index by drug pair (order-independent)
    pair = tuple(sorted([d1, d2]))
    _PAIR_INDEX[pair] = i

# Drug name aliases for common variations
DRUG_ALIASES: dict[str, str] = {
    # Generic/brand variations
    "tylenol": "acetaminophen",
    "paracetamol": "acetaminophen",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "aleve": "naproxen",
    "coumadin": "warfarin",
    "plavix": "clopidogrel",
    "lipitor": "atorvastatin",
    "zocor": "simvastatin",
    "crestor": "rosuvastatin",
    "norvasc": "amlodipine",
    "lasix": "furosemide",
    "prilosec": "omeprazole",
    "nexium": "esomeprazole",
    "protonix": "pantoprazole",
    "zoloft": "sertraline",
    "prozac": "fluoxetine",
    "lexapro": "escitalopram",
    "xanax": "alprazolam",
    "ativan": "lorazepam",
    "valium": "diazepam",
    "klonopin": "clonazepam",
    "percocet": "oxycodone",
    "vicodin": "hydrocodone",
    "glucophage": "metformin",
    "januvia": "sitagliptin",
    "synthroid": "levothyroxine",
    "coreg": "carvedilol",
    "lopressor": "metoprolol",
    "toprol": "metoprolol",
    "lisinopril": "lisinopril",
    "zestril": "lisinopril",
    "prinivil": "lisinopril",
    "vasotec": "enalapril",
    "altace": "ramipril",
    "cozaar": "losartan",
    "diovan": "valsartan",
    "aldactone": "spironolactone",
    "neurontin": "gabapentin",
    "lyrica": "pregabalin",
    "ultram": "tramadol",
    "zyrtec": "cetirizine",
    "claritin": "loratadine",
    "benadryl": "diphenhydramine",
    "augmentin": "amoxicillin-clavulanate",
    "cipro": "ciprofloxacin",
    "levaquin": "levofloxacin",
    "zithromax": "azithromycin",
    "biaxin": "clarithromycin",
    "flagyl": "metronidazole",
    "diflucan": "fluconazole",
    "zyvox": "linezolid",
    "viagra": "sildenafil",
    "cialis": "tadalafil",
    # Abbreviations
    "asa": "aspirin",
    "hctz": "hydrochlorothiazide",
    "apap": "acetaminophen",
    "ntg": "nitroglycerin",
    "sl ntg": "nitroglycerin",
}


# ============================================================================
# Load Extended Drug Interactions from Fixture
# ============================================================================


def _severity_from_string(severity: str) -> InteractionSeverity:
    """Convert severity string to enum."""
    severity_map = {
        "high": InteractionSeverity.MAJOR,
        "major": InteractionSeverity.MAJOR,
        "moderate": InteractionSeverity.MODERATE,
        "low": InteractionSeverity.MINOR,
        "minor": InteractionSeverity.MINOR,
        "contraindicated": InteractionSeverity.CONTRAINDICATED,
    }
    return severity_map.get(severity.lower(), InteractionSeverity.MODERATE)


def _type_from_mechanism(mechanism: str) -> InteractionType:
    """Infer interaction type from mechanism description."""
    mechanism_lower = mechanism.lower()

    if "bleeding" in mechanism_lower:
        return InteractionType.BLEEDING_RISK
    elif "serotonin" in mechanism_lower:
        return InteractionType.SEROTONIN_SYNDROME
    elif "qt" in mechanism_lower or "cardiac" in mechanism_lower:
        return InteractionType.QT_PROLONGATION
    elif "hypotension" in mechanism_lower or "blood pressure" in mechanism_lower:
        return InteractionType.HYPOTENSION
    elif "potassium" in mechanism_lower or "hyperkalemia" in mechanism_lower:
        return InteractionType.HYPERKALEMIA
    elif "glucose" in mechanism_lower or "hypoglycemia" in mechanism_lower:
        return InteractionType.HYPOGLYCEMIA
    elif "kidney" in mechanism_lower or "renal" in mechanism_lower or "nephro" in mechanism_lower:
        return InteractionType.NEPHROTOXICITY
    elif "liver" in mechanism_lower or "hepato" in mechanism_lower:
        return InteractionType.HEPATOTOXICITY
    elif "duplicate" in mechanism_lower or "same class" in mechanism_lower:
        return InteractionType.DUPLICATE_THERAPY
    else:
        return InteractionType.PHARMACODYNAMIC


def load_extended_interactions() -> tuple[list[DrugInteraction], dict[str, set[int]], dict[tuple[str, str], int]]:
    """Load extended drug interactions from fixture file.

    Returns:
        Tuple of (interactions list, drug index, pair index)
    """
    interactions: list[DrugInteraction] = list(DRUG_INTERACTIONS)  # Start with core interactions
    drug_index: dict[str, set[int]] = {}
    pair_index: dict[tuple[str, str], int] = {}

    # Index core interactions first
    for i, interaction in enumerate(interactions):
        d1 = interaction.drug1.lower()
        d2 = interaction.drug2.lower()

        if d1 not in drug_index:
            drug_index[d1] = set()
        if d2 not in drug_index:
            drug_index[d2] = set()

        drug_index[d1].add(i)
        drug_index[d2].add(i)

        pair = tuple(sorted([d1, d2]))
        pair_index[pair] = i

    # Load from fixture file if available
    if FIXTURE_FILE.exists():
        try:
            with open(FIXTURE_FILE, "r") as f:
                data = json.load(f)

            fixture_interactions = data.get("interactions", [])

            for item in fixture_interactions:
                d1 = item.get("drug1", "").lower()
                d2 = item.get("drug2", "").lower()

                if not d1 or not d2:
                    continue

                # Skip if we already have this pair
                pair = tuple(sorted([d1, d2]))
                if pair in pair_index:
                    continue

                interaction = DrugInteraction(
                    drug1=d1,
                    drug2=d2,
                    severity=_severity_from_string(item.get("severity", "moderate")),
                    interaction_type=_type_from_mechanism(item.get("mechanism", "")),
                    description=item.get("mechanism", ""),
                    clinical_effect=item.get("effect", ""),
                    management=item.get("recommendation", "Monitor closely"),
                    references=[],
                )

                idx = len(interactions)
                interactions.append(interaction)

                if d1 not in drug_index:
                    drug_index[d1] = set()
                if d2 not in drug_index:
                    drug_index[d2] = set()

                drug_index[d1].add(idx)
                drug_index[d2].add(idx)
                pair_index[pair] = idx

            logger.info(f"Loaded {len(interactions)} drug interactions ({len(fixture_interactions)} from fixture)")
        except Exception as e:
            logger.warning(f"Failed to load extended drug interactions from {FIXTURE_FILE}: {e}")
    else:
        logger.warning(f"Drug interactions fixture file not found: {FIXTURE_FILE}")

    return interactions, drug_index, pair_index


class DrugInteractionService:
    """Service for checking drug-drug interactions.

    Provides fast lookup of known drug interactions from a curated
    database based on FDA labels and clinical guidelines.

    Integrates with RxNormService for enhanced drug name normalization
    and ingredient-based interaction checking.

    Usage:
        service = DrugInteractionService()
        result = service.check_interactions(["warfarin", "aspirin", "lisinopril"])

        if result.has_major:
            print(f"Found {result.total_interactions} interactions")
            for interaction in result.interactions_found:
                print(f"  - {interaction.drug1} + {interaction.drug2}: {interaction.severity}")

        # With RxNorm integration for brand name resolution
        result = service.check_interactions(["Coumadin", "Advil"])  # Resolves to warfarin + ibuprofen
    """

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, other: object) -> bool:
        return self is other

    def __init__(
        self,
        use_rxnorm: bool = True,
        use_graph: bool = True,
        graph_service: GraphDatabaseService | None = None,
    ) -> None:
        """Initialize the drug interaction service.

        Args:
            use_rxnorm: Whether to use RxNormService for enhanced drug name resolution.
                       Defaults to True. Set to False to disable RxNorm integration.
            use_graph: Whether to enable Neo4j-backed interaction lookups when available.
            graph_service: Optional GraphDatabaseService for Neo4j integration (primarily for tests).
        """
        # Load extended interactions from fixture
        self._interactions, self._drug_index, self._pair_index = load_extended_interactions()
        self._aliases = DRUG_ALIASES
        self._rxnorm_service: "RxNormService | None" = None
        self._use_rxnorm = use_rxnorm
        self._graph_service: GraphDatabaseService | None = None
        self._use_graph = use_graph
        self._concept_lookup_cache: dict[str, tuple[int, str]] = {}

        if use_rxnorm:
            self._init_rxnorm()

        if use_graph:
            self._init_graph(graph_service)

        logger.info(f"Drug interaction service initialized with {len(self._interactions)} interactions")

    def _init_rxnorm(self) -> None:
        """Initialize RxNorm service integration."""
        try:
            from app.services.rxnorm_service import get_rxnorm_service
            self._rxnorm_service = get_rxnorm_service()
            logger.info("RxNorm service integration enabled for drug interactions")
        except Exception as e:
            logger.warning(f"Failed to initialize RxNorm service: {e}")
            self._rxnorm_service = None

    def _lookup_drug_concept(self, drug: str) -> tuple[int, str] | None:
        """Resolve a drug name to (OMOP concept ID, display name)."""
        if not self._rxnorm_service:
            return None

        normalized = drug.lower().strip()
        if normalized in self._concept_lookup_cache:
            return self._concept_lookup_cache[normalized]

        try:
            result = self._rxnorm_service.lookup_drug(drug)
            if result and result.found and result.drug_info:
                concept_id = result.drug_info.omop_concept_id
                if concept_id is None:
                    return None
                display_name = (
                    result.drug_info.generic_name
                    or result.drug_info.concept_name
                    or normalized
                )
                value = (int(concept_id), display_name)
                self._concept_lookup_cache[normalized] = value
                return value
        except Exception as e:
            logger.debug(f"RxNorm concept lookup failed for {drug}: {e}")

        return None

    def _init_graph(self, graph_service: GraphDatabaseService | None) -> None:
        """Initialize Neo4j graph integration if available."""
        try:
            service = graph_service or get_graph_database_service()
            if not service.is_connected and graph_service is None:
                logger.info("Neo4j not connected; graph interaction lookups disabled")
                return

            self._graph_service = service
            self._ensure_graph_schema()

            loaded = self._graph_interactions_loaded()
            if not loaded.get("drug", False) or not loaded.get("concept", False):
                self._load_interactions_to_graph(
                    load_drug=not loaded.get("drug", False),
                    load_concept=not loaded.get("concept", False),
                )
        except Exception as e:
            logger.warning(f"Failed to initialize Neo4j drug interaction graph: {e}")
            self._graph_service = None

    def _ensure_graph_schema(self) -> None:
        """Ensure Neo4j schema exists for drug interaction nodes."""
        if not self._graph_service:
            return

        schema_queries = [
            "CREATE CONSTRAINT drug_name_unique IF NOT EXISTS FOR (d:Drug) REQUIRE d.name IS UNIQUE",
            "CREATE INDEX drug_display_name_idx IF NOT EXISTS FOR (d:Drug) ON (d.display_name)",
        ]

        for query in schema_queries:
            try:
                self._graph_service.execute_write(query)
            except Exception as e:
                logger.debug(f"Neo4j schema creation skipped: {e}")

    def _graph_interactions_loaded(self) -> dict[str, bool]:
        """Check if drug interactions are already present in Neo4j."""
        status = {"drug": False, "concept": False}
        if not self._graph_service:
            return status

        try:
            result = self._graph_service.execute_read(
                "MATCH (:Drug)-[r:INTERACTS_WITH|CONTRAINDICATED_WITH]-(:Drug) RETURN count(r) AS count"
            )
            if result.records:
                status["drug"] = bool(result.records[0].get("count", 0))
        except Exception as e:
            logger.debug(f"Neo4j interaction check failed: {e}")
        try:
            result = self._graph_service.execute_read(
                "MATCH (:Concept)-[r:INTERACTS_WITH|CONTRAINDICATED_WITH]-(:Concept) RETURN count(r) AS count"
            )
            if result.records:
                status["concept"] = bool(result.records[0].get("count", 0))
        except Exception as e:
            logger.debug(f"Neo4j concept interaction check failed: {e}")

        return status

    def _load_interactions_to_graph(
        self,
        load_drug: bool = True,
        load_concept: bool = True,
    ) -> None:
        """Load drug interactions into Neo4j for graph-based lookups."""
        if not self._graph_service:
            return
        if load_concept and not self._rxnorm_service:
            load_concept = False

        def build_row(interaction: DrugInteraction) -> dict[str, Any]:
            d1 = interaction.drug1.lower()
            d2 = interaction.drug2.lower()
            drug1, drug2 = sorted([d1, d2])
            return {
                "drug1": drug1,
                "drug2": drug2,
                "drug1_display": drug1,
                "drug2_display": drug2,
                "severity": interaction.severity.value,
                "interaction_type": interaction.interaction_type.value,
                "description": interaction.description,
                "clinical_effect": interaction.clinical_effect,
                "management": interaction.management,
                "references": interaction.references,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        contraindicated_rows: list[dict[str, Any]] = []
        interaction_rows: list[dict[str, Any]] = []
        contraindicated_concept_rows: list[dict[str, Any]] = []
        interaction_concept_rows: list[dict[str, Any]] = []
        seen_pairs: set[tuple[str, str]] = set()
        seen_concept_pairs: set[tuple[int, int]] = set()

        for interaction in self._interactions:
            row = build_row(interaction)
            pair_key = (row["drug1"], row["drug2"])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            if interaction.severity == InteractionSeverity.CONTRAINDICATED:
                contraindicated_rows.append(row)
            else:
                interaction_rows.append(row)

            if load_concept:
                concept_1 = self._lookup_drug_concept(interaction.drug1)
                concept_2 = self._lookup_drug_concept(interaction.drug2)
                if concept_1 and concept_2:
                    c1_id, c1_name = concept_1
                    c2_id, c2_name = concept_2
                    if c1_id == c2_id:
                        continue
                    sorted_pair = sorted([(c1_id, c1_name), (c2_id, c2_name)], key=lambda item: item[0])
                    concept_pair = (sorted_pair[0][0], sorted_pair[1][0])
                    if concept_pair in seen_concept_pairs:
                        continue
                    seen_concept_pairs.add(concept_pair)
                    concept_row = {
                        "concept_id_1": sorted_pair[0][0],
                        "concept_id_2": sorted_pair[1][0],
                        "concept_name_1": sorted_pair[0][1],
                        "concept_name_2": sorted_pair[1][1],
                        "severity": interaction.severity.value,
                        "interaction_type": interaction.interaction_type.value,
                        "description": interaction.description,
                        "clinical_effect": interaction.clinical_effect,
                        "management": interaction.management,
                        "references": interaction.references,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                    if interaction.severity == InteractionSeverity.CONTRAINDICATED:
                        contraindicated_concept_rows.append(concept_row)
                    else:
                        interaction_concept_rows.append(concept_row)

        def load_batch(rows: list[dict[str, Any]], rel_type: str) -> None:
            if not rows:
                return
            query = f"""
            UNWIND $rows AS row
            MERGE (d1:Drug {{name: row.drug1}})
              ON CREATE SET d1.display_name = row.drug1_display
            MERGE (d2:Drug {{name: row.drug2}})
              ON CREATE SET d2.display_name = row.drug2_display
            MERGE (d1)-[r:{rel_type}]->(d2)
            SET r.severity = row.severity,
                r.interaction_type = row.interaction_type,
                r.description = row.description,
                r.clinical_effect = row.clinical_effect,
                r.management = row.management,
                r.references = row.references,
                r.updated_at = row.updated_at
            RETURN count(r) AS relationships_created
            """
            batch_size = 500
            for i in range(0, len(rows), batch_size):
                self._graph_service.execute_write(query, {"rows": rows[i:i + batch_size]})

        if load_drug:
            load_batch(contraindicated_rows, "CONTRAINDICATED_WITH")
            load_batch(interaction_rows, "INTERACTS_WITH")

        if load_concept and (contraindicated_concept_rows or interaction_concept_rows):
            def load_concept_batch(rows: list[dict[str, Any]], rel_type: str) -> None:
                if not rows:
                    return
                query = f"""
                UNWIND $rows AS row
                MERGE (c1:Concept {{concept_id: row.concept_id_1}})
                  ON CREATE SET c1.name = row.concept_name_1,
                                c1.vocabulary_id = 'RxNorm'
                MERGE (c2:Concept {{concept_id: row.concept_id_2}})
                  ON CREATE SET c2.name = row.concept_name_2,
                                c2.vocabulary_id = 'RxNorm'
                MERGE (c1)-[r:{rel_type}]->(c2)
                SET r.severity = row.severity,
                    r.interaction_type = row.interaction_type,
                    r.description = row.description,
                    r.clinical_effect = row.clinical_effect,
                    r.management = row.management,
                    r.references = row.references,
                    r.updated_at = row.updated_at
                RETURN count(r) AS relationships_created
                """
                batch_size = 500
                for i in range(0, len(rows), batch_size):
                    self._graph_service.execute_write(query, {"rows": rows[i:i + batch_size]})

            load_concept_batch(contraindicated_concept_rows, "CONTRAINDICATED_WITH")
            load_concept_batch(interaction_concept_rows, "INTERACTS_WITH")

    def normalize_drug_name(self, drug: str) -> str:
        """Normalize drug name to lowercase, resolving aliases.

        Uses RxNormService if available for enhanced brand-to-generic resolution.

        Args:
            drug: Drug name to normalize.

        Returns:
            Normalized drug name (generic if possible).
        """
        normalized = drug.lower().strip()

        # First check local aliases
        if normalized in self._aliases:
            return self._aliases[normalized]

        # Try RxNorm service for brand-to-generic resolution
        if self._rxnorm_service:
            try:
                generic = self._rxnorm_service.normalize_to_generic(drug)
                if generic:
                    return generic.lower()
            except Exception as e:
                logger.debug(f"RxNorm lookup failed for {drug}: {e}")

        return normalized

    def get_drug_ingredients(self, drug: str) -> list[str]:
        """Get active ingredients for a drug.

        Uses RxNormService if available to extract ingredients from
        combination products for more comprehensive interaction checking.

        Args:
            drug: Drug name (brand or generic).

        Returns:
            List of ingredient names.
        """
        normalized = self.normalize_drug_name(drug)

        # Try RxNorm service for ingredient extraction
        if self._rxnorm_service:
            try:
                ingredients = self._rxnorm_service.get_ingredients(drug)
                if ingredients:
                    return [i.lower() for i in ingredients]
            except Exception as e:
                logger.debug(f"RxNorm ingredient lookup failed for {drug}: {e}")

        # Fall back to the normalized name as the ingredient
        return [normalized]

    def check_pair(self, drug1: str, drug2: str) -> DrugInteraction | None:
        """Check for interaction between two specific drugs.

        Args:
            drug1: First drug name.
            drug2: Second drug name.

        Returns:
            DrugInteraction if found, None otherwise.
        """
        d1 = self.normalize_drug_name(drug1)
        d2 = self.normalize_drug_name(drug2)

        if d1 == d2:
            return None

        pair = tuple(sorted([d1, d2]))
        idx = self._pair_index.get(pair)

        if idx is not None:
            return self._interactions[idx]

        graph_interaction = self._check_pair_graph(d1, d2)
        if graph_interaction:
            return graph_interaction

        return None

    def _check_pair_graph(self, drug1: str, drug2: str) -> DrugInteraction | None:
        """Check for interaction between two drugs using Neo4j."""
        if not self._graph_service:
            return None

        concept_1 = self._lookup_drug_concept(drug1)
        concept_2 = self._lookup_drug_concept(drug2)

        if concept_1 and concept_2:
            try:
                result = self._graph_service.execute_read(
                    """
                    MATCH (c1:Concept {concept_id: $concept_id_1})-[r:INTERACTS_WITH|CONTRAINDICATED_WITH]-(c2:Concept {concept_id: $concept_id_2})
                    RETURN type(r) AS rel_type,
                           r.severity AS severity,
                           r.interaction_type AS interaction_type,
                           r.description AS description,
                           r.clinical_effect AS clinical_effect,
                           r.management AS management,
                           r.references AS references
                    LIMIT 1
                    """,
                    {"concept_id_1": concept_1[0], "concept_id_2": concept_2[0]},
                )
                if result.records:
                    return self._build_graph_interaction(drug1, drug2, result.records[0])
            except Exception as e:
                logger.debug(f"Neo4j concept interaction lookup failed: {e}")

        try:
            result = self._graph_service.execute_read(
                """
                MATCH (d1:Drug {name: $drug1})-[r:INTERACTS_WITH|CONTRAINDICATED_WITH]-(d2:Drug {name: $drug2})
                RETURN type(r) AS rel_type,
                       r.severity AS severity,
                       r.interaction_type AS interaction_type,
                       r.description AS description,
                       r.clinical_effect AS clinical_effect,
                       r.management AS management,
                       r.references AS references
                LIMIT 1
                """,
                {"drug1": drug1, "drug2": drug2},
            )
        except Exception as e:
            logger.debug(f"Neo4j interaction lookup failed: {e}")
            return None

        if not result.records:
            return None

        return self._build_graph_interaction(drug1, drug2, result.records[0])

    def _build_graph_interaction(
        self,
        drug1: str,
        drug2: str,
        record: dict[str, Any],
    ) -> DrugInteraction:
        """Build a DrugInteraction from a Neo4j record."""
        rel_type = record.get("rel_type", "")
        severity_raw = record.get("severity") or (
            InteractionSeverity.CONTRAINDICATED.value
            if rel_type == "CONTRAINDICATED_WITH"
            else InteractionSeverity.MODERATE.value
        )
        interaction_type_raw = record.get("interaction_type") or InteractionType.PHARMACODYNAMIC.value

        try:
            severity = InteractionSeverity(severity_raw)
        except Exception:
            severity = InteractionSeverity.MODERATE

        try:
            interaction_type = InteractionType(interaction_type_raw)
        except Exception:
            interaction_type = InteractionType.PHARMACODYNAMIC

        return DrugInteraction(
            drug1=drug1,
            drug2=drug2,
            severity=severity,
            interaction_type=interaction_type,
            description=record.get("description") or "Graph-derived interaction",
            clinical_effect=record.get("clinical_effect") or "Unknown clinical effect",
            management=record.get("management") or "Monitor closely",
            references=record.get("references") or [],
        )

    def check_interactions(self, drugs: list[str]) -> InteractionCheckResult:
        """Check for interactions among a list of drugs."""
        # Normalize and extract ingredients, then make hashable for cache
        all_ingredients: set[str] = set()
        for drug in drugs:
            ingredients = self.get_drug_ingredients(drug)
            all_ingredients.update(ingredients)
        normalized = [self.normalize_drug_name(d) for d in drugs]
        all_ingredients.update(normalized)
        drugs_key = tuple(sorted(all_ingredients))
        return self._check_interactions_cached(drugs_key)

    @lru_cache(maxsize=256)
    def _check_interactions_cached(self, drugs_key: tuple[str, ...]) -> InteractionCheckResult:
        """Cached implementation of check_interactions."""
        unique_drugs = list(drugs_key)

        interactions_found: list[DrugInteraction] = []
        seen_pairs: set[tuple[str, str]] = set()

        # Check all pairs
        for i, drug1 in enumerate(unique_drugs):
            for drug2 in unique_drugs[i + 1:]:
                pair = tuple(sorted([drug1, drug2]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                interaction = self.check_pair(drug1, drug2)
                if interaction:
                    interactions_found.append(interaction)

        # Count by severity
        by_severity: dict[str, int] = {}
        for interaction in interactions_found:
            sev = interaction.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

        # Determine highest severity
        highest_severity = None
        has_contraindicated = False
        has_major = False

        for interaction in interactions_found:
            if interaction.severity == InteractionSeverity.CONTRAINDICATED:
                has_contraindicated = True
                highest_severity = InteractionSeverity.CONTRAINDICATED
            elif interaction.severity == InteractionSeverity.MAJOR:
                has_major = True
                if highest_severity != InteractionSeverity.CONTRAINDICATED:
                    highest_severity = InteractionSeverity.MAJOR
            elif highest_severity is None:
                highest_severity = interaction.severity

        return InteractionCheckResult(
            drugs_checked=unique_drugs,
            interactions_found=interactions_found,
            total_interactions=len(interactions_found),
            by_severity=by_severity,
            highest_severity=highest_severity,
            has_contraindicated=has_contraindicated,
            has_major=has_major,
        )

    def get_interactions_for_drug(self, drug: str) -> list[DrugInteraction]:
        """Get all known interactions for a specific drug.

        Args:
            drug: Drug name to look up.

        Returns:
            List of all interactions involving this drug.
        """
        normalized = self.normalize_drug_name(drug)
        indices = self._drug_index.get(normalized, set())
        return [self._interactions[i] for i in indices]

    def check_pathway_interactions(
        self,
        drug1: str,
        drug2: str,
    ) -> list[DrugInteraction]:
        """Check for pathway-based (CYP450) interactions between two drugs.

        Uses Neo4j graph traversal to find indirect interactions via
        shared metabolic enzyme pathways.

        Args:
            drug1: First drug name.
            drug2: Second drug name.

        Returns:
            List of inferred pathway-based interactions.
        """
        if not self._graph_service:
            return []

        d1 = self.normalize_drug_name(drug1)
        d2 = self.normalize_drug_name(drug2)

        try:
            result = self._graph_service.execute_read(
                PATHWAY_INTERACTION_QUERY,
                {"drug1": d1, "drug2": d2},
            )
        except Exception as e:
            logger.debug(f"Pathway interaction query failed: {e}")
            return []

        interactions: list[DrugInteraction] = []
        for record in result.records:
            enzyme = record.get("enzyme", "CYP enzyme")
            effect = record.get("effect", "affects")
            interaction = DrugInteraction(
                drug1=d1,
                drug2=d2,
                severity=InteractionSeverity.MODERATE,
                interaction_type=InteractionType.PHARMACOKINETIC,
                description=record.get("description") or f"CYP-mediated interaction via {enzyme}",
                clinical_effect=f"{d2.title()} {effect}s metabolism of {d1.title()} via {enzyme}",
                management="Monitor drug levels; consider dose adjustment",
                references=["CYP450 pathway inference"],
            )
            interactions.append(interaction)

        return interactions

    def check_qt_prolongation_risk(
        self,
        drugs: list[str],
    ) -> list[dict[str, Any]]:
        """Check for QT prolongation risk among a list of drugs.

        Identifies drugs with known or possible QT-prolonging effects and
        flags combinations that increase torsades de pointes risk.

        Args:
            drugs: List of drug names to check.

        Returns:
            List of QT risk assessments with drug names and risk levels.
        """
        if not self._graph_service:
            return []

        normalized = [self.normalize_drug_name(d) for d in drugs]

        try:
            result = self._graph_service.execute_read(
                QT_DRUGS_IN_LIST_QUERY,
                {"drug_names": normalized},
            )
        except Exception as e:
            logger.debug(f"QT drug query failed: {e}")
            return []

        qt_drugs: list[dict[str, Any]] = []
        for record in result.records:
            qt_drugs.append({
                "drug": record.get("drug_name"),
                "risk_level": record.get("risk_level", "unknown"),
                "mechanism": record.get("mechanism"),
            })

        return qt_drugs

    def check_qt_pair_interaction(
        self,
        drug1: str,
        drug2: str,
    ) -> DrugInteraction | None:
        """Check for QT prolongation interaction between two drugs.

        Args:
            drug1: First drug name.
            drug2: Second drug name.

        Returns:
            DrugInteraction if both drugs prolong QT, None otherwise.
        """
        if not self._graph_service:
            return None

        d1 = self.normalize_drug_name(drug1)
        d2 = self.normalize_drug_name(drug2)

        try:
            result = self._graph_service.execute_read(
                QT_PROLONGATION_QUERY,
                {"drug1": d1, "drug2": d2},
            )
        except Exception as e:
            logger.debug(f"QT pair query failed: {e}")
            return None

        if not result.records:
            return None

        record = result.records[0]
        severity_raw = record.get("combined_severity", "moderate")
        severity = InteractionSeverity.MAJOR if severity_raw == "major" else InteractionSeverity.MODERATE

        return DrugInteraction(
            drug1=d1,
            drug2=d2,
            severity=severity,
            interaction_type=InteractionType.QT_PROLONGATION,
            description="Both drugs prolong QT interval",
            clinical_effect=record.get("clinical_effect") or "Additive QT prolongation risk",
            management="Avoid combination if possible; monitor ECG and electrolytes",
            references=["CredibleMeds QT database"],
        )

    def check_interactions_enhanced(
        self,
        drugs: list[str],
        include_pathway: bool = True,
        include_qt_check: bool = True,
    ) -> InteractionCheckResult:
        """Enhanced interaction check combining curated, graph, and inferred interactions.

        Extends the standard check_interactions() with:
        1. Direct curated interactions from the database
        2. Neo4j graph-based lookups (Concept and Drug nodes)
        3. Pathway-based CYP450 interaction inference
        4. QT prolongation combination checks

        Args:
            drugs: List of drug names to check.
            include_pathway: Whether to include CYP450 pathway inference.
            include_qt_check: Whether to include QT prolongation checks.

        Returns:
            InteractionCheckResult with all found interactions.
        """
        # Start with standard interaction check
        base_result = self.check_interactions(drugs)
        all_interactions = list(base_result.interactions_found)
        seen_pairs: set[tuple[str, str]] = {
            tuple(sorted([i.drug1, i.drug2]))
            for i in all_interactions
        }

        normalized = [self.normalize_drug_name(d) for d in drugs]
        unique_drugs = list(set(normalized))

        # Add pathway-based interactions
        if include_pathway and self._graph_service:
            for i, d1 in enumerate(unique_drugs):
                for d2 in unique_drugs[i + 1:]:
                    pair = tuple(sorted([d1, d2]))
                    if pair not in seen_pairs:
                        pathway_interactions = self.check_pathway_interactions(d1, d2)
                        for pi in pathway_interactions:
                            pair_key = tuple(sorted([pi.drug1, pi.drug2]))
                            if pair_key not in seen_pairs:
                                all_interactions.append(pi)
                                seen_pairs.add(pair_key)

        # Add QT prolongation interactions
        if include_qt_check and self._graph_service:
            for i, d1 in enumerate(unique_drugs):
                for d2 in unique_drugs[i + 1:]:
                    pair = tuple(sorted([d1, d2]))
                    if pair not in seen_pairs:
                        qt_interaction = self.check_qt_pair_interaction(d1, d2)
                        if qt_interaction:
                            all_interactions.append(qt_interaction)
                            seen_pairs.add(pair)

        # Recalculate severity counts
        by_severity: dict[str, int] = {}
        for interaction in all_interactions:
            sev = interaction.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

        highest_severity = None
        has_contraindicated = False
        has_major = False

        for interaction in all_interactions:
            if interaction.severity == InteractionSeverity.CONTRAINDICATED:
                has_contraindicated = True
                highest_severity = InteractionSeverity.CONTRAINDICATED
            elif interaction.severity == InteractionSeverity.MAJOR:
                has_major = True
                if highest_severity != InteractionSeverity.CONTRAINDICATED:
                    highest_severity = InteractionSeverity.MAJOR
            elif highest_severity is None:
                highest_severity = interaction.severity

        return InteractionCheckResult(
            drugs_checked=unique_drugs,
            interactions_found=all_interactions,
            total_interactions=len(all_interactions),
            by_severity=by_severity,
            highest_severity=highest_severity,
            has_contraindicated=has_contraindicated,
            has_major=has_major,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the interaction database.

        Returns:
            Dictionary with database statistics.
        """
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}

        for interaction in self._interactions:
            sev = interaction.severity.value
            typ = interaction.interaction_type.value
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_type[typ] = by_type.get(typ, 0) + 1

        return {
            "total_interactions": len(self._interactions),
            "unique_drugs": len(self._drug_index),
            "aliases_count": len(self._aliases),
            "by_severity": by_severity,
            "by_type": by_type,
        }


# Singleton instance and lock
_drug_interaction_service: DrugInteractionService | None = None
_drug_interaction_lock = Lock()


def get_drug_interaction_service() -> DrugInteractionService:
    """Get the singleton DrugInteractionService instance.

    Returns:
        The singleton DrugInteractionService instance.
    """
    global _drug_interaction_service

    if _drug_interaction_service is None:
        with _drug_interaction_lock:
            if _drug_interaction_service is None:
                logger.info("Creating singleton DrugInteractionService instance")
                _drug_interaction_service = DrugInteractionService()

    return _drug_interaction_service


def reset_drug_interaction_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _drug_interaction_service
    with _drug_interaction_lock:
        _drug_interaction_service = None
