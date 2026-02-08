#!/usr/bin/env python3
"""CLI script to capture and compare API contract snapshots (CTO-5).

Usage:
    # Capture current contract
    python -m scripts.capture_api_contract --version v1.0

    # Capture and compare against a baseline
    python -m scripts.capture_api_contract --version v1.1 \\
        --compare tests/contracts/api_contract_v1.0.json

    # Output as markdown
    python -m scripts.capture_api_contract --version v1.1 \\
        --compare tests/contracts/api_contract_v1.0.json --format markdown

Exit codes:
    0 - Success (no breaking changes)
    1 - Breaking changes detected (CI gating)
    2 - Error during execution
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the backend package is importable when run from repo root
_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))


def main() -> int:
    """Entry point for the contract capture CLI."""
    parser = argparse.ArgumentParser(
        description="Capture and compare API contract snapshots."
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Version label for the snapshot (e.g. v1.0, pr-123).",
    )
    parser.add_argument(
        "--compare",
        type=Path,
        default=None,
        help="Path to a baseline snapshot JSON file to compare against.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        dest="output_format",
        help="Output format for the comparison report (default: json).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to save the snapshot (default: tests/contracts/).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save the snapshot to disk (print only).",
    )

    args = parser.parse_args()

    try:
        from app.main import app
        from app.services.api_contract_service import ApiContractService

        service = ApiContractService(app)

        # Capture current contract
        snapshot = service.capture_contract_snapshot(
            version=args.version,
            app_version=getattr(app, "version", "1.0.0"),
        )

        # Save snapshot
        if not args.no_save:
            saved_path = service.save_snapshot(snapshot, directory=args.output_dir)
            print(f"Snapshot saved to: {saved_path}", file=sys.stderr)
        else:
            print(snapshot.model_dump_json(indent=2))

        # Compare if baseline provided
        if args.compare:
            if not args.compare.exists():
                print(
                    f"Error: baseline file not found: {args.compare}",
                    file=sys.stderr,
                )
                return 2

            baseline = service.load_snapshot(args.compare)
            comparison = service.compare_contracts(baseline, snapshot)

            if args.output_format == "markdown":
                report = service.generate_contract_report(comparison)
                print(report)
            else:
                print(comparison.model_dump_json(indent=2))

            if comparison.has_breaking_changes:
                print(
                    f"\nFAIL: {len(comparison.breaking_changes)} breaking "
                    f"change(s) detected.",
                    file=sys.stderr,
                )
                return 1

            print(
                f"\nPASS: No breaking changes. "
                f"{len(comparison.non_breaking_changes)} non-breaking change(s).",
                file=sys.stderr,
            )

        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
