"""FHIR R4 Resource Validation and US Core Profile Conformance Service.

Dir-CI-3.2: Lightweight FHIR validation without external validator dependencies.
Validates resources against FHIR R4 base spec and US Core STU3.1.1 profiles.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.schemas.fhir_validation import (
    BundleValidationResult,
    FHIRValidationIssue,
    FHIRValidationResult,
    IssueSeverity,
    USCoreConformanceResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known FHIR R4 resource types
# ---------------------------------------------------------------------------
FHIR_R4_RESOURCE_TYPES: set[str] = {
    "Account", "ActivityDefinition", "AdverseEvent", "AllergyIntolerance",
    "Appointment", "AppointmentResponse", "AuditEvent", "Basic", "Binary",
    "BiologicallyDerivedProduct", "BodyStructure", "Bundle",
    "CapabilityStatement", "CarePlan", "CareTeam", "CatalogEntry",
    "ChargeItem", "ChargeItemDefinition", "Claim", "ClaimResponse",
    "ClinicalImpression", "CodeSystem", "Communication",
    "CommunicationRequest", "CompartmentDefinition", "Composition",
    "ConceptMap", "Condition", "Consent", "Contract", "Coverage",
    "CoverageEligibilityRequest", "CoverageEligibilityResponse",
    "DetectedIssue", "Device", "DeviceDefinition", "DeviceMetric",
    "DeviceRequest", "DeviceUseStatement", "DiagnosticReport",
    "DocumentManifest", "DocumentReference", "EffectEvidenceSynthesis",
    "Encounter", "Endpoint", "EnrollmentRequest", "EnrollmentResponse",
    "EpisodeOfCare", "EventDefinition", "Evidence", "EvidenceVariable",
    "ExampleScenario", "ExplanationOfBenefit", "FamilyMemberHistory",
    "Flag", "Goal", "GraphDefinition", "Group", "GuidanceResponse",
    "HealthcareService", "ImagingStudy", "Immunization",
    "ImmunizationEvaluation", "ImmunizationRecommendation",
    "ImplementationGuide", "InsurancePlan", "Invoice", "Library",
    "Linkage", "List", "Location", "Measure", "MeasureReport",
    "Media", "Medication", "MedicationAdministration",
    "MedicationDispense", "MedicationKnowledge", "MedicationRequest",
    "MedicationStatement", "MedicinalProduct",
    "MedicinalProductAuthorization", "MedicinalProductContraindication",
    "MedicinalProductIndication", "MedicinalProductIngredient",
    "MedicinalProductInteraction", "MedicinalProductManufactured",
    "MedicinalProductPackaged", "MedicinalProductPharmaceutical",
    "MedicinalProductUndesirableEffect", "MessageDefinition",
    "MessageHeader", "MolecularSequence", "NamingSystem",
    "NutritionOrder", "Observation", "ObservationDefinition",
    "OperationDefinition", "OperationOutcome", "Organization",
    "OrganizationAffiliation", "Parameters", "Patient", "PaymentNotice",
    "PaymentReconciliation", "Person", "PlanDefinition", "Practitioner",
    "PractitionerRole", "Procedure", "Provenance", "Questionnaire",
    "QuestionnaireResponse", "RelatedPerson", "RequestGroup",
    "ResearchDefinition", "ResearchElementDefinition", "ResearchStudy",
    "ResearchSubject", "RiskAssessment", "RiskEvidenceSynthesis",
    "Schedule", "SearchParameter", "ServiceRequest", "Slot", "Specimen",
    "SpecimenDefinition", "StructureDefinition", "StructureMap",
    "Subscription", "Substance", "SubstanceNucleicAcid",
    "SubstancePolymer", "SubstanceProtein",
    "SubstanceReferenceInformation", "SubstanceSourceMaterial",
    "SubstanceSpecification", "SupplyDelivery", "SupplyRequest", "Task",
    "TerminologyCapabilities", "TestReport", "TestScript", "ValueSet",
    "VerificationResult", "VisionPrescription",
}

# Resources that typically have a required id element
RESOURCES_REQUIRING_ID: set[str] = FHIR_R4_RESOURCE_TYPES - {
    "Bundle", "Parameters", "Binary",
}

# ---------------------------------------------------------------------------
# Known coding system URIs
# ---------------------------------------------------------------------------
KNOWN_CODE_SYSTEMS: dict[str, str] = {
    "http://snomed.info/sct": "SNOMED-CT",
    "http://loinc.org": "LOINC",
    "http://hl7.org/fhir/sid/icd-10": "ICD-10",
    "http://hl7.org/fhir/sid/icd-10-cm": "ICD-10-CM",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm",
    "http://www.ama-assn.org/go/cpt": "CPT",
    "http://hl7.org/fhir/sid/cvx": "CVX",
    "http://hl7.org/fhir/sid/ndc": "NDC",
    "http://terminology.hl7.org/CodeSystem/v3-ActCode": "ActCode",
    "http://terminology.hl7.org/CodeSystem/condition-clinical": "ConditionClinical",
    "http://terminology.hl7.org/CodeSystem/condition-ver-status": "ConditionVerStatus",
    "http://terminology.hl7.org/CodeSystem/observation-category": "ObservationCategory",
    "http://terminology.hl7.org/CodeSystem/medication-request-intent": "MedRequestIntent",
    "http://hl7.org/fhir/medication-request-intent": "MedRequestIntent",
    "http://hl7.org/fhir/request-intent": "RequestIntent",
}

# ---------------------------------------------------------------------------
# Code pattern validators per system
# ---------------------------------------------------------------------------
CODE_PATTERNS: dict[str, re.Pattern[str]] = {
    "http://snomed.info/sct": re.compile(r"^\d{6,18}$"),
    "http://loinc.org": re.compile(r"^\d{1,5}-\d$"),
    "http://hl7.org/fhir/sid/icd-10": re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$"),
    "http://hl7.org/fhir/sid/icd-10-cm": re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$"),
    "http://www.nlm.nih.gov/research/umls/rxnorm": re.compile(r"^\d+$"),
    "http://www.ama-assn.org/go/cpt": re.compile(r"^\d{4}[0-9A-Z]$"),
}

# ---------------------------------------------------------------------------
# FHIR date/datetime patterns
# ---------------------------------------------------------------------------
FHIR_DATE_RE = re.compile(
    r"^\d{4}(-\d{2}(-\d{2})?)?$"
)
FHIR_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)
FHIR_INSTANT_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)

# FHIR reference pattern: ResourceType/id or absolute URL
FHIR_REFERENCE_RE = re.compile(
    r"^(https?://[^\s]+/)?[A-Z][a-zA-Z]+/[A-Za-z0-9\-.]+$"
)

# ---------------------------------------------------------------------------
# US Core profile definitions (STU3.1.1)
# ---------------------------------------------------------------------------

US_CORE_PROFILES: dict[str, dict[str, Any]] = {
    "Patient": {
        "profile_url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient",
        "must_have": ["identifier", "name", "gender"],
        "must_support": ["birthDate", "address", "telecom", "communication"],
        "element_rules": {
            "identifier": {"min": 1, "type": "array"},
            "name": {"min": 1, "type": "array"},
            "gender": {"min": 1, "type": "string", "values": ["male", "female", "other", "unknown"]},
            "birthDate": {"min": 0, "type": "string", "format": "date"},
        },
    },
    "Condition": {
        "profile_url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition",
        "must_have": ["clinicalStatus", "code", "subject"],
        "must_support": ["verificationStatus", "category", "onsetDateTime"],
        "element_rules": {
            "clinicalStatus": {"min": 1, "type": "object"},
            "code": {"min": 1, "type": "object"},
            "subject": {"min": 1, "type": "object", "is_reference": True},
        },
    },
    "Observation": {
        "profile_url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab",
        "must_have": ["status", "category", "code", "subject"],
        "must_support": [
            "effectiveDateTime", "valueQuantity", "valueCodeableConcept",
            "valueString", "interpretation", "referenceRange",
        ],
        "element_rules": {
            "status": {
                "min": 1,
                "type": "string",
                "values": [
                    "registered", "preliminary", "final", "amended",
                    "corrected", "cancelled", "entered-in-error", "unknown",
                ],
            },
            "category": {"min": 1, "type": "array"},
            "code": {"min": 1, "type": "object"},
            "subject": {"min": 1, "type": "object", "is_reference": True},
        },
    },
    "MedicationRequest": {
        "profile_url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-medicationrequest",
        "must_have": ["status", "intent", "subject"],
        "must_support": [
            "reportedBoolean", "reportedReference",
            "medicationCodeableConcept", "medicationReference",
            "authoredOn", "requester", "dosageInstruction",
        ],
        "medication_required": True,
        "element_rules": {
            "status": {
                "min": 1,
                "type": "string",
                "values": [
                    "active", "on-hold", "cancelled", "completed",
                    "entered-in-error", "stopped", "draft", "unknown",
                ],
            },
            "intent": {
                "min": 1,
                "type": "string",
                "values": [
                    "proposal", "plan", "order", "original-order",
                    "reflex-order", "filler-order", "instance-order", "option",
                ],
            },
            "subject": {"min": 1, "type": "object", "is_reference": True},
        },
    },
    "Procedure": {
        "profile_url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-procedure",
        "must_have": ["status", "code", "subject"],
        "must_support": ["performedDateTime", "performedPeriod"],
        "element_rules": {
            "status": {
                "min": 1,
                "type": "string",
                "values": [
                    "preparation", "in-progress", "not-done", "on-hold",
                    "stopped", "completed", "entered-in-error", "unknown",
                ],
            },
            "code": {"min": 1, "type": "object"},
            "subject": {"min": 1, "type": "object", "is_reference": True},
        },
    },
}


# ===========================================================================
# Public API
# ===========================================================================


class FHIRValidator:
    """Lightweight FHIR R4 + US Core profile validator.

    Validates resources against:
    - FHIR R4 base specification requirements (resourceType, data types, etc.)
    - Known coding system code format patterns
    - US Core STU3.1.1 required elements and cardinality
    """

    # -----------------------------------------------------------------------
    # validate_resource
    # -----------------------------------------------------------------------
    def validate_resource(self, resource: dict[str, Any]) -> FHIRValidationResult:
        """Validate a FHIR R4 resource against the base specification.

        Checks:
        - resourceType is present and recognized
        - Required elements present (id for most resource types)
        - Date/datetime fields use correct FHIR format
        - Reference fields use correct format
        - Coding elements have valid system URIs and code format

        Args:
            resource: Dict representation of a FHIR resource.

        Returns:
            FHIRValidationResult with is_valid flag and any issues.
        """
        issues: list[FHIRValidationIssue] = []
        resource_type = resource.get("resourceType")

        # 1. resourceType present
        if not resource_type:
            issues.append(
                FHIRValidationIssue(
                    severity=IssueSeverity.ERROR,
                    path="resourceType",
                    message="Resource must include a 'resourceType' element.",
                    rule_id="fhir-r4-resourcetype-required",
                )
            )
            return FHIRValidationResult(
                resource_type=None, is_valid=False, issues=issues
            )

        # 2. resourceType recognized
        if resource_type not in FHIR_R4_RESOURCE_TYPES:
            issues.append(
                FHIRValidationIssue(
                    severity=IssueSeverity.ERROR,
                    path="resourceType",
                    message=f"Unknown resourceType '{resource_type}'. "
                    f"Must be a valid FHIR R4 resource type.",
                    rule_id="fhir-r4-resourcetype-unknown",
                )
            )
            return FHIRValidationResult(
                resource_type=resource_type, is_valid=False, issues=issues
            )

        # 3. id present for resource types that require it
        if resource_type in RESOURCES_REQUIRING_ID and "id" not in resource:
            issues.append(
                FHIRValidationIssue(
                    severity=IssueSeverity.WARNING,
                    path="id",
                    message=f"{resource_type} resource should include an 'id' element.",
                    rule_id="fhir-r4-id-recommended",
                )
            )

        # 4. Walk the resource tree for structural checks
        self._check_dates(resource, resource_type, issues)
        self._check_references(resource, "", issues)
        self._check_codings(resource, "", issues)

        is_valid = not any(i.severity == IssueSeverity.ERROR for i in issues)
        return FHIRValidationResult(
            resource_type=resource_type, is_valid=is_valid, issues=issues
        )

    # -----------------------------------------------------------------------
    # validate_bundle
    # -----------------------------------------------------------------------
    def validate_bundle(self, bundle: dict[str, Any]) -> BundleValidationResult:
        """Validate a FHIR R4 Bundle and each contained resource.

        Args:
            bundle: Dict representation of a FHIR Bundle.

        Returns:
            BundleValidationResult with per-resource results and bundle-level issues.
        """
        bundle_issues: list[FHIRValidationIssue] = []

        # Check Bundle itself
        rt = bundle.get("resourceType")
        if rt != "Bundle":
            bundle_issues.append(
                FHIRValidationIssue(
                    severity=IssueSeverity.ERROR,
                    path="resourceType",
                    message=f"Expected resourceType 'Bundle', got '{rt}'.",
                    rule_id="fhir-r4-bundle-type",
                )
            )
            return BundleValidationResult(
                total_resources=0,
                valid_count=0,
                invalid_count=0,
                results=[],
                bundle_issues=bundle_issues,
            )

        bundle_type = bundle.get("type")
        if not bundle_type:
            bundle_issues.append(
                FHIRValidationIssue(
                    severity=IssueSeverity.ERROR,
                    path="type",
                    message="Bundle must include a 'type' element.",
                    rule_id="fhir-r4-bundle-type-required",
                )
            )

        entries = bundle.get("entry", [])
        if not isinstance(entries, list):
            bundle_issues.append(
                FHIRValidationIssue(
                    severity=IssueSeverity.ERROR,
                    path="entry",
                    message="Bundle.entry must be an array.",
                    rule_id="fhir-r4-bundle-entry-array",
                )
            )
            return BundleValidationResult(
                total_resources=0,
                valid_count=0,
                invalid_count=0,
                results=[],
                bundle_issues=bundle_issues,
            )

        results: list[FHIRValidationResult] = []
        valid = 0
        invalid = 0

        for idx, entry in enumerate(entries):
            resource = entry.get("resource") if isinstance(entry, dict) else None
            if resource is None:
                bundle_issues.append(
                    FHIRValidationIssue(
                        severity=IssueSeverity.WARNING,
                        path=f"entry[{idx}].resource",
                        message=f"Bundle entry at index {idx} has no 'resource' element.",
                        rule_id="fhir-r4-bundle-entry-resource",
                    )
                )
                continue

            result = self.validate_resource(resource)
            results.append(result)
            if result.is_valid:
                valid += 1
            else:
                invalid += 1

        return BundleValidationResult(
            total_resources=len(results),
            valid_count=valid,
            invalid_count=invalid,
            results=results,
            bundle_issues=bundle_issues,
        )

    # -----------------------------------------------------------------------
    # check_us_core_conformance
    # -----------------------------------------------------------------------
    def check_us_core_conformance(
        self, resource: dict[str, Any]
    ) -> USCoreConformanceResult:
        """Check if a FHIR resource conforms to its US Core profile.

        Supports Patient, Condition, Observation, MedicationRequest, Procedure.

        Args:
            resource: Dict representation of a FHIR resource.

        Returns:
            USCoreConformanceResult with conformance status and missing elements.
        """
        resource_type = resource.get("resourceType")

        if not resource_type or resource_type not in US_CORE_PROFILES:
            profile_url = (
                US_CORE_PROFILES.get(resource_type or "", {}).get("profile_url", "unknown")
                if resource_type
                else "unknown"
            )
            return USCoreConformanceResult(
                resource_type=resource_type,
                profile=profile_url,
                is_conformant=False,
                missing_elements=[],
                issues=[
                    FHIRValidationIssue(
                        severity=IssueSeverity.ERROR,
                        path="resourceType",
                        message=f"No US Core profile defined for resourceType "
                        f"'{resource_type}'. Supported: "
                        f"{', '.join(sorted(US_CORE_PROFILES.keys()))}",
                        rule_id="us-core-unsupported-type",
                    )
                ],
            )

        profile = US_CORE_PROFILES[resource_type]
        profile_url = profile["profile_url"]
        issues: list[FHIRValidationIssue] = []
        missing: list[str] = []

        # Check must-have elements
        for element in profile["must_have"]:
            value = resource.get(element)
            if value is None:
                missing.append(element)
                issues.append(
                    FHIRValidationIssue(
                        severity=IssueSeverity.ERROR,
                        path=element,
                        message=f"US Core {resource_type} requires '{element}' "
                        f"but it is missing.",
                        rule_id=f"us-core-{resource_type.lower()}-{element}-required",
                    )
                )

        # Check element-level rules (type, cardinality, allowed values)
        for element, rules in profile.get("element_rules", {}).items():
            value = resource.get(element)
            if value is None:
                continue  # Already handled in must_have

            expected_type = rules.get("type")
            if expected_type == "array" and not isinstance(value, list):
                issues.append(
                    FHIRValidationIssue(
                        severity=IssueSeverity.ERROR,
                        path=element,
                        message=f"'{element}' must be an array.",
                        rule_id=f"us-core-{resource_type.lower()}-{element}-type",
                    )
                )
            elif expected_type == "array" and isinstance(value, list) and len(value) == 0:
                issues.append(
                    FHIRValidationIssue(
                        severity=IssueSeverity.ERROR,
                        path=element,
                        message=f"'{element}' must have at least one entry.",
                        rule_id=f"us-core-{resource_type.lower()}-{element}-min",
                    )
                )
            elif expected_type == "string" and not isinstance(value, str):
                issues.append(
                    FHIRValidationIssue(
                        severity=IssueSeverity.ERROR,
                        path=element,
                        message=f"'{element}' must be a string.",
                        rule_id=f"us-core-{resource_type.lower()}-{element}-type",
                    )
                )
            elif expected_type == "object" and not isinstance(value, dict):
                issues.append(
                    FHIRValidationIssue(
                        severity=IssueSeverity.ERROR,
                        path=element,
                        message=f"'{element}' must be an object.",
                        rule_id=f"us-core-{resource_type.lower()}-{element}-type",
                    )
                )

            # Check allowed values
            allowed = rules.get("values")
            if allowed and isinstance(value, str) and value not in allowed:
                issues.append(
                    FHIRValidationIssue(
                        severity=IssueSeverity.ERROR,
                        path=element,
                        message=f"'{element}' value '{value}' is not one of "
                        f"the allowed values: {', '.join(allowed)}.",
                        rule_id=f"us-core-{resource_type.lower()}-{element}-value",
                    )
                )

            # Check reference format
            if rules.get("is_reference") and isinstance(value, dict):
                ref = value.get("reference")
                if ref and not FHIR_REFERENCE_RE.match(ref):
                    issues.append(
                        FHIRValidationIssue(
                            severity=IssueSeverity.WARNING,
                            path=f"{element}.reference",
                            message=f"Reference '{ref}' does not match expected "
                            f"format 'ResourceType/id'.",
                            rule_id=f"us-core-{resource_type.lower()}-{element}-ref-format",
                        )
                    )

            # Check date format
            fmt = rules.get("format")
            if fmt == "date" and isinstance(value, str):
                if not FHIR_DATE_RE.match(value):
                    issues.append(
                        FHIRValidationIssue(
                            severity=IssueSeverity.ERROR,
                            path=element,
                            message=f"'{element}' value '{value}' is not a valid "
                            f"FHIR date (expected YYYY, YYYY-MM, or YYYY-MM-DD).",
                            rule_id=f"us-core-{resource_type.lower()}-{element}-date",
                        )
                    )

        # MedicationRequest special: must have medicationCodeableConcept OR medicationReference
        if profile.get("medication_required"):
            has_med_cc = resource.get("medicationCodeableConcept") is not None
            has_med_ref = resource.get("medicationReference") is not None
            if not has_med_cc and not has_med_ref:
                missing.append("medication[x]")
                issues.append(
                    FHIRValidationIssue(
                        severity=IssueSeverity.ERROR,
                        path="medication[x]",
                        message="US Core MedicationRequest requires either "
                        "'medicationCodeableConcept' or 'medicationReference'.",
                        rule_id="us-core-medicationrequest-medication-required",
                    )
                )

        # Must-support warnings (not errors)
        for element in profile.get("must_support", []):
            if resource.get(element) is None:
                issues.append(
                    FHIRValidationIssue(
                        severity=IssueSeverity.INFORMATION,
                        path=element,
                        message=f"US Core must-support element '{element}' is "
                        f"not present. It is recommended but not required.",
                        rule_id=f"us-core-{resource_type.lower()}-{element}-must-support",
                    )
                )

        is_conformant = not any(i.severity == IssueSeverity.ERROR for i in issues)
        return USCoreConformanceResult(
            resource_type=resource_type,
            profile=profile_url,
            is_conformant=is_conformant,
            missing_elements=missing,
            issues=issues,
        )

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _check_dates(
        self,
        resource: dict[str, Any],
        resource_type: str,
        issues: list[FHIRValidationIssue],
    ) -> None:
        """Check known date/datetime fields for correct FHIR format."""
        date_fields = {
            "birthDate": "date",
            "deceasedDateTime": "datetime",
            "onsetDateTime": "datetime",
            "abatementDateTime": "datetime",
            "recordedDate": "datetime",
            "effectiveDateTime": "datetime",
            "issued": "instant",
            "authoredOn": "datetime",
            "occurrenceDateTime": "datetime",
            "performedDateTime": "datetime",
            "date": "datetime",
        }

        for field, fmt in date_fields.items():
            value = resource.get(field)
            if value is None or not isinstance(value, str):
                continue

            if fmt == "date":
                if not FHIR_DATE_RE.match(value):
                    issues.append(
                        FHIRValidationIssue(
                            severity=IssueSeverity.ERROR,
                            path=field,
                            message=f"'{field}' value '{value}' is not a valid FHIR date "
                            f"(expected YYYY, YYYY-MM, or YYYY-MM-DD).",
                            rule_id="fhir-r4-date-format",
                        )
                    )
            else:
                # datetime or instant: accept both date-only and full datetime
                if not FHIR_DATE_RE.match(value) and not FHIR_DATETIME_RE.match(value):
                    issues.append(
                        FHIRValidationIssue(
                            severity=IssueSeverity.ERROR,
                            path=field,
                            message=f"'{field}' value '{value}' is not a valid FHIR "
                            f"dateTime (expected YYYY-MM-DD or "
                            f"YYYY-MM-DDThh:mm:ss[.fff]Z/+HH:MM).",
                            rule_id="fhir-r4-datetime-format",
                        )
                    )

    def _check_references(
        self,
        obj: Any,
        path: str,
        issues: list[FHIRValidationIssue],
    ) -> None:
        """Recursively check reference fields for correct format."""
        if isinstance(obj, dict):
            ref = obj.get("reference")
            if ref is not None and isinstance(ref, str):
                if not FHIR_REFERENCE_RE.match(ref):
                    full_path = f"{path}.reference" if path else "reference"
                    issues.append(
                        FHIRValidationIssue(
                            severity=IssueSeverity.WARNING,
                            path=full_path,
                            message=f"Reference '{ref}' does not match expected "
                            f"format 'ResourceType/id' or absolute URL.",
                            rule_id="fhir-r4-reference-format",
                        )
                    )

            for key, value in obj.items():
                if key in ("resourceType", "id", "text"):
                    continue  # Skip non-structural elements
                child_path = f"{path}.{key}" if path else key
                self._check_references(value, child_path, issues)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                child_path = f"{path}[{idx}]"
                self._check_references(item, child_path, issues)

    def _check_codings(
        self,
        obj: Any,
        path: str,
        issues: list[FHIRValidationIssue],
    ) -> None:
        """Recursively check coding elements for valid system URIs and code format."""
        if isinstance(obj, dict):
            # If this looks like a Coding element (has system + code)
            system = obj.get("system")
            code = obj.get("code")

            if system is not None and code is not None:
                if isinstance(system, str) and isinstance(code, str):
                    self._validate_coding(system, code, path, issues)

            for key, value in obj.items():
                if key in ("resourceType", "id", "text"):
                    continue
                child_path = f"{path}.{key}" if path else key
                self._check_codings(value, child_path, issues)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                child_path = f"{path}[{idx}]"
                self._check_codings(item, child_path, issues)

    def _validate_coding(
        self,
        system: str,
        code: str,
        path: str,
        issues: list[FHIRValidationIssue],
    ) -> None:
        """Validate a coding system URI and code format."""
        # Check if system URI is well-formed
        if not system.startswith(("http://", "https://", "urn:")):
            issues.append(
                FHIRValidationIssue(
                    severity=IssueSeverity.WARNING,
                    path=f"{path}.system" if path else "system",
                    message=f"Coding system '{system}' is not a valid URI "
                    f"(expected http://, https://, or urn:).",
                    rule_id="fhir-r4-coding-system-uri",
                )
            )

        # If we know the system, validate code format
        pattern = CODE_PATTERNS.get(system)
        if pattern and not pattern.match(code):
            system_name = KNOWN_CODE_SYSTEMS.get(system, system)
            issues.append(
                FHIRValidationIssue(
                    severity=IssueSeverity.WARNING,
                    path=f"{path}.code" if path else "code",
                    message=f"Code '{code}' does not match expected format for "
                    f"{system_name} ({system}).",
                    rule_id="fhir-r4-coding-code-format",
                )
            )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_validator: FHIRValidator | None = None


def get_fhir_validator() -> FHIRValidator:
    """Get or create the singleton FHIRValidator instance."""
    global _validator
    if _validator is None:
        _validator = FHIRValidator()
    return _validator
