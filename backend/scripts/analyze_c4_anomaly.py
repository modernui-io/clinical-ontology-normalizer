#!/usr/bin/env python3
"""Deep analysis of the C4 anomaly: why assertions without routing hurt performance.

Analyzes per-question regressions (C3 correct → C4 wrong) and recoveries
(C3 wrong → C4 correct), broken down by category, with example answers
for each regression pattern.

Usage:
    cd backend
    python3 scripts/analyze_c4_anomaly.py
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, "/Users/alexstinard/projects/brainstorm/jan-14-2026/epikg-benchmark/clinicalbench")
from evaluator import score_answer

BASE = Path("/Users/alexstinard/projects/brainstorm/jan-14-2026/epikg-benchmark")
QUESTIONS_PATH = BASE / "clinicalbench" / "questions.json"
C1_PATH = BASE / "results" / "opus" / "C1_llm_alone.json"
C2_PATH = BASE / "results" / "opus" / "C2_vanilla_rag.json"
C3_PATH = BASE / "results" / "opus" / "C3_kg_rag.json"
C4_PATH = BASE / "results" / "opus" / "C4_epistemic_kg_rag.json"
C4G_PATH = BASE / "results" / "opus" / "C4g_intent_aware.json"

HARD_LONGITUDINAL = {"historical", "change", "current_state"}


def load_preds(path):
    with open(path) as f:
        data = json.load(f)
    return {p["question_id"]: p for p in data["predictions"]}


def score_pred(category, expected, pred):
    ans = pred.get("predicted_answer", "")
    if not ans:
        return False
    correct, _ = score_answer(category, expected, ans)
    return correct


def main():
    with open(QUESTIONS_PATH) as f:
        qdata = json.load(f)
    questions = {q["question_id"]: q for q in qdata["questions"]}

    c1 = load_preds(C1_PATH)
    c2 = load_preds(C2_PATH)
    c3 = load_preds(C3_PATH)
    c4 = load_preds(C4_PATH)
    c4g = load_preds(C4G_PATH)

    # Categorize every question into transition buckets
    regressions = []       # C3 correct, C4 wrong
    improvements = []      # C3 wrong, C4 correct
    both_correct = []      # C3 correct, C4 correct
    both_wrong = []        # C3 wrong, C4 wrong
    c4g_recoveries = []    # C3 correct, C4 wrong, C4g correct (recovered)
    c4g_still_wrong = []   # C3 correct, C4 wrong, C4g wrong (not recovered)

    cat_regressions = Counter()
    cat_improvements = Counter()
    cat_both_correct = Counter()
    cat_both_wrong = Counter()
    cat_c4g_recovery = Counter()
    cat_totals = Counter()

    for qid in sorted(questions.keys()):
        q = questions[qid]
        cat = q["category"]
        expected = q["expected_answer"]

        if qid not in c3 or qid not in c4 or qid not in c4g:
            continue

        s3 = score_pred(cat, expected, c3[qid])
        s4 = score_pred(cat, expected, c4[qid])
        s4g = score_pred(cat, expected, c4g[qid])
        s1 = score_pred(cat, expected, c1[qid]) if qid in c1 else None

        cat_totals[cat] += 1

        entry = {
            "qid": qid,
            "category": cat,
            "expected": expected,
            "c1_answer": c1.get(qid, {}).get("predicted_answer", ""),
            "c3_answer": c3[qid].get("predicted_answer", ""),
            "c4_answer": c4[qid].get("predicted_answer", ""),
            "c4g_answer": c4g[qid].get("predicted_answer", ""),
            "c1_correct": s1,
            "c3_correct": s3,
            "c4_correct": s4,
            "c4g_correct": s4g,
            "question": q.get("question", ""),
        }

        if s3 and not s4:
            regressions.append(entry)
            cat_regressions[cat] += 1
            if s4g:
                c4g_recoveries.append(entry)
                cat_c4g_recovery[cat] += 1
            else:
                c4g_still_wrong.append(entry)
        elif not s3 and s4:
            improvements.append(entry)
            cat_improvements[cat] += 1
        elif s3 and s4:
            both_correct.append(entry)
            cat_both_correct[cat] += 1
        else:
            both_wrong.append(entry)
            cat_both_wrong[cat] += 1

    n = sum(cat_totals.values())
    print(f"{'='*70}")
    print(f"C4 ANOMALY ANALYSIS — {n} questions")
    print(f"{'='*70}\n")

    # Transition matrix
    print(f"TRANSITION MATRIX (C3 → C4):")
    print(f"  Both correct:   {len(both_correct):>3} ({len(both_correct)/n:.1%})")
    print(f"  Both wrong:     {len(both_wrong):>3} ({len(both_wrong)/n:.1%})")
    print(f"  Regressions:    {len(regressions):>3} ({len(regressions)/n:.1%})  [C3 ✓ → C4 ✗]")
    print(f"  Improvements:   {len(improvements):>3} ({len(improvements)/n:.1%})  [C3 ✗ → C4 ✓]")
    print(f"  Net effect:     {len(improvements) - len(regressions):>+3} ({(len(improvements) - len(regressions))/n:+.1%})")

    print(f"\n  Of {len(regressions)} regressions:")
    print(f"    Recovered by C4g: {len(c4g_recoveries):>3} ({len(c4g_recoveries)/max(len(regressions),1):.1%})")
    print(f"    Still wrong:      {len(c4g_still_wrong):>3} ({len(c4g_still_wrong)/max(len(regressions),1):.1%})")

    # Per-category breakdown
    all_cats = sorted(cat_totals.keys(), key=lambda x: -cat_regressions.get(x, 0))
    print(f"\n{'='*70}")
    print(f"PER-CATEGORY BREAKDOWN")
    print(f"{'='*70}")
    print(f"{'Category':<18} {'N':>4} {'C3':>5} {'C4':>5} {'C4g':>5} "
          f"{'Regr':>5} {'Impr':>5} {'Net':>5} {'Recov':>5}")
    print("-" * 78)

    for cat in all_cats:
        n_cat = cat_totals[cat]
        c3_acc = (cat_both_correct[cat] + cat_regressions[cat]) / n_cat
        c4_acc = (cat_both_correct[cat] + cat_improvements[cat]) / n_cat
        # C4g accuracy for this category
        c4g_correct_cat = sum(1 for e in regressions + improvements + both_correct + both_wrong
                              if e["category"] == cat and e["c4g_correct"])
        c4g_acc = c4g_correct_cat / n_cat

        regr = cat_regressions.get(cat, 0)
        impr = cat_improvements.get(cat, 0)
        recov = cat_c4g_recovery.get(cat, 0)
        net = impr - regr

        print(f"{cat:<18} {n_cat:>4} {c3_acc:>4.0%} {c4_acc:>4.0%} {c4g_acc:>4.0%} "
              f"{regr:>5} {impr:>5} {net:>+5} {recov:>5}")

    # Hard longitudinal vs easy
    print(f"\n{'='*70}")
    print(f"HARD LONGITUDINAL vs OTHER")
    print(f"{'='*70}")
    hard_regr = sum(1 for e in regressions if e["category"] in HARD_LONGITUDINAL)
    hard_impr = sum(1 for e in improvements if e["category"] in HARD_LONGITUDINAL)
    hard_total = sum(cat_totals[c] for c in HARD_LONGITUDINAL if c in cat_totals)
    other_regr = len(regressions) - hard_regr
    other_impr = len(improvements) - hard_impr
    other_total = n - hard_total

    print(f"  Hard longitudinal ({hard_total} qs): {hard_regr} regressions, {hard_impr} improvements, net {hard_impr - hard_regr:+d}")
    print(f"  Other ({other_total} qs):             {other_regr} regressions, {other_impr} improvements, net {other_impr - other_regr:+d}")

    # Example regressions by category
    print(f"\n{'='*70}")
    print(f"EXAMPLE REGRESSIONS (C3 ✓ → C4 ✗)")
    print(f"{'='*70}")

    shown_cats = set()
    for entry in sorted(regressions, key=lambda e: e["category"]):
        cat = entry["category"]
        if cat in shown_cats:
            continue
        shown_cats.add(cat)
        q_text = entry["question"][:100]
        print(f"\n  [{cat}] {q_text}...")
        print(f"    Expected: {entry['expected'][:80]}")
        print(f"    C3 (✓): {entry['c3_answer'][:80]}")
        print(f"    C4 (✗): {entry['c4_answer'][:80]}")
        print(f"    C4g:    {entry['c4g_answer'][:80]} ({'✓' if entry['c4g_correct'] else '✗'})")

    # Regression answer patterns — what does C4 typically say wrong?
    print(f"\n{'='*70}")
    print(f"C4 REGRESSION ANSWER ANALYSIS")
    print(f"{'='*70}")

    # Check if C4 regressions tend to abstain, flip yes/no, or give wrong details
    c4_abstains = sum(1 for e in regressions
                      if not e["c4_answer"].strip() or
                      "cannot" in e["c4_answer"].lower() or
                      "not available" in e["c4_answer"].lower() or
                      "no information" in e["c4_answer"].lower() or
                      "unable to determine" in e["c4_answer"].lower())

    c4_flips_yn = 0
    for e in regressions:
        c3a = e["c3_answer"].strip().lower()[:3]
        c4a = e["c4_answer"].strip().lower()[:3]
        if (c3a == "yes" and c4a == "no") or (c3a == "no" and c4a == "yes"):
            c4_flips_yn += 1

    print(f"  Total regressions: {len(regressions)}")
    print(f"  C4 abstains/hedges: {c4_abstains} ({c4_abstains/max(len(regressions),1):.0%})")
    print(f"  C4 flips yes/no: {c4_flips_yn} ({c4_flips_yn/max(len(regressions),1):.0%})")
    print(f"  Other wrong detail: {len(regressions) - c4_abstains - c4_flips_yn}")

    # Category × error type
    print(f"\n  By category — abstain/hedge vs flip vs wrong detail:")
    for cat in all_cats:
        cat_regrs = [e for e in regressions if e["category"] == cat]
        if not cat_regrs:
            continue
        abstains = sum(1 for e in cat_regrs
                       if not e["c4_answer"].strip() or
                       "cannot" in e["c4_answer"].lower() or
                       "not available" in e["c4_answer"].lower() or
                       "no information" in e["c4_answer"].lower() or
                       "unable to determine" in e["c4_answer"].lower())
        flips = 0
        for e in cat_regrs:
            c3a = e["c3_answer"].strip().lower()[:3]
            c4a = e["c4_answer"].strip().lower()[:3]
            if (c3a == "yes" and c4a == "no") or (c3a == "no" and c4a == "yes"):
                flips += 1
        other = len(cat_regrs) - abstains - flips
        print(f"    {cat:<18} {len(cat_regrs):>3} regr: {abstains} abstain, {flips} flip, {other} wrong detail")

    # Save detailed regression data for potential further analysis
    output = {
        "summary": {
            "n": n,
            "regressions": len(regressions),
            "improvements": len(improvements),
            "both_correct": len(both_correct),
            "both_wrong": len(both_wrong),
            "c4g_recoveries": len(c4g_recoveries),
            "net_effect": len(improvements) - len(regressions),
            "recovery_rate": len(c4g_recoveries) / max(len(regressions), 1),
        },
        "per_category": {
            cat: {
                "n": cat_totals[cat],
                "regressions": cat_regressions.get(cat, 0),
                "improvements": cat_improvements.get(cat, 0),
                "c4g_recoveries": cat_c4g_recovery.get(cat, 0),
                "net": cat_improvements.get(cat, 0) - cat_regressions.get(cat, 0),
            }
            for cat in all_cats
        },
        "regressions": regressions,
        "improvements": improvements,
    }

    out_path = Path(__file__).parent.parent / "data" / "benchmarks" / "c4_anomaly_analysis.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved detailed analysis to {out_path}")


if __name__ == "__main__":
    main()
