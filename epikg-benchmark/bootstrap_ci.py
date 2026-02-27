#!/usr/bin/env python3
"""Compute BCa bootstrap 95% CIs for ClinicalBench C4g vs C1 accuracy deltas."""

import json
import sys
import numpy as np
from collections import defaultdict

sys.path.insert(0, "/Users/alexstinard/projects/brainstorm/jan-14-2026/epikg-benchmark/clinicalbench")
from evaluator import score_answer

# ── Config ──
N_BOOT = 2000
SEED = 42
ALPHA = 0.05
QUESTIONS_PATH = "/Users/alexstinard/projects/brainstorm/jan-14-2026/epikg-benchmark/clinicalbench/questions.json"
C1_PATH = "/Users/alexstinard/projects/brainstorm/jan-14-2026/epikg-benchmark/results/opus/C1_llm_alone.json"
C4G_PATH = "/Users/alexstinard/projects/brainstorm/jan-14-2026/epikg-benchmark/results/opus/C4g_intent_aware.json"

HARD_LONGITUDINAL = {"historical", "change", "current_state"}

# ── Load data ──
with open(QUESTIONS_PATH) as f:
    qdata = json.load(f)
questions = {q["question_id"]: q for q in qdata["questions"]}

with open(C1_PATH) as f:
    c1data = json.load(f)
c1_preds = {p["question_id"]: p for p in c1data["predictions"]}

with open(C4G_PATH) as f:
    c4g_data = json.load(f)
c4g_preds = {p["question_id"]: p for p in c4g_data["predictions"]}

# ── Score all questions ──
# Build arrays: qids, categories, c1_correct, c4g_correct
qids = []
categories = []
c1_scores = []
c4g_scores = []

for qid in sorted(questions.keys()):
    q = questions[qid]
    c1_pred = c1_preds.get(qid)
    c4g_pred = c4g_preds.get(qid)
    if not c1_pred or not c4g_pred:
        continue

    c1_ans = c1_pred.get("predicted_answer", "")
    c4g_ans = c4g_pred.get("predicted_answer", "")

    c1_correct, _ = score_answer(q["category"], q["expected_answer"], c1_ans) if c1_ans else (False, 0.0)
    c4g_correct, _ = score_answer(q["category"], q["expected_answer"], c4g_ans) if c4g_ans else (False, 0.0)

    qids.append(qid)
    categories.append(q["category"])
    c1_scores.append(1.0 if c1_correct else 0.0)
    c4g_scores.append(1.0 if c4g_correct else 0.0)

c1_scores = np.array(c1_scores)
c4g_scores = np.array(c4g_scores)
categories = np.array(categories)
n = len(qids)

print(f"Loaded {n} questions with predictions in both conditions")
print(f"C1 overall: {c1_scores.mean():.1%} ({int(c1_scores.sum())}/{n})")
print(f"C4g overall: {c4g_scores.mean():.1%} ({int(c4g_scores.sum())}/{n})")
print(f"Delta: {(c4g_scores.mean() - c1_scores.mean()):.1%}")
print()

# ── BCa bootstrap ──

def bca_ci(data_func, indices, n_boot=N_BOOT, alpha=ALPHA, rng=None):
    """
    Compute BCa bootstrap CI.
    data_func(idx) returns the statistic for the given index array.
    indices: original index array.
    """
    if rng is None:
        rng = np.random.default_rng(SEED)

    n = len(indices)
    theta_hat = data_func(indices)

    # Bootstrap distribution
    boot_thetas = np.empty(n_boot)
    for b in range(n_boot):
        boot_idx = rng.choice(indices, size=n, replace=True)
        boot_thetas[b] = data_func(boot_idx)

    # Bias correction: z0
    from scipy.stats import norm
    prop_less = np.mean(boot_thetas < theta_hat)
    # Clamp to avoid inf
    prop_less = np.clip(prop_less, 1e-10, 1 - 1e-10)
    z0 = norm.ppf(prop_less)

    # Acceleration: jackknife
    jack_thetas = np.empty(n)
    for i in range(n):
        jack_idx = np.delete(indices, i)
        jack_thetas[i] = data_func(jack_idx)
    jack_mean = jack_thetas.mean()
    num = np.sum((jack_mean - jack_thetas) ** 3)
    denom = 6.0 * (np.sum((jack_mean - jack_thetas) ** 2) ** 1.5)
    a_hat = num / denom if denom != 0 else 0.0

    # Adjusted percentiles
    z_alpha = norm.ppf(alpha / 2)
    z_1alpha = norm.ppf(1 - alpha / 2)

    a1 = norm.cdf(z0 + (z0 + z_alpha) / (1 - a_hat * (z0 + z_alpha)))
    a2 = norm.cdf(z0 + (z0 + z_1alpha) / (1 - a_hat * (z0 + z_1alpha)))

    # Clamp percentiles
    a1 = np.clip(a1, 0.0, 1.0)
    a2 = np.clip(a2, 0.0, 1.0)

    ci_low = np.percentile(boot_thetas, 100 * a1)
    ci_high = np.percentile(boot_thetas, 100 * a2)

    return theta_hat, ci_low, ci_high, boot_thetas


# ── Statistic functions ──

def overall_delta(idx):
    return c4g_scores[idx].mean() - c1_scores[idx].mean()

def accuracy_c4g(idx):
    return c4g_scores[idx].mean()

def accuracy_c1(idx):
    return c1_scores[idx].mean()


rng = np.random.default_rng(SEED)

# 1. Overall delta
all_idx = np.arange(n)
theta, lo, hi, boot_dist = bca_ci(overall_delta, all_idx, rng=np.random.default_rng(SEED))
print("=" * 60)
print("1. OVERALL C4g vs C1 ACCURACY DELTA (Opus, n=400)")
print(f"   Delta: {theta:.1%}")
print(f"   95% BCa CI: [{lo:.1%}, {hi:.1%}]")
print(f"   Boot mean: {boot_dist.mean():.1%}, Boot SD: {boot_dist.std():.1%}")
print()

# Also report individual condition CIs
theta_c1, lo_c1, hi_c1, _ = bca_ci(accuracy_c1, all_idx, rng=np.random.default_rng(SEED+1))
theta_c4g, lo_c4g, hi_c4g, _ = bca_ci(accuracy_c4g, all_idx, rng=np.random.default_rng(SEED+2))
print(f"   C1 accuracy:  {theta_c1:.1%} [{lo_c1:.1%}, {hi_c1:.1%}]")
print(f"   C4g accuracy: {theta_c4g:.1%} [{lo_c4g:.1%}, {hi_c4g:.1%}]")
print()

# 2. Hard longitudinal subset
hard_mask = np.array([c in HARD_LONGITUDINAL for c in categories])
hard_idx = np.where(hard_mask)[0]
n_hard = len(hard_idx)

def hard_delta(idx):
    # idx indexes into hard_idx
    actual_idx = hard_idx[idx]
    return c4g_scores[actual_idx].mean() - c1_scores[actual_idx].mean()

hard_sub_idx = np.arange(n_hard)
theta_h, lo_h, hi_h, boot_h = bca_ci(hard_delta, hard_sub_idx, rng=np.random.default_rng(SEED+3))
print("=" * 60)
print(f"2. HARD LONGITUDINAL SUBSET (historical + change + current_state, n={n_hard})")
print(f"   Delta: {theta_h:.1%}")
print(f"   95% BCa CI: [{lo_h:.1%}, {hi_h:.1%}]")
print(f"   Boot mean: {boot_h.mean():.1%}, Boot SD: {boot_h.std():.1%}")
print()

# 3. Per-category deltas
print("=" * 60)
print("3. PER-CATEGORY C4g vs C1 DELTAS")
print(f"{'Category':<18} {'n':>4} {'C1':>7} {'C4g':>7} {'Delta':>7} {'95% BCa CI':>20}")
print("-" * 70)

unique_cats = sorted(set(categories))
for cat in unique_cats:
    cat_mask = categories == cat
    cat_idx = np.where(cat_mask)[0]
    n_cat = len(cat_idx)

    def cat_delta(idx, _cat_idx=cat_idx):
        actual_idx = _cat_idx[idx]
        return c4g_scores[actual_idx].mean() - c1_scores[actual_idx].mean()

    cat_sub_idx = np.arange(n_cat)
    theta_c, lo_c, hi_c, _ = bca_ci(cat_delta, cat_sub_idx, rng=np.random.default_rng(SEED + hash(cat) % 1000))

    c1_acc = c1_scores[cat_idx].mean()
    c4g_acc = c4g_scores[cat_idx].mean()

    print(f"{cat:<18} {n_cat:>4} {c1_acc:>6.1%} {c4g_acc:>6.1%} {theta_c:>+6.1%}   [{lo_c:>+6.1%}, {hi_c:>+6.1%}]")

print()
print("=" * 60)
print("Summary for paper:")
print(f"  Overall delta: +{theta:.0%} points, 95% BCa CI [{lo:.1%}, {hi:.1%}]")
print(f"  Hard longitudinal delta: +{theta_h:.0%} points, 95% BCa CI [{lo_h:.1%}, {hi_h:.1%}]")
print(f"  n_boot={N_BOOT}, seed={SEED}")
