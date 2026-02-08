#!/usr/bin/env python3
"""CLI script to generate a Technical Debt Report.

Scans the backend codebase for technical debt indicators and outputs
a markdown report.  Designed to be run locally or in CI to track
debt trends over time.

Usage:
    # From the backend/ directory
    python -m scripts.tech_debt_report

    # With custom root path
    python -m scripts.tech_debt_report --root /path/to/source

    # Output to file
    python -m scripts.tech_debt_report --output debt_report.md

    # JSON output for CI integration
    python -m scripts.tech_debt_report --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add the backend directory to the Python path so we can import app modules
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.tech_debt_scanner import TechDebtScanner  # noqa: E402


def main() -> int:
    """Run the technical debt scan and output results."""
    parser = argparse.ArgumentParser(
        description="Scan Python source files for technical debt indicators.",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=str(backend_dir / "app"),
        help="Root directory to scan (default: backend/app/)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json", "summary"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--max-function-lines",
        type=int,
        default=50,
        help="Maximum lines per function before flagging (default: 50)",
    )
    parser.add_argument(
        "--max-file-lines",
        type=int,
        default=500,
        help="Maximum lines per file before flagging (default: 500)",
    )
    parser.add_argument(
        "--fail-above",
        type=float,
        default=None,
        help="Exit with code 1 if total debt score exceeds this value (for CI gates)",
    )
    parser.add_argument(
        "--exclude-dirs",
        type=str,
        nargs="*",
        default=None,
        help="Additional directories to exclude from scanning",
    )

    args = parser.parse_args()

    # Build scanner configuration
    exclude_dirs = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "migrations",
        "alembic",
    }
    if args.exclude_dirs:
        exclude_dirs.update(args.exclude_dirs)

    scanner = TechDebtScanner(
        root_path=args.root,
        exclude_dirs=exclude_dirs,
        max_function_lines=args.max_function_lines,
        max_file_lines=args.max_file_lines,
    )

    # Run the scan
    report = scanner.scan()

    # Format output
    if args.format == "markdown":
        output = report.to_markdown()
    elif args.format == "json":
        output = json.dumps(report.to_dict(), indent=2)
    elif args.format == "summary":
        output = _format_summary(report)
    else:
        output = report.to_markdown()

    # Write output
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output, encoding="utf-8")
        print(f"Report written to {output_path}")
    else:
        print(output)

    # CI gate: fail if debt score exceeds threshold
    if args.fail_above is not None and report.total_debt_score > args.fail_above:
        print(
            f"\nCI GATE FAILED: Debt score {report.total_debt_score} "
            f"exceeds threshold {args.fail_above}",
            file=sys.stderr,
        )
        return 1

    return 0


def _format_summary(report) -> str:
    """Format a concise summary for terminal output."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  TECHNICAL DEBT SCAN SUMMARY")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Files scanned:     {report.total_files_scanned}")
    lines.append(f"  Files with debt:   {report.files_with_debt}")
    lines.append(f"  Total debt items:  {report.total_items}")
    lines.append(f"  Total debt score:  {report.total_debt_score}")
    lines.append(f"  Lines of code:     {report.total_lines:,}")
    lines.append("")

    by_sev = report.items_by_severity()
    lines.append("  By Severity:")
    for sev_name, count in by_sev.items():
        if count > 0:
            lines.append(f"    {sev_name:>10}: {count}")
    lines.append("")

    by_cat = report.items_by_category()
    lines.append("  By Category:")
    for cat_name, count in by_cat.items():
        if count > 0:
            lines.append(f"    {cat_name:>20}: {count}")
    lines.append("")

    top_files = report.top_files_by_score(10)
    if top_files:
        lines.append("  Top 10 Files by Debt Score:")
        for fr in top_files:
            lines.append(f"    {fr.debt_score:>6.1f}  {fr.file_path}")
    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
