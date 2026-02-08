"""Phenotype Definition Service for cohort identification (CSO-2.3).

Replaces simple ILIKE '%term%' string matching with structured concept set
matching for clinical trial cohort identification. A phenotype is defined
by a set of OMOP concept IDs, ICD-10 codes, and text patterns that together
identify a clinical condition with higher precision and recall.

Matching priority (highest confidence first):
  1. OMOP concept ID match -> confidence 1.0
  2. ICD code match (prefix) -> confidence 0.95
  3. Text pattern match     -> confidence 0.80

Usage:
    from app.services.phenotype_service import get_phenotype_definition_service

    service = get_phenotype_definition_service()
    phenotype = service.define_phenotype(
        name="type_2_diabetes",
        concept_ids=[201826, 443238],
        icd_codes=["E11", "E11.9"],
        text_patterns=["type 2 diabetes", "T2DM"],
        domain="condition",
    )
    match = service.match_phenotype(patient_facts, phenotype)
"""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any

from app.schemas.phenotype import (
    MatchedFact,
    Phenotype,
    PhenotypeCreate,
    PhenotypeLibrary,
    PhenotypeMatch,
    PhenotypeMatchMethod,
)

logger = logging.getLogger(__name__)

# Confidence weights for each match method.
# OMOP concept ID is the gold standard (exact vocabulary match).
# ICD code is near-exact (administrative code, prefix matching).
# Text pattern is the weakest (free-text, case-insensitive substring).
_CONFIDENCE_CONCEPT_ID = 1.0
_CONFIDENCE_ICD_CODE = 0.95
_CONFIDENCE_TEXT_PATTERN = 0.80


class PhenotypeDefinitionService:
    """In-memory registry of phenotype definitions for cohort identification.

    Thread-safe singleton pattern. Pre-loads phenotypes for the three
    Regeneron clinical trials (DME, Atopic Dermatitis, Cutaneous SCC).
    """

    def __init__(self) -> None:
        self._registry: dict[str, Phenotype] = {}
        self._lock = threading.Lock()
        self._init_trial_phenotypes()

    # =========================================================================
    # Pre-loaded phenotypes for Regeneron trials
    # =========================================================================

    def _init_trial_phenotypes(self) -> None:
        """Pre-load phenotype definitions for the three Regeneron trials.

        These cover the primary indications:
        - Diabetic Macular Edema (DME) for EYLEA HD
        - Atopic Dermatitis (AD) for DUPIXENT / LIBERTY ADCHRONOS
        - Cutaneous Squamous Cell Carcinoma (cSCC) for LIBTAYO
        """
        trial_phenotypes = [
            # --- DME / EYLEA HD ---
            PhenotypeCreate(
                name="diabetic_macular_edema",
                domain="condition",
                concept_ids=[4174977, 443727],  # DME, Macular edema
                icd_codes=["H35.81", "E11.311", "E11.3211", "E11.3291"],
                text_patterns=[
                    "diabetic macular edema",
                    "DME",
                    "macular edema",
                    "diabetic retinopathy with macular edema",
                ],
                description="Diabetic Macular Edema - primary indication for EYLEA HD trial (NCT04429503)",
                version="1.0",
            ),
            PhenotypeCreate(
                name="type_2_diabetes",
                domain="condition",
                concept_ids=[201826, 443238, 4193704],
                icd_codes=["E11", "E11.9", "E11.65", "E11.8"],
                text_patterns=[
                    "type 2 diabetes",
                    "T2DM",
                    "type II diabetes",
                    "DM2",
                    "diabetes mellitus type 2",
                    "non-insulin dependent diabetes",
                ],
                description="Type 2 Diabetes Mellitus - required comorbidity for EYLEA HD trial",
                version="1.0",
            ),
            PhenotypeCreate(
                name="diabetic_retinopathy",
                domain="condition",
                concept_ids=[443731, 4174977],
                icd_codes=["E11.31", "E11.32", "E11.33", "E11.34", "E11.35", "H35.0"],
                text_patterns=[
                    "diabetic retinopathy",
                    "nonproliferative diabetic retinopathy",
                    "proliferative diabetic retinopathy",
                    "NPDR",
                    "PDR",
                ],
                description="Diabetic Retinopathy - associated condition for EYLEA HD trial",
                version="1.0",
            ),
            # --- Atopic Dermatitis / DUPIXENT ---
            PhenotypeCreate(
                name="atopic_dermatitis",
                domain="condition",
                concept_ids=[4152283, 140168, 4182711],
                icd_codes=["L20", "L20.0", "L20.81", "L20.82", "L20.84", "L20.89", "L20.9"],
                text_patterns=[
                    "atopic dermatitis",
                    "atopic eczema",
                    "eczema",
                    "AD",
                    "dermatitis atopic",
                ],
                description="Atopic Dermatitis - primary indication for LIBERTY ADCHRONOS / Dupixent trial (NCT02395133)",
                version="1.0",
            ),
            # --- Cutaneous SCC / LIBTAYO ---
            PhenotypeCreate(
                name="cutaneous_squamous_cell_carcinoma",
                domain="condition",
                concept_ids=[4068155, 4310566, 46273614],
                icd_codes=["C44.9", "C44.92", "C44.02", "C44.12", "C44.22", "C44.32", "C44.42"],
                text_patterns=[
                    "cutaneous squamous cell carcinoma",
                    "squamous cell carcinoma of skin",
                    "cSCC",
                    "CSCC",
                    "squamous cell carcinoma skin",
                    "SCC of the skin",
                ],
                description="Cutaneous Squamous Cell Carcinoma - primary indication for LIBTAYO / Cemiplimab trial (NCT02760498)",
                version="1.0",
            ),
            # --- Exclusion phenotypes ---
            PhenotypeCreate(
                name="active_tuberculosis",
                domain="condition",
                concept_ids=[434557, 253954],
                icd_codes=["A15", "A15.0", "A15.4", "A15.5", "A15.6", "A15.7", "A15.8", "A15.9"],
                text_patterns=[
                    "tuberculosis",
                    "TB",
                    "active tuberculosis",
                    "pulmonary tuberculosis",
                ],
                description="Active Tuberculosis - exclusion criterion for DUPIXENT trial",
                version="1.0",
            ),
            PhenotypeCreate(
                name="active_malignancy",
                domain="condition",
                concept_ids=[443392, 4311499],
                icd_codes=["C80", "C80.1"],
                text_patterns=[
                    "malignant neoplasm",
                    "cancer",
                    "malignancy",
                    "active cancer",
                ],
                description="Active Malignancy - exclusion criterion for DUPIXENT trial",
                version="1.0",
            ),
            PhenotypeCreate(
                name="autoimmune_disease",
                domain="condition",
                concept_ids=[4134440, 257628],
                icd_codes=["M35.9", "M35", "M32", "M33", "M34"],
                text_patterns=[
                    "autoimmune disease",
                    "autoimmune disorder",
                    "systemic autoimmune",
                    "connective tissue disease",
                ],
                description="Autoimmune Disease - exclusion criterion for LIBTAYO trial",
                version="1.0",
            ),
        ]

        for phenotype_create in trial_phenotypes:
            self._register_phenotype(phenotype_create)

        logger.info(
            f"Pre-loaded {len(trial_phenotypes)} trial phenotype definitions "
            f"for Regeneron cohort identification"
        )

    # =========================================================================
    # Public API
    # =========================================================================

    def define_phenotype(
        self,
        name: str,
        concept_ids: list[int] | None = None,
        icd_codes: list[str] | None = None,
        text_patterns: list[str] | None = None,
        domain: str = "condition",
        description: str = "",
        version: str = "1.0",
    ) -> Phenotype:
        """Define or update a phenotype in the registry.

        Args:
            name: Unique identifier for the phenotype.
            concept_ids: OMOP standard concept IDs.
            icd_codes: ICD-10-CM codes (prefix matching).
            text_patterns: Case-insensitive text patterns.
            domain: Clinical domain (condition, drug, measurement, etc.).
            description: Human-readable description.
            version: Version string.

        Returns:
            The created/updated Phenotype.
        """
        create = PhenotypeCreate(
            name=name,
            domain=domain,
            concept_ids=concept_ids or [],
            icd_codes=icd_codes or [],
            text_patterns=text_patterns or [],
            description=description,
            version=version,
        )
        return self._register_phenotype(create)

    def define_phenotype_from_schema(self, create: PhenotypeCreate) -> Phenotype:
        """Define a phenotype from a PhenotypeCreate schema.

        Args:
            create: The phenotype creation schema.

        Returns:
            The created/updated Phenotype.
        """
        return self._register_phenotype(create)

    def get_phenotype(self, name: str) -> Phenotype | None:
        """Get a phenotype definition by name.

        Args:
            name: The phenotype name.

        Returns:
            The Phenotype if found, else None.
        """
        with self._lock:
            return self._registry.get(name)

    def list_phenotypes(self) -> PhenotypeLibrary:
        """List all registered phenotype definitions.

        Returns:
            PhenotypeLibrary with all phenotypes and total count.
        """
        with self._lock:
            phenotypes = list(self._registry.values())
        return PhenotypeLibrary(
            phenotypes=phenotypes,
            total=len(phenotypes),
        )

    def delete_phenotype(self, name: str) -> bool:
        """Remove a phenotype from the registry.

        Args:
            name: The phenotype name to remove.

        Returns:
            True if deleted, False if not found.
        """
        with self._lock:
            if name in self._registry:
                del self._registry[name]
                logger.info(f"Deleted phenotype: {name}")
                return True
            return False

    def match_phenotype(
        self,
        patient_facts: list[dict[str, Any]],
        phenotype: Phenotype | str,
    ) -> PhenotypeMatch:
        """Match a phenotype against a list of patient clinical facts.

        Attempts to match using three strategies in order of confidence:
        1. OMOP concept ID exact match (confidence 1.0)
        2. ICD code prefix match on source_code (confidence 0.95)
        3. Text pattern substring match on concept_name (confidence 0.80)

        A fact is only counted once even if it matches multiple methods.
        The highest-confidence method is used for each fact.

        Args:
            patient_facts: List of dicts with keys:
                - fact_id (str)
                - omop_concept_id (int)
                - concept_name (str)
                - domain (str)
                - source_code (str | None)
                - confidence (float)
                - assertion (str, default "present")
            phenotype: Either a Phenotype object or a phenotype name string.

        Returns:
            PhenotypeMatch with match status, confidence, and matched facts.
        """
        # Resolve phenotype name to object if needed
        if isinstance(phenotype, str):
            resolved = self.get_phenotype(phenotype)
            if resolved is None:
                return PhenotypeMatch(
                    phenotype_name=phenotype,
                    matched=False,
                    confidence=0.0,
                    matched_facts=[],
                    match_methods=[],
                )
            phenotype = resolved

        concept_id_set = set(phenotype.concept_ids)
        icd_code_prefixes = [code.upper() for code in phenotype.icd_codes]
        text_patterns_lower = [p.lower() for p in phenotype.text_patterns]

        matched_facts: list[MatchedFact] = []
        seen_fact_ids: set[str] = set()
        methods_used: set[PhenotypeMatchMethod] = set()

        concept_id_count = 0
        icd_code_count = 0
        text_pattern_count = 0

        for fact in patient_facts:
            fact_id = str(fact.get("fact_id", ""))
            omop_concept_id = fact.get("omop_concept_id", 0)
            concept_name = fact.get("concept_name", "")
            domain = fact.get("domain", "")
            source_code = fact.get("source_code")
            fact_confidence = fact.get("confidence", 1.0)
            assertion = fact.get("assertion", "present")

            # Skip negated facts
            if assertion in ("absent", "negated"):
                continue

            # Domain filter: only match facts in the phenotype's domain
            if domain and phenotype.domain and domain != phenotype.domain:
                continue

            if fact_id in seen_fact_ids:
                continue

            # Strategy 1: OMOP concept ID match (highest confidence)
            if omop_concept_id in concept_id_set:
                matched_facts.append(MatchedFact(
                    fact_id=fact_id,
                    concept_name=concept_name,
                    omop_concept_id=omop_concept_id,
                    source_code=source_code,
                    confidence=min(fact_confidence, _CONFIDENCE_CONCEPT_ID),
                    match_method=PhenotypeMatchMethod.CONCEPT_ID,
                ))
                seen_fact_ids.add(fact_id)
                methods_used.add(PhenotypeMatchMethod.CONCEPT_ID)
                concept_id_count += 1
                continue

            # Strategy 2: ICD code prefix match
            if source_code and icd_code_prefixes:
                source_upper = source_code.upper().strip()
                for prefix in icd_code_prefixes:
                    if source_upper == prefix or source_upper.startswith(prefix + ".") or source_upper.startswith(prefix):
                        # More precise check: exact match or prefix with dot
                        if source_upper == prefix or source_upper.startswith(prefix + ".") or (
                            len(source_upper) > len(prefix) and source_upper[len(prefix)] in ".0123456789"
                        ):
                            matched_facts.append(MatchedFact(
                                fact_id=fact_id,
                                concept_name=concept_name,
                                omop_concept_id=omop_concept_id,
                                source_code=source_code,
                                confidence=min(fact_confidence, _CONFIDENCE_ICD_CODE),
                                match_method=PhenotypeMatchMethod.ICD_CODE,
                            ))
                            seen_fact_ids.add(fact_id)
                            methods_used.add(PhenotypeMatchMethod.ICD_CODE)
                            icd_code_count += 1
                            break
                if fact_id in seen_fact_ids:
                    continue

            # Strategy 3: Text pattern match on concept_name
            if concept_name and text_patterns_lower:
                concept_lower = concept_name.lower()
                for pattern in text_patterns_lower:
                    if pattern in concept_lower:
                        matched_facts.append(MatchedFact(
                            fact_id=fact_id,
                            concept_name=concept_name,
                            omop_concept_id=omop_concept_id,
                            source_code=source_code,
                            confidence=min(fact_confidence, _CONFIDENCE_TEXT_PATTERN),
                            match_method=PhenotypeMatchMethod.TEXT_PATTERN,
                        ))
                        seen_fact_ids.add(fact_id)
                        methods_used.add(PhenotypeMatchMethod.TEXT_PATTERN)
                        text_pattern_count += 1
                        break

        # Compute overall confidence
        if matched_facts:
            # Overall confidence is the max confidence of all matched facts
            overall_confidence = max(f.confidence for f in matched_facts)
        else:
            overall_confidence = 0.0

        is_matched = len(matched_facts) > 0

        return PhenotypeMatch(
            phenotype_name=phenotype.name,
            matched=is_matched,
            confidence=round(overall_confidence, 4),
            matched_facts=matched_facts,
            match_methods=sorted(methods_used, key=lambda m: m.value),
            concept_id_matches=concept_id_count,
            icd_code_matches=icd_code_count,
            text_pattern_matches=text_pattern_count,
        )

    def match_phenotype_by_name(
        self,
        patient_facts: list[dict[str, Any]],
        phenotype_name: str,
    ) -> PhenotypeMatch:
        """Match a named phenotype against patient facts.

        Convenience method that looks up the phenotype by name and matches.

        Args:
            patient_facts: List of patient fact dicts.
            phenotype_name: Name of the phenotype to match.

        Returns:
            PhenotypeMatch result.
        """
        return self.match_phenotype(patient_facts, phenotype_name)

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dict with phenotype count and domain breakdown.
        """
        with self._lock:
            phenotypes = list(self._registry.values())

        domain_counts: dict[str, int] = {}
        for p in phenotypes:
            domain_counts[p.domain] = domain_counts.get(p.domain, 0) + 1

        return {
            "total_phenotypes": len(phenotypes),
            "domains": domain_counts,
            "phenotype_names": [p.name for p in phenotypes],
        }

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _register_phenotype(self, create: PhenotypeCreate) -> Phenotype:
        """Register a phenotype in the in-memory registry (thread-safe)."""
        phenotype = Phenotype(
            name=create.name,
            domain=create.domain,
            concept_ids=create.concept_ids,
            icd_codes=create.icd_codes,
            text_patterns=create.text_patterns,
            description=create.description,
            version=create.version,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            is_update = create.name in self._registry
            self._registry[create.name] = phenotype

        action = "Updated" if is_update else "Registered"
        logger.info(
            f"{action} phenotype: {create.name} "
            f"(concepts={len(create.concept_ids)}, "
            f"icd={len(create.icd_codes)}, "
            f"text={len(create.text_patterns)})"
        )
        return phenotype


# =============================================================================
# Singleton
# =============================================================================

_phenotype_service: PhenotypeDefinitionService | None = None
_phenotype_lock = threading.Lock()


def get_phenotype_definition_service() -> PhenotypeDefinitionService:
    """Get the singleton PhenotypeDefinitionService instance."""
    global _phenotype_service
    if _phenotype_service is None:
        with _phenotype_lock:
            if _phenotype_service is None:
                _phenotype_service = PhenotypeDefinitionService()
                logger.info("Initialized PhenotypeDefinitionService")
    return _phenotype_service


def reset_phenotype_definition_service() -> None:
    """Reset the singleton for testing purposes."""
    global _phenotype_service
    with _phenotype_lock:
        _phenotype_service = None
