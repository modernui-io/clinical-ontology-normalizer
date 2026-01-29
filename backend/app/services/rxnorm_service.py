"""RxNorm Drug Database Service.

This module provides comprehensive drug lookup and normalization using
RxNorm (National Library of Medicine's normalized drug naming system).

Features:
- Drug name normalization (brand -> generic)
- Ingredient extraction for interaction checking
- NDC to RxCUI mapping
- Drug class lookup (therapeutic categories)
- Fast lookup with caching and indexing

Note: This service integrates with DrugInteractionService and DrugSafetyService
to provide enhanced clinical decision support.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

FIXTURE_FILE = Path(__file__).parent.parent.parent / "fixtures" / "rxnorm_drugs.json"


class RxNormTermType(str, Enum):
    """RxNorm term types (TTY)."""

    IN = "IN"  # Ingredient
    PIN = "PIN"  # Precise Ingredient
    MIN = "MIN"  # Multiple Ingredients
    BN = "BN"  # Brand Name
    SY = "SY"  # Synonym
    SCDC = "SCDC"  # Semantic Clinical Drug Component
    SCDF = "SCDF"  # Semantic Clinical Drug Form
    SCD = "SCD"  # Semantic Clinical Drug
    SBDC = "SBDC"  # Semantic Branded Drug Component
    SBDF = "SBDF"  # Semantic Branded Drug Form
    SBD = "SBD"  # Semantic Branded Drug
    BPCK = "BPCK"  # Branded Pack
    GPCK = "GPCK"  # Generic Pack
    DF = "DF"  # Dose Form
    DFG = "DFG"  # Dose Form Group


class DrugMatchType(str, Enum):
    """Type of drug name match."""

    EXACT = "exact"
    GENERIC = "generic"
    BRAND = "brand"
    INGREDIENT = "ingredient"
    PARTIAL = "partial"
    FUZZY = "fuzzy"


@dataclass
class DrugIngredient:
    """A drug ingredient."""

    name: str
    rxcui: str = ""
    is_active: bool = True


@dataclass
class DrugInfo:
    """Complete drug information from RxNorm."""

    rxcui: str
    concept_name: str
    tty: str
    generic_name: str = ""
    brand_names: list[str] = field(default_factory=list)
    ingredients: list[str] = field(default_factory=list)
    therapeutic_classes: list[str] = field(default_factory=list)
    dosage_form: str = ""
    strength: str = ""
    route: str = ""
    synonyms: list[str] = field(default_factory=list)
    ndc_codes: list[str] = field(default_factory=list)
    omop_concept_id: int | None = None


@dataclass
class DrugLookupResult:
    """Result of a drug lookup operation."""

    query: str
    found: bool
    match_type: DrugMatchType | None
    drug_info: DrugInfo | None
    generic_name: str | None
    brand_names: list[str]
    ingredients: list[str]
    therapeutic_classes: list[str]
    alternatives: list[DrugInfo] = field(default_factory=list)


@dataclass
class DrugClassLookupResult:
    """Result of a therapeutic class lookup."""

    class_name: str
    drugs: list[DrugInfo]
    total_count: int


@dataclass
class NDCLookupResult:
    """Result of NDC code lookup."""

    ndc: str
    found: bool
    rxcui: str | None
    drug_info: DrugInfo | None


# ============================================================================
# Additional Brand/Generic Mappings for Enhanced Coverage
# ============================================================================

ADDITIONAL_BRAND_MAPPINGS: dict[str, str] = {
    # Commonly prescribed additional mappings
    "tylenol": "acetaminophen",
    "motrin": "ibuprofen",
    "advil": "ibuprofen",
    "aleve": "naproxen",
    "aspirin": "acetylsalicylic acid",
    "asa": "aspirin",
    "ecotrin": "aspirin",
    "bayer": "aspirin",
    "excedrin": "acetaminophen/aspirin/caffeine",
    "anacin": "aspirin/caffeine",
    "bufferin": "aspirin",
    "pepto-bismol": "bismuth subsalicylate",
    "kaopectate": "bismuth subsalicylate",
    "maalox": "aluminum hydroxide/magnesium hydroxide",
    "mylanta": "aluminum hydroxide/magnesium hydroxide/simethicone",
    "tums": "calcium carbonate",
    "rolaids": "calcium carbonate/magnesium hydroxide",
    "gaviscon": "aluminum hydroxide/magnesium carbonate",
    "milk of magnesia": "magnesium hydroxide",
    "ex-lax": "senna",
    "correctol": "bisacodyl",
    "fiber one": "psyllium",
    "konsyl": "psyllium",
    "fibercon": "calcium polycarbophil",
    "gas-x": "simethicone",
    "beano": "alpha-galactosidase",
    "lactaid": "lactase",
    "imodium": "loperamide",
    "kaopectate advanced": "attapulgite",
    "pepto diarrhea control": "loperamide",
    "dramamine": "dimenhydrinate",
    "bonine": "meclizine",
    "unisom": "doxylamine",
    "zzzquil": "diphenhydramine",
    "nyquil": "acetaminophen/dextromethorphan/doxylamine",
    "dayquil": "acetaminophen/dextromethorphan/phenylephrine",
    "theraflu": "acetaminophen/phenylephrine/diphenhydramine",
    "mucinex dm": "dextromethorphan/guaifenesin",
    "robitussin dm": "dextromethorphan/guaifenesin",
    "delsym": "dextromethorphan",
    "sudafed": "pseudoephedrine",
    "sudafed pe": "phenylephrine",
    "afrin": "oxymetazoline",
    "flonase": "fluticasone",
    "nasacort": "triamcinolone",
    "nasonex": "mometasone",
    "rhinocort": "budesonide",
    "zyrtec": "cetirizine",
    "claritin": "loratadine",
    "allegra": "fexofenadine",
    "benadryl": "diphenhydramine",
    "chlor-trimeton": "chlorpheniramine",
    "zaditor": "ketotifen",
    "visine": "tetrahydrozoline",
    "clear eyes": "naphazoline",
    "opcon-a": "naphazoline/pheniramine",
    "systane": "polyethylene glycol/propylene glycol",
    "refresh tears": "carboxymethylcellulose",
    "lamisil": "terbinafine",
    "tinactin": "tolnaftate",
    "lotrimin": "clotrimazole",
    "monistat": "miconazole",
    "vagisil": "benzocaine",
    "azo": "phenazopyridine",
    "cystex": "methenamine/sodium salicylate",
    "preparation h": "phenylephrine/petrolatum/mineral oil",
    "anusol": "zinc oxide/pramoxine",
    "bactine": "benzalkonium chloride/lidocaine",
    "neosporin": "bacitracin/neomycin/polymyxin b",
    "polysporin": "bacitracin/polymyxin b",
    "bacitracin": "bacitracin",
    "betadine": "povidone-iodine",
    "hibiclens": "chlorhexidine",
    "bengay": "menthol/methyl salicylate",
    "icy hot": "menthol/methyl salicylate",
    "biofreeze": "menthol",
    "aspercreme": "trolamine salicylate",
    "voltaren gel": "diclofenac",
    "salonpas": "menthol/methyl salicylate/capsaicin",
    "capsaicin": "capsaicin",
    "zostrix": "capsaicin",
    "hydrocortisone": "hydrocortisone",
    "cortizone-10": "hydrocortisone",
    "cortaid": "hydrocortisone",
    "benadryl cream": "diphenhydramine",
    "calamine": "calamine/zinc oxide",
    "caladryl": "calamine/diphenhydramine",
    "solarcaine": "lidocaine",
    "dermoplast": "benzocaine",
    "orajel": "benzocaine",
    "anbesol": "benzocaine",
    "chloraseptic": "phenol/menthol",
    "cepacol": "benzocaine/menthol",
    "halls": "menthol",
    "ricola": "menthol/herbal",
    "vicks": "menthol/camphor/eucalyptus",
    "vaporub": "camphor/eucalyptus/menthol",
    "breathe right": "mentol",
}

# Common drug class mappings
DRUG_CLASS_KEYWORDS: dict[str, list[str]] = {
    "antibiotic": ["penicillin", "amoxicillin", "cephalosporin", "azithromycin", "ciprofloxacin", "doxycycline", "metronidazole"],
    "antihypertensive": ["lisinopril", "losartan", "amlodipine", "metoprolol", "hydrochlorothiazide"],
    "statin": ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin"],
    "antidiabetic": ["metformin", "glipizide", "insulin", "empagliflozin", "semaglutide"],
    "antidepressant": ["sertraline", "fluoxetine", "escitalopram", "bupropion", "venlafaxine"],
    "anticoagulant": ["warfarin", "apixaban", "rivaroxaban", "heparin", "enoxaparin"],
    "opioid": ["morphine", "oxycodone", "hydrocodone", "fentanyl", "tramadol"],
    "nsaid": ["ibuprofen", "naproxen", "celecoxib", "meloxicam", "diclofenac"],
    "ppi": ["omeprazole", "pantoprazole", "esomeprazole", "lansoprazole"],
    "benzodiazepine": ["alprazolam", "lorazepam", "diazepam", "clonazepam"],
    "bronchodilator": ["albuterol", "ipratropium", "tiotropium", "salmeterol"],
    "corticosteroid": ["prednisone", "dexamethasone", "methylprednisolone", "hydrocortisone"],
    "diuretic": ["furosemide", "hydrochlorothiazide", "spironolactone", "bumetanide"],
    "anticonvulsant": ["levetiracetam", "gabapentin", "pregabalin", "lamotrigine", "valproic acid"],
    "antipsychotic": ["quetiapine", "risperidone", "olanzapine", "aripiprazole"],
    "thyroid": ["levothyroxine", "liothyronine", "methimazole"],
    "immunosuppressant": ["tacrolimus", "cyclosporine", "mycophenolate", "azathioprine"],
    "antiviral": ["acyclovir", "valacyclovir", "oseltamivir", "remdesivir"],
    "antifungal": ["fluconazole", "itraconazole", "terbinafine", "nystatin"],
}


class RxNormService:
    """Service for RxNorm drug lookup and normalization.

    Provides fast lookup of drug information including:
    - Generic/brand name resolution
    - Ingredient extraction
    - Therapeutic class identification
    - NDC to RxCUI mapping

    Usage:
        service = RxNormService()

        # Look up a drug
        result = service.lookup_drug("Lipitor")
        print(f"Generic: {result.generic_name}")  # atorvastatin
        print(f"Class: {result.therapeutic_classes}")  # ['Statins']

        # Normalize drug name
        generic = service.normalize_to_generic("Advil")
        print(generic)  # ibuprofen

        # Get drug ingredients
        ingredients = service.get_ingredients("Percocet")
        print(ingredients)  # ['oxycodone', 'acetaminophen']

        # Find drugs by class
        statins = service.get_drugs_by_class("statins")
    """

    def __init__(self) -> None:
        """Initialize the RxNorm service."""
        self._drugs: list[DrugInfo] = []
        self._brand_to_generic: dict[str, str] = {}
        self._generic_to_brands: dict[str, list[str]] = {}
        self._therapeutic_classes: dict[str, list[str]] = {}
        self._name_index: dict[str, list[int]] = {}  # name -> list of drug indices
        self._rxcui_index: dict[str, int] = {}  # rxcui -> drug index
        self._ingredient_index: dict[str, list[int]] = {}  # ingredient -> drug indices
        self._class_index: dict[str, list[int]] = {}  # class -> drug indices

        self._load_data()
        self._build_indexes()
        logger.info(f"RxNorm service initialized with {len(self._drugs)} drug concepts")

    def _load_data(self) -> None:
        """Load RxNorm data from fixture file."""
        if not FIXTURE_FILE.exists():
            logger.warning(f"RxNorm fixture file not found: {FIXTURE_FILE}")
            return

        try:
            with open(FIXTURE_FILE, "r") as f:
                data = json.load(f)

            # Load concepts
            for concept in data.get("concepts", []):
                drug = DrugInfo(
                    rxcui=str(concept.get("rxcui", concept.get("concept_code", ""))),
                    concept_name=concept.get("concept_name", ""),
                    tty=concept.get("tty", concept.get("concept_class_id", "")),
                    generic_name=concept.get("generic_name", ""),
                    brand_names=concept.get("brand_names", []),
                    ingredients=concept.get("ingredients", []),
                    therapeutic_classes=concept.get("therapeutic_classes", []),
                    dosage_form=concept.get("dosage_form", ""),
                    strength=concept.get("strength", ""),
                    route=concept.get("route", ""),
                    synonyms=concept.get("synonyms", []),
                    ndc_codes=concept.get("ndc_codes", []),
                    omop_concept_id=concept.get("omop_concept_id", concept.get("concept_id")),
                )
                self._drugs.append(drug)

            # Load mappings
            self._brand_to_generic = data.get("brand_to_generic", {})
            self._generic_to_brands = data.get("generic_to_brands", {})
            self._therapeutic_classes = data.get("therapeutic_classes", {})

            # Add additional brand mappings
            for brand, generic in ADDITIONAL_BRAND_MAPPINGS.items():
                if brand.lower() not in self._brand_to_generic:
                    self._brand_to_generic[brand.lower()] = generic.lower()

            logger.info(f"Loaded {len(self._drugs)} drug concepts from fixture")

        except Exception as e:
            logger.error(f"Failed to load RxNorm data: {e}")

    def _build_indexes(self) -> None:
        """Build lookup indexes for fast access."""
        for idx, drug in enumerate(self._drugs):
            # Index by RxCUI
            if drug.rxcui:
                self._rxcui_index[drug.rxcui] = idx

            # Index by name (lowercase)
            name_lower = drug.concept_name.lower()
            if name_lower not in self._name_index:
                self._name_index[name_lower] = []
            self._name_index[name_lower].append(idx)

            # Index by generic name
            if drug.generic_name:
                gen_lower = drug.generic_name.lower()
                if gen_lower not in self._name_index:
                    self._name_index[gen_lower] = []
                if idx not in self._name_index[gen_lower]:
                    self._name_index[gen_lower].append(idx)

            # Index by brand names
            for brand in drug.brand_names:
                brand_lower = brand.lower()
                if brand_lower not in self._name_index:
                    self._name_index[brand_lower] = []
                if idx not in self._name_index[brand_lower]:
                    self._name_index[brand_lower].append(idx)

            # Index by synonyms
            for syn in drug.synonyms:
                syn_lower = syn.lower()
                if syn_lower not in self._name_index:
                    self._name_index[syn_lower] = []
                if idx not in self._name_index[syn_lower]:
                    self._name_index[syn_lower].append(idx)

            # Index by ingredients
            for ingredient in drug.ingredients:
                ing_lower = ingredient.lower()
                if ing_lower not in self._ingredient_index:
                    self._ingredient_index[ing_lower] = []
                if idx not in self._ingredient_index[ing_lower]:
                    self._ingredient_index[ing_lower].append(idx)

            # Index by therapeutic class
            for tc in drug.therapeutic_classes:
                tc_lower = tc.lower()
                if tc_lower not in self._class_index:
                    self._class_index[tc_lower] = []
                if idx not in self._class_index[tc_lower]:
                    self._class_index[tc_lower].append(idx)

        # Also index brand-to-generic mappings
        for brand, generic in self._brand_to_generic.items():
            brand_lower = brand.lower()
            generic_lower = generic.lower()

            # Try to find the generic drug and link
            if generic_lower in self._name_index:
                if brand_lower not in self._name_index:
                    self._name_index[brand_lower] = []
                for idx in self._name_index[generic_lower]:
                    if idx not in self._name_index[brand_lower]:
                        self._name_index[brand_lower].append(idx)

        logger.debug(f"Built indexes: {len(self._name_index)} name entries, "
                    f"{len(self._rxcui_index)} RxCUI entries")

    def _normalize_name(self, name: str) -> str:
        """Normalize a drug name for lookup."""
        # Convert to lowercase
        normalized = name.lower().strip()

        # Remove common suffixes/prefixes
        suffixes = [" tablet", " capsule", " solution", " injection", " cream", " ointment",
                   " gel", " patch", " spray", " inhaler", " mg", " mcg", " ml"]
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()

        # Remove strength patterns like "10mg", "100 mg", etc.
        normalized = re.sub(r'\s*\d+\s*(mg|mcg|ml|g|mg/ml|%)\s*', ' ', normalized).strip()

        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)

        return normalized

    def lookup_drug(self, name: str) -> DrugLookupResult:
        """Look up a drug by name.

        Args:
            name: Drug name (brand, generic, or partial)

        Returns:
            DrugLookupResult with drug information
        """
        normalized = self._normalize_name(name)
        original_lower = name.lower().strip()

        # Try exact match first
        if normalized in self._name_index:
            indices = self._name_index[normalized]
            if indices:
                drug = self._drugs[indices[0]]
                return self._build_lookup_result(
                    query=name,
                    drug=drug,
                    match_type=DrugMatchType.EXACT,
                    alternatives=[self._drugs[i] for i in indices[1:5]]
                )

        # Try brand-to-generic mapping
        if original_lower in self._brand_to_generic:
            generic = self._brand_to_generic[original_lower]
            if generic in self._name_index:
                indices = self._name_index[generic]
                if indices:
                    drug = self._drugs[indices[0]]
                    return self._build_lookup_result(
                        query=name,
                        drug=drug,
                        match_type=DrugMatchType.BRAND,
                        alternatives=[]
                    )

        if normalized in self._brand_to_generic:
            generic = self._brand_to_generic[normalized]
            if generic in self._name_index:
                indices = self._name_index[generic]
                if indices:
                    drug = self._drugs[indices[0]]
                    return self._build_lookup_result(
                        query=name,
                        drug=drug,
                        match_type=DrugMatchType.BRAND,
                        alternatives=[]
                    )

        # Try ingredient lookup
        if normalized in self._ingredient_index:
            indices = self._ingredient_index[normalized]
            # Find the ingredient entry (TTY=IN)
            for idx in indices:
                drug = self._drugs[idx]
                if drug.tty == "IN":
                    return self._build_lookup_result(
                        query=name,
                        drug=drug,
                        match_type=DrugMatchType.INGREDIENT,
                        alternatives=[self._drugs[i] for i in indices if i != idx][:5]
                    )
            # Return first match if no ingredient entry found
            if indices:
                drug = self._drugs[indices[0]]
                return self._build_lookup_result(
                    query=name,
                    drug=drug,
                    match_type=DrugMatchType.INGREDIENT,
                    alternatives=[self._drugs[i] for i in indices[1:5]]
                )

        # Try partial match
        partial_matches = []
        for idx_name, indices in self._name_index.items():
            if normalized in idx_name or idx_name in normalized:
                partial_matches.extend(indices)

        if partial_matches:
            # Deduplicate and sort by relevance
            partial_matches = list(set(partial_matches))[:10]
            drug = self._drugs[partial_matches[0]]
            return self._build_lookup_result(
                query=name,
                drug=drug,
                match_type=DrugMatchType.PARTIAL,
                alternatives=[self._drugs[i] for i in partial_matches[1:5]]
            )

        # Fuzzy match - check for similar names
        fuzzy_matches = self._fuzzy_search(normalized, limit=5)
        if fuzzy_matches:
            return self._build_lookup_result(
                query=name,
                drug=fuzzy_matches[0],
                match_type=DrugMatchType.FUZZY,
                alternatives=fuzzy_matches[1:5]
            )

        # Not found
        return DrugLookupResult(
            query=name,
            found=False,
            match_type=None,
            drug_info=None,
            generic_name=None,
            brand_names=[],
            ingredients=[],
            therapeutic_classes=[],
            alternatives=[],
        )

    def _build_lookup_result(
        self,
        query: str,
        drug: DrugInfo,
        match_type: DrugMatchType,
        alternatives: list[DrugInfo],
    ) -> DrugLookupResult:
        """Build a lookup result from drug info."""
        # Get generic name
        generic_name = drug.generic_name
        if not generic_name and drug.tty == "IN":
            generic_name = drug.concept_name.lower()

        # Get brand names
        brand_names = list(drug.brand_names)
        if generic_name and generic_name in self._generic_to_brands:
            brand_names = list(set(brand_names + self._generic_to_brands[generic_name]))

        # Get ingredients
        ingredients = list(drug.ingredients)
        if not ingredients and generic_name:
            ingredients = [generic_name]

        return DrugLookupResult(
            query=query,
            found=True,
            match_type=match_type,
            drug_info=drug,
            generic_name=generic_name,
            brand_names=brand_names,
            ingredients=ingredients,
            therapeutic_classes=list(drug.therapeutic_classes),
            alternatives=alternatives,
        )

    def _fuzzy_search(self, query: str, limit: int = 5) -> list[DrugInfo]:
        """Perform fuzzy search for drug name."""
        matches = []
        query_lower = query.lower()

        for idx, drug in enumerate(self._drugs):
            name_lower = drug.concept_name.lower()
            generic_lower = drug.generic_name.lower() if drug.generic_name else ""

            # Check if query is contained in name
            if query_lower in name_lower or query_lower in generic_lower:
                matches.append((idx, 0.8))
                continue

            # Check if name starts with query
            if name_lower.startswith(query_lower) or generic_lower.startswith(query_lower):
                matches.append((idx, 0.9))
                continue

            # Simple Levenshtein-like check (first 3 chars match)
            if len(query_lower) >= 3:
                if (name_lower[:3] == query_lower[:3] or
                    (generic_lower and generic_lower[:3] == query_lower[:3])):
                    matches.append((idx, 0.5))

        # Sort by score and return top matches
        matches.sort(key=lambda x: x[1], reverse=True)
        return [self._drugs[idx] for idx, _ in matches[:limit]]

    def normalize_to_generic(self, name: str) -> str | None:
        """Normalize a drug name to its generic equivalent.

        Args:
            name: Drug name (brand or generic)

        Returns:
            Generic drug name or None if not found
        """
        normalized = self._normalize_name(name)
        original_lower = name.lower().strip()

        # Check brand-to-generic mapping
        if original_lower in self._brand_to_generic:
            return self._brand_to_generic[original_lower]

        if normalized in self._brand_to_generic:
            return self._brand_to_generic[normalized]

        # Look up drug
        result = self.lookup_drug(name)
        if result.found and result.generic_name:
            return result.generic_name

        # If it's already an ingredient, return it
        if normalized in self._ingredient_index:
            return normalized

        return None

    def get_brand_names(self, generic_name: str) -> list[str]:
        """Get all brand names for a generic drug.

        Args:
            generic_name: Generic drug name

        Returns:
            List of brand names
        """
        normalized = generic_name.lower().strip()

        # Check mapping
        if normalized in self._generic_to_brands:
            return self._generic_to_brands[normalized]

        # Search drugs
        brands = set()
        if normalized in self._name_index:
            for idx in self._name_index[normalized]:
                drug = self._drugs[idx]
                brands.update(drug.brand_names)

        return list(brands)

    def get_ingredients(self, drug_name: str) -> list[str]:
        """Get active ingredients for a drug.

        Args:
            drug_name: Drug name (brand or generic)

        Returns:
            List of ingredient names
        """
        result = self.lookup_drug(drug_name)
        if result.found:
            return result.ingredients

        # Try normalizing first
        generic = self.normalize_to_generic(drug_name)
        if generic:
            return [generic]

        return []

    def get_therapeutic_class(self, drug_name: str) -> list[str]:
        """Get therapeutic class(es) for a drug.

        Args:
            drug_name: Drug name

        Returns:
            List of therapeutic class names
        """
        result = self.lookup_drug(drug_name)
        if result.found and result.therapeutic_classes:
            return result.therapeutic_classes

        # Try to infer from drug class keywords
        normalized = self.normalize_to_generic(drug_name) or drug_name.lower()
        for class_name, drugs in DRUG_CLASS_KEYWORDS.items():
            if normalized in [d.lower() for d in drugs]:
                return [class_name.title()]

        return []

    def get_drugs_by_class(self, class_name: str) -> DrugClassLookupResult:
        """Get all drugs in a therapeutic class.

        Args:
            class_name: Therapeutic class name

        Returns:
            DrugClassLookupResult with matching drugs
        """
        class_lower = class_name.lower().strip()

        # Check class index
        drugs = []
        if class_lower in self._class_index:
            drugs = [self._drugs[idx] for idx in self._class_index[class_lower]]

        # Also check therapeutic_classes mapping
        if class_lower in self._therapeutic_classes:
            drug_names = self._therapeutic_classes[class_lower]
            for drug_name in drug_names:
                if drug_name in self._name_index:
                    for idx in self._name_index[drug_name]:
                        drug = self._drugs[idx]
                        if drug not in drugs:
                            drugs.append(drug)

        # Check keyword mappings
        if class_lower in DRUG_CLASS_KEYWORDS:
            for drug_name in DRUG_CLASS_KEYWORDS[class_lower]:
                result = self.lookup_drug(drug_name)
                if result.found and result.drug_info and result.drug_info not in drugs:
                    drugs.append(result.drug_info)

        return DrugClassLookupResult(
            class_name=class_name,
            drugs=drugs,
            total_count=len(drugs),
        )

    def lookup_by_rxcui(self, rxcui: str) -> DrugInfo | None:
        """Look up a drug by RxCUI.

        Args:
            rxcui: RxNorm Concept Unique Identifier

        Returns:
            DrugInfo or None if not found
        """
        if rxcui in self._rxcui_index:
            return self._drugs[self._rxcui_index[rxcui]]
        return None

    def lookup_by_ndc(self, ndc: str) -> NDCLookupResult:
        """Look up a drug by NDC code.

        Args:
            ndc: National Drug Code

        Returns:
            NDCLookupResult
        """
        # Normalize NDC (remove dashes)
        normalized_ndc = ndc.replace("-", "")

        for drug in self._drugs:
            if ndc in drug.ndc_codes or normalized_ndc in drug.ndc_codes:
                return NDCLookupResult(
                    ndc=ndc,
                    found=True,
                    rxcui=drug.rxcui,
                    drug_info=drug,
                )

        return NDCLookupResult(
            ndc=ndc,
            found=False,
            rxcui=None,
            drug_info=None,
        )

    def search_drugs(
        self,
        query: str,
        limit: int = 20,
        include_ingredients: bool = True,
        include_brands: bool = True,
        tty_filter: list[str] | None = None,
    ) -> list[DrugInfo]:
        """Search for drugs by name.

        Args:
            query: Search query
            limit: Maximum results to return
            include_ingredients: Include ingredient matches
            include_brands: Include brand name matches
            tty_filter: Filter by term types (e.g., ['IN', 'BN'])

        Returns:
            List of matching DrugInfo
        """
        query_lower = query.lower().strip()
        results = []
        seen = set()

        # Exact matches first
        if query_lower in self._name_index:
            for idx in self._name_index[query_lower]:
                drug = self._drugs[idx]
                if tty_filter and drug.tty not in tty_filter:
                    continue
                if drug.rxcui not in seen:
                    results.append(drug)
                    seen.add(drug.rxcui)

        # Partial matches
        for name, indices in self._name_index.items():
            if query_lower in name:
                for idx in indices:
                    drug = self._drugs[idx]
                    if tty_filter and drug.tty not in tty_filter:
                        continue
                    if drug.rxcui not in seen:
                        results.append(drug)
                        seen.add(drug.rxcui)
                        if len(results) >= limit * 2:  # Get extra for sorting
                            break

        # Sort by relevance (exact matches first, then by name length)
        def sort_key(d: DrugInfo) -> tuple[int, int]:
            name_lower = d.concept_name.lower()
            exact = 0 if name_lower == query_lower else 1
            return (exact, len(name_lower))

        results.sort(key=sort_key)
        return results[:limit]

    def get_all_therapeutic_classes(self) -> list[str]:
        """Get all available therapeutic classes.

        Returns:
            List of therapeutic class names
        """
        classes = set(self._class_index.keys())
        classes.update(self._therapeutic_classes.keys())
        classes.update(DRUG_CLASS_KEYWORDS.keys())
        return sorted(classes)

    def is_drug_in_class(self, drug_name: str, class_name: str) -> bool:
        """Check if a drug belongs to a therapeutic class.

        Args:
            drug_name: Drug name
            class_name: Therapeutic class name

        Returns:
            True if drug is in the class
        """
        classes = self.get_therapeutic_class(drug_name)
        return class_name.lower() in [c.lower() for c in classes]

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the RxNorm database.

        Returns:
            Dictionary with database statistics
        """
        tty_counts: dict[str, int] = {}
        with_class = 0
        with_ingredients = 0

        for drug in self._drugs:
            tty = drug.tty or "unknown"
            tty_counts[tty] = tty_counts.get(tty, 0) + 1
            if drug.therapeutic_classes:
                with_class += 1
            if drug.ingredients:
                with_ingredients += 1

        return {
            "total_drugs": len(self._drugs),
            "total_brand_mappings": len(self._brand_to_generic),
            "total_name_entries": len(self._name_index),
            "total_therapeutic_classes": len(self.get_all_therapeutic_classes()),
            "by_term_type": tty_counts,
            "with_therapeutic_class": with_class,
            "with_ingredients": with_ingredients,
        }


# ============================================================================
# Singleton Pattern
# ============================================================================

_rxnorm_service: RxNormService | None = None
_rxnorm_lock = Lock()


def get_rxnorm_service() -> RxNormService:
    """Get the singleton RxNormService instance.

    Returns:
        The singleton RxNormService instance.
    """
    global _rxnorm_service

    if _rxnorm_service is None:
        with _rxnorm_lock:
            if _rxnorm_service is None:
                logger.info("Creating singleton RxNormService instance")
                _rxnorm_service = RxNormService()

    return _rxnorm_service


def reset_rxnorm_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _rxnorm_service
    with _rxnorm_lock:
        _rxnorm_service = None
