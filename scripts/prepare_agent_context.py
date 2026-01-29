#!/usr/bin/env python3
import argparse
import json
from datetime import date
from pathlib import Path


def load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def match_node(node: dict, queries: list[str]) -> bool:
    if not queries:
        return True
    hay = json.dumps(node, ensure_ascii=True).lower()
    return any(q in hay for q in queries)


def slice_kg(kg: dict, queries: list[str], max_nodes: int, max_edges: int) -> dict:
    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])

    matched_ids = {n["id"] for n in nodes if match_node(n, queries)}
    if not queries:
        matched_ids = {
            n["id"]
            for n in nodes
            if n.get("type") in {"endpoint", "service", "model", "file", "dir"}
        }

    # One-hop expansion
    expanded = set(matched_ids)
    for e in edges:
        if e.get("from") in matched_ids or e.get("to") in matched_ids:
            expanded.add(e.get("from"))
            expanded.add(e.get("to"))

    # Trim
    selected_nodes = [n for n in nodes if n["id"] in expanded][:max_nodes]
    selected_ids = {n["id"] for n in selected_nodes}
    selected_edges = [
        e for e in edges if e.get("from") in selected_ids and e.get("to") in selected_ids
    ][:max_edges]

    return {"nodes": selected_nodes, "edges": selected_edges}


def main():
    parser = argparse.ArgumentParser(description="Prepare agent context bundle.")
    parser.add_argument("--query", action="append", default=[], help="Filter by keyword (repeatable)")
    parser.add_argument(
        "--out",
        default="agent_context_bundle.md",
        help="Output markdown file",
    )
    parser.add_argument("--max-nodes", type=int, default=200)
    parser.add_argument("--max-edges", type=int, default=400)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    agents_md = load_text(root / "AGENTS.md")
    map_md = load_text(root / "CODEBASE_MAP.md")

    kg_path = root / "codebase_kg.json"
    kg = {}
    if kg_path.exists():
        kg = json.loads(kg_path.read_text(encoding="utf-8"))

    queries = [q.lower() for q in args.query]
    kg_slice = slice_kg(kg, queries, args.max_nodes, args.max_edges)

    out_path = root / args.out
    out_path.write_text(
        "\n".join(
            [
                "# Agent Context Bundle",
                f"Generated: {date.today().isoformat()}",
                "",
                "## Task",
                "",
                "<fill in>",
                "",
                "## Constraints",
                "",
                "<fill in>",
                "",
                "## AGENTS.md",
                "```markdown",
                agents_md.rstrip(),
                "```",
                "",
                "## CODEBASE_MAP.md",
                "```markdown",
                map_md.rstrip(),
                "```",
                "",
                "## KG Slice (JSON)",
                "```json",
                json.dumps(kg_slice, indent=2, sort_keys=False),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
