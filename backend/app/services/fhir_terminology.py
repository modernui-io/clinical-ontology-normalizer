"""FHIR R4 Terminology Services.

This module provides FHIR R4 compliant terminology services for clinical code systems.

Implements the following FHIR Terminology Service operations:
- $lookup: Returns concept details for a code in a code system
- $validate-code: Validates that a code is valid within a code system
- $expand: Expands a ValueSet to list its contained codes
- $translate: Translates a code from one code system to another
- $subsumes: Tests the subsumption relationship between two codes
- $closure: Computes the transitive closure of subsumption relationships

Supported code systems:
- SNOMED CT (http://snomed.info/sct)
- ICD-10-CM (http://hl7.org/fhir/sid/icd-10-cm)
- RxNorm (http://www.nlm.nih.gov/research/umls/rxnorm)
- CPT (http://www.ama-assn.org/go/cpt)
- LOINC (http://loinc.org)

Note: This service provides terminology services using locally loaded vocabulary data.
For full terminology services, consider integrating with a terminology server.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# FHIR Code System URIs
# =============================================================================

class CodeSystemURI(str, Enum):
    """Standard FHIR code system URIs."""

    SNOMED = "http://snomed.info/sct"
    ICD10CM = "http://hl7.org/fhir/sid/icd-10-cm"
    ICD10PCS = "http://hl7.org/fhir/sid/icd-10-pcs"
    RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
    CPT = "http://www.ama-assn.org/go/cpt"
    HCPCS = "http://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets"
    LOINC = "http://loinc.org"
    NDC = "http://hl7.org/fhir/sid/ndc"

    @classmethod
    def from_string(cls, uri: str) -> "CodeSystemURI | None":
        """Get CodeSystemURI from string, handling various formats."""
        uri_lower = uri.lower().strip()

        # Direct match
        for member in cls:
            if member.value.lower() == uri_lower:
                return member

        # Common aliases
        aliases = {
            "snomed": cls.SNOMED,
            "snomed-ct": cls.SNOMED,
            "snomedct": cls.SNOMED,
            "icd10": cls.ICD10CM,
            "icd-10": cls.ICD10CM,
            "icd10cm": cls.ICD10CM,
            "icd-10-cm": cls.ICD10CM,
            "icd10pcs": cls.ICD10PCS,
            "icd-10-pcs": cls.ICD10PCS,
            "rxnorm": cls.RXNORM,
            "rx-norm": cls.RXNORM,
            "cpt": cls.CPT,
            "cpt4": cls.CPT,
            "cpt-4": cls.CPT,
            "hcpcs": cls.HCPCS,
            "loinc": cls.LOINC,
            "ndc": cls.NDC,
        }

        return aliases.get(uri_lower)


# =============================================================================
# FHIR Data Types
# =============================================================================

@dataclass
class Coding:
    """FHIR Coding data type."""

    system: str
    code: str
    display: str = ""
    version: str | None = None
    userSelected: bool = False


@dataclass
class CodeableConcept:
    """FHIR CodeableConcept data type."""

    coding: list[Coding] = field(default_factory=list)
    text: str = ""


@dataclass
class Designation:
    """FHIR CodeSystem concept designation."""

    language: str = "en"
    use: Coding | None = None
    value: str = ""


@dataclass
class ConceptProperty:
    """FHIR CodeSystem concept property."""

    code: str
    valueCode: str | None = None
    valueString: str | None = None
    valueBoolean: bool | None = None
    valueInteger: int | None = None
    valueCoding: Coding | None = None


@dataclass
class LookupResult:
    """Result of a $lookup operation."""

    name: str  # Code system name
    version: str | None
    display: str
    designation: list[Designation] = field(default_factory=list)
    property: list[ConceptProperty] = field(default_factory=list)


@dataclass
class ValidateCodeResult:
    """Result of a $validate-code operation."""

    result: bool
    message: str | None = None
    display: str | None = None
    code: str | None = None
    system: str | None = None


@dataclass
class ValueSetExpansionContains:
    """A concept in a ValueSet expansion."""

    system: str
    code: str
    display: str
    version: str | None = None
    inactive: bool = False
    abstract: bool = False
    contains: list["ValueSetExpansionContains"] = field(default_factory=list)


@dataclass
class ValueSetExpansion:
    """FHIR ValueSet expansion."""

    identifier: str
    timestamp: str
    total: int
    offset: int = 0
    contains: list[ValueSetExpansionContains] = field(default_factory=list)
    parameter: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TranslateMatch:
    """A match in a $translate operation."""

    equivalence: str  # equal, equivalent, wider, narrower, etc.
    concept: Coding
    source: str = ""
    product: list[Coding] = field(default_factory=list)


@dataclass
class TranslateResult:
    """Result of a $translate operation."""

    result: bool
    message: str | None = None
    match: list[TranslateMatch] = field(default_factory=list)


@dataclass
class SubsumesResult:
    """Result of a $subsumes operation."""

    outcome: str  # equivalent, subsumes, subsumed-by, not-subsumed


@dataclass
class ClosureEntry:
    """An entry in a closure table representing a subsumption relationship."""

    source: Coding
    target: Coding
    equivalence: str = "subsumes"  # source subsumes target


@dataclass
class ClosureResult:
    """Result of a $closure operation."""

    name: str
    concepts: list[Coding]
    entries: list[ClosureEntry] = field(default_factory=list)


# =============================================================================
# FHIR Parameters Builder
# =============================================================================

class FHIRParametersBuilder:
    """Builder for FHIR Parameters resources."""

    @staticmethod
    def build_lookup_parameters(result: LookupResult) -> dict[str, Any]:
        """Build Parameters resource for $lookup response."""
        parameters = []

        parameters.append({
            "name": "name",
            "valueString": result.name
        })

        if result.version:
            parameters.append({
                "name": "version",
                "valueString": result.version
            })

        parameters.append({
            "name": "display",
            "valueString": result.display
        })

        # Add designations
        for designation in result.designation:
            parts = [
                {"name": "language", "valueCode": designation.language},
                {"name": "value", "valueString": designation.value}
            ]
            if designation.use:
                parts.append({
                    "name": "use",
                    "valueCoding": {
                        "system": designation.use.system,
                        "code": designation.use.code,
                        "display": designation.use.display
                    }
                })
            parameters.append({
                "name": "designation",
                "part": parts
            })

        # Add properties
        for prop in result.property:
            prop_parts: list[dict[str, Any]] = [
                {"name": "code", "valueCode": prop.code}
            ]

            if prop.valueCode is not None:
                prop_parts.append({"name": "value", "valueCode": prop.valueCode})
            elif prop.valueString is not None:
                prop_parts.append({"name": "value", "valueString": prop.valueString})
            elif prop.valueBoolean is not None:
                prop_parts.append({"name": "value", "valueBoolean": prop.valueBoolean})
            elif prop.valueInteger is not None:
                prop_parts.append({"name": "value", "valueInteger": prop.valueInteger})
            elif prop.valueCoding is not None:
                prop_parts.append({
                    "name": "value",
                    "valueCoding": {
                        "system": prop.valueCoding.system,
                        "code": prop.valueCoding.code,
                        "display": prop.valueCoding.display
                    }
                })

            parameters.append({
                "name": "property",
                "part": prop_parts
            })

        return {
            "resourceType": "Parameters",
            "parameter": parameters
        }

    @staticmethod
    def build_validate_code_parameters(result: ValidateCodeResult) -> dict[str, Any]:
        """Build Parameters resource for $validate-code response."""
        parameters = [
            {
                "name": "result",
                "valueBoolean": result.result
            }
        ]

        if result.message:
            parameters.append({
                "name": "message",
                "valueString": result.message
            })

        if result.display:
            parameters.append({
                "name": "display",
                "valueString": result.display
            })

        if result.code:
            parameters.append({
                "name": "code",
                "valueCode": result.code
            })

        if result.system:
            parameters.append({
                "name": "system",
                "valueUri": result.system
            })

        return {
            "resourceType": "Parameters",
            "parameter": parameters
        }

    @staticmethod
    def build_expansion_valueset(
        value_set_url: str,
        expansion: ValueSetExpansion
    ) -> dict[str, Any]:
        """Build ValueSet resource with expansion."""

        def build_contains(c: ValueSetExpansionContains) -> dict[str, Any]:
            result: dict[str, Any] = {
                "system": c.system,
                "code": c.code,
                "display": c.display
            }
            if c.version:
                result["version"] = c.version
            if c.inactive:
                result["inactive"] = c.inactive
            if c.abstract:
                result["abstract"] = c.abstract
            if c.contains:
                result["contains"] = [build_contains(sub) for sub in c.contains]
            return result

        return {
            "resourceType": "ValueSet",
            "url": value_set_url,
            "status": "active",
            "expansion": {
                "identifier": expansion.identifier,
                "timestamp": expansion.timestamp,
                "total": expansion.total,
                "offset": expansion.offset,
                "parameter": expansion.parameter,
                "contains": [build_contains(c) for c in expansion.contains]
            }
        }

    @staticmethod
    def build_translate_parameters(result: TranslateResult) -> dict[str, Any]:
        """Build Parameters resource for $translate response."""
        parameters = [
            {
                "name": "result",
                "valueBoolean": result.result
            }
        ]

        if result.message:
            parameters.append({
                "name": "message",
                "valueString": result.message
            })

        for match in result.match:
            match_parts = [
                {"name": "equivalence", "valueCode": match.equivalence},
                {
                    "name": "concept",
                    "valueCoding": {
                        "system": match.concept.system,
                        "code": match.concept.code,
                        "display": match.concept.display
                    }
                }
            ]
            if match.source:
                match_parts.append({"name": "source", "valueUri": match.source})

            for product in match.product:
                match_parts.append({
                    "name": "product",
                    "valueCoding": {
                        "system": product.system,
                        "code": product.code,
                        "display": product.display
                    }
                })

            parameters.append({
                "name": "match",
                "part": match_parts
            })

        return {
            "resourceType": "Parameters",
            "parameter": parameters
        }

    @staticmethod
    def build_subsumes_parameters(result: SubsumesResult) -> dict[str, Any]:
        """Build Parameters resource for $subsumes response."""
        return {
            "resourceType": "Parameters",
            "parameter": [
                {
                    "name": "outcome",
                    "valueCode": result.outcome
                }
            ]
        }

    @staticmethod
    def build_closure_concept_map(result: ClosureResult) -> dict[str, Any]:
        """Build ConceptMap resource for $closure response."""
        groups: dict[str, list[dict[str, Any]]] = {}

        for entry in result.entries:
            key = entry.source.system
            if key not in groups:
                groups[key] = []
            groups[key].append({
                "source": entry.source.code,
                "sourceDisplay": entry.source.display,
                "target": entry.target.code,
                "targetDisplay": entry.target.display,
                "equivalence": entry.equivalence,
            })

        group_list = []
        for system_uri, elements in groups.items():
            element_map: dict[str, dict[str, Any]] = {}
            for elem in elements:
                src_code = elem["source"]
                if src_code not in element_map:
                    element_map[src_code] = {
                        "code": src_code,
                        "display": elem["sourceDisplay"],
                        "target": []
                    }
                element_map[src_code]["target"].append({
                    "code": elem["target"],
                    "display": elem["targetDisplay"],
                    "equivalence": elem["equivalence"]
                })

            group_list.append({
                "source": system_uri,
                "target": system_uri,
                "element": list(element_map.values())
            })

        return {
            "resourceType": "ConceptMap",
            "name": result.name,
            "status": "active",
            "experimental": True,
            "description": f"Transitive closure table '{result.name}' with {len(result.entries)} relationships",
            "group": group_list
        }


# =============================================================================
# FHIR Terminology Service
# =============================================================================

class FHIRTerminologyService:
    """FHIR R4 Terminology Services implementation.

    Provides terminology operations using locally loaded vocabulary data.

    Usage:
        service = FHIRTerminologyService()

        # Lookup a code
        result = service.lookup("http://snomed.info/sct", "73211009")

        # Validate a code
        result = service.validate_code("http://snomed.info/sct", "73211009", "Diabetes mellitus")

        # Expand a value set
        result = service.expand("http://example.org/ValueSet/common-conditions")

        # Translate between code systems
        result = service.translate("http://snomed.info/sct", "73211009", "http://hl7.org/fhir/sid/icd-10-cm")

        # Test subsumption
        result = service.subsumes("http://snomed.info/sct", "73211009", "46635009")
    """

    def __init__(self) -> None:
        """Initialize the FHIR terminology service."""
        # Lazy load services to avoid circular imports
        self._snomed_service: Any = None
        self._rxnorm_service: Any = None
        self._icd10_service: Any = None
        self._cpt_service: Any = None
        self._loinc_data: dict[str, dict[str, Any]] = {}

        self._load_loinc_data()

        logger.info("FHIR Terminology Service initialized")

    def _get_snomed_service(self) -> Any:
        """Get or create SNOMED service."""
        if self._snomed_service is None:
            try:
                from app.services.snomed_service import get_snomed_service
                self._snomed_service = get_snomed_service()
            except ImportError:
                logger.warning("SNOMED service not available")
        return self._snomed_service

    def _get_rxnorm_service(self) -> Any:
        """Get or create RxNorm service."""
        if self._rxnorm_service is None:
            try:
                from app.services.rxnorm_service import get_rxnorm_service
                self._rxnorm_service = get_rxnorm_service()
            except ImportError:
                logger.warning("RxNorm service not available")
        return self._rxnorm_service

    def _get_icd10_service(self) -> Any:
        """Get or create ICD-10 service."""
        if self._icd10_service is None:
            try:
                from app.services.icd10_suggester import get_icd10_suggester_service
                self._icd10_service = get_icd10_suggester_service()
            except ImportError:
                logger.warning("ICD-10 service not available")
        return self._icd10_service

    def _get_cpt_service(self) -> Any:
        """Get or create CPT service."""
        if self._cpt_service is None:
            try:
                from app.services.cpt_suggester import get_cpt_suggester_service
                self._cpt_service = get_cpt_suggester_service()
            except ImportError:
                logger.warning("CPT service not available")
        return self._cpt_service

    def _load_loinc_data(self) -> None:
        """Load LOINC data from fixture file."""
        from pathlib import Path
        import json

        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "loinc_measurements.json"
        if fixture_path.exists():
            try:
                with open(fixture_path) as f:
                    data = json.load(f)
                for concept in data.get("concepts", []):
                    code = concept.get("concept_code", "")
                    if code:
                        self._loinc_data[code] = concept
                logger.info(f"Loaded {len(self._loinc_data)} LOINC codes")
            except Exception as e:
                logger.warning(f"Failed to load LOINC data: {e}")

    # =========================================================================
    # $lookup Operation
    # =========================================================================

    def lookup(
        self,
        system: str,
        code: str,
        version: str | None = None,
        properties: list[str] | None = None,
    ) -> LookupResult | None:
        """Look up a code in a code system.

        Returns concept details including display name, designations, and properties.

        Args:
            system: The code system URI
            code: The code to look up
            version: Optional code system version
            properties: Optional list of properties to return

        Returns:
            LookupResult with concept details, or None if not found
        """
        code_system = CodeSystemURI.from_string(system)
        if not code_system:
            logger.warning(f"Unknown code system: {system}")
            return None

        if code_system == CodeSystemURI.SNOMED:
            return self._lookup_snomed(code, version, properties)
        elif code_system == CodeSystemURI.ICD10CM:
            return self._lookup_icd10(code, version, properties)
        elif code_system == CodeSystemURI.RXNORM:
            return self._lookup_rxnorm(code, version, properties)
        elif code_system == CodeSystemURI.CPT:
            return self._lookup_cpt(code, version, properties)
        elif code_system == CodeSystemURI.LOINC:
            return self._lookup_loinc(code, version, properties)

        return None

    def _lookup_snomed(
        self,
        code: str,
        version: str | None,
        properties: list[str] | None
    ) -> LookupResult | None:
        """Look up a SNOMED CT code."""
        service = self._get_snomed_service()
        if not service:
            return None

        concept = service.get_concept(code)
        if not concept:
            return None

        designations = []
        # Add synonyms as designations
        for synonym in concept.synonyms:
            designations.append(Designation(
                language="en",
                use=Coding(
                    system="http://snomed.info/sct",
                    code="900000000000013009",
                    display="Synonym"
                ),
                value=synonym
            ))

        concept_properties = [
            ConceptProperty(code="inactive", valueBoolean=not concept.is_standard),
            ConceptProperty(code="domain", valueString=concept.domain_id),
            ConceptProperty(code="semanticType", valueString=concept.semantic_type.value),
        ]

        # Add parent codes as properties
        for parent in concept.parent_codes[:5]:
            concept_properties.append(ConceptProperty(
                code="parent",
                valueCode=parent
            ))

        # Add ICD-10 mappings
        for icd_code in concept.icd10_mappings[:5]:
            concept_properties.append(ConceptProperty(
                code="icd10-mapping",
                valueCoding=Coding(
                    system=CodeSystemURI.ICD10CM.value,
                    code=icd_code,
                    display=""
                )
            ))

        return LookupResult(
            name="SNOMED CT",
            version=version or "2024",
            display=concept.concept_name,
            designation=designations,
            property=concept_properties
        )

    def _lookup_icd10(
        self,
        code: str,
        version: str | None,
        properties: list[str] | None
    ) -> LookupResult | None:
        """Look up an ICD-10-CM code."""
        service = self._get_icd10_service()
        if not service:
            return None

        icd_code = service.get_code(code)
        if not icd_code:
            return None

        designations = []
        for synonym in icd_code.synonyms:
            designations.append(Designation(
                language="en",
                use=Coding(
                    system="http://terminology.hl7.org/CodeSystem/designation-usage",
                    code="synonym",
                    display="Synonym"
                ),
                value=synonym
            ))

        concept_properties = [
            ConceptProperty(code="category", valueString=icd_code.category.value),
            ConceptProperty(code="billable", valueBoolean=icd_code.is_billable),
        ]

        if icd_code.parent_code:
            concept_properties.append(ConceptProperty(
                code="parent",
                valueCode=icd_code.parent_code
            ))

        if icd_code.omop_concept_id:
            concept_properties.append(ConceptProperty(
                code="omop-concept-id",
                valueInteger=icd_code.omop_concept_id
            ))

        return LookupResult(
            name="ICD-10-CM",
            version=version or "2024",
            display=icd_code.description,
            designation=designations,
            property=concept_properties
        )

    def _lookup_rxnorm(
        self,
        code: str,
        version: str | None,
        properties: list[str] | None
    ) -> LookupResult | None:
        """Look up an RxNorm code."""
        service = self._get_rxnorm_service()
        if not service:
            return None

        drug = service.lookup_by_rxcui(code)
        if not drug:
            return None

        designations = []
        for synonym in drug.synonyms:
            designations.append(Designation(
                language="en",
                use=Coding(
                    system="http://terminology.hl7.org/CodeSystem/designation-usage",
                    code="synonym",
                    display="Synonym"
                ),
                value=synonym
            ))

        # Add brand names as designations
        for brand in drug.brand_names:
            designations.append(Designation(
                language="en",
                use=Coding(
                    system="http://terminology.hl7.org/CodeSystem/designation-usage",
                    code="brand",
                    display="Brand Name"
                ),
                value=brand
            ))

        concept_properties = [
            ConceptProperty(code="termType", valueCode=drug.tty),
        ]

        if drug.generic_name:
            concept_properties.append(ConceptProperty(
                code="genericName",
                valueString=drug.generic_name
            ))

        for ingredient in drug.ingredients[:5]:
            concept_properties.append(ConceptProperty(
                code="ingredient",
                valueString=ingredient
            ))

        for tc in drug.therapeutic_classes[:3]:
            concept_properties.append(ConceptProperty(
                code="therapeuticClass",
                valueString=tc
            ))

        if drug.dosage_form:
            concept_properties.append(ConceptProperty(
                code="doseForm",
                valueString=drug.dosage_form
            ))

        return LookupResult(
            name="RxNorm",
            version=version or "2024-AA",
            display=drug.concept_name,
            designation=designations,
            property=concept_properties
        )

    def _lookup_cpt(
        self,
        code: str,
        version: str | None,
        properties: list[str] | None
    ) -> LookupResult | None:
        """Look up a CPT code."""
        service = self._get_cpt_service()
        if not service:
            return None

        cpt_code = service.get_code(code)
        if not cpt_code:
            return None

        designations = []
        for synonym in cpt_code.synonyms:
            designations.append(Designation(
                language="en",
                use=Coding(
                    system="http://terminology.hl7.org/CodeSystem/designation-usage",
                    code="synonym",
                    display="Synonym"
                ),
                value=synonym
            ))

        concept_properties = [
            ConceptProperty(code="category", valueString=cpt_code.category.value),
        ]

        if cpt_code.work_rvu > 0:
            concept_properties.append(ConceptProperty(
                code="workRVU",
                valueString=str(cpt_code.work_rvu)
            ))

        if cpt_code.typical_time_minutes > 0:
            concept_properties.append(ConceptProperty(
                code="typicalTime",
                valueInteger=cpt_code.typical_time_minutes
            ))

        return LookupResult(
            name="CPT",
            version=version or "2024",
            display=cpt_code.description,
            designation=designations,
            property=concept_properties
        )

    def _lookup_loinc(
        self,
        code: str,
        version: str | None,
        properties: list[str] | None
    ) -> LookupResult | None:
        """Look up a LOINC code."""
        if code not in self._loinc_data:
            return None

        concept = self._loinc_data[code]

        designations = []
        for synonym in concept.get("synonyms", []):
            designations.append(Designation(
                language="en",
                use=Coding(
                    system="http://terminology.hl7.org/CodeSystem/designation-usage",
                    code="synonym",
                    display="Synonym"
                ),
                value=synonym
            ))

        concept_properties = []

        if concept.get("domain_id"):
            concept_properties.append(ConceptProperty(
                code="domain",
                valueString=concept["domain_id"]
            ))

        if concept.get("concept_class_id"):
            concept_properties.append(ConceptProperty(
                code="class",
                valueString=concept["concept_class_id"]
            ))

        return LookupResult(
            name="LOINC",
            version=version or "2.76",
            display=concept.get("concept_name", ""),
            designation=designations,
            property=concept_properties
        )

    # =========================================================================
    # $validate-code Operation
    # =========================================================================

    def validate_code(
        self,
        system: str,
        code: str,
        display: str | None = None,
        version: str | None = None,
    ) -> ValidateCodeResult:
        """Validate that a code is valid within a code system.

        Args:
            system: The code system URI
            code: The code to validate
            display: Optional display text to validate
            version: Optional code system version

        Returns:
            ValidateCodeResult indicating if the code is valid
        """
        # Look up the code
        result = self.lookup(system, code, version)

        if result is None:
            return ValidateCodeResult(
                result=False,
                message=f"Code '{code}' not found in system '{system}'",
                code=code,
                system=system
            )

        # If display was provided, check if it matches
        if display:
            display_matches = display.lower() == result.display.lower()
            if not display_matches:
                # Check designations
                for designation in result.designation:
                    if designation.value.lower() == display.lower():
                        display_matches = True
                        break

            if not display_matches:
                return ValidateCodeResult(
                    result=True,  # Code is valid but display doesn't match
                    message=f"Code is valid but display '{display}' does not match preferred display '{result.display}'",
                    display=result.display,
                    code=code,
                    system=system
                )

        return ValidateCodeResult(
            result=True,
            message="Code is valid",
            display=result.display,
            code=code,
            system=system
        )

    # =========================================================================
    # $expand Operation
    # =========================================================================

    def expand(
        self,
        value_set_url: str,
        filter_text: str | None = None,
        offset: int = 0,
        count: int = 100,
    ) -> ValueSetExpansion | None:
        """Expand a ValueSet to list its contained codes.

        Args:
            value_set_url: The ValueSet URL or identifier
            filter_text: Optional filter to apply to the expansion
            offset: Starting offset for pagination
            count: Maximum number of codes to return

        Returns:
            ValueSetExpansion with contained codes
        """
        # Parse the value set URL to determine what to expand
        # Common patterns:
        # - http://hl7.org/fhir/ValueSet/[name]
        # - urn:uuid:[uuid]
        # - Custom URLs

        timestamp = datetime.now(timezone.utc).isoformat()
        identifier = f"urn:uuid:expansion-{datetime.now(timezone.utc).timestamp()}"

        contains: list[ValueSetExpansionContains] = []
        parameters: list[dict[str, Any]] = []

        if filter_text:
            parameters.append({
                "name": "filter",
                "valueString": filter_text
            })

        # Determine which code system to expand based on URL
        value_set_lower = value_set_url.lower()

        if "snomed" in value_set_lower or "condition" in value_set_lower or "disorder" in value_set_lower:
            contains = self._expand_snomed(filter_text, offset, count)
        elif "icd" in value_set_lower or "diagnosis" in value_set_lower:
            contains = self._expand_icd10(filter_text, offset, count)
        elif "rxnorm" in value_set_lower or "medication" in value_set_lower or "drug" in value_set_lower:
            contains = self._expand_rxnorm(filter_text, offset, count)
        elif "cpt" in value_set_lower or "procedure" in value_set_lower:
            contains = self._expand_cpt(filter_text, offset, count)
        elif "loinc" in value_set_lower or "observation" in value_set_lower or "lab" in value_set_lower:
            contains = self._expand_loinc(filter_text, offset, count)
        else:
            # Try all code systems
            contains = self._expand_all(filter_text, offset, count)

        return ValueSetExpansion(
            identifier=identifier,
            timestamp=timestamp,
            total=len(contains),
            offset=offset,
            contains=contains,
            parameter=parameters
        )

    def _expand_snomed(
        self,
        filter_text: str | None,
        offset: int,
        count: int
    ) -> list[ValueSetExpansionContains]:
        """Expand SNOMED CT codes."""
        service = self._get_snomed_service()
        if not service:
            return []

        contains = []

        if filter_text:
            matches = service.match_concept(filter_text, max_results=count + offset)
            for match in matches[offset:offset + count]:
                contains.append(ValueSetExpansionContains(
                    system=CodeSystemURI.SNOMED.value,
                    code=match.concept.concept_code,
                    display=match.concept.concept_name,
                    inactive=not match.concept.is_standard
                ))
        else:
            # Return first N concepts
            concepts = list(service._concepts.values())[offset:offset + count]
            for concept in concepts:
                contains.append(ValueSetExpansionContains(
                    system=CodeSystemURI.SNOMED.value,
                    code=concept.concept_code,
                    display=concept.concept_name,
                    inactive=not concept.is_standard
                ))

        return contains

    def _expand_icd10(
        self,
        filter_text: str | None,
        offset: int,
        count: int
    ) -> list[ValueSetExpansionContains]:
        """Expand ICD-10-CM codes."""
        service = self._get_icd10_service()
        if not service:
            return []

        contains = []

        if filter_text:
            codes = service.search_codes(filter_text, limit=count + offset)
            for code in codes[offset:offset + count]:
                contains.append(ValueSetExpansionContains(
                    system=CodeSystemURI.ICD10CM.value,
                    code=code.code,
                    display=code.description
                ))
        else:
            codes = list(service._codes.values())[offset:offset + count]
            for code in codes:
                contains.append(ValueSetExpansionContains(
                    system=CodeSystemURI.ICD10CM.value,
                    code=code.code,
                    display=code.description
                ))

        return contains

    def _expand_rxnorm(
        self,
        filter_text: str | None,
        offset: int,
        count: int
    ) -> list[ValueSetExpansionContains]:
        """Expand RxNorm codes."""
        service = self._get_rxnorm_service()
        if not service:
            return []

        contains = []

        if filter_text:
            drugs = service.search_drugs(filter_text, limit=count + offset)
            for drug in drugs[offset:offset + count]:
                contains.append(ValueSetExpansionContains(
                    system=CodeSystemURI.RXNORM.value,
                    code=drug.rxcui,
                    display=drug.concept_name
                ))
        else:
            drugs = service._drugs[offset:offset + count]
            for drug in drugs:
                contains.append(ValueSetExpansionContains(
                    system=CodeSystemURI.RXNORM.value,
                    code=drug.rxcui,
                    display=drug.concept_name
                ))

        return contains

    def _expand_cpt(
        self,
        filter_text: str | None,
        offset: int,
        count: int
    ) -> list[ValueSetExpansionContains]:
        """Expand CPT codes."""
        service = self._get_cpt_service()
        if not service:
            return []

        contains = []

        if filter_text:
            codes = service.search_codes(filter_text, limit=count + offset)
            for code in codes[offset:offset + count]:
                contains.append(ValueSetExpansionContains(
                    system=CodeSystemURI.CPT.value,
                    code=code.code,
                    display=code.description
                ))
        else:
            codes = list(service._codes.values())[offset:offset + count]
            for code in codes:
                contains.append(ValueSetExpansionContains(
                    system=CodeSystemURI.CPT.value,
                    code=code.code,
                    display=code.description
                ))

        return contains

    def _expand_loinc(
        self,
        filter_text: str | None,
        offset: int,
        count: int
    ) -> list[ValueSetExpansionContains]:
        """Expand LOINC codes."""
        contains = []
        filter_lower = filter_text.lower() if filter_text else None

        matched_codes = []
        for code, concept in self._loinc_data.items():
            if filter_lower:
                name = concept.get("concept_name", "").lower()
                if filter_lower in name or filter_lower in code.lower():
                    matched_codes.append((code, concept))
            else:
                matched_codes.append((code, concept))

        for code, concept in matched_codes[offset:offset + count]:
            contains.append(ValueSetExpansionContains(
                system=CodeSystemURI.LOINC.value,
                code=code,
                display=concept.get("concept_name", "")
            ))

        return contains

    def _expand_all(
        self,
        filter_text: str | None,
        offset: int,
        count: int
    ) -> list[ValueSetExpansionContains]:
        """Expand from all code systems."""
        contains = []
        per_system = max(count // 5, 10)  # Distribute across systems

        contains.extend(self._expand_snomed(filter_text, 0, per_system))
        contains.extend(self._expand_icd10(filter_text, 0, per_system))
        contains.extend(self._expand_rxnorm(filter_text, 0, per_system))
        contains.extend(self._expand_cpt(filter_text, 0, per_system))
        contains.extend(self._expand_loinc(filter_text, 0, per_system))

        return contains[offset:offset + count]

    # =========================================================================
    # $translate Operation
    # =========================================================================

    def translate(
        self,
        source_system: str,
        code: str,
        target_system: str,
        concept_map_url: str | None = None,
    ) -> TranslateResult:
        """Translate a code from one code system to another.

        Args:
            source_system: The source code system URI
            code: The code to translate
            target_system: The target code system URI
            concept_map_url: Optional ConceptMap URL to use

        Returns:
            TranslateResult with translation matches
        """
        source = CodeSystemURI.from_string(source_system)
        target = CodeSystemURI.from_string(target_system)

        if not source or not target:
            return TranslateResult(
                result=False,
                message=f"Unknown code system: {source_system if not source else target_system}"
            )

        matches: list[TranslateMatch] = []

        # SNOMED -> ICD-10 translation
        if source == CodeSystemURI.SNOMED and target == CodeSystemURI.ICD10CM:
            matches = self._translate_snomed_to_icd10(code)

        # ICD-10 -> SNOMED translation
        elif source == CodeSystemURI.ICD10CM and target == CodeSystemURI.SNOMED:
            matches = self._translate_icd10_to_snomed(code)

        # RxNorm -> Generic name (using RxNorm as target for simplicity)
        elif source == CodeSystemURI.RXNORM:
            matches = self._translate_rxnorm(code, target)

        if not matches:
            return TranslateResult(
                result=False,
                message=f"No translation found from {source.value} to {target.value} for code '{code}'"
            )

        return TranslateResult(
            result=True,
            message=f"Found {len(matches)} translation(s)",
            match=matches
        )

    def _translate_snomed_to_icd10(self, code: str) -> list[TranslateMatch]:
        """Translate SNOMED CT to ICD-10-CM."""
        service = self._get_snomed_service()
        if not service:
            return []

        concept = service.get_concept(code)
        if not concept or not concept.icd10_mappings:
            return []

        matches = []
        icd10_service = self._get_icd10_service()

        for icd_code in concept.icd10_mappings:
            display = ""
            if icd10_service:
                icd_concept = icd10_service.get_code(icd_code)
                if icd_concept:
                    display = icd_concept.description

            matches.append(TranslateMatch(
                equivalence="equivalent",
                concept=Coding(
                    system=CodeSystemURI.ICD10CM.value,
                    code=icd_code,
                    display=display
                ),
                source="SNOMED-ICD10 Map"
            ))

        return matches

    def _translate_icd10_to_snomed(self, code: str) -> list[TranslateMatch]:
        """Translate ICD-10-CM to SNOMED CT."""
        service = self._get_snomed_service()
        if not service:
            return []

        concepts = service.get_snomed_from_icd10(code)
        matches = []

        for concept in concepts:
            matches.append(TranslateMatch(
                equivalence="equivalent",
                concept=Coding(
                    system=CodeSystemURI.SNOMED.value,
                    code=concept.concept_code,
                    display=concept.concept_name
                ),
                source="ICD10-SNOMED Map"
            ))

        return matches

    def _translate_rxnorm(
        self,
        code: str,
        target: CodeSystemURI
    ) -> list[TranslateMatch]:
        """Translate RxNorm codes."""
        service = self._get_rxnorm_service()
        if not service:
            return []

        drug = service.lookup_by_rxcui(code)
        if not drug:
            return []

        matches = []

        # If target is RxNorm, provide ingredient-level translation
        if target == CodeSystemURI.RXNORM and drug.generic_name:
            matches.append(TranslateMatch(
                equivalence="equivalent",
                concept=Coding(
                    system=CodeSystemURI.RXNORM.value,
                    code=code,
                    display=drug.generic_name
                ),
                source="RxNorm Ingredient"
            ))

        # NDC translation
        if target == CodeSystemURI.NDC and drug.ndc_codes:
            for ndc in drug.ndc_codes[:5]:
                matches.append(TranslateMatch(
                    equivalence="equivalent",
                    concept=Coding(
                        system=CodeSystemURI.NDC.value,
                        code=ndc,
                        display=drug.concept_name
                    ),
                    source="RxNorm-NDC Map"
                ))

        return matches

    # =========================================================================
    # $subsumes Operation
    # =========================================================================

    def subsumes(
        self,
        system: str,
        codeA: str,
        codeB: str,
    ) -> SubsumesResult:
        """Test the subsumption relationship between two codes.

        Tests if codeA subsumes codeB (i.e., codeA is an ancestor of codeB).

        Args:
            system: The code system URI
            codeA: The first code
            codeB: The second code

        Returns:
            SubsumesResult with the relationship outcome:
            - "equivalent": The codes are equivalent
            - "subsumes": codeA subsumes codeB (codeA is an ancestor)
            - "subsumed-by": codeB subsumes codeA (codeB is an ancestor)
            - "not-subsumed": Neither code subsumes the other
        """
        code_system = CodeSystemURI.from_string(system)

        if code_system != CodeSystemURI.SNOMED:
            # Subsumption is primarily a SNOMED CT operation
            return SubsumesResult(outcome="not-subsumed")

        if codeA == codeB:
            return SubsumesResult(outcome="equivalent")

        service = self._get_snomed_service()
        if not service:
            return SubsumesResult(outcome="not-subsumed")

        # Check if codeA subsumes codeB (codeA is ancestor of codeB)
        if service.is_descendant_of(codeB, codeA):
            return SubsumesResult(outcome="subsumes")

        # Check if codeB subsumes codeA (codeB is ancestor of codeA)
        if service.is_descendant_of(codeA, codeB):
            return SubsumesResult(outcome="subsumed-by")

        return SubsumesResult(outcome="not-subsumed")

    # =========================================================================
    # $closure Operation
    # =========================================================================

    def closure(
        self,
        name: str,
        concepts: list[Coding],
    ) -> ClosureResult:
        """Compute the transitive closure of subsumption relationships.

        Given a set of concepts, returns all subsumption relationships between
        them (direct and transitive). This is primarily useful for hierarchical
        code systems like SNOMED CT.

        Args:
            name: Identifier for the closure table
            concepts: List of concepts to include in the closure

        Returns:
            ClosureResult with all subsumption relationships between the concepts
        """
        entries: list[ClosureEntry] = []

        # Group concepts by code system
        system_concepts: dict[str, list[Coding]] = {}
        for concept in concepts:
            system = concept.system
            if system not in system_concepts:
                system_concepts[system] = []
            system_concepts[system].append(concept)

        # Process SNOMED CT concepts (primary hierarchy source)
        snomed_uri = CodeSystemURI.SNOMED.value
        if snomed_uri in system_concepts:
            snomed_entries = self._closure_snomed(system_concepts[snomed_uri])
            entries.extend(snomed_entries)

        # Process ICD-10 concepts (parent-child hierarchy)
        icd10_uri = CodeSystemURI.ICD10CM.value
        if icd10_uri in system_concepts:
            icd10_entries = self._closure_icd10(system_concepts[icd10_uri])
            entries.extend(icd10_entries)

        return ClosureResult(
            name=name,
            concepts=concepts,
            entries=entries
        )

    def _closure_snomed(self, concepts: list[Coding]) -> list[ClosureEntry]:
        """Compute closure for SNOMED CT concepts."""
        service = self._get_snomed_service()
        if not service:
            return []

        entries: list[ClosureEntry] = []
        concept_codes = {c.code for c in concepts}
        code_to_coding = {c.code: c for c in concepts}

        # For each concept, find all ancestors that are also in the set
        for concept in concepts:
            ancestors = service.get_ancestors(concept.code, max_depth=10)
            for ancestor in ancestors:
                ancestor_code = ancestor.concept_code
                if ancestor_code in concept_codes and ancestor_code != concept.code:
                    entries.append(ClosureEntry(
                        source=code_to_coding[ancestor_code],
                        target=concept,
                        equivalence="subsumes"
                    ))

        return entries

    def _closure_icd10(self, concepts: list[Coding]) -> list[ClosureEntry]:
        """Compute closure for ICD-10-CM concepts using code hierarchy.

        ICD-10 codes are hierarchical by structure: E11 subsumes E11.6, E11.65, etc.
        This method uses code prefix matching and does not require loading the
        full ICD-10 service.
        """
        entries: list[ClosureEntry] = []

        # ICD-10 uses hierarchical codes: E11 subsumes E11.6, E11.65, etc.
        for concept in concepts:
            code = concept.code
            for other in concepts:
                other_code = other.code
                if other_code == code:
                    continue
                # A shorter code is an ancestor if the longer code starts with it
                # (after normalizing dots)
                code_nodot = code.replace(".", "")
                other_nodot = other_code.replace(".", "")
                if code_nodot.startswith(other_nodot) and len(other_nodot) < len(code_nodot):
                    entries.append(ClosureEntry(
                        source=other,
                        target=concept,
                        equivalence="subsumes"
                    ))

        return entries

    # =========================================================================
    # CodeSystem and ValueSet Resources
    # =========================================================================

    def get_code_system(self, system_id: str) -> dict[str, Any] | None:
        """Get a CodeSystem resource by ID.

        Args:
            system_id: The code system ID (e.g., "snomed-ct", "icd-10-cm")

        Returns:
            FHIR CodeSystem resource or None if not found
        """
        system_map = {
            "snomed-ct": (CodeSystemURI.SNOMED, "SNOMED CT", "SNOMED Clinical Terms"),
            "snomedct": (CodeSystemURI.SNOMED, "SNOMED CT", "SNOMED Clinical Terms"),
            "icd-10-cm": (CodeSystemURI.ICD10CM, "ICD-10-CM", "International Classification of Diseases, 10th Revision, Clinical Modification"),
            "icd10cm": (CodeSystemURI.ICD10CM, "ICD-10-CM", "International Classification of Diseases, 10th Revision, Clinical Modification"),
            "rxnorm": (CodeSystemURI.RXNORM, "RxNorm", "RxNorm Normalized Names for Clinical Drugs"),
            "cpt": (CodeSystemURI.CPT, "CPT", "Current Procedural Terminology"),
            "loinc": (CodeSystemURI.LOINC, "LOINC", "Logical Observation Identifiers Names and Codes"),
        }

        system_id_lower = system_id.lower()
        if system_id_lower not in system_map:
            return None

        uri, name, description = system_map[system_id_lower]

        # Get count from service
        count = 0
        if uri == CodeSystemURI.SNOMED:
            service = self._get_snomed_service()
            if service:
                count = len(service._concepts)
        elif uri == CodeSystemURI.ICD10CM:
            service = self._get_icd10_service()
            if service:
                count = len(service._codes)
        elif uri == CodeSystemURI.RXNORM:
            service = self._get_rxnorm_service()
            if service:
                count = len(service._drugs)
        elif uri == CodeSystemURI.CPT:
            service = self._get_cpt_service()
            if service:
                count = len(service._codes)
        elif uri == CodeSystemURI.LOINC:
            count = len(self._loinc_data)

        return {
            "resourceType": "CodeSystem",
            "id": system_id_lower,
            "url": uri.value,
            "name": name,
            "title": description,
            "status": "active",
            "content": "fragment",
            "count": count
        }

    def get_value_set(self, value_set_id: str) -> dict[str, Any] | None:
        """Get a ValueSet resource by ID.

        Args:
            value_set_id: The value set ID

        Returns:
            FHIR ValueSet resource or None if not found
        """
        # Define common value sets
        value_sets = {
            "common-conditions": {
                "resourceType": "ValueSet",
                "id": "common-conditions",
                "url": "http://example.org/ValueSet/common-conditions",
                "name": "CommonConditions",
                "title": "Common Clinical Conditions",
                "status": "active",
                "description": "Common conditions for clinical documentation",
                "compose": {
                    "include": [
                        {"system": CodeSystemURI.SNOMED.value},
                        {"system": CodeSystemURI.ICD10CM.value}
                    ]
                }
            },
            "common-medications": {
                "resourceType": "ValueSet",
                "id": "common-medications",
                "url": "http://example.org/ValueSet/common-medications",
                "name": "CommonMedications",
                "title": "Common Medications",
                "status": "active",
                "description": "Common medications for clinical documentation",
                "compose": {
                    "include": [
                        {"system": CodeSystemURI.RXNORM.value}
                    ]
                }
            },
            "common-procedures": {
                "resourceType": "ValueSet",
                "id": "common-procedures",
                "url": "http://example.org/ValueSet/common-procedures",
                "name": "CommonProcedures",
                "title": "Common Procedures",
                "status": "active",
                "description": "Common procedures for clinical documentation",
                "compose": {
                    "include": [
                        {"system": CodeSystemURI.CPT.value},
                        {"system": CodeSystemURI.SNOMED.value}
                    ]
                }
            },
            "common-lab-tests": {
                "resourceType": "ValueSet",
                "id": "common-lab-tests",
                "url": "http://example.org/ValueSet/common-lab-tests",
                "name": "CommonLabTests",
                "title": "Common Laboratory Tests",
                "status": "active",
                "description": "Common lab tests for clinical documentation",
                "compose": {
                    "include": [
                        {"system": CodeSystemURI.LOINC.value}
                    ]
                }
            }
        }

        return value_sets.get(value_set_id.lower())

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about available terminology data."""
        stats: dict[str, Any] = {
            "code_systems": {}
        }

        # SNOMED stats
        snomed_service = self._get_snomed_service()
        if snomed_service:
            snomed_stats = snomed_service.get_stats()
            stats["code_systems"]["snomed-ct"] = {
                "name": "SNOMED CT",
                "uri": CodeSystemURI.SNOMED.value,
                "total_concepts": snomed_stats.get("total_concepts", 0),
                "total_synonyms": snomed_stats.get("total_synonyms", 0)
            }

        # ICD-10 stats
        icd10_service = self._get_icd10_service()
        if icd10_service:
            icd10_stats = icd10_service.get_stats()
            stats["code_systems"]["icd-10-cm"] = {
                "name": "ICD-10-CM",
                "uri": CodeSystemURI.ICD10CM.value,
                "total_codes": icd10_stats.get("total_codes", 0),
                "total_synonyms": icd10_stats.get("total_synonyms", 0)
            }

        # RxNorm stats
        rxnorm_service = self._get_rxnorm_service()
        if rxnorm_service:
            rxnorm_stats = rxnorm_service.get_stats()
            stats["code_systems"]["rxnorm"] = {
                "name": "RxNorm",
                "uri": CodeSystemURI.RXNORM.value,
                "total_drugs": rxnorm_stats.get("total_drugs", 0),
                "total_brand_mappings": rxnorm_stats.get("total_brand_mappings", 0)
            }

        # CPT stats
        cpt_service = self._get_cpt_service()
        if cpt_service:
            cpt_stats = cpt_service.get_stats()
            stats["code_systems"]["cpt"] = {
                "name": "CPT",
                "uri": CodeSystemURI.CPT.value,
                "total_codes": cpt_stats.get("total_codes", 0),
                "total_synonyms": cpt_stats.get("total_synonyms", 0)
            }

        # LOINC stats
        stats["code_systems"]["loinc"] = {
            "name": "LOINC",
            "uri": CodeSystemURI.LOINC.value,
            "total_codes": len(self._loinc_data)
        }

        return stats


# =============================================================================
# Singleton Pattern
# =============================================================================

_terminology_service: FHIRTerminologyService | None = None
_terminology_lock = Lock()


def get_fhir_terminology_service() -> FHIRTerminologyService:
    """Get the singleton FHIR terminology service instance.

    Returns:
        The singleton FHIRTerminologyService instance.
    """
    global _terminology_service

    if _terminology_service is None:
        with _terminology_lock:
            if _terminology_service is None:
                logger.info("Creating singleton FHIRTerminologyService instance")
                _terminology_service = FHIRTerminologyService()

    return _terminology_service


def reset_fhir_terminology_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _terminology_service
    with _terminology_lock:
        _terminology_service = None
