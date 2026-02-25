#!/usr/bin/env python3
"""Tiered codebase context generator.

Generates compact indexes and domain guides for Claude's context system:
  - memory/service_registry.md  (Tier 1: one-line-per-file index)
  - memory/domain_rag.md        (Tier 2: RAG pipeline deep-dive)
  - memory/domain_calculators.md(Tier 2: Calculator architecture)
  - memory/domain_kg.md         (Tier 2: Knowledge graph architecture)

Usage:
    python backend/scripts/generate_context_index.py
"""

from __future__ import annotations

import ast
import textwrap
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent.parent  # project root
BACKEND = ROOT / "backend"
SERVICES_DIR = BACKEND / "app" / "services"
MODELS_DIR = BACKEND / "app" / "models"
API_DIR = BACKEND / "app" / "api"
MEMORY_DIR = ROOT / "memory"

# ---------------------------------------------------------------------------
# Domain configs — which files belong to each domain guide
# ---------------------------------------------------------------------------

DOMAIN_CONFIGS: dict[str, dict] = {
    "rag": {
        "title": "RAG Pipeline Architecture",
        "description": "Retrieval-Augmented Generation pipeline: from question to answer via graph + document retrieval.",
        "key_files": [
            "graph_augmented_rag.py",
            "qa_experiment_executor.py",
            "ablation_harness.py",
            "qa_evaluation.py",
            "guideline_rag_service.py",
            "llm_service.py",
            "longbench_runner.py",
        ],
        "related_patterns": ["rag", "retriev", "qa_", "experiment", "ablation", "benchmark"],
    },
    "calculators": {
        "title": "Calculator Architecture",
        "description": "Clinical calculator definitions, execution engine, reasoning service, and KG integration.",
        "key_files": [
            "calculator_definitions.py",
            "calculator_builder.py",
            "clinical_calculator_service.py",
            "clinical_calculators.py",
            "calculator_reasoning_service.py",
            "calculator_kg_integration.py",
            "condition_calculator_mapping.py",
            "kg_calculator_mapper.py",
        ],
        "related_patterns": ["calc", "meld", "sofa", "ascvd", "wells"],
    },
    "kg": {
        "title": "Knowledge Graph Architecture",
        "description": "KG construction, node/edge models, caching, traversal, and visualization.",
        "key_files": [
            "graph_builder.py",
            "graph_builder_db.py",
            "kg_cache_service.py",
            "graph_database_service.py",
            "graph_analytics_service.py",
            "graph_embedding_service.py",
            "kg_visualization_service.py",
            "kg_merge_validator.py",
            "ontology_graph_integration.py",
            "knowledge_graph_fhir_export.py",
        ],
        "related_patterns": ["graph_builder", "kg_", "knowledge_graph"],
    },
}


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _safe_parse(path: Path) -> ast.Module | None:
    """Parse a Python file, returning None on failure."""
    try:
        return ast.parse(path.read_text(errors="replace"))
    except SyntaxError:
        return None


def _first_line(docstring: str | None) -> str:
    """Return the first non-empty line of a docstring."""
    if not docstring:
        return ""
    for line in docstring.strip().splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _format_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Format function arguments compactly: (arg1, arg2, ...) -> return."""
    args = node.args
    parts: list[str] = []

    # Skip 'self' and 'cls'
    all_args = args.args[:]
    if all_args and all_args[0].arg in ("self", "cls"):
        all_args = all_args[1:]

    for a in all_args:
        annotation = ""
        if a.annotation:
            annotation = f": {ast.unparse(a.annotation)}"
        parts.append(f"{a.arg}{annotation}")

    # Add *args and **kwargs if present
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")

    ret = ""
    if node.returns:
        ret = f" -> {ast.unparse(node.returns)}"

    return f"({', '.join(parts)}){ret}"


def extract_service_imports(tree: ast.Module) -> list[str]:
    """Extract service dependency names from import statements."""
    deps: set[str] = set()
    prefix = "app.services."
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(prefix):
                remainder = module[len(prefix):]
                service_name = remainder.split(".")[0]
                if service_name:
                    deps.add(service_name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(prefix):
                    remainder = alias.name[len(prefix):]
                    service_name = remainder.split(".")[0]
                    if service_name:
                        deps.add(service_name)
    return sorted(deps)


def extract_public_functions(tree: ast.Module) -> list[tuple[str, str]]:
    """Extract top-level and class-level public function names + compact signatures.

    Returns list of (name, signature_str).
    """
    results: list[tuple[str, str]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                results.append((node.name, _format_args(node)))
        elif isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not child.name.startswith("_"):
                        results.append((f"{node.name}.{child.name}", _format_args(child)))
    return results


def extract_classes(tree: ast.Module) -> list[tuple[str, str, list[str]]]:
    """Extract classes: (name, docstring_first_line, [base_names])."""
    results: list[tuple[str, str, list[str]]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            doc = _first_line(ast.get_docstring(node))
            bases = []
            for base in node.bases:
                try:
                    bases.append(ast.unparse(base))
                except Exception:
                    pass
            results.append((node.name, doc, bases))
    return results


# ---------------------------------------------------------------------------
# Tier 1: Service Registry
# ---------------------------------------------------------------------------

def generate_service_index() -> list[str]:
    """Generate compact one-line-per-service index."""
    lines: list[str] = ["## Service Index", ""]
    lines.append("```")

    entries: list[tuple[str, int, str, list[str], list[str]]] = []
    service_files = sorted(SERVICES_DIR.glob("*.py"))

    for f in service_files:
        if f.name in ("__init__.py",):
            continue
        tree = _safe_parse(f)
        if tree is None:
            continue

        loc = sum(1 for _ in f.read_text(errors="replace").splitlines())
        doc = _first_line(ast.get_docstring(tree))
        funcs = extract_public_functions(tree)
        deps = extract_service_imports(tree)

        # Pick top 3-4 most important function names
        func_names = [name for name, _ in funcs[:5]]

        entries.append((f.name, loc, doc, func_names, deps))

    for name, loc, doc, func_names, deps in entries:
        fn_str = ", ".join(func_names[:4])
        if len(func_names) > 4:
            fn_str += f" (+{len(func_names) - 4})"
        dep_str = ", ".join(deps[:4])
        if len(deps) > 4:
            dep_str += f" (+{len(deps) - 4})"

        desc = doc if doc else "(no docstring)"
        # Truncate description to keep lines manageable
        if len(desc) > 80:
            desc = desc[:77] + "..."

        line = f"{name} ({loc})"
        if desc:
            line += f" — {desc}"
        if fn_str:
            line += f" | fns: {fn_str}"
        if dep_str:
            line += f" | deps: {dep_str}"

        lines.append(line)

    lines.append("```")
    lines.append("")
    return lines


def generate_model_index() -> list[str]:
    """Generate one-line-per-model index."""
    lines: list[str] = ["## Model Index", ""]
    lines.append("```")

    model_files = sorted(MODELS_DIR.glob("*.py"))

    for f in model_files:
        if f.name == "__init__.py":
            continue
        tree = _safe_parse(f)
        if tree is None:
            continue

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # Check if it's an ORM model (inherits from Base or similar)
            base_names = []
            for base in node.bases:
                try:
                    base_names.append(ast.unparse(base))
                except Exception:
                    pass

            if not any(b in ("Base", "TimestampMixin", "AuditMixin") for b in base_names):
                # Check if any base ends with "Mixin" or "Base"
                is_model = any(
                    b.endswith("Base") or b.endswith("Mixin") or b == "Base"
                    for b in base_names
                )
                if not is_model and base_names:
                    # Still include — might be interesting
                    pass
                elif not base_names:
                    continue

            # Extract column names
            columns: list[str] = []
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name):
                            # Check if RHS is Column() or mapped_column() etc
                            if isinstance(child.value, ast.Call):
                                try:
                                    func_name = ast.unparse(child.value.func)
                                except Exception:
                                    func_name = ""
                                if any(kw in func_name.lower() for kw in ("column", "mapped_column", "relationship")):
                                    columns.append(target.id)
                                elif func_name == "Column" or "Column" in func_name:
                                    columns.append(target.id)
                                else:
                                    columns.append(target.id)
                            else:
                                columns.append(target.id)
                elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                    columns.append(child.target.id)

            # Filter out dunder and private attrs
            columns = [c for c in columns if not c.startswith("_")]

            col_str = ", ".join(columns[:8])
            if len(columns) > 8:
                col_str += f" (+{len(columns) - 8})"

            table_name = ""
            # Try to find __tablename__
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name) and target.id == "__tablename__":
                            if isinstance(child.value, ast.Constant):
                                table_name = str(child.value.value)

            base_str = ", ".join(base_names)
            line = f"{node.name} ({f.name})"
            if table_name:
                line += f" table={table_name}"
            if base_str:
                line += f" [{base_str}]"
            if col_str:
                line += f" — {col_str}"

            lines.append(line)

    lines.append("```")
    lines.append("")
    return lines


def generate_route_index() -> list[str]:
    """Generate compact route table — one line per API file with endpoint count + sample paths."""
    lines: list[str] = ["## Route Index (by file)", ""]
    lines.append("```")

    HTTP_METHODS = {"get", "post", "put", "delete", "patch"}

    api_files = sorted(API_DIR.rglob("*.py"))
    # Group routes by file
    file_routes: dict[str, list[tuple[str, str]]] = {}  # file -> [(method, path)]

    for f in api_files:
        if f.name == "__init__.py":
            continue
        if f.name.startswith("_"):
            continue

        tree = _safe_parse(f)
        if tree is None:
            continue

        # Get router prefix
        prefix = ""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "router":
                        if isinstance(node.value, ast.Call):
                            for kw in node.value.keywords:
                                if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                                    prefix = str(kw.value.value)

        routes: list[tuple[str, str]] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    method = dec.func.attr
                    if method in HTTP_METHODS:
                        route_path = ""
                        if dec.args and isinstance(dec.args[0], ast.Constant):
                            route_path = str(dec.args[0].value)
                        full_path = prefix + route_path
                        routes.append((method.upper(), full_path))

        if routes:
            rel_file = str(f.relative_to(BACKEND))
            file_routes[rel_file] = routes

    total_routes = sum(len(r) for r in file_routes.values())
    lines.append(f"Total: {total_routes} endpoints across {len(file_routes)} files")
    lines.append("")

    for fname, routes in sorted(file_routes.items()):
        methods = defaultdict(int)
        for m, _ in routes:
            methods[m] += 1
        method_str = " ".join(f"{m}:{c}" for m, c in sorted(methods.items()))
        # Show up to 3 sample paths
        sample_paths = sorted(set(p for _, p in routes))[:3]
        sample_str = ", ".join(sample_paths)
        if len(set(p for _, p in routes)) > 3:
            sample_str += ", ..."
        lines.append(f"{fname} ({len(routes)} eps, {method_str}) — {sample_str}")

    lines.append("```")
    lines.append("")
    return lines


def generate_hottest_files() -> list[str]:
    """Top 20 largest service files."""
    lines: list[str] = ["## Hottest Files (by LOC)", ""]
    lines.append("```")

    entries: list[tuple[str, int]] = []
    for f in SERVICES_DIR.glob("*.py"):
        if f.name == "__init__.py":
            continue
        loc = sum(1 for _ in f.read_text(errors="replace").splitlines())
        entries.append((f.name, loc))

    entries.sort(key=lambda e: -e[1])

    for name, loc in entries[:20]:
        bar = "#" * min(loc // 200, 40)
        lines.append(f"{name:50s} {loc:6d}  {bar}")

    lines.append("```")
    lines.append("")
    return lines


def write_service_registry() -> Path:
    """Write the full Tier 1 service registry."""
    out = MEMORY_DIR / "service_registry.md"

    all_lines: list[str] = [
        "# Service Registry (Auto-Generated)",
        "",
        "Generated by `python backend/scripts/generate_context_index.py`",
        "Regenerate when services change.",
        "",
    ]

    all_lines.extend(generate_hottest_files())
    all_lines.extend(generate_service_index())
    all_lines.extend(generate_model_index())
    all_lines.extend(generate_route_index())

    out.write_text("\n".join(all_lines))
    return out


# ---------------------------------------------------------------------------
# Tier 2: Domain Guides
# ---------------------------------------------------------------------------

def generate_domain_guide(domain_key: str, config: dict) -> list[str]:
    """Generate a deep-dive domain guide for a set of key files."""
    lines: list[str] = [
        f"# {config['title']} (Auto-Generated)",
        "",
        f"{config['description']}",
        "",
        "Generated by `python backend/scripts/generate_context_index.py`",
        "",
    ]

    # Key files section with function signatures
    lines.append("## Key Files")
    lines.append("")

    for fname in config["key_files"]:
        fpath = SERVICES_DIR / fname
        if not fpath.exists():
            lines.append(f"### {fname} — NOT FOUND")
            lines.append("")
            continue

        tree = _safe_parse(fpath)
        if tree is None:
            continue

        loc = sum(1 for _ in fpath.read_text(errors="replace").splitlines())
        doc = _first_line(ast.get_docstring(tree))
        deps = extract_service_imports(tree)

        lines.append(f"### {fname} ({loc} lines)")
        if doc:
            lines.append(f"*{doc}*")
        if deps:
            lines.append(f"**Deps**: {', '.join(deps)}")
        lines.append("")

        # Classes
        classes = extract_classes(tree)
        if classes:
            for cname, cdoc, bases in classes:
                base_str = f" ({', '.join(bases)})" if bases else ""
                lines.append(f"- **class {cname}**{base_str}")
                if cdoc:
                    lines.append(f"  {cdoc}")

                # Class methods
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.ClassDef) and node.name == cname:
                        for child in ast.iter_child_nodes(node):
                            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                if child.name.startswith("_") and child.name != "__init__":
                                    continue
                                sig = _format_args(child)
                                method_doc = _first_line(ast.get_docstring(child))
                                prefix = "  - " if child.name != "__init__" else "  - "
                                entry = f"{prefix}`{child.name}{sig}`"
                                if method_doc:
                                    entry += f" — {method_doc}"
                                lines.append(entry)
            lines.append("")

        # Top-level functions
        top_funcs: list[tuple[str, str, str]] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = _format_args(node)
                fdoc = _first_line(ast.get_docstring(node))
                top_funcs.append((node.name, sig, fdoc))

        if top_funcs:
            lines.append("**Functions:**")
            for fname_f, sig, fdoc in top_funcs:
                if fname_f.startswith("_"):
                    continue
                entry = f"- `{fname_f}{sig}`"
                if fdoc:
                    entry += f" — {fdoc}"
                lines.append(entry)
            lines.append("")

    # Data flow section
    lines.append("## Data Flow")
    lines.append("")
    lines.append("```")
    if domain_key == "rag":
        lines.extend([
            "Question → qa_experiment_executor (condition routing)",
            "  → C1: LLM only (raw note)",
            "  → C2: vanilla RAG (document retrieval)",
            "  → C3: KG-RAG (graph paths via graph_augmented_rag)",
            "  → C4: Epistemic KG-RAG (assertion/temporal metadata)",
            "  → C4g: Intent-aware KG-RAG (question-type-specific retrieval)",
            "  → C5: Full system (graph + guidelines + calculators)",
            "",
            "graph_augmented_rag.retrieve_context():",
            "  1. Classify question intent (change/current_state/historical)",
            "  2. Extract concepts from question",
            "  3. Find matching KG nodes",
            "  4. Retrieve relevant edges/paths",
            "  5. Build context string for LLM",
            "  6. Call LLM with context + question → answer",
        ])
    elif domain_key == "calculators":
        lines.extend([
            "calculator_definitions.py — static data for 50+ calculators",
            "  → calculator_builder.py — builds calculator instances",
            "  → clinical_calculator_service.py — execution engine",
            "  → calculator_reasoning_service.py — LLM-driven reasoning",
            "  → calculator_kg_integration.py — feeds results into KG",
            "",
            "Patient data → extract inputs → select calculator → compute → store result",
        ])
    elif domain_key == "kg":
        lines.extend([
            "Documents → NLP extraction → Mentions → ClinicalFacts",
            "  → graph_builder.py — builds in-memory KG from facts",
            "  → graph_builder_db.py — persists KG to PostgreSQL",
            "  → kg_cache_service.py — caches KG in memory for fast retrieval",
            "  → graph_database_service.py — Neo4j persistence (optional)",
            "",
            "KGNode: concept_id, concept_name, domain, patient_id",
            "KGEdge: source_node → target_node, relation_type, temporality, assertion",
        ])
    lines.append("```")
    lines.append("")

    # Known gotchas
    lines.append("## Known Gotchas")
    lines.append("")
    if domain_key == "rag":
        lines.extend([
            "- Documents have no note_date — all NULL; partitioning uses hadm_id instead",
            "- visit_occurrence table is empty — admission tracking via edge hadm_id properties",
            "- Only ~20% of edges have explicit temporality — historical uses admission-based inference",
            "- question_metadata (hadm_1/hadm_2) must flow through executor → retrieve_context → change_retrieval",
            "- keyword evaluator uses word-boundary matching (not substring) — fixed Feb 2025",
        ])
    elif domain_key == "calculators":
        lines.extend([
            "- calculator_definitions.py is 12K+ lines — contains all static calculator data",
            "- Calculator names must match between definitions and condition_calculator_mapping",
            "- ASCVD, MELD, SOFA, Wells are the most commonly tested calculators",
        ])
    elif domain_key == "kg":
        lines.extend([
            "- source_document_date is NULL on all edges — use hadm_id for temporal partitioning",
            "- DB uses async driver (asyncpg) — scripts need psycopg2 or sync URL conversion",
            "- Concept extraction uses junk-term filter (_JUNK_TERMS) to avoid noise",
            "- KG seeding script (seed_benchmark_kg.py) creates per-admission edges",
        ])
    lines.append("")

    return lines


def write_domain_guides() -> list[Path]:
    """Write all Tier 2 domain guides."""
    paths: list[Path] = []

    for domain_key, config in DOMAIN_CONFIGS.items():
        out = MEMORY_DIR / f"domain_{domain_key}.md"
        content = generate_domain_guide(domain_key, config)
        out.write_text("\n".join(content))
        paths.append(out)
        print(f"  Wrote {out} ({len(content)} lines)")

    return paths


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating Tier 1: Service Registry...")
    reg_path = write_service_registry()
    reg_lines = reg_path.read_text().count("\n")
    print(f"  Wrote {reg_path} ({reg_lines} lines)")

    print("\nGenerating Tier 2: Domain Guides...")
    write_domain_guides()

    print("\nDone. Files written to memory/")


if __name__ == "__main__":
    main()
