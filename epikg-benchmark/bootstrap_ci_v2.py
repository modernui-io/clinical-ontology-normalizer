#!/usr/bin/env python3
"""Compute BCa bootstrap 95% CIs for ClinicalBench — includes C4 ablation decomposition.

Extends bootstrap_ci.py to include C4 (assertions + no intent routing) for
decomposing the C3→C4g gap into assertions-only (C3→C4) and routing (C4→C4g).
"""

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
BASE = "/Users/alexstinard/projects/brainstorm/jan-14-2026/epikg-benchmark"
QUESTIONS_PATH = f"{BASE}/clinicalbench/questions.json"
C1_PATH = f"{BASE}/results/opus/C1_llm_alone.json"
C3_PATH = f"{BASE}/results/opus/C3_kg_rag.json"
C4_PATH = f"{BASE}/results/opus/C4_epistemic_kg_rag.json"
C4G_PATH = f"{BASE}/results/opus/C4g_intent_aware.json"

HARD_LONGITUDINAL = {"historical", "change", "current_state"}

# ── Load data ──
with open(QUESTIONS_PATH) as f:
    qdata = json.load(f)
questions = {q["question_id"]: q for q in qdata["questions"]}

def load_preds(path):
    with open(path) as f:
        data = json.load(f)
    return {p["question_id"]: p for p in data["predictions"]}

c1_preds = load_preds(C1_PATH)
c3_preds = load_preds(C3_PATH)
c4_preds = load_preds(C4_PATH)
c4g_preds = load_preds(C4G_PATH)

# ── Score all questions ──
qids = []
categories = []
c1_scores = []
c3_scores = []
c4_scores = []
c4g_scores = []

for qid in sorted(questions.keys()):
    q = questions[qid]
    c1_pred = c1_preds.get(qid)
    c3_pred = c3_preds.get(qid)
    c4_pred = c4_preds.get(qid)
    c4g_pred = c4g_preds.get(qid)
    if not c1_pred or not c3_pred or not c4_pred or not c4g_pred:
        continue

    def score(pred):
        ans = pred.get("predicted_answer", "")
        if not ans:
            return 0.0
        correct, _ = score_answer(q["category"], q["expected_answer"], ans)
        return 1.0 if correct else 0.0

    qids.append(qid)
    categories.append(q["category"])
    c1_scores.append(score(c1_pred))
    c3_scores.append(score(c3_pred))
    c4_scores.append(score(c4_pred))
    c4g_scores.append(score(c4g_pred))

c1_scores = np.array(c1_scores)
c3_scores = np.array(c3_scores)
c4_scores = np.array(c4_scores)
c4g_scores = np.array(c4g_scores)
categories = np.array(categories)
n = len(qids)

print(f"Loaded {n} questions with predictions in all four conditions")
print(f"C1 overall:  {c1_scores.mean():.1%} ({int(c1_scores.sum())}/{n})")
print(f"C3 overall:  {c3_scores.mean():.1%} ({int(c3_scores.sum())}/{n})")
print(f"C4 overall:  {c4_scores.mean():.1%} ({int(c4_scores.sum())}/{n})")
print(f"C4g overall: {c4g_scores.mean():.1%} ({int(c4g_scores.sum())}/{n})")
print()
print(f"C3->C4 delta (assertions only):  {(c4_scores.mean() - c3_scores.mean()):.1%}")
print(f"C4->C4g delta (intent routing):  {(c4g_scores.mean() - c4_scores.mean()):.1%}")
print(f"C3->C4g delta (both):            {(c4g_scores.mean() - c3_scores.mean()):.1%}")
print()

# ── BCa bootstrap ──

def bca_ci(data_func, indices, n_boot=N_BOOT, alpha=ALPHA, rng=None):
    if rng is None:
        rng = np.random.default_rng(SEED)
    from scipy.stats import norm

    n_idx = len(indices)
    theta_hat = data_func(indices)

    boot_thetas = np.empty(n_boot)
    for b in range(n_boot):
        boot_idx = rng.choice(indices, size=n_idx, replace=True)
        boot_thetas[b] = data_func(boot_idx)

    prop_less = np.clip(np.mean(boot_thetas < theta_hat), 1e-10, 1 - 1e-10)
    z0 = norm.ppf(prop_less)

    jack_thetas = np.empty(n_idx)
    for i in range(n_idx):
        jack_idx = np.delete(indices, i)
        jack_thetas[i] = data_func(jack_idx)
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

    return theta_hat, ci_low, ci_high, boot_thetas


# ── Statistic functions ──

def c3_to_c4_delta(idx):
    return c4_scores[idx].mean() - c3_scores[idx].mean()

def c4_to_c4g_delta(idx):
    return c4g_scores[idx].mean() - c4_scores[idx].mean()

def c3_to_c4g_delta(idx):
    return c4g_scores[idx].mean() - c3_scores[idx].mean()

def overall_delta(idx):
    return c4g_scores[idx].mean() - c1_scores[idx].mean()

def c1_to_c3_delta(idx):
    return c3_scores[idx].mean() - c1_scores[idx].mean()

def accuracy_c4(idx):
    return c4_scores[idx].mean()

all_idx = np.arange(n)

# ══════════════════════════════════════════════════════════════
# 1. C4 ABLATION DECOMPOSITION (new)
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("C4 ABLATION DECOMPOSITION")
print("=" * 60)

# C4 accuracy + CI
theta_c4, lo_c4, hi_c4, _ = bca_ci(accuracy_c4, all_idx, rng=np.random.default_rng(SEED+20))
print(f"C4 accuracy: {theta_c4:.1%} [{lo_c4:.1%}, {hi_c4:.1%}]")
print()

# C3→C4 (assertions only, no routing)
theta_34, lo_34, hi_34, boot_34 = bca_ci(c3_to_c4_delta, all_idx, rng=np.random.default_rng(SEED+21))
print(f"C3→C4 delta (assertions only): {theta_34:+.1%} [{lo_34:+.1%}, {hi_34:+.1%}]")

# C4→C4g (intent routing)
theta_4g, lo_4g, hi_4g, boot_4g = bca_ci(c4_to_c4g_delta, all_idx, rng=np.random.default_rng(SEED+22))
print(f"C4→C4g delta (intent routing): {theta_4g:+.1%} [{lo_4g:+.1%}, {hi_4g:+.1%}]")

# C3→C4g (both, for reference)
theta_3g, lo_3g, hi_3g, _ = bca_ci(c3_to_c4g_delta, all_idx, rng=np.random.default_rng(SEED+12))
print(f"C3→C4g delta (both):           {theta_3g:+.1%} [{lo_3g:+.1%}, {hi_3g:+.1%}]")
print()

# ══════════════════════════════════════════════════════════════
# 2. PER-CATEGORY BREAKDOWN (C4 vs C3 vs C4g)
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("PER-CATEGORY: C3 vs C4 vs C4g")
print(f"{'Category':<18} {'n':>4} {'C3':>7} {'C4':>7} {'C4g':>7} {'C3→C4':>8} {'C4→C4g':>8}")
print("-" * 70)

unique_cats = sorted(set(categories))
for cat in unique_cats:
    cat_mask = categories == cat
    cat_idx = np.where(cat_mask)[0]
    n_cat = len(cat_idx)
    c3_acc = c3_scores[cat_idx].mean()
    c4_acc = c4_scores[cat_idx].mean()
    c4g_acc = c4g_scores[cat_idx].mean()
    print(f"{cat:<18} {n_cat:>4} {c3_acc:>6.1%} {c4_acc:>6.1%} {c4g_acc:>6.1%} {c4_acc-c3_acc:>+7.1%} {c4g_acc-c4_acc:>+7.1%}")

print()

# ══════════════════════════════════════════════════════════════
# 3. McNEMAR'S TESTS (C3 vs C4, C4 vs C4g)
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("McNEMAR'S TESTS")
from scipy.stats import chi2 as chi2_dist

def mcnemar(name, scores_a, scores_b):
    b = int(np.sum((scores_a == 1) & (scores_b == 0)))
    c = int(np.sum((scores_a == 0) & (scores_b == 1)))
    both_right = int(np.sum((scores_a == 1) & (scores_b == 1)))
    both_wrong = int(np.sum((scores_a == 0) & (scores_b == 0)))
    print(f"\n  {name}:")
    print(f"    Both right: {both_right}, Both wrong: {both_wrong}")
    print(f"    A right/B wrong: {b}, A wrong/B right: {c}")
    if b + c > 0:
        chi2 = (abs(b - c) - 1) ** 2 / (b + c)
        p_val = 1 - chi2_dist.cdf(chi2, df=1)
        print(f"    McNemar chi2: {chi2:.1f}, p={p_val:.2e}")
        return chi2, p_val
    return 0, 1.0

results_mcnemar = [
    ("C3 vs C4 (assertion effect)", mcnemar("C3 vs C4 (assertion effect)", c3_scores, c4_scores)),
    ("C4 vs C4g (routing effect)", mcnemar("C4 vs C4g (routing effect)", c4_scores, c4g_scores)),
    ("C3 vs C4g (combined)", mcnemar("C3 vs C4g (combined)", c3_scores, c4g_scores)),
    ("C1 vs C4g (overall)", mcnemar("C1 vs C4g (overall)", c1_scores, c4g_scores)),
]

# Benjamini-Hochberg FDR correction
p_vals = np.array([r[1][1] for r in results_mcnemar])
n_tests = len(p_vals)
sorted_idx = np.argsort(p_vals)
bh_adjusted = np.empty(n_tests)
for i, idx in enumerate(sorted_idx):
    bh_adjusted[idx] = min(p_vals[idx] * n_tests / (i + 1), 1.0)
# Enforce monotonicity (adjusted p-values should be non-decreasing in sorted order)
for i in range(n_tests - 2, -1, -1):
    idx = sorted_idx[i]
    idx_next = sorted_idx[i + 1]
    bh_adjusted[idx] = min(bh_adjusted[idx], bh_adjusted[idx_next])

print(f"\n  Benjamini-Hochberg FDR correction ({n_tests} tests):")
for i, (name, (chi2, p)) in enumerate(results_mcnemar):
    sig = "*" if bh_adjusted[i] < 0.05 else ""
    print(f"    {name}: p_raw={p:.2e}, p_BH={bh_adjusted[i]:.2e} {sig}")

print()

# ══════════════════════════════════════════════════════════════
# 4. PATIENT-LEVEL CLUSTER BOOTSTRAP
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("PATIENT-LEVEL CLUSTER BOOTSTRAP CIs")

patient_ids = []
for qid in qids:
    q = questions[qid]
    patient_ids.append(q["mimic_subject_id"])
patient_ids = np.array(patient_ids)
unique_patients = np.unique(patient_ids)
n_patients = len(unique_patients)
patient_to_idx = {pid: np.where(patient_ids == pid)[0] for pid in unique_patients}

print(f"  {n_patients} patients, {n} questions")

def patient_cluster_boot_ci(stat_func, n_boot=N_BOOT, alpha=ALPHA, rng=None):
    if rng is None:
        rng = np.random.default_rng(SEED)
    from scipy.stats import norm

    all_i = np.arange(n)
    theta_hat = stat_func(all_i)

    boot_thetas = np.empty(n_boot)
    for b in range(n_boot):
        sampled_patients = rng.choice(unique_patients, size=n_patients, replace=True)
        boot_question_idx = np.concatenate([patient_to_idx[p] for p in sampled_patients])
        boot_thetas[b] = stat_func(boot_question_idx)

    prop_less = np.clip(np.mean(boot_thetas < theta_hat), 1e-10, 1 - 1e-10)
    z0 = norm.ppf(prop_less)

    jack_thetas = np.empty(n_patients)
    for i, pid in enumerate(unique_patients):
        leave_out = patient_to_idx[pid]
        jack_idx = np.setdiff1d(all_i, leave_out)
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

pt_34, pt_34_lo, pt_34_hi = patient_cluster_boot_ci(c3_to_c4_delta, rng=np.random.default_rng(SEED+200))
print(f"  C3→C4 (patient-level):  {pt_34:+.1%} [{pt_34_lo:+.1%}, {pt_34_hi:+.1%}]")

pt_4g, pt_4g_lo, pt_4g_hi = patient_cluster_boot_ci(c4_to_c4g_delta, rng=np.random.default_rng(SEED+201))
print(f"  C4→C4g (patient-level): {pt_4g:+.1%} [{pt_4g_lo:+.1%}, {pt_4g_hi:+.1%}]")

pt_3g, pt_3g_lo, pt_3g_hi = patient_cluster_boot_ci(c3_to_c4g_delta, rng=np.random.default_rng(SEED+202))
print(f"  C3→C4g (patient-level): {pt_3g:+.1%} [{pt_3g_lo:+.1%}, {pt_3g_hi:+.1%}]")

print()

# ══════════════════════════════════════════════════════════════
# 5. SUMMARY FOR PAPER
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("SUMMARY FOR PAPER")
print("=" * 60)
print(f"C4 accuracy: {theta_c4:.1%} (95% BCa CI: [{lo_c4:.1%}, {hi_c4:.1%}])")
print(f"C3→C4 (assertions only): {theta_34:+.1%} [{lo_34:+.1%}, {hi_34:+.1%}]")
print(f"C4→C4g (intent routing):  {theta_4g:+.1%} [{lo_4g:+.1%}, {hi_4g:+.1%}]")
print(f"C3→C4g (both, reference): {theta_3g:+.1%} [{lo_3g:+.1%}, {hi_3g:+.1%}]")
print()
print("Key finding: Assertions without routing HURT performance.")
print("The C3→C4g gain is entirely from intent routing, not assertions alone.")
print("Assertions only become valuable when paired with routing (C4→C4g).")
