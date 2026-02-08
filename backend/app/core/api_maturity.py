"""API endpoint maturity classification.

Maps router prefixes to maturity tiers (PRODUCTION, PILOT, SCAFFOLD).
Used by MaturityGateMiddleware to block scaffold endpoints in production
and label all responses with an X-API-Maturity header.
"""

from __future__ import annotations

from enum import Enum


class EndpointMaturity(str, Enum):
    """Maturity tier for API endpoints."""

    PRODUCTION = "production"
    PILOT = "pilot"
    SCAFFOLD = "scaffold"


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
    # ── PILOT: established features, not yet hardened ──
    "/trials": EndpointMaturity.PILOT,
    "/fhir": EndpointMaturity.PILOT,
    "/graph": EndpointMaturity.PILOT,
    "/graph-rag": EndpointMaturity.PILOT,
    "/graph/reasoning": EndpointMaturity.PILOT,
    "/nlp": EndpointMaturity.PILOT,
    "/cohorts": EndpointMaturity.PILOT,
    "/terminology": EndpointMaturity.PILOT,  # shares /fhir prefix but has own router
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
    "/prediction-audit": EndpointMaturity.PILOT,  # nested under /predictions/audit
    "/data-sources": EndpointMaturity.PILOT,
    "/kg/health": EndpointMaturity.PILOT,
    "/coding-assistant": EndpointMaturity.PILOT,
    "/ai-coding": EndpointMaturity.PILOT,
    "/feedback": EndpointMaturity.PILOT,
    # ── SCAFFOLD: experimental / not wired ──
    "/agent": EndpointMaturity.SCAFFOLD,
    "/clinical-agent": EndpointMaturity.SCAFFOLD,
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
