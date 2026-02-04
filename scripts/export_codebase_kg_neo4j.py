#!/usr/bin/env python3
import argparse
import csv
import json
import os


def main():
    parser = argparse.ArgumentParser(description="Export codebase_kg.json to Neo4j CSV.")
    parser.add_argument("--kg", default="codebase_kg.json", help="Path to codebase KG JSON")
    parser.add_argument("--outdir", default="kg_export", help="Output directory for CSVs")
    args = parser.parse_args()

    with open(args.kg, "r", encoding="utf-8") as f:
        kg = json.load(f)

    os.makedirs(args.outdir, exist_ok=True)

    nodes_path = os.path.join(args.outdir, "nodes.csv")
    edges_path = os.path.join(args.outdir, "edges.csv")

    with open(nodes_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id:ID", "label", "type", "path", "meta"])
        for node in kg.get("nodes", []):
            meta = node.get("meta")
            writer.writerow(
                [
                    node.get("id"),
                    node.get("label"),
                    node.get("type"),
                    node.get("path"),
                    json.dumps(meta, ensure_ascii=True) if meta else "",
                ]
            )

    with open(edges_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([":START_ID", ":END_ID", "type"])
        for edge in kg.get("edges", []):
            writer.writerow([edge.get("from"), edge.get("to"), edge.get("type")])

    print(f"Wrote {nodes_path}")
    print(f"Wrote {edges_path}")


if __name__ == "__main__":
    main()
