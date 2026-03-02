#!/usr/bin/env python3
"""Compute BCa bootstrap 95% CIs for ClinicalBench C4g vs C1 (and C3) accuracy deltas."""

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
C3_PATH = "/Users/alexstinard/projects/brainstorm/jan-14-2026/epikg-benchmark/results/opus/C3_kg_rag.json"
C4G_PATH = "/Users/alexstinard/projects/brainstorm/jan-14-2026/epikg-benchmark/results/opus/C4g_intent_aware.json"

HARD_LONGITUDINAL = {"historical", "change", "current_state"}

# ── Load data ──
with open(QUESTIONS_PATH) as f:
    qdata = json.load(f)
questions = {q["question_id"]: q for q in qdata["questions"]}

with open(C1_PATH) as f:
    c1data = json.load(f)
c1_preds = {p["question_id"]: p for p in c1data["predictions"]}

with open(C3_PATH) as f:
    c3_data = json.load(f)
c3_preds = {p["question_id"]: p for p in c3_data["predictions"]}

with open(C4G_PATH) as f:
    c4g_data = json.load(f)
c4g_preds = {p["question_id"]: p for p in c4g_data["predictions"]}

# ── Score all questions ──
# Build arrays: qids, categories, c1_correct, c3_correct, c4g_correct
qids = []
categories = []
c1_scores = []
c3_scores = []
c4g_scores = []

for qid in sorted(questions.keys()):
    q = questions[qid]
    c1_pred = c1_preds.get(qid)
    c3_pred = c3_preds.get(qid)
    c4g_pred = c4g_preds.get(qid)
    if not c1_pred or not c3_pred or not c4g_pred:
        continue

    c1_ans = c1_pred.get("predicted_answer", "")
    c3_ans = c3_pred.get("predicted_answer", "")
    c4g_ans = c4g_pred.get("predicted_answer", "")

    c1_correct, _ = score_answer(q["category"], q["expected_answer"], c1_ans) if c1_ans else (False, 0.0)
    c3_correct, _ = score_answer(q["category"], q["expected_answer"], c3_ans) if c3_ans else (False, 0.0)
    c4g_correct, _ = score_answer(q["category"], q["expected_answer"], c4g_ans) if c4g_ans else (False, 0.0)

    qids.append(qid)
    categories.append(q["category"])
    c1_scores.append(1.0 if c1_correct else 0.0)
    c3_scores.append(1.0 if c3_correct else 0.0)
    c4g_scores.append(1.0 if c4g_correct else 0.0)

c1_scores = np.array(c1_scores)
c3_scores = np.array(c3_scores)
c4g_scores = np.array(c4g_scores)
categories = np.array(categories)
n = len(qids)

print(f"Loaded {n} questions with predictions in all three conditions")
print(f"C1 overall: {c1_scores.mean():.1%} ({int(c1_scores.sum())}/{n})")
print(f"C3 overall: {c3_scores.mean():.1%} ({int(c3_scores.sum())}/{n})")
print(f"C4g overall: {c4g_scores.mean():.1%} ({int(c4g_scores.sum())}/{n})")
print(f"C1->C3 delta: {(c3_scores.mean() - c1_scores.mean()):.1%}")
print(f"C3->C4g delta: {(c4g_scores.mean() - c3_scores.mean()):.1%}")
print(f"C1->C4g delta: {(c4g_scores.mean() - c1_scores.mean()):.1%}")
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

def c1_to_c3_delta(idx):
    return c3_scores[idx].mean() - c1_scores[idx].mean()

def c3_to_c4g_delta(idx):
    return c4g_scores[idx].mean() - c3_scores[idx].mean()

def accuracy_c4g(idx):
    return c4g_scores[idx].mean()

def accuracy_c3(idx):
    return c3_scores[idx].mean()

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
theta_c3, lo_c3, hi_c3, _ = bca_ci(accuracy_c3, all_idx, rng=np.random.default_rng(SEED+10))
print(f"   C1 accuracy:  {theta_c1:.1%} [{lo_c1:.1%}, {hi_c1:.1%}]")
print(f"   C3 accuracy:  {theta_c3:.1%} [{lo_c3:.1%}, {hi_c3:.1%}]")
print(f"   C4g accuracy: {theta_c4g:.1%} [{lo_c4g:.1%}, {hi_c4g:.1%}]")
print()

# 1b. C1->C3 delta (structured retrieval effect)
theta_13, lo_13, hi_13, boot_13 = bca_ci(c1_to_c3_delta, all_idx, rng=np.random.default_rng(SEED+11))
print("=" * 60)
print("1b. C1->C3 DELTA (structured retrieval effect, n=400)")
print(f"   Delta: {theta_13:.1%}")
print(f"   95% BCa CI: [{lo_13:.1%}, {hi_13:.1%}]")
print()

# 1c. C3->C4g delta (epistemic annotation effect)
theta_34, lo_34, hi_34, boot_34 = bca_ci(c3_to_c4g_delta, all_idx, rng=np.random.default_rng(SEED+12))
print("=" * 60)
print("1c. C3->C4g DELTA (epistemic annotation effect, n=400)")
print(f"   Delta: {theta_34:.1%}")
print(f"   95% BCa CI: [{lo_34:.1%}, {hi_34:.1%}]")
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

# ── 4. PATIENT-LEVEL BOOTSTRAP CIs ──
# Resample patients (not questions) with replacement, include all their questions
print("=" * 60)
print("4. PATIENT-LEVEL BOOTSTRAP CIs (cluster bootstrap)")

# Build patient -> question index mapping
patient_ids = []
for qid in qids:
    q = questions[qid]
    patient_ids.append(q["mimic_subject_id"])
patient_ids = np.array(patient_ids)
unique_patients = np.unique(patient_ids)
n_patients = len(unique_patients)
patient_to_idx = {pid: np.where(patient_ids == pid)[0] for pid in unique_patients}

print(f"   {n_patients} patients, {n} questions")

def patient_cluster_boot_ci(stat_func, n_boot=N_BOOT, alpha=ALPHA, rng=None):
    """BCa bootstrap resampling patients (clusters) instead of questions."""
    if rng is None:
        rng = np.random.default_rng(SEED)

    from scipy.stats import norm

    # Observed statistic on all data
    all_idx = np.arange(n)
    theta_hat = stat_func(all_idx)

    # Bootstrap: resample patients, gather all their question indices
    boot_thetas = np.empty(n_boot)
    for b in range(n_boot):
        sampled_patients = rng.choice(unique_patients, size=n_patients, replace=True)
        boot_question_idx = np.concatenate([patient_to_idx[p] for p in sampled_patients])
        boot_thetas[b] = stat_func(boot_question_idx)

    # BCa correction
    prop_less = np.clip(np.mean(boot_thetas < theta_hat), 1e-10, 1 - 1e-10)
    z0 = norm.ppf(prop_less)

    # Jackknife over patients
    jack_thetas = np.empty(n_patients)
    for i, pid in enumerate(unique_patients):
        leave_out = patient_to_idx[pid]
        jack_idx = np.setdiff1d(all_idx, leave_out)
        jack_thetas[i] = stat_func(jack_idx)
    jack_mean = jack_thetas.mean()
    num = np.sum((jack_mean - jack_thetas) ** 3)
    denom = 6.0 * (np.sum((jack_mean - jack_thetas) ** 2) ** 1.5)
    a_hat = num / denom if denom != 0 else 0.0

    z_alpha = norm.ppf(alpha / 2)
    z_1alpha = norm.ppf(1 - alpha / 2)
    a1 = norm.cdf(z0 + (z0 + z_alpha) / (1 - a_hat * (z0 + z_alpha)))
    a2 = norm.cdf(z0 + (z0 + z_1alpha) / (1 - a_hat * (z0 + z_1alpha)))
    a1 = np.clip(a1, 0.0, 1.0)
    a2 = np.clip(a2, 0.0, 1.0)

    ci_low = np.percentile(boot_thetas, 100 * a1)
    ci_high = np.percentile(boot_thetas, 100 * a2)

    return theta_hat, ci_low, ci_high

# Overall delta (patient-level)
pt_theta, pt_lo, pt_hi = patient_cluster_boot_ci(overall_delta, rng=np.random.default_rng(SEED+100))
print(f"   Overall C4g-C1 (patient-level): {pt_theta:.1%} [{pt_lo:.1%}, {pt_hi:.1%}]")

# C1->C3 (patient-level)
pt_13_theta, pt_13_lo, pt_13_hi = patient_cluster_boot_ci(c1_to_c3_delta, rng=np.random.default_rng(SEED+101))
print(f"   C1->C3 (patient-level):         {pt_13_theta:.1%} [{pt_13_lo:.1%}, {pt_13_hi:.1%}]")

# C3->C4g (patient-level)
pt_34_theta, pt_34_lo, pt_34_hi = patient_cluster_boot_ci(c3_to_c4g_delta, rng=np.random.default_rng(SEED+102))
print(f"   C3->C4g (patient-level):         {pt_34_theta:.1%} [{pt_34_lo:.1%}, {pt_34_hi:.1%}]")

# Hard longitudinal (patient-level) — need patient mapping for hard subset
def hard_delta_all(idx):
    """Compute delta on hard longitudinal questions within the given question indices."""
    mask = np.isin(idx, hard_idx)
    sub = idx[mask]
    if len(sub) == 0:
        return 0.0
    return c4g_scores[sub].mean() - c1_scores[sub].mean()

pt_h_theta, pt_h_lo, pt_h_hi = patient_cluster_boot_ci(hard_delta_all, rng=np.random.default_rng(SEED+103))
print(f"   Hard longitudinal (patient-level): {pt_h_theta:.1%} [{pt_h_lo:.1%}, {pt_h_hi:.1%}]")
print()

# ── 5. McNEMAR'S TEST ──
print("=" * 60)
print("5. McNEMAR'S TEST (C1 vs C4g)")

# Discordant pairs
c1_right_c4g_wrong = np.sum((c1_scores == 1) & (c4g_scores == 0))
c1_wrong_c4g_right = np.sum((c1_scores == 0) & (c4g_scores == 1))
both_right = np.sum((c1_scores == 1) & (c4g_scores == 1))
both_wrong = np.sum((c1_scores == 0) & (c4g_scores == 0))

print(f"   Both right: {int(both_right)}")
print(f"   Both wrong: {int(both_wrong)}")
print(f"   C1 right, C4g wrong: {int(c1_right_c4g_wrong)}")
print(f"   C1 wrong, C4g right: {int(c1_wrong_c4g_right)}")

# McNemar chi-squared (with continuity correction)
b = c1_right_c4g_wrong
c = c1_wrong_c4g_right
if b + c > 0:
    chi2 = (abs(b - c) - 1) ** 2 / (b + c)
    from scipy.stats import chi2 as chi2_dist
    p_val = 1 - chi2_dist.cdf(chi2, df=1)
    print(f"   McNemar chi2 (continuity-corrected): {chi2:.1f}, df=1, p={p_val:.2e}")
    if p_val < 0.001:
        print(f"   Highly significant (p < 0.001)")

# Also C1 vs C3
c1_right_c3_wrong = np.sum((c1_scores == 1) & (c3_scores == 0))
c1_wrong_c3_right = np.sum((c1_scores == 0) & (c3_scores == 1))
b13 = c1_right_c3_wrong
c13 = c1_wrong_c3_right
if b13 + c13 > 0:
    chi2_13 = (abs(b13 - c13) - 1) ** 2 / (b13 + c13)
    p_13 = 1 - chi2_dist.cdf(chi2_13, df=1)
    print(f"\n   McNemar C1 vs C3: chi2={chi2_13:.1f}, p={p_13:.2e}")
    print(f"   C1 right/C3 wrong: {int(b13)}, C1 wrong/C3 right: {int(c13)}")

# C3 vs C4g
c3_right_c4g_wrong = np.sum((c3_scores == 1) & (c4g_scores == 0))
c3_wrong_c4g_right = np.sum((c3_scores == 0) & (c4g_scores == 1))
b34 = c3_right_c4g_wrong
c34 = c3_wrong_c4g_right
if b34 + c34 > 0:
    chi2_34 = (abs(b34 - c34) - 1) ** 2 / (b34 + c34)
    p_34 = 1 - chi2_dist.cdf(chi2_34, df=1)
    print(f"\n   McNemar C3 vs C4g: chi2={chi2_34:.1f}, p={p_34:.2e}")
    print(f"   C3 right/C4g wrong: {int(b34)}, C3 wrong/C4g right: {int(c34)}")

# Benjamini-Hochberg FDR correction on all McNemar tests
_mcn_pvals = []
_mcn_names = []
if b + c > 0:
    _mcn_pvals.append(p_val); _mcn_names.append("C1 vs C4g")
if b13 + c13 > 0:
    _mcn_pvals.append(p_13); _mcn_names.append("C1 vs C3")
if b34 + c34 > 0:
    _mcn_pvals.append(p_34); _mcn_names.append("C3 vs C4g")
if len(_mcn_pvals) > 1:
    _p = np.array(_mcn_pvals)
    _n = len(_p)
    _sidx = np.argsort(_p)
    _bh = np.empty(_n)
    for _i, _idx in enumerate(_sidx):
        _bh[_idx] = min(_p[_idx] * _n / (_i + 1), 1.0)
    for _i in range(_n - 2, -1, -1):
        _bh[_sidx[_i]] = min(_bh[_sidx[_i]], _bh[_sidx[_i + 1]])
    print(f"\n   Benjamini-Hochberg FDR correction ({_n} tests):")
    for _i, _name in enumerate(_mcn_names):
        _sig = "*" if _bh[_i] < 0.05 else ""
        print(f"     {_name}: p_raw={_mcn_pvals[_i]:.2e}, p_BH={_bh[_i]:.2e} {_sig}")

print()
print("=" * 60)
print("Summary for paper:")
print(f"  Overall C1->C4g delta: +{theta:.0%} points, 95% BCa CI [{lo:.1%}, {hi:.1%}]")
print(f"  C1->C3 delta (retrieval): +{theta_13:.0%} points, 95% BCa CI [{lo_13:.1%}, {hi_13:.1%}]")
print(f"  C3->C4g delta (epistemic): +{theta_34:.0%} points, 95% BCa CI [{lo_34:.1%}, {hi_34:.1%}]")
print(f"  Hard longitudinal delta: +{theta_h:.0%} points, 95% BCa CI [{lo_h:.1%}, {hi_h:.1%}]")
print(f"  Patient-level overall: +{pt_theta:.0%} points, 95% BCa CI [{pt_lo:.1%}, {pt_hi:.1%}]")
print(f"  Patient-level hard long: +{pt_h_theta:.0%} points, 95% BCa CI [{pt_h_lo:.1%}, {pt_h_hi:.1%}]")
print(f"  McNemar C1 vs C4g: chi2={chi2:.1f}, p={p_val:.2e}")
print(f"  n_boot={N_BOOT}, seed={SEED}, n_patients={n_patients}")
