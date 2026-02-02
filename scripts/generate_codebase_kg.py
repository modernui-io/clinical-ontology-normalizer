#!/usr/bin/env python3
import argparse
import ast
import json
import os
import re
from datetime import date


IMPORT_FROM_RE = re.compile(r"^\s*from\s+(app\.[\w\.]+)\s+import\s+([\w\*,\s]+)")
IMPORT_RE = re.compile(r"^\s*import\s+(app\.[\w\.]+)")
ROUTE_RE = re.compile(
    r"@router\.(get|post|put|delete|patch|options|head)\(\s*([\"'])(.*?)\2",
    re.DOTALL,
)


def iter_py_files(base_dir: str):
    for root, _, files in os.walk(base_dir):
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(root, name)


def parse_imports(file_path: str):
    mods = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                m = IMPORT_FROM_RE.match(line)
                if m:
                    mods.append(m.group(1))
                    continue
                m = IMPORT_RE.match(line)
                if m:
                    mods.append(m.group(1))
    except Exception:
        return []
    return mods


def _ast_literal(node):
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Str):
        return node.s
    if isinstance(node, ast.List):
        return [_ast_literal(elt) for elt in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_ast_literal(elt) for elt in node.elts)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _parse_routes_ast(file_path: str):
    routes = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
    except Exception:
        return routes

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        fn_name = node.name
        for dec in node.decorator_list:
            call = dec if isinstance(dec, ast.Call) else None
            if call is None:
                continue
            func = call.func
            if not isinstance(func, ast.Attribute):
                continue
            if not isinstance(func.value, ast.Name):
                continue
            if func.value.id != "router":
                continue
            method = func.attr.upper()
            if method not in {
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "PATCH",
                "OPTIONS",
                "HEAD",
            }:
                continue

            path = ""
            if call.args:
                path_val = _ast_literal(call.args[0])
                if isinstance(path_val, str):
                    path = path_val

            meta = {
                "method": method,
                "path": path,
                "function": fn_name,
            }
            for kw in call.keywords:
                if kw.arg in {
                    "response_model",
                    "tags",
                    "summary",
                    "description",
                    "status_code",
                }:
                    meta[kw.arg] = _ast_literal(kw.value)
            routes.append(meta)
    return routes


def parse_routes(file_path: str):
    routes = _parse_routes_ast(file_path)
    if routes:
        return routes
    fallback = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        for m in ROUTE_RE.finditer(content):
            method = m.group(1).upper()
            path = m.group(3).strip()
            fallback.append({"method": method, "path": path})
    except Exception:
        return []
    return fallback


def module_to_path(root: str, mod: str):
    if not mod.startswith("app."):
        return None
    rel = mod.replace(".", "/")
    if not rel.startswith("app/"):
        return None
    base = os.path.join(root, "backend", rel)
    if os.path.isfile(base + ".py"):
        return os.path.relpath(base + ".py", root)
    if os.path.isdir(base):
        init = os.path.join(base, "__init__.py")
        if os.path.isfile(init):
            return os.path.relpath(init, root)
    return None


def add_node(nodes, node_id, node_type, label, path):
    if node_id in nodes:
        return
    nodes[node_id] = {
        "id": node_id,
        "type": node_type,
        "label": label,
        "path": path,
    }


def add_edge(edges, src, dst, edge_type):
    edges.append({"from": src, "to": dst, "type": edge_type})


def build_kg(root: str):
    api_dir = os.path.join(root, "backend", "app", "api")
    services_dir = os.path.join(root, "backend", "app", "services")

    nodes = {}
    edges = []

    # Base nodes
    add_node(nodes, "repo", "repo", "Clinical Ontology Normalizer", ".")

    for d in [
        "backend",
        "frontend",
        "specs",
        "fixtures",
        "k8s",
        "infra",
        "fhir-mcp",
    ]:
        add_node(nodes, d, "dir", d, d)
        add_edge(edges, "repo", d, "contains")

    # Backend core subdirs
    for d in [
        "backend/app",
        "backend/app/api",
        "backend/app/services",
        "backend/app/models",
        "backend/app/schemas",
        "backend/app/core",
        "backend/app/jobs",
        "backend/app/etl",
        "backend/app/connectors",
    ]:
        add_node(nodes, d, "dir", d, d)
        add_edge(edges, "backend", d, "contains")

    # Entry points
    for f, label in [
        ("backend/app/main.py", "FastAPI app"),
        ("backend/app/api/__init__.py", "API router index"),
        ("backend/app/core/config.py", "App config"),
        ("backend/app/core/database.py", "DB init"),
    ]:
        add_node(nodes, f, "file", label, f)

    # API -> Service edges
    for abs_path in iter_py_files(api_dir):
        rel_path = os.path.relpath(abs_path, root)
        mods = parse_imports(abs_path)
        service_paths = set()
        for mod in mods:
            if mod.startswith("app.services"):
                p = module_to_path(root, mod)
                if p:
                    service_paths.add(p)

        routes = parse_routes(abs_path)
        if not service_paths and not routes:
            continue

        add_node(nodes, rel_path, "file", os.path.basename(rel_path), rel_path)
        add_edge(edges, "backend/app/api", rel_path, "contains")

        for sp in sorted(service_paths):
            add_node(nodes, sp, "service", os.path.basename(sp), sp)
            add_edge(edges, "backend/app/services", sp, "contains")
            add_edge(edges, rel_path, sp, "uses")

        # API file -> endpoints, and endpoint -> services
        for meta in routes:
            method = meta.get("method", "GET")
            path = meta.get("path", "")
            endpoint_id = f"endpoint:{method} {path} ({rel_path})"
            add_node(nodes, endpoint_id, "endpoint", f"{method} {path}", rel_path)
            nodes[endpoint_id]["meta"] = meta
            add_edge(edges, rel_path, endpoint_id, "defines")
            for sp in sorted(service_paths):
                add_edge(edges, endpoint_id, sp, "uses")

    # Service -> Model edges
    for abs_path in iter_py_files(services_dir):
        rel_path = os.path.relpath(abs_path, root)
        mods = parse_imports(abs_path)
        model_paths = set()
        for mod in mods:
            if mod.startswith("app.models"):
                p = module_to_path(root, mod)
                if p:
                    model_paths.add(p)
        if not model_paths:
            continue
        add_node(nodes, rel_path, "service", os.path.basename(rel_path), rel_path)
        add_edge(edges, "backend/app/services", rel_path, "contains")
        for mp in sorted(model_paths):
            add_node(nodes, mp, "model", os.path.basename(mp), mp)
            add_edge(edges, "backend/app/models", mp, "contains")
            add_edge(edges, rel_path, mp, "uses")

    # Frontend core subdirs
    for d in [
        "frontend/src/app",
        "frontend/src/components",
        "frontend/src/hooks",
        "frontend/src/components/KnowledgeGraph",
    ]:
        add_node(nodes, d, "dir", d, d)
        add_edge(edges, "frontend", d, "contains")

    return {
        "schema_version": "1.0",
        "generated_at": date.today().isoformat(),
        "root": "repo",
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate codebase_kg.json")
    parser.add_argument(
        "--root", default=None, help="Repo root (defaults to parent of scripts/)"
    )
    parser.add_argument(
        "--out", default=None, help="Output path (defaults to <root>/codebase_kg.json)"
    )
    args = parser.parse_args()

    if args.root:
        root = os.path.abspath(args.root)
    else:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    out_path = args.out or os.path.join(root, "codebase_kg.json")
    kg = build_kg(root)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(kg, f, indent=2, sort_keys=False)

    print(f"Wrote {out_path} with {len(kg['nodes'])} nodes, {len(kg['edges'])} edges")


if __name__ == "__main__":
    main()
