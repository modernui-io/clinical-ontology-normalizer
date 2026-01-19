"""Drug Interaction Database Service.

Provides drug-drug interaction checking using a curated database of
known interactions based on FDA and clinical guidelines.

This service integrates with RxNormService for enhanced drug name
normalization and ingredient extraction.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, TYPE_CHECKING

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

    def __init__(self, use_rxnorm: bool = True) -> None:
        """Initialize the drug interaction service.

        Args:
            use_rxnorm: Whether to use RxNormService for enhanced drug name resolution.
                       Defaults to True. Set to False to disable RxNorm integration.
        """
        # Load extended interactions from fixture
        self._interactions, self._drug_index, self._pair_index = load_extended_interactions()
        self._aliases = DRUG_ALIASES
        self._rxnorm_service: "RxNormService | None" = None
        self._use_rxnorm = use_rxnorm

        if use_rxnorm:
            self._init_rxnorm()

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

        return None

    def check_interactions(self, drugs: list[str]) -> InteractionCheckResult:
        """Check for interactions among a list of drugs.

        Uses RxNormService if available to:
        1. Resolve brand names to generics
        2. Extract ingredients from combination products
        3. Check interactions at the ingredient level

        Args:
            drugs: List of drug names to check.

        Returns:
            InteractionCheckResult with all found interactions.
        """
        # Normalize all drug names and extract ingredients
        all_ingredients: set[str] = set()

        for drug in drugs:
            # Get ingredients (may return multiple for combination products)
            ingredients = self.get_drug_ingredients(drug)
            all_ingredients.update(ingredients)

        # Also include normalized names for backward compatibility
        normalized = [self.normalize_drug_name(d) for d in drugs]
        all_ingredients.update(normalized)

        unique_drugs = list(all_ingredients)

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
