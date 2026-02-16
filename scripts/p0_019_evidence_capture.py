#!/usr/bin/env python3
"""P0-019 evidence execution harness for OpenEHR dry-run + reconciliation + rollback.

Usage:
  export X_API_KEY=...
  python3 scripts/p0_019_evidence_capture.py \
    --base-url http://localhost:8000/api/v1 \
    --out-dir docs/evidence/p0-019
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import argparse
from datetime import datetime, timezone, timedelta
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "backend"))
from tests.fixtures.openehr_dry_run_compositions import ALL_COMPOSITIONS  # type: ignore


REQUIRED_COUNTERS = ("conditions", "medications", "measurements", "procedures", "allergies")


def to_iso(ts: datetime) -> str:
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now() -> datetime:
    return datetime.now(timezone.utc)


def build_headers(api_key: Optional[str]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def request_json(
    method: str,
    base_url: str,
    path: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    try:
        response = requests.request(method, url, headers=headers, json=payload, timeout=180)
    except requests.RequestException as exc:
        return {
            "status": 0,
            "error": str(exc),
            "body": "",
        }

    try:
        response.raise_for_status()
        return {"status": response.status_code, "data": response.json()}
    except requests.HTTPError as exc:
        return {
            "status": response.status_code,
            "error": str(exc),
            "body": response.text[:1500],
        }
    except ValueError:
        return {"status": response.status_code, "error": "invalid json response", "body": response.text[:1500]}


def compare_counts(actual: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, bool]:
    return {field: int(actual.get(field, 0)) == int(expected.get(field, 0)) for field in REQUIRED_COUNTERS}


def pass_status(results: Dict[str, bool]) -> bool:
    return all(results.values())


@dataclass
class StepResult:
    step: str
    scenario: str
    patient_id: str
    status_code: int
    status: str
    duration_seconds: float
    payload: Dict[str, Any]
    response: Dict[str, Any]
    checks: Dict[str, bool]


def run_dry_run(
    base_url: str,
    headers: Dict[str, str],
    scenario: str,
    composition: Dict[str, Any],
    expected: Dict[str, Any],
    run_id: str,
) -> Dict[str, Any]:
    patient_id = f"p0-019-dryrun-{scenario}-{run_id}"
    start = now()
    payload = {
        "composition": composition,
        "patient_id": patient_id,
        "source_metadata": {
            "scenario": scenario,
            "run_id": run_id,
            "source_system": "meditech",
            "site_id": "ops-staging",
        },
    }
    resp = request_json("POST", base_url, "/openehr/dry-run", headers, payload)
    elapsed = (now() - start).total_seconds()

    body = resp.get("data", {})
    checks: Dict[str, bool] = {
        "http_200": resp["status"] == 200 and "error" not in resp,
        "success_flag": bool(body.get("success")) if isinstance(body, dict) else False,
        "counts_match": pass_status(compare_counts(body if isinstance(body, dict) else {}, expected)),
        "response_has_expected_fields": all(f in (body.keys() if isinstance(body, dict) else {}) for f in [
            "conditions",
            "medications",
            "measurements",
            "procedures",
            "allergies",
            "nodes",
            "edges",
            "skipped",
        ]),
    }

    return asdict(
        StepResult(
            step="dry-run",
            scenario=scenario,
            patient_id=patient_id,
            status_code=resp["status"],
            status="PASS" if all(checks.values()) else "FAIL",
            duration_seconds=round(elapsed, 3),
            payload=payload,
            response=resp,
            checks=checks,
        )
    )


def run_roundtrip_and_rollback(
    base_url: str,
    headers: Dict[str, str],
    scenario: str,
    composition: Dict[str, Any],
    expected: Dict[str, Any],
    run_id: str,
) -> Dict[str, Any]:
    patient_id = f"p0-019-trip-{scenario}-{run_id}"
    composition_start = now()
    import_payload = {
        "composition": composition,
        "patient_id": patient_id,
        "source_metadata": {
            "scenario": scenario,
            "run_id": run_id,
            "source_system": "meditech",
            "site_id": "ops-staging",
        },
    }
    import_resp = request_json("POST", base_url, "/openehr/composition", headers, import_payload)
    import_done = now()

    import_body = import_resp.get("data", {})
    import_checks = {
        "http_200": import_resp["status"] == 200 and "error" not in import_resp,
        "success_flag": bool(import_body.get("success")) if isinstance(import_body, dict) else False,
        "counts_match": pass_status(compare_counts(import_body if isinstance(import_body, dict) else {}, expected)),
    }
    import_step = StepResult(
        step="composition-import",
        scenario=scenario,
        patient_id=patient_id,
        status_code=import_resp["status"],
        status="PASS" if all(import_checks.values()) else "FAIL",
        duration_seconds=round((import_done - composition_start).total_seconds(), 3),
        payload=import_payload,
        response=import_resp,
        checks=import_checks,
    )

    reconcile_payload = {}
    reconcile_start = now()
    reconcile_resp = request_json(
        "POST",
        base_url,
        f"/openehr/reconcile/{patient_id}",
        headers,
        reconcile_payload,
    )
    reconcile_done = now()
    reconcile_body = reconcile_resp.get("data", {})
    reconcile_checks = {
        "http_200": reconcile_resp["status"] == 200 and "error" not in reconcile_resp,
        "match": bool(reconcile_body.get("match")) if isinstance(reconcile_body, dict) else False,
        "fingerprint_present": isinstance(reconcile_body, dict) and bool(reconcile_body.get("import_fingerprint"))
        and bool(reconcile_body.get("export_reimport_fingerprint")),
        "fingerprint_equal": False,
    }
    if isinstance(reconcile_body, dict):
        reconcile_checks["fingerprint_equal"] = (
            reconcile_body.get("import_fingerprint", "")
            == reconcile_body.get("export_reimport_fingerprint", "")
        )

    reconcile_step = StepResult(
        step="reconcile",
        scenario=scenario,
        patient_id=patient_id,
        status_code=reconcile_resp["status"],
        status="PASS" if all(reconcile_checks.values()) else "FAIL",
        duration_seconds=round((reconcile_done - reconcile_start).total_seconds(), 3),
        payload=reconcile_payload,
        response=reconcile_resp,
        checks=reconcile_checks,
    )

    batch_start = to_iso(composition_start - timedelta(minutes=1))
    batch_end = to_iso(reconcile_done + timedelta(minutes=3))
    rollback_payload = {
        "patient_id": patient_id,
        "batch_start": batch_start,
        "batch_end": batch_end,
    }
    rollback_start = now()
    rollback_resp = request_json(
        "POST",
        base_url,
        "/openehr/rollback",
        headers,
        rollback_payload,
    )
    rollback_done = now()
    rollback_body = rollback_resp.get("data", {})
    rollback_checks = {
        "http_200": rollback_resp["status"] == 200 and "error" not in rollback_resp,
        "rollback_success": bool(rollback_body.get("success")) if isinstance(rollback_body, dict) else False,
    }

    rollback_step = StepResult(
        step="rollback",
        scenario=scenario,
        patient_id=patient_id,
        status_code=rollback_resp["status"],
        status="PASS" if all(rollback_checks.values()) else "FAIL",
        duration_seconds=round((rollback_done - rollback_start).total_seconds(), 3),
        payload=rollback_payload,
        response=rollback_resp,
        checks=rollback_checks,
    )

    verify_start = now()
    verify_resp = request_json(
        "POST",
        base_url,
        f"/openehr/reconcile/{patient_id}",
        headers,
        {},
    )
    verify_done = now()
    verify_body = verify_resp.get("data", {})
    verify_checks = {
        "http_200_or_404": verify_resp["status"] == 200,
        "residual_gone": False,
    }
    if isinstance(verify_body, dict):
        mismatches = verify_body.get("mismatches", [])
        verify_checks["residual_gone"] = (
            verify_body.get("match") is False
            and isinstance(mismatches, list)
            and any("No facts found for patient" in m for m in mismatches)
        )

    verify_step = StepResult(
        step="reconcile-after-rollback",
        scenario=scenario,
        patient_id=patient_id,
        status_code=verify_resp["status"],
        status="PASS" if all(verify_checks.values()) else "FAIL",
        duration_seconds=round((verify_done - verify_start).total_seconds(), 3),
        payload={},
        response=verify_resp,
        checks=verify_checks,
    )

    return {
        "scenario": scenario,
        "patient_id": patient_id,
        "composition_import": asdict(import_step),
        "reconcile": asdict(reconcile_step),
        "rollback": asdict(rollback_step),
        "reconcile_after_rollback": asdict(verify_step),
        "batch_window": {"start": batch_start, "end": batch_end},
    }


def write_markdown_report(path: Path, run_id: str, metadata: Dict[str, Any], dry_runs: list[Dict[str, Any]], trips: list[Dict[str, Any]]) -> None:
    lines = [
        "# P0-019 Evidence Packet",
        "",
        f"- Run ID: `{run_id}`",
        f"- Executed: `{metadata['started_at']}`",
        f"- Base URL: `{metadata['base_url']}`",
        f"- Operator: `{metadata['operator']}`",
        "",
        "## Summary",
        "",
        f"- Dry-run scenarios: `{len(dry_runs)}`",
        f"- Round-trip + rollback scenarios: `{len(trips)}`",
        "",
        "## Dry-run Results",
        "",
        "| Scenario | Patient ID | Status | HTTP | Duration (s) | Success | Counts Match |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for row in dry_runs:
        checks = row["checks"]
        line = (
            f"| {row['scenario']} | {row['patient_id']} | {row['status']} | "
            f"{row['status_code']} | {row['duration_seconds']} | {checks.get('success_flag')} | "
            f"{checks.get('counts_match')} |"
        )
        lines.append(line)

    lines.extend(["", "## Round-trip + Rollback Results", "", "| Scenario | Status | Patient ID | Import | Reconcile | Rollback | Residual Verify |", "| --- | --- | --- | --- | --- | --- | --- |"])
    for row in trips:
        all_pass = (
            row["composition_import"]["status"] == "PASS"
            and row["reconcile"]["status"] == "PASS"
            and row["rollback"]["status"] == "PASS"
            and row["reconcile_after_rollback"]["status"] == "PASS"
        )
        lines.append(
            f"| {row['scenario']} | {'PASS' if all_pass else 'FAIL'} | {row['patient_id']} | "
            f"{row['composition_import']['status']} | {row['reconcile']['status']} | {row['rollback']['status']} | {row['reconcile_after_rollback']['status']} |"
        )

    with path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P0-019 evidence capture for OpenEHR workflows")
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1")
    parser.add_argument(
        "--api-key",
        default=None,
        help="Optional API key for X-API-Key header",
    )
    parser.add_argument(
        "--out-dir",
        default="docs/evidence/p0-019",
        help="Directory to store evidence JSON/Markdown artifacts",
    )
    parser.add_argument(
        "--scenarios",
        nargs="*",
        default=list(ALL_COMPOSITIONS.keys()),
        help="Subset of scenario keys to execute",
    )
    parser.add_argument(
        "--operator",
        default="ops-exec",
        help="Operator name/email to record in evidence package",
    )
    parser.add_argument(
        "--skip-rollback",
        action="store_true",
        help="Skip /openehr/rollback and residual verify",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected = [key for key in args.scenarios if key in ALL_COMPOSITIONS]
    if not selected:
        print("No valid scenarios selected.")
        return 2

    run_id = now().strftime("%Y%m%dT%H%M%SZ")
    headers = build_headers(args.api_key or "")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = to_iso(now())

    dry_runs = []
    trip_runs = []

    for key in selected:
        builder, expected = ALL_COMPOSITIONS[key]
        comp = builder()
        dry_runs.append(
            run_dry_run(
                args.base_url,
                headers,
                key,
                comp,
                expected,
                run_id,
            )
        )
        if not args.skip_rollback:
            trip_runs.append(
                run_roundtrip_and_rollback(
                    args.base_url,
                    headers,
                    key,
                    comp,
                    expected,
                    run_id,
                )
            )

    metadata = {
        "run_id": run_id,
        "started_at": started,
        "base_url": args.base_url,
        "operator": args.operator,
        "skip_rollback": args.skip_rollback,
        "scenarios": selected,
    }

    artifact_base = out_dir / f"p0-019-evidence-{run_id}"
    json_path = artifact_base.with_suffix(".json")
    md_path = artifact_base.with_suffix(".md")

    payload = {
        "metadata": metadata,
        "dry_runs": dry_runs,
        "round_trip_runs": trip_runs,
    }
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    write_markdown_report(md_path, run_id, metadata, dry_runs, trip_runs)

    # Print summary to stdout
    total_dry = len(dry_runs)
    pass_dry = sum(1 for r in dry_runs if r["status"] == "PASS")
    total_trip = len(trip_runs)
    pass_trip = sum(
        1
        for r in trip_runs
        if r["composition_import"]["status"] == "PASS"
        and r["reconcile"]["status"] == "PASS"
        and r["rollback"]["status"] == "PASS"
        and r["reconcile_after_rollback"]["status"] == "PASS"
    )

    print(f"[p0-019] evidence saved: {json_path} and {md_path}")
    print(f"[p0-019] dry-runs: {pass_dry}/{total_dry} PASS")
    if trip_runs:
        print(f"[p0-019] round-trips: {pass_trip}/{total_trip} PASS")
    overall = pass_dry == total_dry and pass_trip == total_trip
    print(f"[p0-019] OVERALL: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
