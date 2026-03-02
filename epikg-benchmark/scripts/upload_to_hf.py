#!/usr/bin/env python3
"""Upload ClinicalBench staging data + supplementary files to HuggingFace.

Usage:
    cd epikg-benchmark
    uv run python scripts/upload_to_hf.py
"""

from pathlib import Path
from huggingface_hub import HfApi

REPO_ID = "alexstinard/epikg-clinicalbench"
ROOT = Path(__file__).resolve().parent.parent
STAGING = ROOT / "staging"

api = HfApi()

# 1. Upload the dataset card as README.md
print("Uploading dataset card (README.md)...")
api.upload_file(
    path_or_fileobj=str(ROOT / "hf_dataset_card.md"),
    path_in_repo="README.md",
    repo_id=REPO_ID,
    repo_type="dataset",
)

# 2. Upload all Parquet files from staging/
print("Uploading Parquet files...")
api.upload_folder(
    folder_path=str(STAGING),
    repo_id=REPO_ID,
    repo_type="dataset",
)

# 3. Upload supplementary files
supplementary = [
    ("clinicalbench/evaluator.py", "evaluator.py"),
    ("bootstrap_ci.py", "bootstrap_ci.py"),
    ("bootstrap_ci_v2.py", "bootstrap_ci_v2.py"),
    ("checksums.sha256", "checksums.sha256"),
]

print("Uploading supplementary files...")
for local_path, repo_path in supplementary:
    full_path = ROOT / local_path
    if full_path.exists():
        api.upload_file(
            path_or_fileobj=str(full_path),
            path_in_repo=repo_path,
            repo_id=REPO_ID,
            repo_type="dataset",
        )
        print(f"  {repo_path} OK")
    else:
        print(f"  {repo_path} SKIPPED (not found: {full_path})")

print(f"\nDone! Dataset available at: https://huggingface.co/datasets/{REPO_ID}")
