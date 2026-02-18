"""API endpoint maturity classification.

Maps router prefixes to maturity tiers (PRODUCTION, PILOT, SCAFFOLD).
Used by MaturityGateMiddleware to block scaffold endpoints in production
and label all responses with an X-API-Maturity header.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EndpointMaturity(str, Enum):
    """Maturity tier for API endpoints."""

    PRODUCTION = "production"
    PILOT = "pilot"
    SCAFFOLD = "scaffold"


@dataclass
class DeprecationInfo:
    """Deprecation metadata for a route prefix."""

    sunset_date: str  # ISO date
    successor: str | None = None  # replacement path prefix
    message: str = ""


DEPRECATION_SCHEDULE: dict[str, DeprecationInfo] = {
    "/nlp": DeprecationInfo(
        sunset_date="2026-06-30",
        successor="/clinical-agent",
        message="Migrate to /api/v1/clinical-agent",
    ),
}


# Map URL path prefixes (under /api/v1) to maturity tiers.
# Paths are matched longest-prefix-first by the middleware.
ENDPOINT_MATURITY_REGISTRY: dict[str, EndpointMaturity] = {
    # ── PRODUCTION: core data paths, billing, drug safety ──
    "/patients": EndpointMaturity.PRODUCTION,
    "/documents": EndpointMaturity.PRODUCTION,
    "/search": EndpointMaturity.PRODUCTION,
    "/coding": EndpointMaturity.PRODUCTION,
    "/auth": EndpointMaturity.PRODUCTION,
    "/users": EndpointMaturity.PRODUCTION,
    "/jobs": EndpointMaturity.PRODUCTION,
    "/audit": EndpointMaturity.PRODUCTION,
    "/export": EndpointMaturity.PRODUCTION,
    "/notes": EndpointMaturity.PRODUCTION,
    "/drug-safety": EndpointMaturity.PRODUCTION,
    "/icd10-suggestions": EndpointMaturity.PRODUCTION,
    "/cpt-suggestions": EndpointMaturity.PRODUCTION,
    "/hcc-analysis": EndpointMaturity.PRODUCTION,
    "/differential-diagnosis": EndpointMaturity.PRODUCTION,
    "/calculators": EndpointMaturity.PRODUCTION,
    "/lab-reference": EndpointMaturity.PRODUCTION,
    "/vocabulary-mapping": EndpointMaturity.PRODUCTION,
    "/vocabularies": EndpointMaturity.PRODUCTION,
    "/dashboard": EndpointMaturity.PRODUCTION,
    "/reconciliation": EndpointMaturity.PRODUCTION,
    "/notifications": EndpointMaturity.PRODUCTION,
    "/metriport": EndpointMaturity.PRODUCTION,
    "/quality": EndpointMaturity.PRODUCTION,
    "/quality-measures": EndpointMaturity.PRODUCTION,
    # ── PRODUCTION: observability ──
    "/health": EndpointMaturity.PRODUCTION,
    "/metrics": EndpointMaturity.PRODUCTION,
    "/diagnostics": EndpointMaturity.PRODUCTION,
    # ── PILOT: established features, not yet hardened ──
    "/trials": EndpointMaturity.PILOT,
    "/fhir": EndpointMaturity.PILOT,
    "/graph": EndpointMaturity.PILOT,
    "/graph-rag": EndpointMaturity.PILOT,
    "/graph/reasoning": EndpointMaturity.PILOT,
    "/nlp": EndpointMaturity.PILOT,
    "/cohorts": EndpointMaturity.PILOT,
    "/terminology": EndpointMaturity.PILOT,
    "/valuesets": EndpointMaturity.PILOT,
    "/semantic-search": EndpointMaturity.PILOT,
    "/timeline": EndpointMaturity.PILOT,
    "/smart": EndpointMaturity.PILOT,
    "/smart-server": EndpointMaturity.PILOT,
    "/cds-services": EndpointMaturity.PILOT,
    "/etl": EndpointMaturity.PILOT,
    "/predictions": EndpointMaturity.PILOT,
    "/risk": EndpointMaturity.PILOT,
    "/risk-thresholds": EndpointMaturity.PILOT,
    "/alert-rules": EndpointMaturity.PILOT,
    "/prediction-audit": EndpointMaturity.PILOT,
    "/data-sources": EndpointMaturity.PILOT,
    "/kg/health": EndpointMaturity.PILOT,
    "/coding-assistant": EndpointMaturity.PILOT,
    "/ai-coding": EndpointMaturity.PILOT,
    "/feedback": EndpointMaturity.PILOT,
    "/clinical-agent": EndpointMaturity.PILOT,
    # ── PILOT: clinical trials integration ──
    "/sites": EndpointMaturity.PILOT,
    "/screening-results": EndpointMaturity.PILOT,
    "/medidata-rave": EndpointMaturity.PILOT,
    "/veeva-vault": EndpointMaturity.PILOT,
    "/lineage": EndpointMaturity.PILOT,
    "/consent": EndpointMaturity.PILOT,
    "/clinician-feedback": EndpointMaturity.PILOT,
    # ── SCAFFOLD: experimental / not wired ──
    "/agent": EndpointMaturity.SCAFFOLD,
    "/guidelines": EndpointMaturity.SCAFFOLD,
    "/federated": EndpointMaturity.SCAFFOLD,
    "/tefca": EndpointMaturity.SCAFFOLD,
    "/synthetic": EndpointMaturity.SCAFFOLD,
    "/streaming": EndpointMaturity.SCAFFOLD,
    "/ws": EndpointMaturity.SCAFFOLD,
    "/sse": EndpointMaturity.SCAFFOLD,
    "/llm": EndpointMaturity.SCAFFOLD,
    "/llm/finetune": EndpointMaturity.SCAFFOLD,
    "/voice": EndpointMaturity.SCAFFOLD,
    "/model-registry": EndpointMaturity.SCAFFOLD,
    "/pipeline-scheduling": EndpointMaturity.SCAFFOLD,
    "/data-completeness": EndpointMaturity.SCAFFOLD,
    "/data-consistency": EndpointMaturity.SCAFFOLD,
    "/phenotypes": EndpointMaturity.SCAFFOLD,
    "/pipelines": EndpointMaturity.SCAFFOLD,
    "/kg/benchmark": EndpointMaturity.SCAFFOLD,
    "/kg/orchestration": EndpointMaturity.SCAFFOLD,
    "/fhir/knowledge-graph": EndpointMaturity.SCAFFOLD,
    "/cdisc": EndpointMaturity.SCAFFOLD,
    "/ai": EndpointMaturity.SCAFFOLD,
    "/assistant": EndpointMaturity.SCAFFOLD,
    "/visualizations": EndpointMaturity.SCAFFOLD,
    "/policy": EndpointMaturity.SCAFFOLD,
    # ── SCAFFOLD: clinical trial operations ──
    "/access-review": EndpointMaturity.SCAFFOLD,
    "/adaptive-trial": EndpointMaturity.SCAFFOLD,
    "/adverse-event-reconciliation": EndpointMaturity.SCAFFOLD,
    "/adverse-events": EndpointMaturity.SCAFFOLD,
    "/ancillary-studies": EndpointMaturity.SCAFFOLD,
    "/benefit-risk-assessment": EndpointMaturity.SCAFFOLD,
    "/biobank": EndpointMaturity.SCAFFOLD,
    "/bioequivalence": EndpointMaturity.SCAFFOLD,
    "/biomarker-analysis": EndpointMaturity.SCAFFOLD,
    "/biostatistics-ops": EndpointMaturity.SCAFFOLD,
    "/capa-management": EndpointMaturity.SCAFFOLD,
    "/cdisc-standards": EndpointMaturity.SCAFFOLD,
    "/central-irb": EndpointMaturity.SCAFFOLD,
    "/central-laboratory": EndpointMaturity.SCAFFOLD,
    "/central-monitoring": EndpointMaturity.SCAFFOLD,
    "/clinical-data-management": EndpointMaturity.SCAFFOLD,
    "/clinical-data-review": EndpointMaturity.SCAFFOLD,
    "/clinical-event-adjudication": EndpointMaturity.SCAFFOLD,
    "/clinical-hold-management": EndpointMaturity.SCAFFOLD,
    "/clinical-monitoring": EndpointMaturity.SCAFFOLD,
    "/clinical-ops-metrics": EndpointMaturity.SCAFFOLD,
    "/clinical-operations-analytics": EndpointMaturity.SCAFFOLD,
    "/clinical-outcome-assessment": EndpointMaturity.SCAFFOLD,
    "/clinical-pharmacokinetics": EndpointMaturity.SCAFFOLD,
    "/clinical-pharmacology": EndpointMaturity.SCAFFOLD,
    "/clinical-simulation": EndpointMaturity.SCAFFOLD,
    "/clinical-supply-forecast": EndpointMaturity.SCAFFOLD,
    "/clinical-supply-returns": EndpointMaturity.SCAFFOLD,
    "/clinical-trial-agreement": EndpointMaturity.SCAFFOLD,
    "/clinical-valuesets": EndpointMaturity.SCAFFOLD,
    "/cohort-phenotypes": EndpointMaturity.SCAFFOLD,
    "/companion-diagnostics": EndpointMaturity.SCAFFOLD,
    "/concomitant-medication": EndpointMaturity.SCAFFOLD,
    "/consent-preferences": EndpointMaturity.SCAFFOLD,
    "/contract-lifecycle": EndpointMaturity.SCAFFOLD,
    "/crf-management": EndpointMaturity.SCAFFOLD,
    "/criteria": EndpointMaturity.SCAFFOLD,
    "/cross-functional-team": EndpointMaturity.SCAFFOLD,
    "/ctms": EndpointMaturity.SCAFFOLD,
    "/data-locks": EndpointMaturity.SCAFFOLD,
    "/data-privacy": EndpointMaturity.SCAFFOLD,
    "/data-queries": EndpointMaturity.SCAFFOLD,
    "/data-quality": EndpointMaturity.SCAFFOLD,
    "/data-quality/mapping": EndpointMaturity.SCAFFOLD,
    "/data-transfer": EndpointMaturity.SCAFFOLD,
    "/decentralized-trials": EndpointMaturity.SCAFFOLD,
    "/defect-tracking": EndpointMaturity.SCAFFOLD,
    "/delegation-log": EndpointMaturity.SCAFFOLD,
    "/digital-biomarkers": EndpointMaturity.SCAFFOLD,
    "/document-management": EndpointMaturity.SCAFFOLD,
    "/dose-escalation": EndpointMaturity.SCAFFOLD,
    "/drift": EndpointMaturity.SCAFFOLD,
    "/drug-accountability": EndpointMaturity.SCAFFOLD,
    "/dsmb": EndpointMaturity.SCAFFOLD,
    "/dsmb-management": EndpointMaturity.SCAFFOLD,
    "/ectd-submission": EndpointMaturity.SCAFFOLD,
    "/econsent": EndpointMaturity.SCAFFOLD,
    "/edc": EndpointMaturity.SCAFFOLD,
    "/edc-forms": EndpointMaturity.SCAFFOLD,
    "/emergency-unblinding": EndpointMaturity.SCAFFOLD,
    "/endpoint-adjudication": EndpointMaturity.SCAFFOLD,
    "/endpoint-adjudication-committee": EndpointMaturity.SCAFFOLD,
    "/enrollment-forecasting": EndpointMaturity.SCAFFOLD,
    "/environmental-monitoring": EndpointMaturity.SCAFFOLD,
    "/epro": EndpointMaturity.SCAFFOLD,
    "/experiments": EndpointMaturity.SCAFFOLD,
    "/external-data-integration": EndpointMaturity.SCAFFOLD,
    "/fairness": EndpointMaturity.SCAFFOLD,
    "/ha-meeting-tracker": EndpointMaturity.SCAFFOLD,
    "/heor": EndpointMaturity.SCAFFOLD,
    "/imaging-management": EndpointMaturity.SCAFFOLD,
    "/inspection-readiness": EndpointMaturity.SCAFFOLD,
    "/interim-analysis": EndpointMaturity.SCAFFOLD,
    "/inventory-reconciliation": EndpointMaturity.SCAFFOLD,
    "/investigator-brochure": EndpointMaturity.SCAFFOLD,
    "/investigator-management": EndpointMaturity.SCAFFOLD,
    "/investigator-meeting": EndpointMaturity.SCAFFOLD,
    "/investigator-oversight": EndpointMaturity.SCAFFOLD,
    "/invoice-management": EndpointMaturity.SCAFFOLD,
    "/ip-accountability": EndpointMaturity.SCAFFOLD,
    "/irt": EndpointMaturity.SCAFFOLD,
    "/lab-certification": EndpointMaturity.SCAFFOLD,
    "/lab-data-management": EndpointMaturity.SCAFFOLD,
    "/lab-proficiency": EndpointMaturity.SCAFFOLD,
    "/labeling-management": EndpointMaturity.SCAFFOLD,
    "/language-services": EndpointMaturity.SCAFFOLD,
    "/manufacturing-ops": EndpointMaturity.SCAFFOLD,
    "/medical-affairs": EndpointMaturity.SCAFFOLD,
    "/medical-coding": EndpointMaturity.SCAFFOLD,
    "/medical-device-tracking": EndpointMaturity.SCAFFOLD,
    "/medical-information": EndpointMaturity.SCAFFOLD,
    "/medical-monitor": EndpointMaturity.SCAFFOLD,
    "/medical-review": EndpointMaturity.SCAFFOLD,
    "/medical-writing": EndpointMaturity.SCAFFOLD,
    "/medications": EndpointMaturity.SCAFFOLD,
    "/patient-diary": EndpointMaturity.SCAFFOLD,
    "/patient-insurance-verification": EndpointMaturity.SCAFFOLD,
    "/patient-registry": EndpointMaturity.SCAFFOLD,
    "/patient-retention": EndpointMaturity.SCAFFOLD,
    "/patient-stipends": EndpointMaturity.SCAFFOLD,
    "/patient-stratification": EndpointMaturity.SCAFFOLD,
    "/patient-travel": EndpointMaturity.SCAFFOLD,
    "/patient-visit-tracking": EndpointMaturity.SCAFFOLD,
    "/pharmacogenomics": EndpointMaturity.SCAFFOLD,
    "/pharmacovigilance": EndpointMaturity.SCAFFOLD,
    "/post-marketing-surveillance": EndpointMaturity.SCAFFOLD,
    "/product-complaint": EndpointMaturity.SCAFFOLD,
    "/product-licensure": EndpointMaturity.SCAFFOLD,
    "/protocol-amendments": EndpointMaturity.SCAFFOLD,
    "/protocol-compliance": EndpointMaturity.SCAFFOLD,
    "/protocol-design": EndpointMaturity.SCAFFOLD,
    "/protocol-deviations": EndpointMaturity.SCAFFOLD,
    "/protocol-feasibility": EndpointMaturity.SCAFFOLD,
    "/protocol-knowledge-assessment": EndpointMaturity.SCAFFOLD,
    "/publication-planning": EndpointMaturity.SCAFFOLD,
    "/quality-management": EndpointMaturity.SCAFFOLD,
    "/randomization": EndpointMaturity.SCAFFOLD,
    "/real-world-evidence": EndpointMaturity.SCAFFOLD,
    "/reference-safety-info": EndpointMaturity.SCAFFOLD,
    "/referrals": EndpointMaturity.SCAFFOLD,
    "/regulatory-correspondence": EndpointMaturity.SCAFFOLD,
    "/regulatory-inspection": EndpointMaturity.SCAFFOLD,
    "/regulatory-intelligence": EndpointMaturity.SCAFFOLD,
    "/regulatory-intelligence-hub": EndpointMaturity.SCAFFOLD,
    "/regulatory-submissions": EndpointMaturity.SCAFFOLD,
    "/risk-based-monitoring": EndpointMaturity.SCAFFOLD,
    "/risk-management": EndpointMaturity.SCAFFOLD,
    "/sae-reporting": EndpointMaturity.SCAFFOLD,
    "/safety-database": EndpointMaturity.SCAFFOLD,
    "/safety-monitoring": EndpointMaturity.SCAFFOLD,
    "/safety-signal-detection": EndpointMaturity.SCAFFOLD,
    "/screen-failure": EndpointMaturity.SCAFFOLD,
    "/screening-dashboard": EndpointMaturity.SCAFFOLD,
    "/signal-detection": EndpointMaturity.SCAFFOLD,
    "/site-audit": EndpointMaturity.SCAFFOLD,
    "/site-communication": EndpointMaturity.SCAFFOLD,
    "/site-feasibility": EndpointMaturity.SCAFFOLD,
    "/site-initiation": EndpointMaturity.SCAFFOLD,
    "/site-payments": EndpointMaturity.SCAFFOLD,
    "/site-performance": EndpointMaturity.SCAFFOLD,
    "/site-qualification": EndpointMaturity.SCAFFOLD,
    "/site-resource-planning": EndpointMaturity.SCAFFOLD,
    "/source-data-verification": EndpointMaturity.SCAFFOLD,
    "/specimen-management": EndpointMaturity.SCAFFOLD,
    "/statistical-analysis": EndpointMaturity.SCAFFOLD,
    "/study-closeout": EndpointMaturity.SCAFFOLD,
    "/study-startup": EndpointMaturity.SCAFFOLD,
    "/subject-withdrawal": EndpointMaturity.SCAFFOLD,
    "/supply-chain": EndpointMaturity.SCAFFOLD,
    "/supply-forecasting": EndpointMaturity.SCAFFOLD,
    "/supply-serialization": EndpointMaturity.SCAFFOLD,
    "/terminology/review-queue": EndpointMaturity.SCAFFOLD,
    "/tissue-tracking": EndpointMaturity.SCAFFOLD,
    "/training": EndpointMaturity.SCAFFOLD,
    "/treatment-compliance-monitoring": EndpointMaturity.SCAFFOLD,
    "/trial-disclosure": EndpointMaturity.SCAFFOLD,
    "/trial-insurance": EndpointMaturity.SCAFFOLD,
    "/trial-management": EndpointMaturity.SCAFFOLD,
    "/unblinding-management": EndpointMaturity.SCAFFOLD,
    # ── SCAFFOLD: compliance & security ──
    "/compliance/hitrust": EndpointMaturity.SCAFFOLD,
    "/compliance/soc2": EndpointMaturity.SCAFFOLD,
    "/incident-response": EndpointMaturity.SCAFFOLD,
    "/pentest-management": EndpointMaturity.SCAFFOLD,
    "/privacy-impact": EndpointMaturity.SCAFFOLD,
    "/admin/secrets": EndpointMaturity.SCAFFOLD,
    "/security": EndpointMaturity.SCAFFOLD,
    "/security/incidents": EndpointMaturity.SCAFFOLD,
    "/security/network": EndpointMaturity.SCAFFOLD,
    "/threat-intelligence": EndpointMaturity.SCAFFOLD,
    "/vulnerability-management": EndpointMaturity.SCAFFOLD,
    "/governance": EndpointMaturity.SCAFFOLD,
    "/governance/classification": EndpointMaturity.SCAFFOLD,
    "/policies": EndpointMaturity.SCAFFOLD,
    # ── SCAFFOLD: infrastructure & DevOps ──
    "/api-gateway": EndpointMaturity.SCAFFOLD,
    "/api-management": EndpointMaturity.SCAFFOLD,
    "/architecture/scalability": EndpointMaturity.SCAFFOLD,
    "/cicd-pipeline": EndpointMaturity.SCAFFOLD,
    "/deployment-verification": EndpointMaturity.SCAFFOLD,
    "/disaster-recovery": EndpointMaturity.SCAFFOLD,
    "/infrastructure": EndpointMaturity.SCAFFOLD,
    "/infrastructure/iac": EndpointMaturity.SCAFFOLD,
    "/infrastructure/scaling": EndpointMaturity.SCAFFOLD,
    "/observability": EndpointMaturity.SCAFFOLD,
    "/performance-benchmarks": EndpointMaturity.SCAFFOLD,
    "/regression-testing": EndpointMaturity.SCAFFOLD,
    "/release-management": EndpointMaturity.SCAFFOLD,
    "/validation": EndpointMaturity.SCAFFOLD,
    # ── SCAFFOLD: analytics & reporting ──
    "/analytics/diversity": EndpointMaturity.SCAFFOLD,
    "/analytics/screening": EndpointMaturity.SCAFFOLD,
    "/competitive-intelligence": EndpointMaturity.SCAFFOLD,
    "/diversity-analytics": EndpointMaturity.SCAFFOLD,
    "/operational-dashboard": EndpointMaturity.SCAFFOLD,
    "/revenue-analytics": EndpointMaturity.SCAFFOLD,
    "/user-analytics": EndpointMaturity.SCAFFOLD,
    # ── SCAFFOLD: data management & integration ──
    "/batch": EndpointMaturity.SCAFFOLD,
    "/etl-management": EndpointMaturity.SCAFFOLD,
    "/etl-validation": EndpointMaturity.SCAFFOLD,
    "/etmf": EndpointMaturity.SCAFFOLD,
    "/feature-store": EndpointMaturity.SCAFFOLD,
    "/fhir-validation": EndpointMaturity.SCAFFOLD,
    "/openehr": EndpointMaturity.SCAFFOLD,
    "/x12": EndpointMaturity.SCAFFOLD,
    "/kg/completeness": EndpointMaturity.SCAFFOLD,
    # ── SCAFFOLD: ML & AI operations ──
    "/agent-chat": EndpointMaturity.SCAFFOLD,
    "/engagement": EndpointMaturity.SCAFFOLD,
    "/llm-settings": EndpointMaturity.SCAFFOLD,
    "/ml": EndpointMaturity.SCAFFOLD,
    "/ml/gold-standard": EndpointMaturity.SCAFFOLD,
    "/model-governance": EndpointMaturity.SCAFFOLD,
    "/pipeline": EndpointMaturity.SCAFFOLD,
    # ── SCAFFOLD: financial & vendor management ──
    "/budget-management": EndpointMaturity.SCAFFOLD,
    "/cost-modeling": EndpointMaturity.SCAFFOLD,
    "/payment-reconciliation": EndpointMaturity.SCAFFOLD,
    "/vendor-management": EndpointMaturity.SCAFFOLD,
    "/vendor-qualification": EndpointMaturity.SCAFFOLD,
    "/workforce-planning": EndpointMaturity.SCAFFOLD,
    # ── SCAFFOLD: regulatory & submissions ──
    "/country-regulatory": EndpointMaturity.SCAFFOLD,
    "/partnerships/integrations": EndpointMaturity.SCAFFOLD,
    "/partnerships/rfp": EndpointMaturity.SCAFFOLD,
    "/portfolio-governance": EndpointMaturity.SCAFFOLD,
    # ── SCAFFOLD: operations & logistics ──
    "/operations/bc": EndpointMaturity.SCAFFOLD,
    "/ops": EndpointMaturity.SCAFFOLD,
}

# Pre-sort prefixes longest-first so matching picks the most specific prefix.
_SORTED_PREFIXES: list[tuple[str, EndpointMaturity]] = sorted(
    ENDPOINT_MATURITY_REGISTRY.items(),
    key=lambda item: len(item[0]),
    reverse=True,
)


def classify_path(path: str) -> EndpointMaturity | None:
    """Return the maturity tier for a request path, or None if unclassified.

    Strips the /api/v1 prefix before matching against the registry.
    """
    # Strip versioned API prefix
    api_prefix = "/api/v1"
    if path.startswith(api_prefix):
        path = path[len(api_prefix):]

    if not path or path == "/":
        return None

    for prefix, maturity in _SORTED_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return maturity

    return None


def validate_completeness(registered_prefixes: set[str]) -> list[str]:
    """Return list of prefixes not covered by the maturity registry."""
    missing = []
    for prefix in sorted(registered_prefixes):
        if classify_path(f"/api/v1{prefix}") is None:
            missing.append(prefix)
    return missing
