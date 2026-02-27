#!/usr/bin/env python3
"""Export EpiKG benchmark data for public reproducibility package.

Strips proprietary fields (source_fact_id, clinical_context, confidence)
and exports only what's needed for independent verification:
- Questions with MIMIC-IV references (requires PhysioNet access to verify)
- Gold answers with scoring keywords
- Raw model predictions per condition (with predicted_answer text for re-scoring)
- Checksums for integrity verification
"""

import hashlib
import json
import os

BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
RESULTS = os.path.join(BACKEND, "data", "benchmarks", "results")
OPUS_DIR = os.path.join(RESULTS, "opus_compare")
MAIN_CP = os.path.join(RESULTS, "clinicalbench_checkpoint.jsonl")
OUT = os.path.dirname(__file__)


def load_questions(task_file: str) -> list[dict]:
    with open(os.path.join(BACKEND, "data", "benchmarks", task_file)) as f:
        return json.load(f)["questions"]


def strip_question(q: dict) -> dict:
    """Keep only fields needed for reproducibility. Strip proprietary context."""
    return {
        "question_id": q["question_id"],
        "task": q["task"],
        "category": q.get("subtype", "unknown"),
        "question": q["question"],
        "expected_answer": q["expected_answer"],
        "mimic_subject_id": q["mimic_subject_id"],
        "mimic_hadm_id": q.get("mimic_hadm_id"),
        "difficulty": q.get("difficulty"),
        "assertion_label": q.get("metadata", {}).get("assertion"),
        "domain": q.get("metadata", {}).get("domain"),
        "section": q.get("metadata", {}).get("section"),
    }


def export_clinicalbench():
    """Export ClinicalBench questions (Task A + Task B, 400 total)."""
    questions = []
    for task_file in ["task_a.json", "task_b.json"]:
        path = os.path.join(BACKEND, "data", "benchmarks", task_file)
        if os.path.exists(path):
            questions.extend(load_questions(task_file))

    qids_path = os.path.join(RESULTS, "all_400_qids.json")
    if os.path.exists(qids_path):
        with open(qids_path) as f:
            valid_qids = set(json.load(f))
        questions = [q for q in questions if q["question_id"] in valid_qids]

    stripped = [strip_question(q) for q in questions]
    stripped.sort(key=lambda x: x["question_id"])

    out_path = os.path.join(OUT, "clinicalbench", "questions.json")
    with open(out_path, "w") as f:
        json.dump({"benchmark": "ClinicalBench", "version": "1.0", "n_questions": len(stripped), "questions": stripped}, f, indent=2)
    print(f"ClinicalBench: {len(stripped)} questions -> {out_path}")
    return stripped


def extract_from_checkpoint(checkpoint_path: str, condition: str) -> list[dict]:
    """Extract predictions with answer text from a JSONL checkpoint file."""
    predictions = []
    seen = set()
    with open(checkpoint_path) as f:
        for line in f:
            entry = json.loads(line)
            if entry.get("condition") != condition:
                continue
            qid = entry["question_id"]
            if qid in seen:
                continue
            seen.add(qid)
            predictions.append({
                "question_id": qid,
                "predicted_answer": entry.get("predicted_answer", ""),
                "correct": entry.get("correct", False),
                "score": entry.get("score", 0.0),
                "category": entry.get("category", ""),
                "latency_ms": entry.get("latency_ms"),
            })
    return sorted(predictions, key=lambda x: x["question_id"])


def extract_prescored(result_path: str) -> list[dict]:
    """Extract pre-scored results (no answer text) from a result JSON file."""
    with open(result_path) as f:
        data = json.load(f)
    predictions = []
    pq = data.get("per_question", [])
    if isinstance(pq, list):
        for item in pq:
            predictions.append({
                "question_id": item["question_id"],
                "predicted_answer": item.get("predicted_answer", item.get("answer", "")),
                "correct": item.get("correct", False),
                "score": item.get("score", 0.0),
                "category": item.get("category", ""),
            })
    return sorted(predictions, key=lambda x: x["question_id"])


def write_predictions(predictions: list[dict], model: str, condition: str, out_path: str):
    """Write predictions to JSON file."""
    with open(out_path, "w") as f:
        json.dump({
            "model": model,
            "condition": condition,
            "n_predictions": len(predictions),
            "predictions": predictions,
        }, f, indent=2)
    n_with_answer = sum(1 for p in predictions if p.get("predicted_answer"))
    print(f"  {condition}: {len(predictions)} predictions ({n_with_answer} with answer text) -> {out_path}")


def export_opus_results():
    """Export Opus predictions from checkpoint files (which have answer text)."""
    print("\nOpus 4.6:")
    opus_sources = {
        "C1_llm_alone": (os.path.join(OPUS_DIR, "compare_opus_C1_llm_alone_checkpoint.jsonl"), "C1_llm_alone"),
        "C4_epistemic_kg_rag": (MAIN_CP, "C4_epistemic_kg_rag"),
        "C4g_intent_aware": (os.path.join(OPUS_DIR, "compare_opus_checkpoint.jsonl"), "C4g_intent_aware"),
        "C6_long_context": (os.path.join(OPUS_DIR, "compare_opus_C6_long_context_checkpoint.jsonl"), "C6_long_context"),
    }

    for cond_id, (cp_path, cp_condition) in opus_sources.items():
        if not os.path.exists(cp_path):
            print(f"  {cond_id}: SKIP (checkpoint not found)")
            continue
        predictions = extract_from_checkpoint(cp_path, cp_condition)
        if predictions:
            out_path = os.path.join(OUT, "results", "opus", f"{cond_id}.json")
            write_predictions(predictions, "claude-opus-4-20250514", cond_id, out_path)


def export_medgemma_results():
    """Export MedGemma predictions."""
    print("\nMedGemma 27B:")

    # MedGemma C1: from main checkpoint (59.8%, 400 entries with answers)
    predictions = extract_from_checkpoint(MAIN_CP, "C1_llm_alone")
    if predictions:
        out_path = os.path.join(OUT, "results", "medgemma", "C1_llm_alone.json")
        write_predictions(predictions, "gemma3:27b (4-bit GGUF)", "C1_llm_alone", out_path)

    # MedGemma C4g: from main checkpoint (399 entries, 398 with answer text)
    predictions = extract_from_checkpoint(MAIN_CP, "C4g_intent_aware")
    if predictions:
        out_path = os.path.join(OUT, "results", "medgemma", "C4g_intent_aware.json")
        write_predictions(predictions, "gemma3:27b (4-bit GGUF)", "C4g_intent_aware", out_path)


def generate_checksums():
    """SHA-256 checksums for all exported files."""
    checksums = {}
    for root, dirs, files in os.walk(OUT):
        for fname in sorted(files):
            if fname.endswith((".json", ".py")) and fname != "export_benchmark.py":
                fpath = os.path.join(root, fname)
                relpath = os.path.relpath(fpath, OUT)
                with open(fpath, "rb") as f:
                    checksums[relpath] = hashlib.sha256(f.read()).hexdigest()

    out_path = os.path.join(OUT, "checksums.sha256")
    with open(out_path, "w") as f:
        for path, sha in sorted(checksums.items()):
            f.write(f"{sha}  {path}\n")
    print(f"\nChecksums: {len(checksums)} files -> {out_path}")


if __name__ == "__main__":
    print("=" * 60)
    print("EpiKG Benchmark Export")
    print("=" * 60)
    export_clinicalbench()
    export_opus_results()
    export_medgemma_results()
    generate_checksums()
    print("\nDone. Review exports before publishing.")
