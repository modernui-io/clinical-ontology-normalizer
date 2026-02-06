"""Concept linking logic for clinical NLP.

This module contains:
- Normalization to standard vocabularies (SNOMED, RxNorm, ICD-10, CPT, LOINC)
- Clinical code mappings
- Integration with terminology services
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from .nlp_entity_normalizers import (
    EntityType,
    NormalizedCode,
    NormalizationVocabulary,
)
from .nlp_entity_extractors import ExtractedEntity

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes for Normalization Results
# ============================================================================


@dataclass
class NormalizationResult:
    """Result of entity normalization."""

    entity_id: str
    original_text: str
    normalized_codes: list[NormalizedCode]
    best_match: NormalizedCode | None
    processing_time_ms: float


# ============================================================================
# Clinical Code Mappings - Curated lookup table for common clinical terms
# ============================================================================

# Comprehensive clinical code mappings
# Format: "Normalized Text": {"VOCABULARY": ("code", "display name")}
CLINICAL_CODE_MAPPINGS: dict[str, dict[str, tuple[str, str]]] = {
    # ========================================================================
    # DIAGNOSES - SNOMED-CT and ICD-10-CM codes
    # ========================================================================
    "Diabetes": {
        "SNOMED-CT": ("73211009", "Diabetes mellitus"),
        "ICD-10-CM": ("E11.9", "Type 2 diabetes mellitus without complications"),
    },
    "Hypertension": {
        "SNOMED-CT": ("38341003", "Hypertensive disorder"),
        "ICD-10-CM": ("I10", "Essential (primary) hypertension"),
    },
    "Heart Failure": {
        "SNOMED-CT": ("84114007", "Heart failure"),
        "ICD-10-CM": ("I50.9", "Heart failure, unspecified"),
    },
    "Coronary Artery Disease": {
        "SNOMED-CT": ("53741008", "Coronary arteriosclerosis"),
        "ICD-10-CM": ("I25.10", "Atherosclerotic heart disease of native coronary artery"),
    },
    "Atrial Fibrillation": {
        "SNOMED-CT": ("49436004", "Atrial fibrillation"),
        "ICD-10-CM": ("I48.91", "Unspecified atrial fibrillation"),
    },
    "Chronic Kidney Disease": {
        "SNOMED-CT": ("709044004", "Chronic kidney disease"),
        "ICD-10-CM": ("N18.9", "Chronic kidney disease, unspecified"),
    },
    "CKD Stage 1": {
        "SNOMED-CT": ("431855005", "Chronic kidney disease stage 1"),
        "ICD-10-CM": ("N18.1", "Chronic kidney disease, stage 1"),
    },
    "CKD Stage 2": {
        "SNOMED-CT": ("431856006", "Chronic kidney disease stage 2"),
        "ICD-10-CM": ("N18.2", "Chronic kidney disease, stage 2"),
    },
    "CKD Stage 3": {
        "SNOMED-CT": ("433144002", "Chronic kidney disease stage 3"),
        "ICD-10-CM": ("N18.3", "Chronic kidney disease, stage 3"),
    },
    "CKD Stage 4": {
        "SNOMED-CT": ("431857002", "Chronic kidney disease stage 4"),
        "ICD-10-CM": ("N18.4", "Chronic kidney disease, stage 4"),
    },
    "CKD Stage 5": {
        "SNOMED-CT": ("433146000", "Chronic kidney disease stage 5"),
        "ICD-10-CM": ("N18.5", "Chronic kidney disease, stage 5"),
    },
    "End Stage Renal Disease": {
        "SNOMED-CT": ("46177005", "End-stage renal disease"),
        "ICD-10-CM": ("N18.6", "End stage renal disease"),
    },
    "COPD": {
        "SNOMED-CT": ("13645005", "Chronic obstructive lung disease"),
        "ICD-10-CM": ("J44.9", "Chronic obstructive pulmonary disease, unspecified"),
    },
    "Asthma": {
        "SNOMED-CT": ("195967001", "Asthma"),
        "ICD-10-CM": ("J45.909", "Unspecified asthma, uncomplicated"),
    },
    "Pneumonia": {
        "SNOMED-CT": ("233604007", "Pneumonia"),
        "ICD-10-CM": ("J18.9", "Pneumonia, unspecified organism"),
    },
    "Stroke": {
        "SNOMED-CT": ("230690007", "Cerebrovascular accident"),
        "ICD-10-CM": ("I63.9", "Cerebral infarction, unspecified"),
    },
    "Myocardial Infarction": {
        "SNOMED-CT": ("22298006", "Myocardial infarction"),
        "ICD-10-CM": ("I21.9", "Acute myocardial infarction, unspecified"),
    },
    "Depression": {
        "SNOMED-CT": ("35489007", "Depressive disorder"),
        "ICD-10-CM": ("F32.9", "Major depressive disorder, single episode, unspecified"),
    },
    "Anxiety": {
        "SNOMED-CT": ("48694002", "Anxiety"),
        "ICD-10-CM": ("F41.9", "Anxiety disorder, unspecified"),
    },
    "Hyperlipidemia": {
        "SNOMED-CT": ("55822004", "Hyperlipidemia"),
        "ICD-10-CM": ("E78.5", "Hyperlipidemia, unspecified"),
    },
    "Hypothyroidism": {
        "SNOMED-CT": ("40930008", "Hypothyroidism"),
        "ICD-10-CM": ("E03.9", "Hypothyroidism, unspecified"),
    },
    "GERD": {
        "SNOMED-CT": ("235595009", "Gastroesophageal reflux disease"),
        "ICD-10-CM": ("K21.0", "Gastro-esophageal reflux disease with esophagitis"),
    },
    "Obesity": {
        "SNOMED-CT": ("414916001", "Obesity"),
        "ICD-10-CM": ("E66.9", "Obesity, unspecified"),
    },
    "Sleep Apnea": {
        "SNOMED-CT": ("73430006", "Sleep apnea"),
        "ICD-10-CM": ("G47.30", "Sleep apnea, unspecified"),
    },
    "Deep Vein Thrombosis": {
        "SNOMED-CT": ("128053003", "Deep venous thrombosis"),
        "ICD-10-CM": ("I82.409", "Acute embolism and thrombosis of unspecified deep veins of lower extremity"),
    },
    "Pulmonary Embolism": {
        "SNOMED-CT": ("59282003", "Pulmonary embolism"),
        "ICD-10-CM": ("I26.99", "Other pulmonary embolism without acute cor pulmonale"),
    },
    "Urinary Tract Infection": {
        "SNOMED-CT": ("68566005", "Urinary tract infection"),
        "ICD-10-CM": ("N39.0", "Urinary tract infection, site not specified"),
    },
    "Sepsis": {
        "SNOMED-CT": ("91302008", "Sepsis"),
        "ICD-10-CM": ("A41.9", "Sepsis, unspecified organism"),
    },
    "Syncope": {
        "SNOMED-CT": ("271594007", "Syncope"),
        "ICD-10-CM": ("R55", "Syncope and collapse"),
    },
    "Dehydration": {
        "SNOMED-CT": ("34095006", "Dehydration"),
        "ICD-10-CM": ("E86.0", "Dehydration"),
    },
    "Acute Kidney Injury": {
        "SNOMED-CT": ("14669001", "Acute kidney injury"),
        "ICD-10-CM": ("N17.9", "Acute kidney failure, unspecified"),
    },
    "Anemia": {
        "SNOMED-CT": ("271737000", "Anemia"),
        "ICD-10-CM": ("D64.9", "Anemia, unspecified"),
    },
    # ========================================================================
    # SYMPTOMS - SNOMED-CT and ICD-10-CM codes
    # ========================================================================
    "Fever": {
        "SNOMED-CT": ("386661006", "Fever"),
        "ICD-10-CM": ("R50.9", "Fever, unspecified"),
    },
    "Cough": {
        "SNOMED-CT": ("49727002", "Cough"),
        "ICD-10-CM": ("R05.9", "Cough, unspecified"),
    },
    "Shortness of Breath": {
        "SNOMED-CT": ("267036007", "Dyspnea"),
        "ICD-10-CM": ("R06.00", "Dyspnea, unspecified"),
    },
    "Chest Pain": {
        "SNOMED-CT": ("29857009", "Chest pain"),
        "ICD-10-CM": ("R07.9", "Chest pain, unspecified"),
    },
    "Abdominal Pain": {
        "SNOMED-CT": ("21522001", "Abdominal pain"),
        "ICD-10-CM": ("R10.9", "Unspecified abdominal pain"),
    },
    "Headache": {
        "SNOMED-CT": ("25064002", "Headache"),
        "ICD-10-CM": ("R51.9", "Headache, unspecified"),
    },
    "Nausea": {
        "SNOMED-CT": ("422587007", "Nausea"),
        "ICD-10-CM": ("R11.0", "Nausea"),
    },
    "Vomiting": {
        "SNOMED-CT": ("422400008", "Vomiting"),
        "ICD-10-CM": ("R11.10", "Vomiting, unspecified"),
    },
    "Diarrhea": {
        "SNOMED-CT": ("62315008", "Diarrhea"),
        "ICD-10-CM": ("R19.7", "Diarrhea, unspecified"),
    },
    "Fatigue": {
        "SNOMED-CT": ("84229001", "Fatigue"),
        "ICD-10-CM": ("R53.83", "Other fatigue"),
    },
    "Dizziness": {
        "SNOMED-CT": ("404640003", "Dizziness"),
        "ICD-10-CM": ("R42", "Dizziness and giddiness"),
    },
    "Weakness": {
        "SNOMED-CT": ("13791008", "Asthenia"),
        "ICD-10-CM": ("R53.1", "Weakness"),
    },
    "Confusion": {
        "SNOMED-CT": ("40917007", "Confusion"),
        "ICD-10-CM": ("R41.0", "Disorientation, unspecified"),
    },
    "Palpitations": {
        "SNOMED-CT": ("80313002", "Palpitations"),
        "ICD-10-CM": ("R00.2", "Palpitations"),
    },
    "Edema": {
        "SNOMED-CT": ("267038008", "Edema"),
        "ICD-10-CM": ("R60.9", "Edema, unspecified"),
    },
    # ========================================================================
    # MEDICATIONS - RxNorm codes
    # ========================================================================
    "Metformin": {
        "RxNorm": ("6809", "Metformin"),
    },
    "Lisinopril": {
        "RxNorm": ("29046", "Lisinopril"),
    },
    "Atorvastatin": {
        "RxNorm": ("83367", "Atorvastatin"),
    },
    "Amlodipine": {
        "RxNorm": ("17767", "Amlodipine"),
    },
    "Aspirin": {
        "RxNorm": ("1191", "Aspirin"),
    },
    "Furosemide": {
        "RxNorm": ("4603", "Furosemide"),
    },
    "Metoprolol": {
        "RxNorm": ("6918", "Metoprolol"),
    },
    "Omeprazole": {
        "RxNorm": ("7646", "Omeprazole"),
    },
    "Insulin": {
        "RxNorm": ("5856", "Insulin"),
    },
    "Warfarin": {
        "RxNorm": ("11289", "Warfarin"),
    },
    "Gabapentin": {
        "RxNorm": ("25480", "Gabapentin"),
    },
    "Sertraline": {
        "RxNorm": ("36437", "Sertraline"),
    },
    "Prednisone": {
        "RxNorm": ("8640", "Prednisone"),
    },
    "Levothyroxine": {
        "RxNorm": ("10582", "Levothyroxine"),
    },
    # ========================================================================
    # PROCEDURES - CPT and SNOMED-CT codes
    # ========================================================================
    "Echocardiogram": {
        "CPT": ("93306", "Echocardiography, transthoracic, complete"),
        "SNOMED-CT": ("40701008", "Echocardiography"),
    },
    "Colonoscopy": {
        "CPT": ("45378", "Colonoscopy, diagnostic"),
        "SNOMED-CT": ("73761001", "Colonoscopy"),
    },
    "CT Scan": {
        "CPT": ("70460", "Computed tomography"),
        "SNOMED-CT": ("77477000", "Computerized axial tomography"),
    },
    "MRI": {
        "CPT": ("70553", "Magnetic resonance imaging"),
        "SNOMED-CT": ("113091000", "Magnetic resonance imaging"),
    },
    "X-Ray": {
        "CPT": ("71046", "Radiologic examination, chest"),
        "SNOMED-CT": ("363680008", "Radiographic imaging procedure"),
    },
    "EKG": {
        "CPT": ("93000", "Electrocardiogram, routine"),
        "SNOMED-CT": ("29303009", "Electrocardiographic procedure"),
    },
    "Dialysis": {
        "CPT": ("90935", "Hemodialysis procedure"),
        "SNOMED-CT": ("108241001", "Dialysis procedure"),
    },
    # ========================================================================
    # LAB RESULTS - LOINC codes
    # ========================================================================
    "Hemoglobin": {
        "LOINC": ("718-7", "Hemoglobin [Mass/volume] in Blood"),
    },
    "Glucose": {
        "LOINC": ("2345-7", "Glucose [Mass/volume] in Serum or Plasma"),
    },
    "Creatinine": {
        "LOINC": ("2160-0", "Creatinine [Mass/volume] in Serum or Plasma"),
    },
    "Sodium": {
        "LOINC": ("2951-2", "Sodium [Moles/volume] in Serum or Plasma"),
    },
    "Potassium": {
        "LOINC": ("2823-3", "Potassium [Moles/volume] in Serum or Plasma"),
    },
    "WBC": {
        "LOINC": ("6690-2", "Leukocytes [#/volume] in Blood"),
    },
    "Platelet": {
        "LOINC": ("777-3", "Platelets [#/volume] in Blood"),
    },
    "BUN": {
        "LOINC": ("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma"),
    },
    "HbA1c": {
        "LOINC": ("4548-4", "Hemoglobin A1c [Mass fraction]"),
    },
    "Troponin": {
        "LOINC": ("6598-7", "Troponin T, cardiac [Mass/volume] in Serum or Plasma"),
    },
    "BNP": {
        "LOINC": ("30934-4", "Natriuretic peptide B [Mass/volume] in Serum or Plasma"),
    },
    "INR": {
        "LOINC": ("34714-6", "INR in Platelet poor plasma by Coagulation assay"),
    },
    # ========================================================================
    # VITAL SIGNS - LOINC codes
    # ========================================================================
    "Blood Pressure": {
        "LOINC": ("55284-4", "Blood pressure systolic and diastolic"),
    },
    "Heart Rate": {
        "LOINC": ("8867-4", "Heart rate"),
    },
    "Temperature": {
        "LOINC": ("8310-5", "Body temperature"),
    },
    "Respiratory Rate": {
        "LOINC": ("9279-1", "Respiratory rate"),
    },
    "Oxygen Saturation": {
        "LOINC": ("59408-5", "Oxygen saturation in Arterial blood by Pulse oximetry"),
    },
    "Weight": {
        "LOINC": ("29463-7", "Body weight"),
    },
    "BMI": {
        "LOINC": ("39156-5", "Body mass index (BMI) [Ratio]"),
    },
}


# ============================================================================
# Linker Mixin Class
# ============================================================================


class LinkerMixin:
    """Mixin providing concept linking and normalization methods."""

    # These will be set by the main class
    _clinical_abbreviations: dict
    _loinc_codes: dict
    _rxnorm_service: Any
    _snomed_service: Any
    _icd10_service: Any
    _cpt_service: Any
    _drug_interactions_service: Any

    def _get_rxnorm_service(self) -> Any:
        """Get the RxNorm terminology service."""
        if self._rxnorm_service is None:
            try:
                from app.services.rxnorm_service import get_rxnorm_service
                self._rxnorm_service = get_rxnorm_service()
            except ImportError:
                pass
        return self._rxnorm_service

    def _get_snomed_service(self) -> Any:
        """Get the SNOMED-CT terminology service."""
        if self._snomed_service is None:
            try:
                from app.services.snomed_service import get_snomed_service
                self._snomed_service = get_snomed_service()
            except ImportError:
                pass
        return self._snomed_service

    def _get_icd10_service(self) -> Any:
        """Get the ICD-10 terminology service."""
        if self._icd10_service is None:
            try:
                from app.services.icd10_service import get_icd10_service
                self._icd10_service = get_icd10_service()
            except ImportError:
                pass
        return self._icd10_service

    def _get_cpt_service(self) -> Any:
        """Get the CPT terminology service."""
        if self._cpt_service is None:
            try:
                from app.services.cpt_service import get_cpt_service
                self._cpt_service = get_cpt_service()
            except ImportError:
                pass
        return self._cpt_service

    def _get_drug_interactions_service(self) -> Any:
        """Get the drug interactions service."""
        if self._drug_interactions_service is None:
            try:
                from app.services.drug_interactions_service import get_drug_interactions_service
                self._drug_interactions_service = get_drug_interactions_service()
            except ImportError:
                pass
        return self._drug_interactions_service

    def normalize_entity(
        self,
        entity: ExtractedEntity,
        vocabularies: list[NormalizationVocabulary] | None = None,
    ) -> NormalizationResult:
        """Normalize an entity to standard vocabulary codes.

        Args:
            entity: The entity to normalize.
            vocabularies: Optional list of vocabularies to use. If None, uses defaults.

        Returns:
            NormalizationResult with matched codes.
        """
        start_time = time.perf_counter()

        if vocabularies is None:
            # Default vocabularies based on entity type
            vocab_map = {
                EntityType.DIAGNOSIS: [NormalizationVocabulary.SNOMED_CT, NormalizationVocabulary.ICD10_CM],
                EntityType.SYMPTOM: [NormalizationVocabulary.SNOMED_CT],
                EntityType.MEDICATION: [NormalizationVocabulary.RXNORM, NormalizationVocabulary.NDC],
                EntityType.PROCEDURE: [NormalizationVocabulary.CPT, NormalizationVocabulary.ICD10_PCS],
                EntityType.LAB_RESULT: [NormalizationVocabulary.LOINC],
                EntityType.VITAL_SIGN: [NormalizationVocabulary.LOINC],
                EntityType.ANATOMICAL_LOCATION: [NormalizationVocabulary.SNOMED_CT],
            }
            vocabularies = vocab_map.get(entity.entity_type, [NormalizationVocabulary.SNOMED_CT])

        # Use real terminology services for normalization
        normalized_codes = self._normalize_with_services(entity, vocabularies)

        processing_time = (time.perf_counter() - start_time) * 1000

        return NormalizationResult(
            entity_id=entity.id,
            original_text=entity.text,
            normalized_codes=normalized_codes,
            best_match=normalized_codes[0] if normalized_codes else None,
            processing_time_ms=round(processing_time, 2),
        )

    def _normalize_with_services(
        self,
        entity: ExtractedEntity,
        vocabularies: list[NormalizationVocabulary],
    ) -> list[NormalizedCode]:
        """Normalize entity using real terminology services.

        Uses comprehensive clinical terminology services:
        - RxNorm for medications
        - SNOMED-CT for diagnoses, symptoms, and anatomical locations
        - ICD-10-CM for diagnoses
        - CPT for procedures
        - LOINC for lab results and vital signs

        Falls back to static CLINICAL_CODE_MAPPINGS if services unavailable.
        """
        # Ensure clinical abbreviations are loaded
        self._load_clinical_abbreviations()

        codes: list[NormalizedCode] = []
        normalized_text = entity.normalized_text
        search_text = normalized_text.lower().strip()

        # Try clinical abbreviations first (fast lookup with OMOP concept IDs)
        abbrev = self._clinical_abbreviations.get(search_text)
        if abbrev:
            omop_id = abbrev.get("omop_concept_id")
            if omop_id:
                codes.append(
                    NormalizedCode(
                        code=str(omop_id),
                        display=abbrev.get("name", normalized_text),
                        system=NormalizationVocabulary.OMOP,
                        confidence=0.95,
                        is_preferred=False,
                    )
                )

        # Try static CLINICAL_CODE_MAPPINGS for exact matches (curated, high-quality)
        static_codes = self._fallback_static_lookup(normalized_text, vocabularies)
        if static_codes:
            codes.extend(static_codes)
        else:
            # Use terminology services based on entity type
            if entity.entity_type == EntityType.MEDICATION:
                codes.extend(self._normalize_medication(normalized_text, vocabularies))
            elif entity.entity_type in (EntityType.DIAGNOSIS, EntityType.SYMPTOM):
                codes.extend(self._normalize_diagnosis(normalized_text, vocabularies))
            elif entity.entity_type == EntityType.PROCEDURE:
                codes.extend(self._normalize_procedure(normalized_text, vocabularies))
            elif entity.entity_type in (EntityType.LAB_RESULT, EntityType.VITAL_SIGN):
                codes.extend(self._normalize_lab_or_vital(normalized_text, vocabularies))

        # Deduplicate codes by (code, system) to prevent duplicates from multiple sources
        seen: set[tuple[str, str]] = set()
        unique_codes: list[NormalizedCode] = []
        for c in codes:
            key = (c.code, c.system.value if hasattr(c.system, 'value') else str(c.system))
            if key not in seen:
                seen.add(key)
                unique_codes.append(c)

        return unique_codes

    def _normalize_medication(
        self, text: str, vocabularies: list[NormalizationVocabulary]
    ) -> list[NormalizedCode]:
        """Normalize medication using RxNorm service."""
        codes: list[NormalizedCode] = []

        if NormalizationVocabulary.RXNORM not in vocabularies:
            return codes

        rxnorm = self._get_rxnorm_service()
        if rxnorm is None:
            return codes

        try:
            result = rxnorm.lookup_drug(text)
            if result.found and result.drug_info:
                drug = result.drug_info
                codes.append(
                    NormalizedCode(
                        code=drug.rxcui,
                        display=drug.generic_name or drug.concept_name,
                        system=NormalizationVocabulary.RXNORM,
                        confidence=0.95 if result.match_type.value == "exact" else 0.85,
                        is_preferred=True,
                    )
                )
                # Add OMOP concept ID if available
                if drug.omop_concept_id:
                    codes[0].code = f"{drug.rxcui} (OMOP: {drug.omop_concept_id})"
        except Exception as e:
            logger.debug(f"RxNorm lookup failed for '{text}': {e}")

        return codes

    def _normalize_diagnosis(
        self, text: str, vocabularies: list[NormalizationVocabulary]
    ) -> list[NormalizedCode]:
        """Normalize diagnosis using SNOMED and ICD-10 services with cross-mapping."""
        codes: list[NormalizedCode] = []
        snomed_codes_for_crossmap: list[str] = []

        # Try SNOMED-CT first
        if NormalizationVocabulary.SNOMED_CT in vocabularies:
            snomed = self._get_snomed_service()
            if snomed:
                try:
                    matches = snomed.match_concept(text, max_results=3)
                    for i, match in enumerate(matches):
                        concept = match.concept
                        codes.append(
                            NormalizedCode(
                                code=str(concept.concept_id),
                                display=concept.concept_name,
                                system=NormalizationVocabulary.SNOMED_CT,
                                confidence=match.score * 0.95,
                                is_preferred=(i == 0),
                            )
                        )
                        if i == 0:
                            snomed_codes_for_crossmap.append(str(concept.concept_id))
                except Exception as e:
                    logger.debug(f"SNOMED lookup failed for '{text}': {e}")

        # Try ICD-10-CM (via cross-map from SNOMED or direct lookup)
        if NormalizationVocabulary.ICD10_CM in vocabularies:
            icd10 = self._get_icd10_service()
            if icd10:
                try:
                    # Try cross-mapping from SNOMED first
                    if snomed_codes_for_crossmap:
                        for snomed_code in snomed_codes_for_crossmap:
                            icd10_codes = icd10.crossmap_from_snomed(snomed_code)
                            for i, icd_code in enumerate(icd10_codes[:2]):
                                codes.append(
                                    NormalizedCode(
                                        code=icd_code.code,
                                        display=icd_code.description,
                                        system=NormalizationVocabulary.ICD10_CM,
                                        confidence=0.90 if i == 0 else 0.80,
                                        is_preferred=(i == 0 and not any(c.system == NormalizationVocabulary.SNOMED_CT for c in codes)),
                                    )
                                )
                    else:
                        # Direct search
                        matches = icd10.search(text, max_results=2)
                        for i, match in enumerate(matches):
                            codes.append(
                                NormalizedCode(
                                    code=match.code,
                                    display=match.description,
                                    system=NormalizationVocabulary.ICD10_CM,
                                    confidence=match.score * 0.90,
                                    is_preferred=(i == 0),
                                )
                            )
                except Exception as e:
                    logger.debug(f"ICD-10 lookup failed for '{text}': {e}")

        return codes

    def _normalize_procedure(
        self, text: str, vocabularies: list[NormalizationVocabulary]
    ) -> list[NormalizedCode]:
        """Normalize procedure using CPT and SNOMED services."""
        codes: list[NormalizedCode] = []

        # Try CPT first
        if NormalizationVocabulary.CPT in vocabularies:
            cpt = self._get_cpt_service()
            if cpt:
                try:
                    matches = cpt.search(text, max_results=2)
                    for i, match in enumerate(matches):
                        codes.append(
                            NormalizedCode(
                                code=match.code,
                                display=match.description,
                                system=NormalizationVocabulary.CPT,
                                confidence=match.score * 0.90,
                                is_preferred=(i == 0),
                            )
                        )
                except Exception as e:
                    logger.debug(f"CPT lookup failed for '{text}': {e}")

        # Try SNOMED-CT procedure concepts
        if NormalizationVocabulary.SNOMED_CT in vocabularies:
            snomed = self._get_snomed_service()
            if snomed:
                try:
                    from app.services.snomed_service import SemanticType
                    matches = snomed.match_concept(
                        text, max_results=2, semantic_types=[SemanticType.PROCEDURE]
                    )
                    for match in matches:
                        concept = match.concept
                        codes.append(
                            NormalizedCode(
                                code=str(concept.concept_id),
                                display=concept.concept_name,
                                system=NormalizationVocabulary.SNOMED_CT,
                                confidence=match.score * 0.90,
                                is_preferred=(len(codes) == 0),
                            )
                        )
                except Exception as e:
                    logger.debug(f"SNOMED procedure lookup failed for '{text}': {e}")

        return codes

    def _normalize_lab_or_vital(
        self, text: str, vocabularies: list[NormalizationVocabulary]
    ) -> list[NormalizedCode]:
        """Normalize lab result or vital sign using LOINC data."""
        codes: list[NormalizedCode] = []

        if NormalizationVocabulary.LOINC not in vocabularies:
            return codes

        # Search in LOINC codes loaded from fixture
        search_text = text.lower().strip()

        # Try exact match first
        loinc_concept = self._loinc_codes.get(search_text)
        if loinc_concept:
            codes.append(
                NormalizedCode(
                    code=loinc_concept.get("concept_code", ""),
                    display=loinc_concept.get("concept_name", text),
                    system=NormalizationVocabulary.LOINC,
                    confidence=0.95,
                    is_preferred=True,
                )
            )
        else:
            # Try partial match on common lab names
            seen_codes: set[str] = set()
            for key, concept in self._loinc_codes.items():
                if isinstance(key, str) and search_text in key:
                    code = concept.get("concept_code", "")
                    # Skip if we've already added this code (deduplication)
                    if code in seen_codes:
                        continue
                    seen_codes.add(code)
                    codes.append(
                        NormalizedCode(
                            code=code,
                            display=concept.get("concept_name", text),
                            system=NormalizationVocabulary.LOINC,
                            confidence=0.80,
                            is_preferred=(len(codes) == 0),
                        )
                    )
                    if len(codes) >= 3:
                        break

        return codes

    def _fallback_static_lookup(
        self, normalized_text: str, vocabularies: list[NormalizationVocabulary]
    ) -> list[NormalizedCode]:
        """Fall back to static CLINICAL_CODE_MAPPINGS lookup."""
        codes: list[NormalizedCode] = []

        if normalized_text in CLINICAL_CODE_MAPPINGS:
            for vocab in vocabularies:
                vocab_key = vocab.value
                if vocab_key in CLINICAL_CODE_MAPPINGS[normalized_text]:
                    code, display = CLINICAL_CODE_MAPPINGS[normalized_text][vocab_key]
                    codes.append(
                        NormalizedCode(
                            code=code,
                            display=display,
                            system=vocab,
                            confidence=0.85,
                            is_preferred=len(codes) == 0,
                        )
                    )

        return codes

    def _mock_normalize(
        self,
        entity: ExtractedEntity,
        vocabularies: list[NormalizationVocabulary],
    ) -> list[NormalizedCode]:
        """Normalize entity to standard vocabulary codes.

        This method now uses real terminology services when available,
        with fallback to static mappings.
        """
        return self._normalize_with_services(entity, vocabularies)

    def check_drug_interactions(
        self,
        medication_entities: list[ExtractedEntity],
    ) -> list[dict]:
        """Check for drug-drug interactions between extracted medications.

        Args:
            medication_entities: List of medication entities.

        Returns:
            List of interaction results.
        """
        interactions: list[dict] = []

        service = self._get_drug_interactions_service()
        if service is None:
            return interactions

        # Get RxCUIs for all medications
        rxcuis = []
        for entity in medication_entities:
            if entity.entity_type != EntityType.MEDICATION:
                continue

            # Look up RxCUI
            rxnorm = self._get_rxnorm_service()
            if rxnorm:
                try:
                    result = rxnorm.lookup_drug(entity.normalized_text)
                    if result.found and result.drug_info:
                        rxcuis.append({
                            "rxcui": result.drug_info.rxcui,
                            "name": entity.normalized_text,
                            "entity_id": entity.id,
                        })
                except Exception:
                    pass

        # Check pairwise interactions
        for i, drug1 in enumerate(rxcuis):
            for drug2 in rxcuis[i + 1:]:
                try:
                    result = service.check_interaction(drug1["rxcui"], drug2["rxcui"])
                    if result.has_interaction:
                        interactions.append({
                            "drug1": drug1["name"],
                            "drug1_id": drug1["entity_id"],
                            "drug2": drug2["name"],
                            "drug2_id": drug2["entity_id"],
                            "severity": result.severity.value if result.severity else "unknown",
                            "description": result.description,
                        })
                except Exception as e:
                    logger.debug(f"Drug interaction check failed: {e}")

        return interactions
