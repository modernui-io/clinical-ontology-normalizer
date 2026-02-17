"""Unified condition matching service for clinical guideline/calculator/policy matching.

Replaces ad-hoc substring matching (e.g., ``if sc in pc or pc in sc``) across
guideline_rag_service, clinical_agent, calculator_reasoning_service,
condition_calculator_mapping, and policy_service with a tiered, scored approach
that prevents false matches like "anemia" → "sickle cell anemia".

Matching tiers (highest to lowest):
  1. Exact match (score 1.0) — normalized string equality
  2. OMOP hierarchy match (score 0.85) — IS_A relationship via OMOPHierarchyService
  3. Qualified substring match (score 0.6) — word-boundary match that rejects
     compound medical terms (e.g., "anemia" does NOT match "sickle cell anemia")
  4. No match (score 0.0)

Primary condition gating:
  When a guideline provides ``primary_conditions``, at least one must match a
  patient condition at tier 1 or 2 before secondary conditions contribute.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compound medical terms where a substring should NOT match the full term.
# "anemia" alone must not match "sickle cell anemia" — the latter is a
# distinct disease entity, not a modifier of generic anemia.
# ---------------------------------------------------------------------------
COMPOUND_TERM_REGISTRY: set[str] = {
    # Anemia subtypes
    "sickle cell anemia",
    "sickle cell disease",
    "pernicious anemia",
    "aplastic anemia",
    "fanconi anemia",
    "diamond-blackfan anemia",
    "hemolytic anemia",
    "megaloblastic anemia",
    "sideroblastic anemia",
    "thalassemia",
    # Cancer subtypes (prevent "cancer" matching wrong type)
    "breast cancer",
    "lung cancer",
    "colorectal cancer",
    "colon cancer",
    "rectal cancer",
    "pancreatic cancer",
    "prostate cancer",
    "ovarian cancer",
    "cervical cancer",
    "bladder cancer",
    "liver cancer",
    "hepatocellular carcinoma",
    "renal cell carcinoma",
    "thyroid cancer",
    "gastric cancer",
    "esophageal cancer",
    "endometrial cancer",
    "skin cancer",
    "melanoma",
    "basal cell carcinoma",
    "squamous cell carcinoma",
    "non-small cell lung cancer",
    "small cell lung cancer",
    # Heart disease subtypes
    "coronary artery disease",
    "peripheral artery disease",
    "peripheral arterial disease",
    "aortic valve disease",
    "mitral valve disease",
    "rheumatic heart disease",
    "congenital heart disease",
    "ischemic heart disease",
    # Kidney disease subtypes
    "polycystic kidney disease",
    "diabetic kidney disease",
    "chronic kidney disease",
    "acute kidney injury",
    # Diabetes subtypes
    "type 1 diabetes",
    "type 2 diabetes",
    "gestational diabetes",
    # Pain subtypes
    "low back pain",
    "neuropathic pain",
    "chronic pain",
    # Other compound terms
    "cystic fibrosis",
    "multiple sclerosis",
    "amyotrophic lateral sclerosis",
    "systemic lupus erythematosus",
    "rheumatoid arthritis",
    "psoriatic arthritis",
    "reactive arthritis",
    "ankylosing spondylitis",
    "inflammatory bowel disease",
    "irritable bowel syndrome",
    "celiac disease",
    "crohn disease",
    "ulcerative colitis",
    "pulmonary embolism",
    "deep vein thrombosis",
    "atrial fibrillation",
    "ventricular tachycardia",
    "pulmonary hypertension",
    "portal hypertension",
    "intracranial hypertension",
    "obstructive sleep apnea",
    "central sleep apnea",
}


@dataclass
class ConditionMatch:
    """Result of matching a single patient condition to a single target condition."""

    patient_condition: str
    target_condition: str
    score: float  # 0.0 – 1.0
    tier: str  # "exact" | "hierarchy" | "qualified_substring" | "none"


@dataclass
class MatchResult:
    """Aggregate result of matching patient conditions against a set of target conditions."""

    matches: list[ConditionMatch] = field(default_factory=list)
    best_score: float = 0.0
    primary_gate_passed: bool = True  # True when no primary_conditions constraint

    @property
    def has_match(self) -> bool:
        return self.best_score > 0.0 and self.primary_gate_passed


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

_STRIP_RE = re.compile(r"[^a-z0-9\s-]")


def _normalize(term: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace."""
    return _STRIP_RE.sub("", term.lower()).strip()


def _normalize_set(terms: list[str] | set[str]) -> set[str]:
    return {_normalize(t) for t in terms if t}


# ---------------------------------------------------------------------------
# Core matching logic
# ---------------------------------------------------------------------------

def _is_compound_term_conflict(short: str, long: str) -> bool:
    """Return True when *short* is a sub-phrase of a compound medical term
    that appears in *long*, meaning the substring match is misleading.

    Example: short="anemia", long="sickle cell anemia" → True
    (because "sickle cell anemia" is a registered compound term and
    "anemia" is merely its suffix, not an equivalent condition).
    """
    long_n = _normalize(long)
    short_n = _normalize(short)

    if short_n == long_n:
        return False  # exact match, not a conflict

    for compound in COMPOUND_TERM_REGISTRY:
        compound_n = _normalize(compound)
        # The long string must contain (or be) the compound term
        if compound_n in long_n or long_n in compound_n:
            # And the short string must be a proper sub-phrase of that compound
            if short_n != compound_n and short_n in compound_n:
                return True
    return False


def _word_boundary_match(candidate: str, target: str) -> bool:
    """Check if *candidate* appears in *target* at a word boundary.

    "anemia" in "iron deficiency anemia" → True  (word boundary)
    "anemia" in "sickle cell anemia"     → True at word level, but blocked by compound check
    "cancer" in "pancreatic cancer"       → True  (word boundary)
    "can"    in "pancreatic cancer"       → False (not at word boundary)
    """
    candidate_n = _normalize(candidate)
    target_n = _normalize(target)
    pattern = r"(?:^|\s)" + re.escape(candidate_n) + r"(?:\s|$)"
    return bool(re.search(pattern, target_n))


def _match_single(
    patient_cond: str,
    target_cond: str,
    *,
    use_hierarchy: bool = True,
) -> ConditionMatch:
    """Score a single patient-condition vs. target-condition pair."""
    pc = _normalize(patient_cond)
    tc = _normalize(target_cond)

    # Tier 1: Exact match
    if pc == tc:
        return ConditionMatch(patient_cond, target_cond, 1.0, "exact")

    # Tier 2: OMOP hierarchy match
    if use_hierarchy:
        try:
            from app.services.omop_hierarchy_service import get_omop_hierarchy_service

            hierarchy = get_omop_hierarchy_service()
            if hierarchy.is_available:
                result = hierarchy.check_hierarchy_match(pc, tc, max_distance=3)
                if result.matched:
                    return ConditionMatch(patient_cond, target_cond, 0.85, "hierarchy")
        except Exception:
            pass  # hierarchy unavailable — fall through

    # Tier 3: Qualified substring match with compound-term protection
    # Check both directions: candidate in target, target in candidate
    for short, long in [(pc, tc), (tc, pc)]:
        if short in long and short != long:
            # Block if it's a compound-term conflict
            if _is_compound_term_conflict(short, long):
                continue
            # Require word-boundary match
            if _word_boundary_match(short, long):
                return ConditionMatch(patient_cond, target_cond, 0.6, "qualified_substring")

    # Also check word-level overlap for multi-word conditions
    pc_words = set(pc.split())
    tc_words = set(tc.split())
    common = {w for w in (pc_words & tc_words) if len(w) > 3}
    if common:
        # Only count word overlap if no compound-term conflict
        if not _is_compound_term_conflict(pc, tc) and not _is_compound_term_conflict(tc, pc):
            return ConditionMatch(patient_cond, target_cond, 0.4, "qualified_substring")

    return ConditionMatch(patient_cond, target_cond, 0.0, "none")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_conditions(
    patient_conditions: list[str] | set[str],
    target_conditions: list[str] | set[str],
    primary_conditions: list[str] | None = None,
    *,
    use_hierarchy: bool = True,
) -> MatchResult:
    """Match a patient's conditions against a guideline/calculator/policy's target conditions.

    Args:
        patient_conditions: Conditions the patient has.
        target_conditions: Conditions the guideline/calculator/policy applies to.
        primary_conditions: If set, the guideline's *primary* disease(s). At least
            one must match at tier 1 or 2 before secondary conditions contribute.
        use_hierarchy: Whether to attempt OMOP hierarchy lookups.

    Returns:
        MatchResult with per-pair scores, best_score, and primary_gate_passed.
    """
    result = MatchResult()
    pc_list = list(patient_conditions) if not isinstance(patient_conditions, list) else patient_conditions
    tc_list = list(target_conditions) if not isinstance(target_conditions, list) else target_conditions

    if not pc_list or not tc_list:
        return result

    # Primary-condition gating
    if primary_conditions:
        result.primary_gate_passed = False
        primary_norm = _normalize_set(primary_conditions)
        for pc in pc_list:
            pc_norm = _normalize(pc)
            for prim in primary_norm:
                m = _match_single(pc_norm, prim, use_hierarchy=use_hierarchy)
                if m.score >= 0.85:  # tier 1 or 2
                    result.primary_gate_passed = True
                    break
            if result.primary_gate_passed:
                break

    if not result.primary_gate_passed:
        # Primary gate failed — no matches should count
        return result

    # Score all patient×target pairs, keep best per target
    best_per_target: dict[str, ConditionMatch] = {}
    for pc in pc_list:
        for tc in tc_list:
            m = _match_single(pc, tc, use_hierarchy=use_hierarchy)
            if m.score > 0:
                tc_key = _normalize(tc)
                if tc_key not in best_per_target or m.score > best_per_target[tc_key].score:
                    best_per_target[tc_key] = m

    result.matches = list(best_per_target.values())
    if result.matches:
        result.best_score = max(m.score for m in result.matches)

    return result


def match_conditions_simple(
    patient_conditions: list[str] | set[str],
    target_conditions: list[str] | set[str],
    *,
    use_hierarchy: bool = True,
) -> bool:
    """Convenience: return True if any patient condition matches any target condition."""
    r = match_conditions(patient_conditions, target_conditions, use_hierarchy=use_hierarchy)
    return r.has_match


def score_condition_overlap(
    patient_conditions: list[str] | set[str],
    target_conditions: list[str] | set[str],
    primary_conditions: list[str] | None = None,
    *,
    use_hierarchy: bool = True,
) -> float:
    """Return a 0.0–1.0 score representing how well patient conditions align
    with target conditions. Useful as a relevance-scoring primitive."""
    r = match_conditions(
        patient_conditions, target_conditions, primary_conditions,
        use_hierarchy=use_hierarchy,
    )
    if not r.has_match:
        return 0.0
    # Aggregate: best_score weighted by fraction of targets matched
    coverage = len(r.matches) / max(len(list(target_conditions)), 1)
    return round(r.best_score * (0.7 + 0.3 * min(coverage, 1.0)), 4)
