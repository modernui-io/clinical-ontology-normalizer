#!/usr/bin/env python3
"""Export blinded physician adjudication scoring sheets per PHYSICIAN_VALIDATION_PROTOCOL.md.

Produces:
  - Two CSV files (one per reviewer) with randomized condition labels (A/B)
  - A key file mapping condition labels to actual conditions
  - JSONL for optional web UI ingestion

Sampling follows the protocol:
  ClinicalBench: 120 questions × 2 conditions (C1, C4g) = 240 scored pairs
  SliceBench: 48 questions × 2 conditions (B2, B3) = 96 scored pairs (TODO)
"""

import json
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../epikg-benchmark/clinicalbench"))
from evaluator import score_answer

SEED = 42
import random
rng = random.Random(SEED)

# ── Config ──
QUESTIONS_PATH = "epikg-benchmark/clinicalbench/questions.json"
C1_PATH = "epikg-benchmark/results/opus/C1_llm_alone.json"
C4G_PATH = "epikg-benchmark/results/opus/C4g_intent_aware.json"
OUTPUT_DIR = "backend/data/benchmarks/results/physician_adjudication"

# Protocol-specified sample sizes per category
SAMPLE_SIZES = {
    "uncertainty": 20,
    "sequence": 20,
    "change": 15,
    "current_state": 15,
    "historical": 15,
    "conditional": 10,
    "family_history": 10,
    "duration": 10,
    "negation": 5,
}

# ── Load data ──
with open(QUESTIONS_PATH) as f:
    qdata = json.load(f)
questions = {q["question_id"]: q for q in qdata["questions"]}

with open(C1_PATH) as f:
    c1_data = json.load(f)
c1_preds = {p["question_id"]: p for p in c1_data["predictions"]}

with open(C4G_PATH) as f:
    c4g_data = json.load(f)
c4g_preds = {p["question_id"]: p for p in c4g_data["predictions"]}

# ── Group by category ──
by_category = defaultdict(list)
for qid, q in questions.items():
    if qid in c1_preds and qid in c4g_preds:
        by_category[q["category"]].append(qid)

# ── Stratified sampling ──
# Aim for ~50/50 split between correct and incorrect automated scores
sampled_qids = []
for cat, target_n in SAMPLE_SIZES.items():
    pool = by_category.get(cat, [])
    if not pool:
        print(f"WARNING: No questions for category {cat}")
        continue

    # Split into correct/incorrect under C4g (where evaluator might err)
    correct_pool = []
    incorrect_pool = []
    for qid in pool:
        q = questions[qid]
        ans = c4g_preds[qid].get("predicted_answer", "")
        is_correct, _ = score_answer(cat, q["expected_answer"], ans) if ans else (False, 0.0)
        if is_correct:
            correct_pool.append(qid)
        else:
            incorrect_pool.append(qid)

    # Sample ~50/50 correct/incorrect
    n_correct = min(len(correct_pool), target_n // 2)
    n_incorrect = min(len(incorrect_pool), target_n - n_correct)
    n_correct = min(len(correct_pool), target_n - n_incorrect)  # fill remainder

    rng.shuffle(correct_pool)
    rng.shuffle(incorrect_pool)
    sampled = correct_pool[:n_correct] + incorrect_pool[:n_incorrect]

    # If we still need more, pull from whichever pool has remaining
    remaining = target_n - len(sampled)
    if remaining > 0:
        leftover = [q for q in pool if q not in sampled]
        rng.shuffle(leftover)
        sampled.extend(leftover[:remaining])

    sampled_qids.extend(sampled)
    print(f"{cat:<18} sampled {len(sampled)}/{target_n} (correct={n_correct}, incorrect={n_incorrect}, pool={len(pool)})")

print(f"\nTotal sampled: {len(sampled_qids)} questions × 2 conditions = {len(sampled_qids) * 2} scored pairs")

# ── Build scoring sheet ──
# For each question, create two items (C1 and C4g) with randomized labels
items = []
condition_key = {}  # item_id -> actual condition

item_counter = 1
for qid in sorted(sampled_qids):
    q = questions[qid]

    # Randomize which condition is A vs B
    if rng.random() < 0.5:
        label_map = {"C1_llm_alone": "A", "C4g_intent_aware": "B"}
    else:
        label_map = {"C1_llm_alone": "B", "C4g_intent_aware": "A"}

    for cond, preds in [("C1_llm_alone", c1_preds), ("C4g_intent_aware", c4g_preds)]:
        item_id = f"VAL_{item_counter:04d}"
        item_counter += 1
        pred = preds.get(qid, {})
        ans = pred.get("predicted_answer", "")

        # Score with v2 evaluator for reference (blinded from reviewers)
        auto_correct, auto_score = score_answer(q["category"], q["expected_answer"], ans) if ans else (False, 0.0)

        items.append({
            "item_id": item_id,
            "question_id": qid,
            "category": q["category"],
            "question": q["question"],
            "expected_answer": q["expected_answer"],
            "condition_label": label_map[cond],
            "model_answer": ans,
            # Hidden from reviewers:
            "_actual_condition": cond,
            "_auto_correct": auto_correct,
            "_auto_score": auto_score,
        })
        condition_key[item_id] = cond

# Shuffle items so reviewer doesn't see systematic patterns
rng.shuffle(items)

# ── Write outputs ──
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. Reviewer CSV (blinded — no condition key, no auto scores)
reviewer_fields = ["item_id", "category", "condition_label", "question", "expected_answer", "model_answer",
                   "physician_score", "physician_notes"]

for reviewer_num in [1, 2]:
    csv_path = os.path.join(OUTPUT_DIR, f"reviewer_{reviewer_num}_scoring_sheet.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=reviewer_fields)
        writer.writeheader()
        for item in items:
            row = {k: item.get(k, "") for k in reviewer_fields}
            writer.writerow(row)
    print(f"Written: {csv_path}")

# 2. Key file (for reconciliation after blinded review)
key_path = os.path.join(OUTPUT_DIR, "condition_key.json")
with open(key_path, "w") as f:
    json.dump(condition_key, f, indent=2)
print(f"Written: {key_path}")

# 3. Full JSONL (for programmatic analysis)
jsonl_path = os.path.join(OUTPUT_DIR, "adjudication_items.jsonl")
with open(jsonl_path, "w") as f:
    for item in items:
        f.write(json.dumps(item) + "\n")
print(f"Written: {jsonl_path}")

print(f"\nDone. {len(items)} items exported for physician adjudication.")
print(f"Each reviewer scores: {len(items)} items ({len(sampled_qids)} questions × 2 conditions)")
