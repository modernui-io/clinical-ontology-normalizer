#!/usr/bin/env python3
"""LLM-as-Judge evaluator for ClinicalBench predictions.

Rescores all C1 and C4g predictions using Claude Opus as judge,
then computes concordance with the keyword evaluator v2 and
the physician pilot (n=30).

Usage:
    python llm_judge.py --conditions C1 C4g --checkpoint llm_judge_checkpoint.jsonl
    python llm_judge.py --analyze-only  # skip API calls, just analyze existing results
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

# ── Paths ──
BASE = Path(__file__).resolve().parent.parent
QUESTIONS_PATH = BASE / "clinicalbench" / "questions.json"
RESULTS_DIR = BASE / "results" / "opus"
JUDGE_DIR = BASE / "results" / "llm_judge"
PHYSICIAN_ITEMS = Path("/Users/alexstinard/projects/brainstorm/jan-14-2026/backend/data/benchmarks/results/physician_adjudication/adjudication_items.jsonl")
PHYSICIAN_VALIDATIONS = Path("/Users/alexstinard/projects/brainstorm/jan-14-2026/backend/data/benchmarks/results/physician_adjudication/adjudication_validations.jsonl")

# ── Judge prompt ──
JUDGE_SYSTEM_PROMPT = """\
You are evaluating a clinical QA system's answer against a reference answer.
You must judge whether the system's answer is clinically correct.
Be strict but fair: the system answer need not use the exact same words, \
but must convey the same clinical fact."""

JUDGE_USER_TEMPLATE = """\
Question: {question}
Category: {category}
Reference answer: {expected}
System answer: {predicted}

Rate the system answer:
1 = Correct (captures the key clinical fact accurately)
0.5 = Partially correct (right direction but missing key details or hedging excessively)
0 = Incorrect (wrong, misleading, abstains without justification, or misses the key point)

Respond with ONLY a JSON object: {{"score": <number>, "reason": "<one sentence>"}}"""


async def judge_one(question_id: str, question: str, category: str,
                    expected: str, predicted: str, condition: str,
                    client, model: str) -> dict:
    """Score a single prediction using LLM-as-judge."""
    prompt = JUDGE_USER_TEMPLATE.format(
        question=question, category=category,
        expected=expected, predicted=predicted
    )
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=150,
            temperature=0,
            system=JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Parse JSON from response
        # Handle cases where model wraps in markdown code blocks
        if text.startswith("```"):
            text = re.sub(r"```(?:json)?\s*", "", text).rstrip("`").strip()
        parsed = json.loads(text)
        score = float(parsed["score"])
        reason = parsed.get("reason", "")
        return {
            "question_id": question_id,
            "condition": condition,
            "judge_score": score,
            "judge_reason": reason,
            "raw_response": text,
        }
    except Exception as e:
        return {
            "question_id": question_id,
            "condition": condition,
            "judge_score": -1,
            "judge_reason": f"ERROR: {e}",
            "raw_response": "",
        }


async def run_judge(conditions: list[str], checkpoint_path: Path,
                    model: str = "claude-opus-4-20250514",
                    max_concurrent: int = 5) -> list[dict]:
    """Run LLM judge on all predictions for given conditions."""
    import anthropic

    # Load questions
    with open(QUESTIONS_PATH) as f:
        qdata = json.load(f)
    questions = {q["question_id"]: q for q in qdata["questions"]}

    # Load predictions for each condition
    condition_files = {
        "C1": RESULTS_DIR / "C1_llm_alone.json",
        "C4g": RESULTS_DIR / "C4g_intent_aware.json",
        "C4": RESULTS_DIR / "C4_epistemic_kg_rag.json",
        "C3": RESULTS_DIR / "C3_kg_rag.json",
    }
    all_preds = {}
    for cond in conditions:
        path = condition_files.get(cond)
        if not path or not path.exists():
            print(f"WARNING: No predictions for {cond}")
            continue
        with open(path) as f:
            data = json.load(f)
        all_preds[cond] = {p["question_id"]: p for p in data["predictions"]}

    # Load checkpoint
    done = set()
    results = []
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            for line in f:
                r = json.loads(line)
                done.add((r["question_id"], r["condition"]))
                results.append(r)
        print(f"Loaded {len(done)} existing judgments from checkpoint")

    # Build work items
    work = []
    for cond in conditions:
        preds = all_preds.get(cond, {})
        for qid in sorted(questions.keys()):
            if (qid, cond) in done:
                continue
            q = questions[qid]
            pred = preds.get(qid)
            if not pred:
                continue
            predicted = pred.get("predicted_answer", "")
            if not predicted:
                # Empty answer — score 0 without API call
                result = {
                    "question_id": qid,
                    "condition": cond,
                    "judge_score": 0.0,
                    "judge_reason": "Empty answer",
                    "raw_response": "",
                }
                results.append(result)
                with open(checkpoint_path, "a") as f:
                    f.write(json.dumps(result) + "\n")
                done.add((qid, cond))
                continue
            work.append((qid, q["question"], q["category"],
                        q["expected_answer"], predicted, cond))

    if not work:
        print("All judgments already complete.")
        return results

    print(f"{len(work)} judgments to run ({len(done)} already done)")

    # Run with concurrency limit
    client = anthropic.AsyncAnthropic()
    semaphore = asyncio.Semaphore(max_concurrent)
    completed = 0

    async def bounded_judge(item):
        nonlocal completed
        async with semaphore:
            result = await judge_one(*item, client=client, model=model)
            completed += 1
            if completed % 50 == 0:
                print(f"  Progress: {completed}/{len(work)}")
            return result

    # Process in batches to checkpoint frequently
    batch_size = 20
    for i in range(0, len(work), batch_size):
        batch = work[i:i+batch_size]
        batch_results = await asyncio.gather(*[bounded_judge(item) for item in batch])
        with open(checkpoint_path, "a") as f:
            for r in batch_results:
                results.append(r)
                f.write(json.dumps(r) + "\n")

    await client.close()
    return results


def analyze_results(results: list[dict]) -> dict:
    """Analyze LLM judge results vs keyword evaluator and physician."""
    from evaluator import score_answer

    # Load questions
    with open(QUESTIONS_PATH) as f:
        qdata = json.load(f)
    questions = {q["question_id"]: q for q in qdata["questions"]}

    # Load keyword evaluator predictions
    condition_files = {
        "C1": RESULTS_DIR / "C1_llm_alone.json",
        "C4g": RESULTS_DIR / "C4g_intent_aware.json",
    }
    keyword_preds = {}
    for cond, path in condition_files.items():
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            keyword_preds[cond] = {p["question_id"]: p for p in data["predictions"]}

    # ── 1. Condition-level accuracy under LLM judge ──
    print("\n" + "=" * 60)
    print("LLM-AS-JUDGE RESULTS")
    print("=" * 60)

    by_condition = defaultdict(list)
    for r in results:
        if r["judge_score"] >= 0:  # skip errors
            by_condition[r["condition"]].append(r)

    for cond in sorted(by_condition.keys()):
        rs = by_condition[cond]
        # Count correct (score >= 0.5 as correct for binary comparison)
        n = len(rs)
        n_correct_strict = sum(1 for r in rs if r["judge_score"] == 1.0)
        n_partial = sum(1 for r in rs if r["judge_score"] == 0.5)
        n_wrong = sum(1 for r in rs if r["judge_score"] == 0.0)
        mean_score = sum(r["judge_score"] for r in rs) / n

        print(f"\n{cond} (n={n}):")
        print(f"  Correct (1.0):  {n_correct_strict} ({n_correct_strict/n:.1%})")
        print(f"  Partial (0.5):  {n_partial} ({n_partial/n:.1%})")
        print(f"  Wrong (0.0):    {n_wrong} ({n_wrong/n:.1%})")
        print(f"  Mean score:     {mean_score:.3f}")

        # Per-category
        by_cat = defaultdict(list)
        for r in rs:
            q = questions.get(r["question_id"])
            if q:
                by_cat[q["category"]].append(r)

        print(f"\n  {'Category':<18} {'n':>4} {'Correct':>8} {'Partial':>8} {'Wrong':>8} {'Mean':>8}")
        print(f"  {'-'*55}")
        for cat in sorted(by_cat.keys()):
            cat_rs = by_cat[cat]
            nc = len(cat_rs)
            c1 = sum(1 for r in cat_rs if r["judge_score"] == 1.0)
            cp = sum(1 for r in cat_rs if r["judge_score"] == 0.5)
            c0 = sum(1 for r in cat_rs if r["judge_score"] == 0.0)
            m = sum(r["judge_score"] for r in cat_rs) / nc
            print(f"  {cat:<18} {nc:>4} {c1:>8} {cp:>8} {c0:>8} {m:>8.2f}")

    # ── 2. Concordance with keyword evaluator ──
    print("\n" + "=" * 60)
    print("CONCORDANCE: LLM JUDGE vs KEYWORD EVALUATOR")
    print("=" * 60)

    # Build paired comparisons
    agree = 0
    judge_strict_keyword_lenient = 0  # judge wrong, keyword correct
    judge_lenient_keyword_strict = 0  # judge correct, keyword wrong
    both_correct = 0
    both_wrong = 0
    total_paired = 0

    for r in results:
        if r["judge_score"] < 0:
            continue
        cond = r["condition"]
        qid = r["question_id"]
        q = questions.get(qid)
        if not q or cond not in keyword_preds:
            continue
        pred = keyword_preds[cond].get(qid)
        if not pred:
            continue

        # Keyword evaluator result
        kw_correct, _ = score_answer(
            q["category"], q["expected_answer"],
            pred.get("predicted_answer", "")
        )
        # LLM judge: score >= 0.5 = correct for binary comparison
        judge_correct = r["judge_score"] >= 0.5

        total_paired += 1
        if kw_correct == judge_correct:
            agree += 1
            if kw_correct:
                both_correct += 1
            else:
                both_wrong += 1
        elif kw_correct and not judge_correct:
            judge_strict_keyword_lenient += 1
        else:
            judge_lenient_keyword_strict += 1

    if total_paired > 0:
        print(f"\nTotal paired comparisons: {total_paired}")
        print(f"Agreement:           {agree} ({agree/total_paired:.1%})")
        print(f"  Both correct:      {both_correct}")
        print(f"  Both wrong:        {both_wrong}")
        print(f"Keyword correct, judge wrong: {judge_strict_keyword_lenient} ({judge_strict_keyword_lenient/total_paired:.1%})")
        print(f"Judge correct, keyword wrong: {judge_lenient_keyword_strict} ({judge_lenient_keyword_strict/total_paired:.1%})")

        # Cohen's kappa
        p_o = agree / total_paired
        p_kw = (both_correct + judge_strict_keyword_lenient) / total_paired
        p_jg = (both_correct + judge_lenient_keyword_strict) / total_paired
        p_e = p_kw * p_jg + (1 - p_kw) * (1 - p_jg)
        kappa = (p_o - p_e) / (1 - p_e) if p_e < 1 else 0
        print(f"Cohen's kappa:       {kappa:.3f}")

        # Per-condition concordance
        for cond in sorted(by_condition.keys()):
            cond_agree = 0
            cond_total = 0
            cond_kw_only = 0
            cond_judge_only = 0
            for r in by_condition[cond]:
                qid = r["question_id"]
                q = questions.get(qid)
                if not q or cond not in keyword_preds:
                    continue
                pred = keyword_preds[cond].get(qid)
                if not pred:
                    continue
                kw_correct, _ = score_answer(q["category"], q["expected_answer"], pred.get("predicted_answer", ""))
                judge_correct = r["judge_score"] >= 0.5
                cond_total += 1
                if kw_correct == judge_correct:
                    cond_agree += 1
                elif kw_correct and not judge_correct:
                    cond_kw_only += 1
                else:
                    cond_judge_only += 1
            if cond_total > 0:
                print(f"\n  {cond}: agreement {cond_agree/cond_total:.1%} ({cond_agree}/{cond_total})")
                print(f"    Keyword stricter: {cond_judge_only}, Judge stricter: {cond_kw_only}")

    # ── 3. Comparison with physician pilot ──
    print("\n" + "=" * 60)
    print("CONCORDANCE: LLM JUDGE vs PHYSICIAN (n=30 overlap)")
    print("=" * 60)

    if PHYSICIAN_ITEMS.exists() and PHYSICIAN_VALIDATIONS.exists():
        # Load physician items with actual conditions
        phys_items = {}
        with open(PHYSICIAN_ITEMS) as f:
            for line in f:
                item = json.loads(line)
                key = (item["question_id"], item["_actual_condition"])
                phys_items[key] = item

        # Load latest physician validations
        phys_reviews = {}
        with open(PHYSICIAN_VALIDATIONS) as f:
            for line in f:
                r = json.loads(line)
                key = (r["item_id"], r["question_id"])
                phys_reviews[key] = r

        # Map item_id to actual condition
        item_to_cond = {}
        with open(PHYSICIAN_ITEMS) as f:
            for line in f:
                item = json.loads(line)
                item_to_cond[item["item_id"]] = item["_actual_condition"]

        # Build physician judgment map: (question_id, condition) -> correct/partial/incorrect
        phys_judgments = {}
        for (item_id, qid), review in phys_reviews.items():
            actual_cond = item_to_cond.get(item_id, "")
            # Map to our condition names
            if "C1" in actual_cond:
                cond = "C1"
            elif "C4g" in actual_cond:
                cond = "C4g"
            else:
                continue
            phys_judgments[(qid, cond)] = review["model_answer_rating"]

        # Compare judge vs physician
        judge_map = {(r["question_id"], r["condition"]): r for r in results if r["judge_score"] >= 0}

        phys_agree = 0
        phys_total = 0
        judge_strict_phys = 0
        judge_lenient_phys = 0
        kw_agree_phys = 0
        kw_strict_phys = 0
        kw_lenient_phys = 0

        for (qid, cond), rating in phys_judgments.items():
            judge_r = judge_map.get((qid, cond))
            if not judge_r:
                continue

            phys_correct = rating in ("correct", "partially_correct")
            judge_correct = judge_r["judge_score"] >= 0.5

            phys_total += 1
            if phys_correct == judge_correct:
                phys_agree += 1
            elif phys_correct and not judge_correct:
                judge_strict_phys += 1
            else:
                judge_lenient_phys += 1

            # Also compute keyword vs physician
            q = questions.get(qid)
            if q and cond in keyword_preds:
                pred = keyword_preds[cond].get(qid)
                if pred:
                    kw_correct, _ = score_answer(q["category"], q["expected_answer"], pred.get("predicted_answer", ""))
                    if kw_correct == phys_correct:
                        kw_agree_phys += 1
                    elif phys_correct and not kw_correct:
                        kw_strict_phys += 1
                    else:
                        kw_lenient_phys += 1

        if phys_total > 0:
            print(f"\nOverlapping items: {phys_total}")
            print(f"\nLLM Judge vs Physician:")
            print(f"  Agreement:        {phys_agree}/{phys_total} ({phys_agree/phys_total:.1%})")
            print(f"  Judge too strict: {judge_strict_phys}/{phys_total} ({judge_strict_phys/phys_total:.1%})")
            print(f"  Judge too lenient:{judge_lenient_phys}/{phys_total} ({judge_lenient_phys/phys_total:.1%})")

            print(f"\nKeyword Evaluator vs Physician (same {phys_total} items):")
            kw_total = kw_agree_phys + kw_strict_phys + kw_lenient_phys
            if kw_total > 0:
                print(f"  Agreement:        {kw_agree_phys}/{kw_total} ({kw_agree_phys/kw_total:.1%})")
                print(f"  Keyword too strict:{kw_strict_phys}/{kw_total} ({kw_strict_phys/kw_total:.1%})")
                print(f"  Keyword too lenient:{kw_lenient_phys}/{kw_total} ({kw_lenient_phys/kw_total:.1%})")
        else:
            print("No overlapping items found between LLM judge and physician reviews.")
    else:
        print("Physician adjudication files not found.")

    # ── 4. Delta comparison ──
    print("\n" + "=" * 60)
    print("DELTA COMPARISON")
    print("=" * 60)

    for threshold_label, threshold in [("strict (1.0)", 1.0), ("lenient (>=0.5)", 0.5)]:
        cond_accs = {}
        for cond in sorted(by_condition.keys()):
            rs = by_condition[cond]
            n_correct = sum(1 for r in rs if r["judge_score"] >= threshold)
            cond_accs[cond] = n_correct / len(rs) if rs else 0
            print(f"  {cond} accuracy ({threshold_label}): {cond_accs[cond]:.1%} ({n_correct}/{len(rs)})")

        if "C1" in cond_accs and "C4g" in cond_accs:
            delta = cond_accs["C4g"] - cond_accs["C1"]
            print(f"  C4g-C1 delta ({threshold_label}): {delta:+.1%}")
        print()

    # ── 5. Save summary ──
    summary = {
        "n_judged": len([r for r in results if r["judge_score"] >= 0]),
        "conditions": {},
    }
    for cond in sorted(by_condition.keys()):
        rs = by_condition[cond]
        n = len(rs)
        summary["conditions"][cond] = {
            "n": n,
            "correct_strict": sum(1 for r in rs if r["judge_score"] == 1.0),
            "partial": sum(1 for r in rs if r["judge_score"] == 0.5),
            "wrong": sum(1 for r in rs if r["judge_score"] == 0.0),
            "mean_score": sum(r["judge_score"] for r in rs) / n,
        }
    if total_paired > 0:
        summary["keyword_concordance"] = {
            "agreement": agree / total_paired,
            "kappa": kappa,
            "n_paired": total_paired,
        }
    if phys_total > 0:
        summary["physician_concordance"] = {
            "judge_agreement": phys_agree / phys_total,
            "judge_too_strict": judge_strict_phys / phys_total,
            "keyword_agreement": kw_agree_phys / kw_total if kw_total > 0 else 0,
            "n_items": phys_total,
        }

    summary_path = JUDGE_DIR / "llm_judge_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved summary to {summary_path}")

    return summary


async def main():
    parser = argparse.ArgumentParser(description="LLM-as-Judge for ClinicalBench")
    parser.add_argument("--conditions", nargs="+", default=["C1", "C4g"])
    parser.add_argument("--model", default="claude-opus-4-20250514")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--max-concurrent", type=int, default=5)
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()

    JUDGE_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_path = Path(args.checkpoint) if args.checkpoint else JUDGE_DIR / "llm_judge_checkpoint.jsonl"

    if args.analyze_only:
        if not checkpoint_path.exists():
            print(f"No checkpoint at {checkpoint_path}")
            return
        results = []
        with open(checkpoint_path) as f:
            for line in f:
                results.append(json.loads(line))
        analyze_results(results)
        return

    results = await run_judge(
        conditions=args.conditions,
        checkpoint_path=checkpoint_path,
        model=args.model,
        max_concurrent=args.max_concurrent,
    )
    analyze_results(results)


if __name__ == "__main__":
    asyncio.run(main())
