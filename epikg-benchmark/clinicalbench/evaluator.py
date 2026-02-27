#!/usr/bin/env python3
"""ClinicalBench Deterministic Keyword Evaluator.

Standalone reimplementation of the keyword evaluator used in:
  "EpiKG: End-to-End Epistemic Preservation in Clinical Knowledge Graphs
   for Assertion-Aware Retrieval-Augmented Generation"

This evaluator performs exact word-boundary regex matching against
gold-standard assertion and temporal keywords. It is fully deterministic
(no LLM judge) and is used for all ClinicalBench results in the paper.

Usage:
    python evaluator.py --questions questions.json --predictions ../results/opus/C4g_intent_aware.json

The evaluator reads questions (with expected answers and categories) and
predictions (with predicted answers), then scores each prediction.
"""

import argparse
import json
import re
import sys
from collections import defaultdict


# ── Evidence echo stripping ──

def _strip_evidence_echo(text: str) -> str:
    """Strip echoed evidence preamble from model answers.

    Models sometimes start answers by repeating 'Assertion Notes'
    or evidence sections. This pollutes keyword-based scoring
    because historical/negation keywords in the echo trigger false
    matches. We strip the preamble so only the model's actual answer
    is scored.
    """
    stripped = text.strip()
    preamble_starts = ("Assertion Notes", "=== TEMPORAL STATUS", "=== CURRENT STATUS", "=== CROSS-ADMISSION")
    if not any(stripped.startswith(p) for p in preamble_starts):
        return text
    # Split on double-newline — find the first paragraph that looks
    # like an actual answer (starts with a word, not a bullet/header)
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
    # Fallback: skip leading bullet lines
    lines = text.split("\n")
    for i, line in enumerate(lines):
        s = line.strip()
        if i > 0 and s and not s.startswith(("-", "*", ">", "Assertion", "=", "#", "|")):
            return "\n".join(lines[i:]).strip()
    return text


# ── Abstention detection ──

# Patterns indicating the model is saying info is unavailable in the notes
_ABSTENTION_PATTERNS = [
    re.compile(r'\b(?:notes?|records?|documentation)\b.*\b(?:do(?:es)?\s+not|lack[s]?|fail[s]?\s+to)\s+(?:mention|contain|include|provide|document|address|specify)', re.IGNORECASE),
    re.compile(r'\bno\s+(?:mention|information|data)\s+(?:of|about|regarding|concerning)\b', re.IGNORECASE),
    re.compile(r'\b(?:cannot|can\'?t|unable\s+to)\s+(?:determine|assess|evaluate|answer|ascertain|establish)\b', re.IGNORECASE),
    re.compile(r'\b(?:insufficient|inadequate)\s+(?:evidence|information|data|documentation)\b', re.IGNORECASE),
    re.compile(r'\bnot\s+(?:mentioned|documented|provided|available|specified|addressed|included)\b', re.IGNORECASE),
    re.compile(r'\b(?:information|evidence|data)\s+is\s+(?:missing|unavailable|lacking|absent|not\s+available)\b', re.IGNORECASE),
    re.compile(r'\b(?:provided|available)\s+(?:notes?|records?)\s+do(?:es)?\s+not\b', re.IGNORECASE),
]

# Clinical claim patterns that override abstention (checked in first ~200 chars)
_CLINICAL_CLAIM_PATTERNS = [
    re.compile(r'\bpatient\s+(?:does\s+not|has\s+not|is\s+not|did\s+not)\b', re.IGNORECASE),
    re.compile(r'\b(?:denies|denied|ruled\s+out)\b', re.IGNORECASE),
    re.compile(r'\bno\s+evidence\s+of\b', re.IGNORECASE),
    re.compile(r'\bpatient\s+has\s+no\b', re.IGNORECASE),
    re.compile(r'^No[.,]', re.IGNORECASE),
]


def _is_abstention(text: str) -> bool:
    """Detect if model answer is an abstention (info unavailable) rather than a clinical claim."""
    # Strip markdown bold/italic markers for pattern matching
    clean = re.sub(r'\*+', '', text)
    # Check first ~200 chars for clinical claims that override abstention
    lead = clean[:200]
    for pat in _CLINICAL_CLAIM_PATTERNS:
        if pat.search(lead):
            return False
    # Check full text for abstention patterns
    for pat in _ABSTENTION_PATTERNS:
        if pat.search(clean):
            return True
    return False


# ── Scoring ──

def _make_patterns(keywords: list[str]) -> list[re.Pattern]:
    return [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in keywords]


def _has_match(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)


def score_answer(category: str, expected_answer: str, predicted_answer: str) -> tuple[bool, float]:
    """Score a single prediction. Returns (correct, score)."""
    expected_lower = expected_answer.lower()
    predicted_clean = _strip_evidence_echo(predicted_answer)
    predicted_lower = predicted_clean.lower()

    # Abstention gate: "I don't know" / "not mentioned" is always wrong
    if _is_abstention(predicted_clean):
        return False, 0.0

    if category == "negation":
        negation_keywords = [
            "no", "negative", "denies", "absent", "not", "none", "nkda",
            "nothing", "cannot", "denied", "ruled out", "no evidence",
        ]
        patterns = _make_patterns(negation_keywords)
        answer_has = _has_match(predicted_lower, patterns)
        expected_has = _has_match(expected_lower, patterns)
        correct = answer_has == expected_has
        return correct, 1.0 if correct else 0.0

    elif category == "uncertainty":
        uncertainty_keywords = [
            "uncertain", "possible", "suspected", "pending", "cannot rule out",
            "unclear", "equivocal", "likely", "probable", "concerning for",
            "suggestive", "may be", "may indicate", "not confirmed",
            "not definitively", "cannot exclude", "cannot be confirmed",
            "provisional", "tentative",
        ]
        patterns = _make_patterns(uncertainty_keywords)
        correct = _has_match(predicted_lower, patterns)
        return correct, 1.0 if correct else 0.0

    elif category == "family_history":
        fh_keywords = ["family", "mother", "father", "sister", "brother", "relative"]
        fh_patterns = _make_patterns(fh_keywords)
        distinguishes_fh = _has_match(predicted_lower, fh_patterns)
        patient_neg_patterns = [
            re.compile(r'\bpatient does not\b'),
            re.compile(r"\bpatient's\b.*\bnormal\b"),
            re.compile(r'\bno\b.*\bin patient\b'),
        ]
        patient_clear = (
            _has_match(predicted_lower, patient_neg_patterns)
            or "family history only" in predicted_lower
        )
        correct = distinguishes_fh or patient_clear
        return correct, 1.0 if correct else 0.0

    elif category == "conditional":
        conditional_keywords = ["if", "conditional", "pending", "depending", "only if"]
        patterns = _make_patterns(conditional_keywords)
        correct = _has_match(predicted_lower, patterns)
        return correct, 1.0 if correct else 0.0

    elif category in ("current_state", "historical"):
        current_kw = ["current", "active", "present", "ongoing", "is on"]
        historical_kw = ["was", "former", "previously", "resolved", "discontinued", "prior"]
        cur_patterns = _make_patterns(current_kw)
        hist_patterns = _make_patterns(historical_kw)

        # Strip section names that cause false matches
        ans_temporal = predicted_lower
        section_names = ["past medical history", "history of present illness", "history of"]
        for sn in section_names:
            ans_temporal = ans_temporal.replace(sn, "")

        is_current = _has_match(ans_temporal, cur_patterns)
        is_historical = _has_match(ans_temporal, hist_patterns)

        # Strong affirmative override
        strong_current = re.compile(
            r'\bcurrently active\b|\bis currently\b|\bcurrently present\b|\bis active\b'
        )
        if strong_current.search(predicted_lower):
            is_current = True
            is_historical = False

        if category == "current_state":
            correct = is_current and not is_historical
        else:
            correct = is_historical
        return correct, 1.0 if correct else 0.0

    elif category == "sequence":
        strip_punct = re.compile(r'[^\w\s]')
        exp_clean = strip_punct.sub('', expected_lower)
        pred_clean = strip_punct.sub('', predicted_lower)
        stop_words = {
            "the", "a", "an", "is", "of", "in", "to", "for", "was", "and",
            "then", "by", "first", "followed", "identified", "before", "after",
            "key", "changes", "new", "medications", "discontinued", "between",
            "admissions", "noted", "patients", "medication", "differences",
        }
        exp_terms = set(exp_clean.split()) - stop_words
        pred_terms = set(pred_clean.split())
        overlap = exp_terms & pred_terms
        score = len(overlap) / max(len(exp_terms), 1)
        order_keywords = ["first", "then", "followed", "before", "after", "prior",
                          "subsequently", "later"]
        order_patterns = _make_patterns(order_keywords)
        has_order = _has_match(predicted_lower, order_patterns)
        correct = score >= 0.3 and has_order
        return correct, score

    elif category == "change":
        strip_punct = re.compile(r'[^\w\s]')
        exp_clean = strip_punct.sub('', expected_lower)
        pred_clean = strip_punct.sub('', predicted_lower)
        stop_words = {
            "the", "a", "an", "is", "of", "in", "to", "for", "was", "and",
            "then", "by", "first", "followed", "identified", "before", "after",
            "key", "changes", "new", "medications", "discontinued", "between",
            "admissions", "noted", "patients", "medication", "differences",
        }
        exp_terms = set(exp_clean.split()) - stop_words
        pred_terms = set(pred_clean.split())
        overlap = exp_terms & pred_terms
        score = len(overlap) / max(len(exp_terms), 1)
        change_keywords = ["added", "removed", "discontinued", "new", "changed",
                           "started", "stopped", "replaced", "switched",
                           "initiated", "modified"]
        change_patterns = _make_patterns(change_keywords)
        has_change = _has_match(predicted_lower, change_patterns)
        correct = score >= 0.3 and has_change
        return correct, score

    elif category == "duration":
        duration_keywords = [
            "day", "days", "week", "weeks", "month", "months", "year", "years",
            "duration", "since", "period", "length", "span", "chronic", "ongoing",
            "acute", "new", "admission", "admissions", "multiple", "recurrent",
            "long-standing", "longstanding",
        ]
        dur_patterns = _make_patterns(duration_keywords)
        has_duration = _has_match(predicted_lower, dur_patterns)
        expected_chronic = any(kw in expected_lower for kw in ["chronic", "ongoing", "multiple"])
        expected_new = any(kw in expected_lower for kw in ["new", "acute", "single", "only 1"])
        answer_chronic = any(kw in predicted_lower for kw in ["chronic", "ongoing", "multiple admissions", "recurrent"])
        answer_new = any(kw in predicted_lower for kw in ["new", "acute", "single admission", "first time"])
        chronicity_match = (expected_chronic and answer_chronic) or (expected_new and answer_new)
        exp_terms = set(expected_lower.split()) - {"the", "a", "an", "is", "of", "in", "to", "for", "was"}
        pred_terms = set(predicted_lower.split())
        overlap = exp_terms & pred_terms
        term_score = len(overlap) / max(len(exp_terms), 1)
        score = term_score
        if chronicity_match:
            score = max(score, 0.8)
        correct = score >= 0.3
        return correct, score

    else:
        # Fallback: term overlap
        exp_terms = set(expected_lower.split()) - {"the", "a", "an", "is", "of", "in", "to", "for"}
        pred_terms = set(predicted_lower.split())
        overlap = exp_terms & pred_terms
        score = len(overlap) / max(len(exp_terms), 1)
        correct = score >= 0.3
        return correct, score


def evaluate(questions_path: str, predictions_path: str) -> dict:
    """Evaluate predictions against gold answers."""
    with open(questions_path) as f:
        qdata = json.load(f)
    questions = {q["question_id"]: q for q in qdata["questions"]}

    with open(predictions_path) as f:
        pdata = json.load(f)
    predictions = {p["question_id"]: p for p in pdata["predictions"]}

    results = []
    by_category = defaultdict(lambda: {"correct": 0, "total": 0})
    total_correct = 0

    for qid, q in sorted(questions.items()):
        pred = predictions.get(qid)
        if not pred:
            continue
        answer_text = pred.get("predicted_answer", "")
        if not answer_text:
            # Empty answer = wrong
            results.append({
                "question_id": qid,
                "category": q["category"],
                "correct": False,
                "score": 0.0,
            })
            by_category[q["category"]]["total"] += 1
            continue

        correct, score = score_answer(
            q["category"], q["expected_answer"], answer_text
        )
        results.append({
            "question_id": qid,
            "category": q["category"],
            "correct": correct,
            "score": score,
        })
        cat = q["category"]
        by_category[cat]["total"] += 1
        if correct:
            by_category[cat]["correct"] += 1
            total_correct += 1

    n = len(results)
    print(f"\n{'='*50}")
    print(f"Model: {pdata.get('model', 'unknown')}")
    print(f"Condition: {pdata.get('condition', 'unknown')}")
    print(f"Overall: {total_correct}/{n} = {total_correct/n:.1%}")
    print(f"{'='*50}")
    print(f"{'Category':<18} {'Correct':>8} {'Total':>6} {'Accuracy':>10}")
    print(f"{'-'*44}")
    for cat in sorted(by_category):
        c = by_category[cat]["correct"]
        t = by_category[cat]["total"]
        print(f"{cat:<18} {c:>8} {t:>6} {c/t:>10.1%}")

    return {
        "accuracy": total_correct / n if n else 0,
        "n": n,
        "correct": total_correct,
        "category_accuracies": {
            cat: vals["correct"] / vals["total"]
            for cat, vals in sorted(by_category.items())
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClinicalBench Keyword Evaluator")
    parser.add_argument("--questions", default="questions.json")
    parser.add_argument("--predictions", required=True)
    args = parser.parse_args()
    evaluate(args.questions, args.predictions)
