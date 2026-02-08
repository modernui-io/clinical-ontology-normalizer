#!/usr/bin/env python3
"""Service dependency mapper (CTO-7).

Scans backend/app/services/*.py for import statements, builds a
dependency graph, detects circular dependencies, and outputs in
multiple formats: Mermaid, JSON, and a plain-text summary.

Usage:
    python backend/scripts/service_dependency_graph.py
    python backend/scripts/service_dependency_graph.py --format mermaid
    python backend/scripts/service_dependency_graph.py --format json
    python backend/scripts/service_dependency_graph.py --format summary
    python backend/scripts/service_dependency_graph.py --format all       # default
    python backend/scripts/service_dependency_graph.py --out deps.json --format json
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVICE_IMPORT_PREFIX = "app.services."
HIGH_DEP_THRESHOLD = 5   # services importing more than this get flagged


# ---------------------------------------------------------------------------
# Core graph builder
# ---------------------------------------------------------------------------

def extract_service_imports(source: str) -> list[str]:
    """Extract service module names imported from ``app.services.*``.

    Returns a deduplicated list of service module basenames, e.g.
    ``["graph_builder", "audit_service"]``.
    """
    deps: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(SERVICE_IMPORT_PREFIX):
                # e.g. "app.services.graph_builder" -> "graph_builder"
                remainder = module[len(SERVICE_IMPORT_PREFIX):]
                # Take only the first component (handles sub-packages)
                service_name = remainder.split(".")[0]
                if service_name:
                    deps.add(service_name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith(SERVICE_IMPORT_PREFIX):
                    remainder = name[len(SERVICE_IMPORT_PREFIX):]
                    service_name = remainder.split(".")[0]
                    if service_name:
                        deps.add(service_name)

    return sorted(deps)


def build_dependency_graph(
    services_dir: Path,
) -> dict[str, list[str]]:
    """Build an adjacency list: service -> [services it imports].

    Only considers ``*.py`` files directly in the services directory
    (not sub-packages' internal files).
    """
    graph: dict[str, list[str]] = {}
    service_files = sorted(services_dir.glob("*.py"))

    all_service_names: set[str] = set()
    for f in service_files:
        if f.name == "__init__.py":
            continue
        all_service_names.add(f.stem)

    for f in service_files:
        if f.name == "__init__.py":
            continue
        name = f.stem
        source = f.read_text(errors="replace")
        raw_deps = extract_service_imports(source)
        # Only keep deps that actually exist as service files & exclude self
        deps = [d for d in raw_deps if d in all_service_names and d != name]
        graph[name] = deps

    return graph


# ---------------------------------------------------------------------------
# Circular dependency detection (DFS-based)
# ---------------------------------------------------------------------------

def find_circular_dependencies(graph: dict[str, list[str]]) -> list[list[str]]:
    """Return all elementary cycles in the graph.

    Uses a DFS-based approach to find cycles. Returns a list of cycles,
    where each cycle is a list of node names forming the loop.
    """
    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()
    path: list[str] = []

    def _dfs(node: str) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbour in graph.get(node, []):
            if neighbour not in visited:
                _dfs(neighbour)
            elif neighbour in rec_stack:
                # Found a cycle: extract the cycle from path
                idx = path.index(neighbour)
                cycle = path[idx:] + [neighbour]
                # Normalise: rotate so smallest element is first
                min_idx = cycle[:-1].index(min(cycle[:-1]))
                normalised = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
                if normalised not in cycles:
                    cycles.append(normalised)

        path.pop()
        rec_stack.discard(node)

    for node in sorted(graph):
        if node not in visited:
            _dfs(node)

    return cycles


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def compute_stats(graph: dict[str, list[str]]) -> dict[str, Any]:
    """Compute summary statistics from the dependency graph."""
    # Reverse graph: who depends on me?
    depended_on: dict[str, int] = defaultdict(int)
    for service, deps in graph.items():
        for d in deps:
            depended_on[d] += 1

    dep_counts = {s: len(deps) for s, deps in graph.items()}
    high_dep = {s: c for s, c in dep_counts.items() if c > HIGH_DEP_THRESHOLD}

    most_depended = sorted(depended_on.items(), key=lambda x: -x[1])[:10]
    most_dependent = sorted(dep_counts.items(), key=lambda x: -x[1])[:10]

    return {
        "total_services": len(graph),
        "total_edges": sum(len(d) for d in graph.values()),
        "most_depended_on": [{"service": s, "dependents": c} for s, c in most_depended],
        "most_dependent": [{"service": s, "dependencies": c} for s, c in most_dependent],
        "high_dependency_services": [
            {"service": s, "count": c} for s, c in sorted(high_dep.items(), key=lambda x: -x[1])
        ],
    }


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def format_mermaid(graph: dict[str, list[str]], cycles: list[list[str]]) -> str:
    """Generate a Mermaid flowchart diagram."""
    lines = ["graph LR"]
    for service in sorted(graph):
        for dep in sorted(graph[service]):
            lines.append(f"    {service} --> {dep}")

    if cycles:
        lines.append("")
        lines.append("    %% Circular dependencies detected:")
        for cycle in cycles:
            lines.append(f"    %% {' -> '.join(cycle)}")

    return "\n".join(lines)


def format_json(
    graph: dict[str, list[str]],
    cycles: list[list[str]],
    stats: dict[str, Any],
) -> str:
    """Generate JSON output with graph, cycles, and stats."""
    data = {
        "adjacency_list": {k: v for k, v in sorted(graph.items())},
        "circular_dependencies": cycles,
        "stats": stats,
    }
    return json.dumps(data, indent=2)


def format_summary(
    graph: dict[str, list[str]],
    cycles: list[list[str]],
    stats: dict[str, Any],
) -> str:
    """Generate a plain-text summary."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  Service Dependency Graph - Summary")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Total services: {stats['total_services']}")
    lines.append(f"  Total dependency edges: {stats['total_edges']}")

    lines.append("")
    lines.append("  Most depended-on services:")
    for item in stats["most_depended_on"][:10]:
        lines.append(f"    {item['service']:40s}  ({item['dependents']} dependents)")

    lines.append("")
    lines.append("  Most dependent services (most imports):")
    for item in stats["most_dependent"][:10]:
        lines.append(f"    {item['service']:40s}  ({item['dependencies']} dependencies)")

    if stats["high_dependency_services"]:
        lines.append("")
        lines.append(f"  ** Services with > {HIGH_DEP_THRESHOLD} dependencies (refactoring candidates):")
        for item in stats["high_dependency_services"]:
            lines.append(f"    {item['service']:40s}  ({item['count']} deps)")

    if cycles:
        lines.append("")
        lines.append(f"  ** Circular dependencies detected ({len(cycles)}):")
        for cycle in cycles:
            lines.append(f"    {' -> '.join(cycle)}")
    else:
        lines.append("")
        lines.append("  No circular dependencies detected.")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_dependency_analysis(
    services_dir: Path | None = None,
) -> tuple[dict[str, list[str]], list[list[str]], dict[str, Any]]:
    """Run the full analysis pipeline and return (graph, cycles, stats)."""
    if services_dir is None:
        services_dir = Path(__file__).resolve().parent.parent / "app" / "services"

    graph = build_dependency_graph(services_dir)
    cycles = find_circular_dependencies(graph)
    stats = compute_stats(graph)
    return graph, cycles, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Service dependency mapper")
    parser.add_argument(
        "--format",
        choices=["mermaid", "json", "summary", "all"],
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
        "--services-dir",
        type=str,
        default=None,
        help="Path to services directory (default: auto-detect)",
    )
    args = parser.parse_args()

    services_dir = Path(args.services_dir) if args.services_dir else None
    graph, cycles, stats = run_dependency_analysis(services_dir)

    parts: list[str] = []

    if args.format in ("mermaid", "all"):
        parts.append(format_mermaid(graph, cycles))

    if args.format in ("json", "all"):
        parts.append(format_json(graph, cycles, stats))

    if args.format in ("summary", "all"):
        parts.append(format_summary(graph, cycles, stats))

    output = "\n\n".join(parts)

    if args.out:
        Path(args.out).write_text(output)
        print(f"Output written to {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
