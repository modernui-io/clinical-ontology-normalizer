#!/usr/bin/env python3
"""API endpoint inventory builder (CTO-7).

Scans all API router files to catalog every endpoint with metadata:
method, path, function name, file, response model, auth requirement,
and maturity tier.

Usage:
    python backend/scripts/endpoint_inventory.py
    python backend/scripts/endpoint_inventory.py --format markdown
    python backend/scripts/endpoint_inventory.py --format csv
    python backend/scripts/endpoint_inventory.py --format json
    python backend/scripts/endpoint_inventory.py --format all       # default
    python backend/scripts/endpoint_inventory.py --out endpoints.json --format json
"""

from __future__ import annotations

import argparse
import ast
import csv
import io
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Maturity tier detection keywords
# ---------------------------------------------------------------------------

TIER_KEYWORDS: dict[str, list[str]] = {
    "Production": [
        "document", "nlp", "omop", "fact", "drug_safety", "billing",
        "coding", "calculator", "icd10", "cpt", "hcc", "health",
        "auth", "audit", "patient", "error",
    ],
    "Pilot": [
        "graph", "kg", "rag", "fhir", "smart", "cds", "agent",
        "cohort", "guideline", "phenotype", "trial", "clinical_agent",
        "differential", "timeline", "risk", "prediction", "quality",
        "reconciliation", "notification", "dashboard", "search",
        "semantic", "llm", "assistant", "feedback", "data_quality",
        "data_completeness", "data_consistency", "lab_reference",
        "med_reconciliation", "pipeline", "export", "etl",
        "metriport", "cdisc", "terminology", "vocabulary",
        "valueset", "visualization", "lineage", "streaming", "sse",
    ],
    "Scaffold": [
        "tefca", "federated", "voice", "llm_finetuning",
        "model_registry", "synthetic", "x12", "websocket",
    ],
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EndpointInfo:
    method: str
    path: str
    function_name: str
    file: str
    response_model: str
    auth_required: bool
    maturity_tier: str
    tags: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# AST-based endpoint extraction
# ---------------------------------------------------------------------------

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def _get_string_value(node: ast.expr) -> str | None:
    """Extract a string value from an AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _get_keyword_value(keywords: list[ast.keyword], name: str) -> str | None:
    """Extract a keyword argument string value from decorator keywords."""
    for kw in keywords:
        if kw.arg == name:
            val = _get_string_value(kw.value)
            if val is not None:
                return val
            # Handle Name references (e.g., response_model=SomeModel)
            if isinstance(kw.value, ast.Name):
                return kw.value.id
            if isinstance(kw.value, ast.Attribute):
                return f"{_attr_chain(kw.value)}"
    return None


def _attr_chain(node: ast.Attribute) -> str:
    """Reconstruct a dotted attribute chain."""
    parts: list[str] = [node.attr]
    current = node.value
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _has_auth_dependency(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function has auth-related dependencies in its signature."""
    auth_indicators = [
        "current_user", "get_current_user", "get_current_active_user",
        "require_admin", "require_role", "CurrentUser",
        "PermissionChecker", "RoleChecker",
    ]
    source_repr = ast.dump(func_node)
    return any(indicator in source_repr for indicator in auth_indicators)


def _detect_maturity_tier(file_stem: str) -> str:
    """Detect the maturity tier based on filename."""
    for tier, keywords in TIER_KEYWORDS.items():
        for keyword in keywords:
            if keyword in file_stem:
                return tier
    return "Pilot"  # Default tier


def extract_router_prefix(source: str) -> str:
    """Extract the router prefix from a file's source code.

    Looks for patterns like:
        router = APIRouter(prefix="/foo", ...)
    """
    # Try AST first
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("router",):
                    if isinstance(node.value, ast.Call):
                        prefix = _get_keyword_value(node.value.keywords, "prefix")
                        if prefix:
                            return prefix
    return ""


def extract_router_tags(source: str) -> list[str]:
    """Extract the router tags from source code."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("router",):
                    if isinstance(node.value, ast.Call):
                        for kw in node.value.keywords:
                            if kw.arg == "tags" and isinstance(kw.value, ast.List):
                                return [
                                    _get_string_value(elt) or ""
                                    for elt in kw.value.elts
                                    if _get_string_value(elt)
                                ]
    return []


def extract_endpoints_from_file(filepath: Path) -> list[EndpointInfo]:
    """Extract all endpoint definitions from a single router file."""
    source = filepath.read_text(errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    prefix = extract_router_prefix(source)
    tags = extract_router_tags(source)
    tier = _detect_maturity_tier(filepath.stem)
    endpoints: list[EndpointInfo] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for decorator in node.decorator_list:
            method: str | None = None
            route_path: str = ""
            response_model: str = ""
            summary: str = ""

            # @router.get("/path", ...)
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                attr = decorator.func
                if attr.attr in HTTP_METHODS:
                    method = attr.attr.upper()
                    # First positional arg is the path
                    if decorator.args:
                        route_path = _get_string_value(decorator.args[0]) or ""
                    response_model = _get_keyword_value(decorator.keywords, "response_model") or ""
                    summary = _get_keyword_value(decorator.keywords, "summary") or ""

            # @router.get (no call parens - unlikely but handle)
            elif isinstance(decorator, ast.Attribute):
                if decorator.attr in HTTP_METHODS:
                    method = decorator.attr.upper()

            if method:
                full_path = prefix + route_path
                auth = _has_auth_dependency(node)

                endpoints.append(EndpointInfo(
                    method=method,
                    path=full_path,
                    function_name=node.name,
                    file=str(filepath),
                    response_model=response_model,
                    auth_required=auth,
                    maturity_tier=tier,
                    tags=tags,
                    summary=summary,
                ))

    return endpoints


# ---------------------------------------------------------------------------
# Scanner: walk all API files
# ---------------------------------------------------------------------------

def scan_api_directory(api_dir: Path) -> list[EndpointInfo]:
    """Scan all Python files in the API directory tree for endpoints."""
    all_endpoints: list[EndpointInfo] = []

    for py_file in sorted(api_dir.rglob("*.py")):
        if py_file.name == "__init__.py":
            # Still scan init files - they sometimes define routes
            # but only if they import sub-routers (skip those)
            source = py_file.read_text(errors="replace")
            if "include_router" in source:
                continue
        if py_file.name.startswith("_") and py_file.name != "__init__.py":
            continue
        # Skip non-router files
        skip_names = {"dependencies", "error_handlers", "errors", "middleware"}
        if py_file.stem in skip_names:
            continue

        endpoints = extract_endpoints_from_file(py_file)
        all_endpoints.extend(endpoints)

    return all_endpoints


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def compute_stats(endpoints: list[EndpointInfo]) -> dict[str, Any]:
    """Compute summary statistics."""
    from collections import Counter

    methods = Counter(e.method for e in endpoints)
    tiers = Counter(e.maturity_tier for e in endpoints)
    auth_count = sum(1 for e in endpoints if e.auth_required)

    return {
        "total_endpoints": len(endpoints),
        "by_method": dict(methods.most_common()),
        "by_maturity_tier": dict(tiers.most_common()),
        "auth_required": auth_count,
        "no_auth": len(endpoints) - auth_count,
    }


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_markdown(endpoints: list[EndpointInfo], stats: dict[str, Any]) -> str:
    """Format endpoints as a Markdown table."""
    lines: list[str] = []
    lines.append("# API Endpoint Inventory")
    lines.append("")
    lines.append(f"Total endpoints: **{stats['total_endpoints']}**")
    lines.append("")

    # Stats
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    for method, count in stats["by_method"].items():
        lines.append(f"| {method} | {count} |")
    lines.append(f"| Auth required | {stats['auth_required']} |")
    lines.append(f"| No auth | {stats['no_auth']} |")
    lines.append("")

    lines.append("### By Maturity Tier")
    lines.append("")
    lines.append("| Tier | Count |")
    lines.append("|------|-------|")
    for tier, count in stats["by_maturity_tier"].items():
        lines.append(f"| {tier} | {count} |")
    lines.append("")

    # Endpoint table
    lines.append("## Endpoints")
    lines.append("")
    lines.append("| Method | Path | Function | Auth | Tier | Response Model |")
    lines.append("|--------|------|----------|------|------|---------------|")
    for e in sorted(endpoints, key=lambda x: (x.path, x.method)):
        auth_str = "Yes" if e.auth_required else "No"
        rm = e.response_model or "-"
        lines.append(f"| {e.method} | `{e.path}` | {e.function_name} | {auth_str} | {e.maturity_tier} | {rm} |")

    return "\n".join(lines)


def format_csv_output(endpoints: list[EndpointInfo]) -> str:
    """Format endpoints as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["method", "path", "function_name", "file", "response_model", "auth_required", "maturity_tier", "tags", "summary"])
    for e in sorted(endpoints, key=lambda x: (x.path, x.method)):
        writer.writerow([
            e.method,
            e.path,
            e.function_name,
            e.file,
            e.response_model,
            e.auth_required,
            e.maturity_tier,
            ";".join(e.tags),
            e.summary,
        ])
    return output.getvalue()


def format_json_output(endpoints: list[EndpointInfo], stats: dict[str, Any]) -> str:
    """Format endpoints as JSON."""
    data = {
        "stats": stats,
        "endpoints": [e.to_dict() for e in sorted(endpoints, key=lambda x: (x.path, x.method))],
    }
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_endpoint_inventory(
    api_dir: Path | None = None,
) -> tuple[list[EndpointInfo], dict[str, Any]]:
    """Run the endpoint inventory scan and return (endpoints, stats)."""
    if api_dir is None:
        api_dir = Path(__file__).resolve().parent.parent / "app" / "api"

    endpoints = scan_api_directory(api_dir)
    stats = compute_stats(endpoints)
    return endpoints, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="API endpoint inventory")
    parser.add_argument(
        "--format",
        choices=["markdown", "csv", "json", "all"],
        default="all",
        help="Output format (default: all)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Write output to file instead of stdout",
    )
    parser.add_argument(
        "--api-dir",
        type=str,
        default=None,
        help="Path to API directory (default: auto-detect)",
    )
    args = parser.parse_args()

    api_dir = Path(args.api_dir) if args.api_dir else None
    endpoints, stats = run_endpoint_inventory(api_dir)

    parts: list[str] = []

    if args.format in ("markdown", "all"):
        parts.append(format_markdown(endpoints, stats))

    if args.format in ("csv", "all"):
        parts.append(format_csv_output(endpoints))

    if args.format in ("json", "all"):
        parts.append(format_json_output(endpoints, stats))

    output = "\n\n".join(parts)

    if args.out:
        Path(args.out).write_text(output)
        print(f"Output written to {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
