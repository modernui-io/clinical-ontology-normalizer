#!/usr/bin/env python3
"""Convert ClinicalBench JSON data to Parquet for HuggingFace hosting.

Produces a staging/ directory with Parquet files organized by HF config:
  staging/
  ├── questions/test/data.parquet
  ├── predictions_opus/test/data.parquet
  ├── predictions_medgemma/test/data.parquet
  ├── predictions_gptoss/test/data.parquet
  ├── predictions_qwen35/test/data.parquet
  └── llm_judge/test/data.parquet

Usage:
    cd epikg-benchmark
    uv run python scripts/convert_to_hf.py
"""

import json
import os
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
STAGING = ROOT / "staging"

# --- Model directory -> HF config name ---
MODEL_CONFIGS = {
    "opus": "predictions_opus",
    "medgemma": "predictions_medgemma",
    "gptoss": "predictions_gptoss",
    "qwen35": "predictions_qwen35",
}

# Canonical model names (normalize variants)
MODEL_NAME_MAP = {
    "claude-opus-4-20250514": "claude-opus-4.6",
    "claude-opus-4-6": "claude-opus-4.6",
    "medgemma-27b": "medgemma-27b",
    "gpt-oss-20b": "gpt-oss-20b",
    "qwen3.5-direct (qwen3.5:35b weights, Q4_K_M)": "qwen3.5-35b",
}


def convert_questions():
    """Convert questions.json -> questions/test/data.parquet."""
    src = ROOT / "clinicalbench" / "questions.json"
    with open(src) as f:
        data = json.load(f)

    rows = []
    for q in data["questions"]:
        rows.append({
            "question_id": q["question_id"],
            "task": q["task"],
            "category": q["category"],
            "question": q["question"],
            "expected_answer": q["expected_answer"],
            "mimic_subject_id": q["mimic_subject_id"],
            "mimic_hadm_id": q.get("mimic_hadm_id"),
            "difficulty": q.get("difficulty", ""),
            "assertion_label": q.get("assertion_label", ""),
            "domain": q.get("domain", ""),
            "section": q.get("section", ""),
        })

    df = pd.DataFrame(rows)

    # Enforce types
    df["mimic_subject_id"] = df["mimic_subject_id"].astype("int64")
    df["mimic_hadm_id"] = df["mimic_hadm_id"].astype("Int64")  # nullable int

    out = STAGING / "questions" / "test"
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "data.parquet", index=False)
    print(f"  questions: {len(df)} rows -> {out / 'data.parquet'}")
    return df


def _load_standard_predictions(filepath: Path) -> list[dict]:
    """Load predictions from a standard-format JSON (has 'predictions' key)."""
    with open(filepath) as f:
        data = json.load(f)

    model_raw = data["model"]
    model = MODEL_NAME_MAP.get(model_raw, model_raw)
    condition = data["condition"]

    rows = []
    for p in data["predictions"]:
        rows.append({
            "question_id": p["question_id"],
            "model": model,
            "condition": condition,
            "predicted_answer": p.get("predicted_answer", ""),
            "correct": p["correct"],
            "score": float(p["score"]),
            "category": p["category"],
            "latency_ms": p.get("latency_ms"),
        })
    return rows


def _load_c7_predictions(filepath: Path) -> list[dict]:
    """Load predictions from C7 deterministic format (has 'per_question' key)."""
    with open(filepath) as f:
        data = json.load(f)

    rows = []
    for p in data["per_question"]:
        rows.append({
            "question_id": p["question_id"],
            "model": "deterministic",
            "condition": "C7_deterministic",
            "predicted_answer": "",
            "correct": p["correct"],
            "score": float(p["score"]),
            "category": p["category"],
            "latency_ms": None,
        })
    return rows


def convert_predictions(model_dir: str, config_name: str):
    """Convert all prediction files for a model into a single stacked Parquet."""
    results_dir = ROOT / "results" / model_dir
    if not results_dir.exists():
        print(f"  {config_name}: SKIPPED (directory not found)")
        return None

    all_rows = []
    for fpath in sorted(results_dir.glob("*.json")):
        if fpath.name == "C7_deterministic.json":
            all_rows.extend(_load_c7_predictions(fpath))
        else:
            all_rows.extend(_load_standard_predictions(fpath))

    if not all_rows:
        print(f"  {config_name}: SKIPPED (no data)")
        return None

    df = pd.DataFrame(all_rows)
    df["correct"] = df["correct"].astype(bool)
    df["score"] = df["score"].astype("float64")
    df["latency_ms"] = df["latency_ms"].astype("Float64")  # nullable float

    out = STAGING / config_name / "test"
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "data.parquet", index=False)
    print(f"  {config_name}: {len(df)} rows ({df['condition'].nunique()} conditions) -> {out / 'data.parquet'}")
    return df


def convert_llm_judge():
    """Convert llm_judge_checkpoint.jsonl -> llm_judge/test/data.parquet."""
    src = ROOT / "results" / "llm_judge" / "llm_judge_checkpoint.jsonl"
    if not src.exists():
        print("  llm_judge: SKIPPED (file not found)")
        return None

    rows = []
    with open(src) as f:
        for line in f:
            rec = json.loads(line)
            rows.append({
                "question_id": rec["question_id"],
                "condition": rec["condition"],
                "judge_score": float(rec["judge_score"]),
                "judge_reason": rec["judge_reason"],
            })

    df = pd.DataFrame(rows)
    df["judge_score"] = df["judge_score"].astype("float64")

    out = STAGING / "llm_judge" / "test"
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "data.parquet", index=False)
    print(f"  llm_judge: {len(df)} rows -> {out / 'data.parquet'}")
    return df


def main():
    print(f"Source: {ROOT}")
    print(f"Output: {STAGING}")
    print()

    # Clean staging
    if STAGING.exists():
        import shutil
        shutil.rmtree(STAGING)

    print("Converting...")
    q_df = convert_questions()

    pred_dfs = {}
    for model_dir, config_name in MODEL_CONFIGS.items():
        df = convert_predictions(model_dir, config_name)
        if df is not None:
            pred_dfs[config_name] = df

    judge_df = convert_llm_judge()

    # Validation
    print("\nValidation:")
    assert len(q_df) == 400, f"Expected 400 questions, got {len(q_df)}"
    print(f"  questions: {len(q_df)} rows OK")

    for name, df in pred_dfs.items():
        # Each condition should have 400 predictions (except medgemma C4g which has 399)
        for cond, grp in df.groupby("condition"):
            n = len(grp)
            if n not in (399, 400):
                print(f"  WARNING: {name}/{cond} has {n} rows (expected 400)")
            else:
                print(f"  {name}/{cond}: {n} rows OK")

    if judge_df is not None:
        assert len(judge_df) == 800, f"Expected 800 judge rows, got {len(judge_df)}"
        print(f"  llm_judge: {len(judge_df)} rows OK")

    print("\nDone! Staging directory ready for upload.")


if __name__ == "__main__":
    main()
