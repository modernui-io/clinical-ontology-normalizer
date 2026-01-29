"""Billing Optimization Engine.

This module provides comprehensive billing optimization analysis including:

- Encounter-level code optimization
- Missed billing opportunity detection
- Bundling/unbundling compliance (CCI edits)
- Medical necessity verification
- Documentation gap analysis
- Revenue estimation based on RVUs
- CER citations for all recommendations

Note: This is a clinical decision support tool. All recommendations should
be reviewed by qualified medical coders and billing professionals.
"""

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class OptimizationCategory(Enum):
    """Category of billing optimization."""

    UPCODING_OPPORTUNITY = "upcoding_opportunity"  # Documentation supports higher code
    MISSED_SERVICE = "missed_service"  # Billable service not coded
    BUNDLING_ISSUE = "bundling_issue"  # Improper code bundling
    MEDICAL_NECESSITY = "medical_necessity"  # Diagnosis doesn't support procedure
    DOCUMENTATION_GAP = "documentation_gap"  # Missing documentation
    MODIFIER_NEEDED = "modifier_needed"  # Modifier should be added
    COMPLIANCE_RISK = "compliance_risk"  # Potential compliance issue


class SeverityLevel(Enum):
    """Severity of the optimization finding."""

    HIGH = "high"  # Significant revenue or compliance impact
    MEDIUM = "medium"  # Moderate impact
    LOW = "low"  # Minor impact


class ConfidenceLevel(Enum):
    """Confidence in the optimization recommendation."""

    HIGH = "high"  # Strong documentation support
    MEDIUM = "medium"  # Good support, review recommended
    LOW = "low"  # Possible improvement, verification needed


@dataclass
class BillingCERCitation:
    """Claim-Evidence-Reasoning citation for billing optimization."""

    claim: str  # What is being recommended
    evidence: list[str]  # Documentation/clinical support
    reasoning: str  # Why this recommendation applies
    strength: ConfidenceLevel
    regulatory_basis: list[str] = field(default_factory=list)  # CMS/payer rules


@dataclass
class OptimizationFinding:
    """A single billing optimization finding."""

    category: OptimizationCategory
    severity: SeverityLevel
    title: str
    description: str
    current_code: str | None  # Current code if applicable
    recommended_code: str | None  # Recommended code if applicable
    revenue_impact: float  # Estimated revenue change (positive = increase)
    cer_citation: BillingCERCitation
    action_items: list[str]  # Steps to implement recommendation
    documentation_needed: list[str]  # Additional documentation required


@dataclass
class EncounterCodes:
    """Codes submitted for an encounter."""

    cpt_codes: list[str] = field(default_factory=list)
    icd10_codes: list[str] = field(default_factory=list)
    modifiers: list[tuple[str, str]] = field(default_factory=list)  # (cpt, modifier)


@dataclass
class EncounterContext:
    """Clinical context for an encounter."""

    setting: str = "office"  # office, inpatient, emergency, telehealth
    patient_type: str = "established"  # new or established
    time_spent: int | None = None  # Minutes
    mdm_complexity: str | None = None  # straightforward, low, moderate, high
    diagnoses: list[str] = field(default_factory=list)  # Diagnosis descriptions
    procedures_performed: list[str] = field(default_factory=list)  # Procedure descriptions
    documentation_elements: dict[str, bool] = field(default_factory=dict)  # What's documented


@dataclass
class BillingOptimizationResult:
    """Result from billing optimization analysis."""

    encounter_codes: EncounterCodes
    encounter_context: EncounterContext
    findings: list[OptimizationFinding]
    total_findings: int
    by_category: dict[str, int]
    by_severity: dict[str, int]
    estimated_current_rvu: float
    estimated_optimized_rvu: float
    potential_revenue_increase: float
    compliance_score: float  # 0-100, higher is better
    overall_assessment: str
    priority_actions: list[str]


# ============================================================================
# Code Bundling Rules (CCI - Correct Coding Initiative edits)
# ============================================================================

# Simplified CCI bundling rules: (comprehensive_code, component_code)
# Component should not be billed separately when comprehensive is billed
CCI_BUNDLES: list[tuple[str, str, str]] = [
    # E/M bundling
    ("99214", "99211", "Higher E/M includes lower level service"),
    ("99215", "99214", "Higher E/M includes lower level service"),
    ("99215", "99213", "Higher E/M includes lower level service"),

    # ECG with E/M
    ("99285", "93000", "ED visit typically includes ECG interpretation"),

    # Lab draws
    ("36415", "99211", "Venipuncture typically bundled with minimal visit"),

    # Injections
    ("96372", "36415", "Injection includes venipuncture when same site"),

    # Chest X-ray
    ("71046", "71045", "2-view CXR includes single view"),
]

# Medical necessity: CPT codes and their commonly supporting ICD-10 codes
MEDICAL_NECESSITY_MAP: dict[str, list[str]] = {
    "93000": ["R00.0", "R00.1", "I48.91", "I25.10", "R07.9", "I10"],  # ECG
    "71046": ["R05", "R06.02", "J18.9", "R07.9", "J44.1"],  # Chest X-ray
    "80053": ["E11.9", "N18.9", "K76.0", "I10", "E78.5"],  # CMP
    "85025": ["D64.9", "J18.9", "A41.9", "R50.9"],  # CBC
    "80061": ["E78.5", "I25.10", "E11.9", "I10"],  # Lipid panel
    "83036": ["E11.9", "E10.9", "E11.65"],  # HbA1c
}

# E/M code requirements for upcoding analysis
EM_CODE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "99211": {
        "description": "Minimal problem, may not require physician",
        "min_time": 0,
        "mdm": "N/A",
        "work_rvu": 0.18,
    },
    "99212": {
        "description": "Straightforward MDM or 10-19 min",
        "min_time": 10,
        "mdm": "straightforward",
        "work_rvu": 0.70,
    },
    "99213": {
        "description": "Low complexity MDM or 20-29 min",
        "min_time": 20,
        "mdm": "low",
        "work_rvu": 1.30,
    },
    "99214": {
        "description": "Moderate complexity MDM or 30-39 min",
        "min_time": 30,
        "mdm": "moderate",
        "work_rvu": 1.92,
    },
    "99215": {
        "description": "High complexity MDM or 40-54 min",
        "min_time": 40,
        "mdm": "high",
        "work_rvu": 2.80,
    },
}

# Common billable services often missed
COMMONLY_MISSED_SERVICES: list[dict[str, Any]] = [
    {
        "triggers": ["smoking", "tobacco", "cigarette", "nicotine"],
        "cpt": "99406",
        "description": "Tobacco cessation counseling (3-10 min)",
        "requirements": ["Counseling documented", "Time documented"],
    },
    {
        "triggers": ["depression screening", "phq", "phq-9", "depression screen"],
        "cpt": "G0444",
        "description": "Annual depression screening",
        "requirements": ["Screening performed", "Results documented"],
    },
    {
        "triggers": ["alcohol", "audit", "cage", "alcohol screening"],
        "cpt": "G0442",
        "description": "Annual alcohol misuse screening",
        "requirements": ["Screening performed", "Results documented"],
    },
    {
        "triggers": ["chronic care", "care plan", "multiple chronic"],
        "cpt": "99490",
        "description": "Chronic care management (20+ min/month)",
        "requirements": ["20+ minutes of CCM time", "Care plan documented", "Patient consent"],
    },
    {
        "triggers": ["transition", "discharge", "hospital follow"],
        "cpt": "99495",
        "description": "Transitional care management (moderate complexity)",
        "requirements": ["Contact within 2 business days", "Face-to-face within 14 days"],
    },
    {
        "triggers": ["vaccine", "immunization", "flu shot", "pneumovax"],
        "cpt": "90471",
        "description": "Immunization administration",
        "requirements": ["Vaccine administered", "Lot number documented"],
    },
]


# ============================================================================
# Billing Optimization Service
# ============================================================================

_billing_service: "BillingOptimizationService | None" = None
_billing_lock = threading.Lock()


def get_billing_optimization_service() -> "BillingOptimizationService":
    """Get the singleton billing optimization service instance."""
    global _billing_service
    if _billing_service is None:
        with _billing_lock:
            if _billing_service is None:
                _billing_service = BillingOptimizationService()
    return _billing_service


def reset_billing_optimization_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _billing_service
    with _billing_lock:
        _billing_service = None


class BillingOptimizationService:
    """Service for optimizing medical billing and coding."""

    def __init__(self) -> None:
        """Initialize the billing optimization service."""
        self._cci_bundles = CCI_BUNDLES
        self._medical_necessity = MEDICAL_NECESSITY_MAP
        self._em_requirements = EM_CODE_REQUIREMENTS
        self._missed_services = COMMONLY_MISSED_SERVICES

    def analyze_encounter(
        self,
        codes: EncounterCodes,
        context: EncounterContext,
    ) -> BillingOptimizationResult:
        """Analyze an encounter for billing optimization opportunities.

        Args:
            codes: CPT and ICD-10 codes currently assigned
            context: Clinical context of the encounter

        Returns:
            BillingOptimizationResult with findings and recommendations.
        """
        findings: list[OptimizationFinding] = []

        # 1. Check E/M coding optimization
        em_findings = self._analyze_em_coding(codes, context)
        findings.extend(em_findings)

        # 2. Check for missed billable services
        missed_findings = self._find_missed_services(codes, context)
        findings.extend(missed_findings)

        # 3. Check bundling compliance
        bundling_findings = self._check_bundling(codes)
        findings.extend(bundling_findings)

        # 4. Check medical necessity
        necessity_findings = self._check_medical_necessity(codes)
        findings.extend(necessity_findings)

        # 5. Check for modifier needs
        modifier_findings = self._check_modifiers(codes, context)
        findings.extend(modifier_findings)

        # 6. Check documentation gaps
        doc_findings = self._analyze_documentation(codes, context)
        findings.extend(doc_findings)

        # Calculate metrics
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        total_revenue_impact = 0.0

        for f in findings:
            cat = f.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            sev = f.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1
            total_revenue_impact += f.revenue_impact

        # Calculate RVUs
        current_rvu = self._calculate_rvu(codes.cpt_codes)
        optimized_rvu = current_rvu + sum(
            f.revenue_impact / 36.0  # Approximate conversion factor
            for f in findings
            if f.revenue_impact > 0
        )

        # Calculate compliance score
        compliance_issues = sum(1 for f in findings
                                 if f.category in [OptimizationCategory.BUNDLING_ISSUE,
                                                   OptimizationCategory.COMPLIANCE_RISK,
                                                   OptimizationCategory.MEDICAL_NECESSITY])
        compliance_score = max(0, 100 - (compliance_issues * 15))

        # Generate overall assessment
        overall = self._generate_assessment(findings, compliance_score)

        # Priority actions
        priority_actions = [
            f.action_items[0] if f.action_items else f.title
            for f in sorted(findings, key=lambda x: (
                0 if x.severity == SeverityLevel.HIGH else
                1 if x.severity == SeverityLevel.MEDIUM else 2
            ))[:5]
        ]

        return BillingOptimizationResult(
            encounter_codes=codes,
            encounter_context=context,
            findings=findings,
            total_findings=len(findings),
            by_category=by_category,
            by_severity=by_severity,
            estimated_current_rvu=round(current_rvu, 2),
            estimated_optimized_rvu=round(optimized_rvu, 2),
            potential_revenue_increase=round(total_revenue_impact, 2),
            compliance_score=round(compliance_score, 1),
            overall_assessment=overall,
            priority_actions=priority_actions,
        )

    def _analyze_em_coding(
        self,
        codes: EncounterCodes,
        context: EncounterContext,
    ) -> list[OptimizationFinding]:
        """Analyze E/M coding for optimization opportunities."""
        findings = []

        # Find current E/M code
        current_em = None
        for cpt in codes.cpt_codes:
            if cpt in self._em_requirements:
                current_em = cpt
                break

        if not current_em:
            return findings

        current_req = self._em_requirements[current_em]

        # Check if higher code is supported by time
        if context.time_spent:
            for code, req in sorted(
                self._em_requirements.items(),
                key=lambda x: x[1]["work_rvu"],
                reverse=True
            ):
                if code <= current_em:
                    continue
                if context.time_spent >= req["min_time"]:
                    revenue_diff = (req["work_rvu"] - current_req["work_rvu"]) * 36.0
                    findings.append(OptimizationFinding(
                        category=OptimizationCategory.UPCODING_OPPORTUNITY,
                        severity=SeverityLevel.HIGH if revenue_diff > 50 else SeverityLevel.MEDIUM,
                        title=f"E/M Upcoding Opportunity: {current_em} → {code}",
                        description=(
                            f"Time documented ({context.time_spent} min) supports {code} "
                            f"(requires {req['min_time']}+ min)"
                        ),
                        current_code=current_em,
                        recommended_code=code,
                        revenue_impact=revenue_diff,
                        cer_citation=BillingCERCitation(
                            claim=f"{code} is supported by documented encounter time",
                            evidence=[
                                f"Total time documented: {context.time_spent} minutes",
                                f"{code} requires {req['min_time']}+ minutes",
                                f"Current code {current_em} requires {current_req['min_time']}+ minutes",
                            ],
                            reasoning=(
                                f"Per CMS guidelines, E/M codes may be selected based on total time "
                                f"when time is the predominant factor. The documented time of "
                                f"{context.time_spent} minutes meets the threshold for {code}."
                            ),
                            strength=ConfidenceLevel.HIGH,
                            regulatory_basis=[
                                "CMS E/M Guidelines 2021+",
                                "Time-based E/M code selection",
                            ],
                        ),
                        action_items=[
                            f"Change E/M code from {current_em} to {code}",
                            "Ensure time documentation is complete",
                            "Verify all time activities are documented",
                        ],
                        documentation_needed=[
                            "Total time on date of encounter",
                            "Activities performed during time",
                        ],
                    ))
                    break  # Only suggest one level up

        # Check if higher code is supported by MDM
        if context.mdm_complexity:
            mdm_order = ["straightforward", "low", "moderate", "high"]
            current_mdm_idx = mdm_order.index(current_req["mdm"]) if current_req["mdm"] in mdm_order else -1
            context_mdm_idx = mdm_order.index(context.mdm_complexity) if context.mdm_complexity in mdm_order else -1

            if context_mdm_idx > current_mdm_idx:
                for code, req in self._em_requirements.items():
                    if req["mdm"] == context.mdm_complexity and code > current_em:
                        revenue_diff = (req["work_rvu"] - current_req["work_rvu"]) * 36.0
                        findings.append(OptimizationFinding(
                            category=OptimizationCategory.UPCODING_OPPORTUNITY,
                            severity=SeverityLevel.HIGH if revenue_diff > 50 else SeverityLevel.MEDIUM,
                            title=f"E/M MDM Upcoding: {current_em} → {code}",
                            description=(
                                f"MDM complexity ({context.mdm_complexity}) supports {code}"
                            ),
                            current_code=current_em,
                            recommended_code=code,
                            revenue_impact=revenue_diff,
                            cer_citation=BillingCERCitation(
                                claim=f"{code} is supported by documented MDM complexity",
                                evidence=[
                                    f"MDM documented as: {context.mdm_complexity}",
                                    f"{code} requires {req['mdm']} MDM",
                                ],
                                reasoning=(
                                    f"The documented medical decision making complexity of "
                                    f"'{context.mdm_complexity}' meets the criteria for {code}."
                                ),
                                strength=ConfidenceLevel.MEDIUM,
                                regulatory_basis=["CMS MDM table criteria"],
                            ),
                            action_items=[
                                f"Change E/M code from {current_em} to {code}",
                                "Verify MDM elements are documented",
                            ],
                            documentation_needed=[
                                "Number/complexity of problems addressed",
                                "Data reviewed/ordered",
                                "Risk of complications",
                            ],
                        ))
                        break

        return findings

    def _find_missed_services(
        self,
        codes: EncounterCodes,
        context: EncounterContext,
    ) -> list[OptimizationFinding]:
        """Find billable services that may have been missed."""
        findings = []

        # Combine all text for searching
        all_text = " ".join([
            context.setting,
            " ".join(context.diagnoses),
            " ".join(context.procedures_performed),
        ]).lower()

        for service in self._missed_services:
            # Check if any trigger is in the text
            triggered = any(t in all_text for t in service["triggers"])

            if triggered:
                # Check if already coded
                if service["cpt"] not in codes.cpt_codes:
                    findings.append(OptimizationFinding(
                        category=OptimizationCategory.MISSED_SERVICE,
                        severity=SeverityLevel.MEDIUM,
                        title=f"Missed Billable Service: {service['cpt']}",
                        description=service["description"],
                        current_code=None,
                        recommended_code=service["cpt"],
                        revenue_impact=25.0,  # Estimated average
                        cer_citation=BillingCERCitation(
                            claim=f"{service['cpt']} may be billable for this encounter",
                            evidence=[
                                f"Documentation suggests: {', '.join(service['triggers'][:2])}",
                                f"Service: {service['description']}",
                            ],
                            reasoning=(
                                f"The encounter documentation includes elements that suggest "
                                f"{service['description']} was performed. If documentation "
                                f"requirements are met, this service may be separately billable."
                            ),
                            strength=ConfidenceLevel.MEDIUM,
                            regulatory_basis=["Medicare fee schedule"],
                        ),
                        action_items=[
                            f"Review if {service['description']} was performed",
                            f"Add {service['cpt']} if requirements are met",
                        ],
                        documentation_needed=service["requirements"],
                    ))

        return findings

    def _check_bundling(self, codes: EncounterCodes) -> list[OptimizationFinding]:
        """Check for bundling/unbundling issues."""
        findings = []

        for comprehensive, component, reason in self._cci_bundles:
            if comprehensive in codes.cpt_codes and component in codes.cpt_codes:
                findings.append(OptimizationFinding(
                    category=OptimizationCategory.BUNDLING_ISSUE,
                    severity=SeverityLevel.HIGH,
                    title=f"CCI Bundling Edit: {component} bundled with {comprehensive}",
                    description=reason,
                    current_code=component,
                    recommended_code=None,
                    revenue_impact=-25.0,  # May need to remove code
                    cer_citation=BillingCERCitation(
                        claim=f"{component} should not be billed separately with {comprehensive}",
                        evidence=[
                            f"Both {comprehensive} and {component} are on the claim",
                            f"CCI edit: {reason}",
                        ],
                        reasoning=(
                            f"Per CMS Correct Coding Initiative (CCI) edits, {component} is "
                            f"bundled into {comprehensive}. Billing both codes may result in "
                            f"claim denial or audit risk."
                        ),
                        strength=ConfidenceLevel.HIGH,
                        regulatory_basis=[
                            "CMS CCI edits",
                            "NCCI Policy Manual",
                        ],
                    ),
                    action_items=[
                        f"Remove {component} from the claim",
                        "OR add appropriate modifier if unbundling is justified",
                    ],
                    documentation_needed=[
                        "Separate and distinct service documentation if unbundling",
                    ],
                ))

        return findings

    def _check_medical_necessity(self, codes: EncounterCodes) -> list[OptimizationFinding]:
        """Check that diagnoses support procedures (medical necessity)."""
        findings = []

        for cpt in codes.cpt_codes:
            if cpt in self._medical_necessity:
                supporting_dx = self._medical_necessity[cpt]
                has_support = any(dx in codes.icd10_codes for dx in supporting_dx)

                if not has_support and codes.icd10_codes:
                    findings.append(OptimizationFinding(
                        category=OptimizationCategory.MEDICAL_NECESSITY,
                        severity=SeverityLevel.HIGH,
                        title=f"Medical Necessity Gap: {cpt}",
                        description=f"No supporting diagnosis for {cpt}",
                        current_code=cpt,
                        recommended_code=None,
                        revenue_impact=0,
                        cer_citation=BillingCERCitation(
                            claim=f"{cpt} may lack medical necessity documentation",
                            evidence=[
                                f"Current diagnoses: {', '.join(codes.icd10_codes[:3])}",
                                f"Common supporting diagnoses: {', '.join(supporting_dx[:3])}",
                            ],
                            reasoning=(
                                f"Payers require medical necessity for {cpt}. The current "
                                f"diagnosis codes may not clearly support this service. "
                                f"Consider adding a more specific diagnosis if clinically appropriate."
                            ),
                            strength=ConfidenceLevel.MEDIUM,
                            regulatory_basis=[
                                "Medicare LCD/NCD policies",
                                "Medical necessity requirements",
                            ],
                        ),
                        action_items=[
                            "Review if a more specific diagnosis applies",
                            f"Consider adding: {', '.join(supporting_dx[:2])}",
                        ],
                        documentation_needed=[
                            "Clinical indication for the service",
                            "Signs/symptoms supporting the procedure",
                        ],
                    ))

        return findings

    def _check_modifiers(
        self,
        codes: EncounterCodes,
        context: EncounterContext,
    ) -> list[OptimizationFinding]:
        """Check if modifiers should be added."""
        findings = []

        # Check for modifier 25 need (significant, separately identifiable E/M)
        em_codes = [c for c in codes.cpt_codes if c in self._em_requirements]
        procedure_codes = [c for c in codes.cpt_codes if c not in self._em_requirements]

        if em_codes and procedure_codes:
            em_code = em_codes[0]
            has_mod_25 = any(m[0] == em_code and m[1] == "25" for m in codes.modifiers)

            if not has_mod_25:
                findings.append(OptimizationFinding(
                    category=OptimizationCategory.MODIFIER_NEEDED,
                    severity=SeverityLevel.MEDIUM,
                    title=f"Modifier 25 May Be Needed: {em_code}",
                    description="E/M billed with procedure may need modifier 25",
                    current_code=em_code,
                    recommended_code=f"{em_code}-25",
                    revenue_impact=0,
                    cer_citation=BillingCERCitation(
                        claim=f"Modifier 25 may be required for {em_code}",
                        evidence=[
                            f"E/M code: {em_code}",
                            f"Procedure codes: {', '.join(procedure_codes[:2])}",
                            "No modifier 25 currently attached",
                        ],
                        reasoning=(
                            f"When an E/M service is billed with a procedure on the same day, "
                            f"modifier 25 indicates the E/M was significant and separately "
                            f"identifiable from the procedure. This may be required for payment."
                        ),
                        strength=ConfidenceLevel.MEDIUM,
                        regulatory_basis=[
                            "CPT modifier 25 guidelines",
                            "Payer E/M + procedure policies",
                        ],
                    ),
                    action_items=[
                        f"Add modifier 25 to {em_code} if E/M is separately identifiable",
                        "Ensure E/M documentation supports separate service",
                    ],
                    documentation_needed=[
                        "Separate and distinct E/M documentation",
                        "Chief complaint beyond procedure",
                    ],
                ))

        return findings

    def _analyze_documentation(
        self,
        codes: EncounterCodes,
        context: EncounterContext,
    ) -> list[OptimizationFinding]:
        """Analyze documentation for gaps that affect coding."""
        findings = []

        # Check for missing time documentation on E/M
        em_codes = [c for c in codes.cpt_codes if c in self._em_requirements]
        if em_codes and context.time_spent is None:
            findings.append(OptimizationFinding(
                category=OptimizationCategory.DOCUMENTATION_GAP,
                severity=SeverityLevel.LOW,
                title="Time Documentation Missing",
                description="Total encounter time not documented",
                current_code=em_codes[0],
                recommended_code=None,
                revenue_impact=0,
                cer_citation=BillingCERCitation(
                    claim="Time documentation could support E/M code selection",
                    evidence=[
                        "Time-based coding is an option for E/M",
                        "No time currently documented",
                    ],
                    reasoning=(
                        "Per 2021+ E/M guidelines, time can be the sole factor for code "
                        "selection. Documenting total time provides flexibility in code "
                        "selection and audit defense."
                    ),
                    strength=ConfidenceLevel.LOW,
                    regulatory_basis=["CMS E/M time-based coding"],
                ),
                action_items=[
                    "Document total time on date of encounter",
                    "Include time-based activities",
                ],
                documentation_needed=[
                    "Total time in minutes",
                    "Activities: counseling, care coordination, documentation review",
                ],
            ))

        # Check for missing MDM documentation
        if em_codes and context.mdm_complexity is None:
            findings.append(OptimizationFinding(
                category=OptimizationCategory.DOCUMENTATION_GAP,
                severity=SeverityLevel.LOW,
                title="MDM Complexity Not Clear",
                description="Medical decision making complexity not clearly documented",
                current_code=em_codes[0],
                recommended_code=None,
                revenue_impact=0,
                cer_citation=BillingCERCitation(
                    claim="Clear MDM documentation supports E/M level",
                    evidence=[
                        "MDM-based coding requires documented elements",
                        "Current MDM level unclear",
                    ],
                    reasoning=(
                        "Medical decision making documentation should clearly show: "
                        "number/complexity of problems, data reviewed, and risk. "
                        "This supports code selection and audit defense."
                    ),
                    strength=ConfidenceLevel.LOW,
                    regulatory_basis=["CMS MDM table"],
                ),
                action_items=[
                    "Document problems addressed with complexity",
                    "Document data reviewed/ordered",
                    "Document risk assessment",
                ],
                documentation_needed=[
                    "Problem list with complexity indicators",
                    "Tests/data reviewed or ordered",
                    "Risk of treatment/management",
                ],
            ))

        return findings

    def _calculate_rvu(self, cpt_codes: list[str]) -> float:
        """Calculate total work RVU for CPT codes."""
        total = 0.0
        for code in cpt_codes:
            if code in self._em_requirements:
                total += self._em_requirements[code]["work_rvu"]
            else:
                # Estimate for non-E/M codes
                total += 0.5
        return total

    def _generate_assessment(
        self,
        findings: list[OptimizationFinding],
        compliance_score: float,
    ) -> str:
        """Generate overall assessment text."""
        if not findings:
            return "Encounter coding appears optimized. No significant findings."

        high_count = sum(1 for f in findings if f.severity == SeverityLevel.HIGH)
        compliance_issues = sum(
            1 for f in findings
            if f.category in [OptimizationCategory.BUNDLING_ISSUE,
                              OptimizationCategory.COMPLIANCE_RISK,
                              OptimizationCategory.MEDICAL_NECESSITY]
        )

        parts = []

        if high_count > 0:
            parts.append(f"{high_count} high-priority findings require attention.")

        if compliance_issues > 0:
            parts.append(f"{compliance_issues} compliance issues should be addressed before submission.")

        upcode_opps = sum(1 for f in findings if f.category == OptimizationCategory.UPCODING_OPPORTUNITY)
        if upcode_opps > 0:
            parts.append(f"{upcode_opps} potential upcoding opportunities identified.")

        if compliance_score < 70:
            parts.append("Compliance score is below threshold - review recommended.")

        return " ".join(parts) if parts else "Review findings and implement recommendations."

    def get_stats(self) -> dict:
        """Get service statistics."""
        return {
            "cci_bundles_tracked": len(self._cci_bundles),
            "medical_necessity_rules": len(self._medical_necessity),
            "em_codes_tracked": len(self._em_requirements),
            "missed_service_rules": len(self._missed_services),
        }
