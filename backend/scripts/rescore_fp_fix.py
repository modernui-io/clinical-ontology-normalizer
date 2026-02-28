#!/usr/bin/env python3
"""Re-score benchmark checkpoints with FP-fix scoring logic.

Self-contained — all scoring logic inlined, no imports from evaluator modules.
Reads checkpoint JSONL files, deduplicates by question_id (keep last entry),
rescores with both old and fixed evaluators, and prints before/after comparison.

Fixes applied:
  1. Abstention gate — model says "notes do not mention" → scored as wrong
  2. Sequence — requires ordering keywords (not just term overlap)
  3. Change — requires change keywords (not just term overlap)
  4. Duration — removes min-0.5 floor for has_duration
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# ============================================================================
# Shared helpers
# ============================================================================

def _make_patterns(keywords: list[str]) -> list[re.Pattern]:
    return [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in keywords]


def _has_match(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)


def _strip_evidence_echo(text: str) -> str:
    """Strip echoed evidence preamble before scoring."""
    stripped = text.strip()
    preamble_starts = (
        "Assertion Notes",
        "=== TEMPORAL STATUS",
        "=== CURRENT STATUS",
        "=== CROSS-ADMISSION",
    )
    if not any(stripped.startswith(p) for p in preamble_starts):
        return text

    parts = re.split(r"\n\n+", text)
    for part in parts[1:]:
        s = part.strip()
        if not s:
            continue
        first_line = s.split("\n")[0].strip()
        if first_line.startswith(("-", "*", ">", "=", "#", "|")):
            continue
        if first_line.startswith("Assertion"):
            continue
        return s

    lines = text.split("\n")
    for i, line in enumerate(lines):
        s = line.strip()
        if i > 0 and s and not s.startswith(("-", "*", ">", "Assertion", "=", "#", "|")):
            return "\n".join(lines[i:]).strip()
    return text


# ============================================================================
# Abstention detection (NEW in fixed scorer)
# ============================================================================

_ABSTENTION_PATTERNS = [
    re.compile(
        r'\b(?:notes?|records?|documentation)\b.*\b(?:do(?:es)?\s+not|lack[s]?|fail[s]?\s+to)'
        r'\s+(?:mention|contain|include|provide|document|address|specify)',
        re.IGNORECASE,
    ),
    re.compile(
        r'\bno\s+(?:mention|information|data)\s+(?:of|about|regarding|concerning)\b',
        re.IGNORECASE,
    ),
    re.compile(
        r'\b(?:cannot|can\'?t|unable\s+to)\s+(?:determine|assess|evaluate|answer|ascertain|establish)\b',
        re.IGNORECASE,
    ),
    re.compile(
        r'\b(?:insufficient|inadequate)\s+(?:evidence|information|data|documentation)\b',
        re.IGNORECASE,
    ),
    re.compile(
        r'\bnot\s+(?:mentioned|documented|provided|available|specified|addressed|included)\b',
        re.IGNORECASE,
    ),
    re.compile(
        r'\b(?:information|evidence|data)\s+is\s+(?:missing|unavailable|lacking|absent|not\s+available)\b',
        re.IGNORECASE,
    ),
    re.compile(
        r'\b(?:provided|available)\s+(?:notes?|records?)\s+do(?:es)?\s+not\b',
        re.IGNORECASE,
    ),
]

_CLINICAL_CLAIM_PATTERNS = [
    re.compile(r'\bpatient\s+(?:does\s+not|has\s+not|is\s+not|did\s+not)\b', re.IGNORECASE),
    re.compile(r'\b(?:denies|denied|ruled\s+out)\b', re.IGNORECASE),
    re.compile(r'\bno\s+evidence\s+of\b', re.IGNORECASE),
    re.compile(r'\bpatient\s+has\s+no\b', re.IGNORECASE),
    re.compile(r'^No[.,]', re.IGNORECASE),
]


def _is_abstention(text: str) -> bool:
    # Strip markdown bold/italic markers for pattern matching
    clean = re.sub(r'\*+', '', text)
    lead = clean[:200]
    for pat in _CLINICAL_CLAIM_PATTERNS:
        if pat.search(lead):
            return False
    for pat in _ABSTENTION_PATTERNS:
        if pat.search(clean):
            return True
    return False


# ============================================================================
# Shared category scoring helpers
# ============================================================================

_NEGATION_KW = ["no", "negative", "denies", "absent", "not",
                "none", "nkda", "nothing", "cannot", "denied",
                "ruled out", "no evidence"]

_UNCERTAINTY_KW = [
    "uncertain", "possible", "suspected", "pending",
    "cannot rule out", "unclear", "equivocal",
    "likely", "probable", "concerning for", "suggestive",
    "may be", "may indicate", "not confirmed",
    "not definitively", "cannot exclude", "cannot be confirmed",
    "provisional", "tentative",
]

_FH_KW = ["family", "mother", "father", "sister", "brother", "relative"]
_CONDITIONAL_KW = ["if", "conditional", "pending", "depending", "only if"]
_TEMPORAL_STATUS_KW = ["was", "former", "previously", "discontinued",
                       "completed", "resolved", "history of", "quit"]
_CURRENT_KW = ["current", "active", "present", "ongoing", "is on"]
_HISTORICAL_KW = ["was", "former", "previously", "resolved",
                   "discontinued", "prior"]
_SECTION_NAMES = ["past medical history", "history of present illness", "history of"]

_ORDER_KW = ["first", "then", "followed", "before", "after",
             "prior", "subsequently", "later"]
_CHANGE_KW = ["added", "removed", "discontinued", "new", "changed",
              "started", "stopped", "replaced", "switched",
              "initiated", "modified"]

_DURATION_KW = ["day", "days", "week", "weeks", "month", "months",
                "year", "years", "duration", "since", "period",
                "length", "span", "chronic", "ongoing", "acute", "new",
                "admission", "admissions", "multiple", "recurrent",
                "long-standing", "longstanding"]

_CALC_KW = ["score", "risk", "low", "moderate", "high", "points", "calculate"]
_FUSION_KW = ["however", "while", "compared", "discrepancy",
              "consistent", "inconsistent", "both", "across"]

_SEQ_CHANGE_STOPWORDS = {
    "the", "a", "an", "is", "of", "in", "to", "for", "was", "and",
    "then", "by", "first", "followed", "identified", "before", "after",
    "key", "changes", "new", "medications", "discontinued", "between",
    "admissions", "noted", "patients", "medication", "differences",
}

_STRIP_PUNCT = re.compile(r'[^\w\s]')

_STRONG_CURRENT = re.compile(
    r'\bcurrently active\b|\bis currently\b|\bcurrently present\b|\bis active\b'
)


# ============================================================================
# Score helpers for current_state / historical (shared by both scorers)
# ============================================================================

def _score_current_historical(category: str, predicted_lower: str) -> tuple[bool, float]:
    ans_for_temporal = predicted_lower
    for sn in _SECTION_NAMES:
        ans_for_temporal = ans_for_temporal.replace(sn, "")

    cur_pats = _make_patterns(_CURRENT_KW)
    hist_pats = _make_patterns(_HISTORICAL_KW)
    answer_is_current = _has_match(ans_for_temporal, cur_pats)
    answer_is_historical = _has_match(ans_for_temporal, hist_pats)

    if _STRONG_CURRENT.search(predicted_lower):
        answer_is_current = True
        answer_is_historical = False

    if category == "current_state":
        correct = answer_is_current and not answer_is_historical
    else:  # historical
        correct = answer_is_historical
    return correct, 1.0 if correct else 0.0


# ============================================================================
# OLD scorer (current production logic — no abstention, no seq/change/dur fix)
# ============================================================================

def score_answer_old(category: str, expected_answer: str, predicted_answer: str) -> tuple[bool, float]:
    predicted_clean = _strip_evidence_echo(predicted_answer)
    expected_lower = expected_answer.lower()
    predicted_lower = predicted_clean.lower()

    if category == "negation":
        pats = _make_patterns(_NEGATION_KW)
        answer_neg = _has_match(predicted_lower, pats)
        expected_neg = _has_match(expected_lower, pats)
        correct = answer_neg == expected_neg
        return correct, 1.0 if correct else 0.0

    elif category == "uncertainty":
        pats = _make_patterns(_UNCERTAINTY_KW)
        correct = _has_match(predicted_lower, pats)
        return correct, 1.0 if correct else 0.0

    elif category == "family_history":
        fh_pats = _make_patterns(_FH_KW)
        distinguishes_fh = _has_match(predicted_lower, fh_pats)
        patient_clear = (
            bool(re.search(r'\bpatient does not\b', predicted_lower))
            or bool(re.search(r"\bpatient's\b.*\bnormal\b", predicted_lower))
            or bool(re.search(r'\bno\b.*\bin patient\b', predicted_lower))
            or "family history only" in predicted_lower
        )
        correct = distinguishes_fh or patient_clear
        return correct, 1.0 if correct else 0.0

    elif category == "conditional":
        pats = _make_patterns(_CONDITIONAL_KW)
        correct = _has_match(predicted_lower, pats)
        return correct, 1.0 if correct else 0.0

    elif category == "temporal_status":
        pats = _make_patterns(_TEMPORAL_STATUS_KW)
        correct = _has_match(predicted_lower, pats)
        return correct, 1.0 if correct else 0.0

    elif category in ("current_state", "historical"):
        return _score_current_historical(category, predicted_lower)

    elif category in ("sequence", "change"):
        # OLD: sequence and change combined, no ordering/change keyword requirement
        expected_clean = _STRIP_PUNCT.sub('', expected_lower)
        predicted_clean_p = _STRIP_PUNCT.sub('', predicted_lower)
        expected_terms = set(expected_clean.split()) - _SEQ_CHANGE_STOPWORDS
        predicted_terms = set(predicted_clean_p.split())
        overlap = expected_terms & predicted_terms
        score = len(overlap) / max(len(expected_terms), 1)
        order_pats = _make_patterns(_ORDER_KW)
        if _has_match(predicted_lower, order_pats):
            score = min(score + 0.2, 1.0)
        correct = score >= 0.3
        return correct, score

    elif category == "duration":
        # OLD: has min-0.5 floor for has_duration
        dur_pats = _make_patterns(_DURATION_KW)
        has_duration = _has_match(predicted_lower, dur_pats)
        expected_chronic = any(kw in expected_lower for kw in ["chronic", "ongoing", "multiple"])
        expected_new = any(kw in expected_lower for kw in ["new", "acute", "single", "only 1"])
        answer_chronic = any(kw in predicted_lower for kw in ["chronic", "ongoing", "multiple admissions", "recurrent"])
        answer_new = any(kw in predicted_lower for kw in ["new", "acute", "single admission", "first time"])
        chronicity_match = (expected_chronic and answer_chronic) or (expected_new and answer_new)
        expected_terms = set(expected_lower.split()) - {"the", "a", "an", "is", "of", "in", "to", "for", "was"}
        predicted_terms = set(predicted_lower.split())
        overlap = expected_terms & predicted_terms
        term_score = len(overlap) / max(len(expected_terms), 1)
        score = max(term_score, 0.5 if has_duration else 0.0)  # OLD: min-0.5 floor
        if chronicity_match:
            score = max(score, 0.8)
        correct = score >= 0.3
        return correct, score

    elif category in ("heart", "wells_pe", "sofa", "ckd_epi", "ascvd", "meld", "other"):
        expected_terms = set(expected_lower.split()) - {
            "the", "a", "an", "is", "of", "in", "to", "for", "was", "and",
            "score", "based", "on", "patient", "this", "with", "that",
        }
        predicted_terms = set(predicted_lower.split())
        overlap = expected_terms & predicted_terms
        score = len(overlap) / max(len(expected_terms), 1)
        calc_pats = _make_patterns(_CALC_KW)
        if _has_match(predicted_lower, calc_pats):
            score = min(score + 0.15, 1.0)
        correct = score >= 0.3
        return correct, score

    elif category in ("vital_note", "lab_note", "temporal_fusion", "cross_note_discordance"):
        expected_terms = set(expected_lower.split()) - {
            "the", "a", "an", "is", "of", "in", "to", "for", "was", "and",
            "patient", "this", "with", "that", "from", "note", "notes",
        }
        predicted_terms = set(predicted_lower.split())
        overlap = expected_terms & predicted_terms
        score = len(overlap) / max(len(expected_terms), 1)
        fusion_pats = _make_patterns(_FUSION_KW)
        if _has_match(predicted_lower, fusion_pats):
            score = min(score + 0.1, 1.0)
        correct = score >= 0.25
        return correct, score

    else:
        # Fallback: term overlap
        expected_terms = set(expected_lower.split()) - {"the", "a", "an", "is", "of", "in", "to", "for"}
        predicted_terms = set(predicted_lower.split())
        overlap = expected_terms & predicted_terms
        score = len(overlap) / max(len(expected_terms), 1)
        correct = score >= 0.3
        return correct, score


# ============================================================================
# FIXED scorer (abstention gate + sequence/change/duration fixes)
# ============================================================================

def score_answer_fixed(category: str, expected_answer: str, predicted_answer: str) -> tuple[bool, float]:
    predicted_clean = _strip_evidence_echo(predicted_answer)
    expected_lower = expected_answer.lower()
    predicted_lower = predicted_clean.lower()

    # --- Abstention gate (NEW) ---
    if _is_abstention(predicted_clean):
        return False, 0.0

    if category == "negation":
        pats = _make_patterns(_NEGATION_KW)
        answer_neg = _has_match(predicted_lower, pats)
        expected_neg = _has_match(expected_lower, pats)
        correct = answer_neg == expected_neg
        return correct, 1.0 if correct else 0.0

    elif category == "uncertainty":
        pats = _make_patterns(_UNCERTAINTY_KW)
        correct = _has_match(predicted_lower, pats)
        return correct, 1.0 if correct else 0.0

    elif category == "family_history":
        fh_pats = _make_patterns(_FH_KW)
        distinguishes_fh = _has_match(predicted_lower, fh_pats)
        patient_clear = (
            bool(re.search(r'\bpatient does not\b', predicted_lower))
            or bool(re.search(r"\bpatient's\b.*\bnormal\b", predicted_lower))
            or bool(re.search(r'\bno\b.*\bin patient\b', predicted_lower))
            or "family history only" in predicted_lower
        )
        correct = distinguishes_fh or patient_clear
        return correct, 1.0 if correct else 0.0

    elif category == "conditional":
        pats = _make_patterns(_CONDITIONAL_KW)
        correct = _has_match(predicted_lower, pats)
        return correct, 1.0 if correct else 0.0

    elif category == "temporal_status":
        pats = _make_patterns(_TEMPORAL_STATUS_KW)
        correct = _has_match(predicted_lower, pats)
        return correct, 1.0 if correct else 0.0

    elif category in ("current_state", "historical"):
        return _score_current_historical(category, predicted_lower)

    elif category == "sequence":
        # FIXED: require ordering keywords
        expected_clean = _STRIP_PUNCT.sub('', expected_lower)
        predicted_clean_p = _STRIP_PUNCT.sub('', predicted_lower)
        expected_terms = set(expected_clean.split()) - _SEQ_CHANGE_STOPWORDS
        predicted_terms = set(predicted_clean_p.split())
        overlap = expected_terms & predicted_terms
        score = len(overlap) / max(len(expected_terms), 1)
        order_pats = _make_patterns(_ORDER_KW)
        has_order = _has_match(predicted_lower, order_pats)
        correct = score >= 0.3 and has_order
        return correct, score

    elif category == "change":
        # FIXED: separate block, require change keywords
        expected_clean = _STRIP_PUNCT.sub('', expected_lower)
        predicted_clean_p = _STRIP_PUNCT.sub('', predicted_lower)
        expected_terms = set(expected_clean.split()) - _SEQ_CHANGE_STOPWORDS
        predicted_terms = set(predicted_clean_p.split())
        overlap = expected_terms & predicted_terms
        score = len(overlap) / max(len(expected_terms), 1)
        change_pats = _make_patterns(_CHANGE_KW)
        has_change = _has_match(predicted_lower, change_pats)
        correct = score >= 0.3 and has_change
        return correct, score

    elif category == "duration":
        # FIXED: remove min-0.5 floor
        dur_pats = _make_patterns(_DURATION_KW)
        _has_duration = _has_match(predicted_lower, dur_pats)
        expected_chronic = any(kw in expected_lower for kw in ["chronic", "ongoing", "multiple"])
        expected_new = any(kw in expected_lower for kw in ["new", "acute", "single", "only 1"])
        answer_chronic = any(kw in predicted_lower for kw in ["chronic", "ongoing", "multiple admissions", "recurrent"])
        answer_new = any(kw in predicted_lower for kw in ["new", "acute", "single admission", "first time"])
        chronicity_match = (expected_chronic and answer_chronic) or (expected_new and answer_new)
        expected_terms = set(expected_lower.split()) - {"the", "a", "an", "is", "of", "in", "to", "for", "was"}
        predicted_terms = set(predicted_lower.split())
        overlap = expected_terms & predicted_terms
        term_score = len(overlap) / max(len(expected_terms), 1)
        score = term_score  # FIXED: no min-0.5 floor
        if chronicity_match:
            score = max(score, 0.8)
        correct = score >= 0.3
        return correct, score

    elif category in ("heart", "wells_pe", "sofa", "ckd_epi", "ascvd", "meld", "other"):
        expected_terms = set(expected_lower.split()) - {
            "the", "a", "an", "is", "of", "in", "to", "for", "was", "and",
            "score", "based", "on", "patient", "this", "with", "that",
        }
        predicted_terms = set(predicted_lower.split())
        overlap = expected_terms & predicted_terms
        score = len(overlap) / max(len(expected_terms), 1)
        calc_pats = _make_patterns(_CALC_KW)
        if _has_match(predicted_lower, calc_pats):
            score = min(score + 0.15, 1.0)
        correct = score >= 0.3
        return correct, score

    elif category in ("vital_note", "lab_note", "temporal_fusion", "cross_note_discordance"):
        expected_terms = set(expected_lower.split()) - {
            "the", "a", "an", "is", "of", "in", "to", "for", "was", "and",
            "patient", "this", "with", "that", "from", "note", "notes",
        }
        predicted_terms = set(predicted_lower.split())
        overlap = expected_terms & predicted_terms
        score = len(overlap) / max(len(expected_terms), 1)
        fusion_pats = _make_patterns(_FUSION_KW)
        if _has_match(predicted_lower, fusion_pats):
            score = min(score + 0.1, 1.0)
        correct = score >= 0.25
        return correct, score

    else:
        expected_terms = set(expected_lower.split()) - {"the", "a", "an", "is", "of", "in", "to", "for"}
        predicted_terms = set(predicted_lower.split())
        overlap = expected_terms & predicted_terms
        score = len(overlap) / max(len(expected_terms), 1)
        correct = score >= 0.3
        return correct, score


# ============================================================================
# Checkpoint manifest
# ============================================================================

CHECKPOINT_MANIFEST: list[tuple[str, str, object]] = [
    ("Opus C1",      "opus_compare/compare_opus_C1_llm_alone_checkpoint.jsonl",       None),
    ("Opus C4g",     "opus_compare/compare_opus_checkpoint.jsonl",                     lambda r: "C4g" in r.get("condition", "")),
    ("Opus C6",      "opus_compare/compare_opus_C6_long_context_checkpoint.jsonl",     None),
    ("MedGemma C1",  "clinicalbench_checkpoint.jsonl",                                 lambda r: "C1_llm_alone" in r.get("condition", "")),
    ("MedGemma C4g", "clinicalbench_checkpoint.jsonl",                                 lambda r: "C4g_intent_aware" in r.get("condition", "")),
    ("MedGemma C4",  "clinicalbench_checkpoint.jsonl",                                 lambda r: "C4_epistemic" in r.get("condition", "") and "C4g" not in r.get("condition", "")),
    ("GPT-OSS C1",   "opus_compare/compare_gptoss_C1_llm_alone_checkpoint.jsonl",     None),
    ("GPT-OSS C4g",  "opus_compare/compare_gptoss_checkpoint.jsonl",                   None),
]

BASE_DIR = Path(__file__).resolve().parent.parent / "data" / "benchmarks" / "results"


# ============================================================================
# Main
# ============================================================================

def load_checkpoint(filepath: Path, filt) -> list[dict]:
    """Load JSONL, apply filter, deduplicate by question_id (keep last)."""
    if not filepath.exists():
        return []
    records = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if filt is not None and not filt(rec):
                continue
            records.append(rec)

    # Deduplicate: keep last entry per question_id
    seen: dict[str, int] = {}
    for i, rec in enumerate(records):
        seen[rec["question_id"]] = i
    deduped = [records[i] for i in sorted(seen.values())]
    return deduped


def main() -> None:
    summary_rows: list[tuple[str, int, float, float, float, int, int]] = []

    for label, relpath, filt in CHECKPOINT_MANIFEST:
        filepath = BASE_DIR / relpath
        records = load_checkpoint(filepath, filt)
        if not records:
            print(f"SKIP {label}: {relpath} (not found or empty after filter)")
            print()
            continue

        # Category-level tracking
        cat_stats: dict[str, dict] = defaultdict(lambda: {
            "n": 0, "old_correct": 0, "new_correct": 0,
            "fp_to_fn": 0, "fn_to_fp": 0,
        })
        abstention_examples: list[tuple[str, str, str, bool, bool]] = []

        for rec in records:
            cat = rec["category"]
            expected = rec["expected_answer"]
            predicted = rec["predicted_answer"]

            old_correct, _ = score_answer_old(cat, expected, predicted)
            new_correct, _ = score_answer_fixed(cat, expected, predicted)

            bucket = cat_stats[cat]
            bucket["n"] += 1
            if old_correct:
                bucket["old_correct"] += 1
            if new_correct:
                bucket["new_correct"] += 1
            if old_correct and not new_correct:
                bucket["fp_to_fn"] += 1
            if not old_correct and new_correct:
                bucket["fn_to_fp"] += 1

            # Track abstention examples
            predicted_clean = _strip_evidence_echo(predicted)
            if _is_abstention(predicted_clean) and old_correct != new_correct:
                if len(abstention_examples) < 3:
                    snippet = predicted_clean[:100].replace('\n', ' ')
                    abstention_examples.append((
                        rec["question_id"], cat, snippet,
                        old_correct, new_correct,
                    ))

        # Compute totals
        total_n = sum(s["n"] for s in cat_stats.values())
        total_old = sum(s["old_correct"] for s in cat_stats.values())
        total_new = sum(s["new_correct"] for s in cat_stats.values())
        total_fp_fn = sum(s["fp_to_fn"] for s in cat_stats.values())
        total_fn_fp = sum(s["fn_to_fp"] for s in cat_stats.values())
        old_pct = 100.0 * total_old / total_n if total_n else 0
        new_pct = 100.0 * total_new / total_n if total_n else 0
        delta = new_pct - old_pct

        # Print per-condition table
        print(f"=== {label} (n={total_n}) ===")
        hdr = f"{'Category':<20s} {'n':>4s}  {'Old%':>6s}  {'New%':>6s}  {'dpp':>6s}  {'FP>FN':>5s}  {'FN>FP':>5s}"
        sep = "\u2500" * len(hdr)
        print(hdr)
        print(sep)

        # Sort categories for consistent display
        cat_order = [
            "negation", "conditional", "uncertainty", "family_history",
            "temporal_status", "current_state", "historical", "sequence",
            "change", "duration",
        ]
        all_cats = sorted(cat_stats.keys(), key=lambda c: (
            cat_order.index(c) if c in cat_order else 100, c
        ))

        for cat in all_cats:
            s = cat_stats[cat]
            n = s["n"]
            op = 100.0 * s["old_correct"] / n if n else 0
            np_ = 100.0 * s["new_correct"] / n if n else 0
            dp = np_ - op
            print(f"{cat:<20s} {n:>4d}  {op:>5.1f}%  {np_:>5.1f}%  {dp:>+5.1f}  {s['fp_to_fn']:>5d}  {s['fn_to_fp']:>5d}")

        print(sep)
        print(f"{'TOTAL':<20s} {total_n:>4d}  {old_pct:>5.1f}%  {new_pct:>5.1f}%  {delta:>+5.1f}  {total_fp_fn:>5d}  {total_fn_fp:>5d}")
        print()

        # Abstention examples
        if abstention_examples:
            print(f"  Abstention examples ({label}):")
            for qid, cat, snippet, old_c, new_c in abstention_examples:
                print(f"    {qid} [{cat}]: \"{snippet}...\"")
                print(f"      old_correct={old_c} -> new_correct={new_c}")
            print()

        summary_rows.append((label, total_n, old_pct, new_pct, delta, total_fp_fn, total_fn_fp))

    # Print summary table
    if summary_rows:
        print()
        print("=== SUMMARY ===")
        hdr = f"{'Condition':<20s} {'n':>4s}  {'Old%':>6s}  {'New%':>6s}  {'dpp':>6s}  {'FP>FN':>5s}  {'FN>FP':>5s}"
        sep = "\u2500" * len(hdr)
        print(hdr)
        print(sep)
        for label, n, op, np_, dp, fp_fn, fn_fp in summary_rows:
            print(f"{label:<20s} {n:>4d}  {op:>5.1f}%  {np_:>5.1f}%  {dp:>+5.1f}  {fp_fn:>5d}  {fn_fp:>5d}")
        print(sep)


if __name__ == "__main__":
    main()
