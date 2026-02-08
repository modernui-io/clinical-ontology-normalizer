#!/usr/bin/env python3
"""Migration chain validation script.

VPE-3: Database Migration Safety

Validates the Alembic migration chain for integrity issues:
  1. Verifies the revision chain has no gaps or unreachable revisions
  2. Checks that there is exactly one head (no diverged branches)
  3. Validates that every migration file has both upgrade() and downgrade() functions
  4. Warns about downgrade() functions that are empty (pass-only)
  5. Detects filename collisions (multiple files with same numeric prefix)

Usage:
    python backend/scripts/check_migrations.py

    # From within the backend directory:
    python scripts/check_migrations.py

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path


def get_versions_dir() -> Path:
    """Locate the alembic/versions directory."""
    # Try relative to this script's location
    script_dir = Path(__file__).resolve().parent
    backend_dir = script_dir.parent
    versions_dir = backend_dir / "alembic" / "versions"
    if versions_dir.is_dir():
        return versions_dir

    # Try relative to cwd
    cwd_versions = Path.cwd() / "alembic" / "versions"
    if cwd_versions.is_dir():
        return cwd_versions

    # Try cwd/backend
    cwd_backend = Path.cwd() / "backend" / "alembic" / "versions"
    if cwd_backend.is_dir():
        return cwd_backend

    print("ERROR: Could not locate alembic/versions directory")
    sys.exit(1)


def parse_migration_file(filepath: Path) -> dict | None:
    """Parse a migration file and extract revision metadata and function presence.

    Returns a dict with:
        - revision: str
        - down_revision: str | None
        - has_upgrade: bool
        - has_downgrade: bool
        - downgrade_is_empty: bool  (True if downgrade body is only pass/docstrings)
        - filename: str
    """
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"  WARNING: Could not parse {filepath.name}: {e}")
        return None

    result = {
        "revision": None,
        "down_revision": None,
        "has_upgrade": False,
        "has_downgrade": False,
        "downgrade_is_empty": False,
        "filename": filepath.name,
        "filepath": str(filepath),
    }

    # Extract module-level assignments for revision and down_revision
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            # Handle both `revision = "xxx"` and `revision: str = "xxx"`
            if isinstance(node, ast.AnnAssign):
                target_name = getattr(node.target, "id", None)
                value_node = node.value
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                target_name = getattr(node.targets[0], "id", None)
                value_node = node.value
            else:
                continue

            if target_name == "revision" and value_node is not None:
                if isinstance(value_node, ast.Constant):
                    result["revision"] = value_node.value
            elif target_name == "down_revision" and value_node is not None:
                if isinstance(value_node, ast.Constant):
                    result["down_revision"] = value_node.value
                    # None means base migration

        elif isinstance(node, ast.FunctionDef):
            if node.name == "upgrade":
                result["has_upgrade"] = True
            elif node.name == "downgrade":
                result["has_downgrade"] = True
                # Check if downgrade body is empty (only pass statements and/or docstrings)
                real_stmts = []
                for stmt in node.body:
                    if isinstance(stmt, ast.Pass):
                        continue
                    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                        # Docstring
                        continue
                    real_stmts.append(stmt)
                result["downgrade_is_empty"] = len(real_stmts) == 0

    return result


def check_single_head(migrations: list[dict]) -> tuple[bool, list[str]]:
    """Check that the migration chain has exactly one head.

    A head is a revision that is not referenced as any other revision's down_revision.
    """
    errors = []
    all_revisions = {m["revision"] for m in migrations}
    all_down_revisions = {m["down_revision"] for m in migrations if m["down_revision"] is not None}

    # Heads = revisions not referenced as a down_revision by anything
    heads = all_revisions - all_down_revisions
    if len(heads) == 0:
        errors.append("No head revision found -- possible circular reference in migration chain")
    elif len(heads) > 1:
        errors.append(
            f"Multiple heads detected (diverged branches): {sorted(heads)}. "
            f"Expected exactly one head. Run 'alembic merge heads' to resolve."
        )
    else:
        head = heads.pop()
        print(f"  OK: Single head revision: {head}")

    return len(errors) == 0, errors


def check_chain_integrity(migrations: list[dict]) -> tuple[bool, list[str]]:
    """Verify the down_revision chain is unbroken from head to base.

    Checks:
    - Every down_revision references a valid revision (or None for base)
    - No orphaned revisions (unreachable from head)
    - Exactly one base migration (down_revision = None)
    """
    errors = []
    warnings = []

    revision_map = {m["revision"]: m for m in migrations}
    all_revisions = set(revision_map.keys())

    # Check that all down_revisions reference valid revisions
    for m in migrations:
        down = m["down_revision"]
        if down is not None and down not in all_revisions:
            errors.append(
                f"Broken chain: {m['filename']} (rev={m['revision']}) references "
                f"down_revision='{down}' which does not exist"
            )

    # Check exactly one base
    bases = [m for m in migrations if m["down_revision"] is None]
    if len(bases) == 0:
        errors.append("No base migration found (no revision with down_revision = None)")
    elif len(bases) > 1:
        base_names = [f"{m['filename']} (rev={m['revision']})" for m in bases]
        errors.append(f"Multiple base migrations found: {base_names}")
    else:
        print(f"  OK: Base migration: {bases[0]['filename']} (rev={bases[0]['revision']})")

    # Walk chain from head to base to find unreachable revisions
    all_down_refs = {m["down_revision"] for m in migrations if m["down_revision"] is not None}
    heads = all_revisions - all_down_refs

    reachable = set()
    for head in heads:
        current = head
        visited = set()
        while current is not None and current not in visited:
            visited.add(current)
            reachable.add(current)
            m = revision_map.get(current)
            if m is None:
                break
            current = m["down_revision"]

    unreachable = all_revisions - reachable
    if unreachable:
        for rev in sorted(unreachable):
            m = revision_map[rev]
            errors.append(
                f"Unreachable revision: {m['filename']} (rev={rev}) -- "
                f"not in the chain from any head to base"
            )
    else:
        print(f"  OK: All {len(all_revisions)} revisions are reachable in the chain")

    return len(errors) == 0, errors


def check_functions(migrations: list[dict]) -> tuple[bool, list[str]]:
    """Check that all migrations have upgrade() and downgrade() functions."""
    errors = []
    warnings = []

    for m in migrations:
        if not m["has_upgrade"]:
            errors.append(f"Missing upgrade() function: {m['filename']} (rev={m['revision']})")
        if not m["has_downgrade"]:
            errors.append(f"Missing downgrade() function: {m['filename']} (rev={m['revision']})")
        elif m["downgrade_is_empty"]:
            warnings.append(
                f"Empty downgrade() (pass only): {m['filename']} (rev={m['revision']}) -- "
                f"rollback will be a no-op"
            )

    if not errors:
        print(f"  OK: All {len(migrations)} migrations have upgrade() and downgrade() functions")

    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}")

    return len(errors) == 0, errors


def check_filename_collisions(migrations: list[dict]) -> tuple[bool, list[str]]:
    """Check for filename prefix collisions (e.g., two files starting with '016_')."""
    warnings = []
    prefix_map: dict[str, list[str]] = {}

    for m in migrations:
        # Extract numeric prefix from filename (e.g., "016" from "016_create_calculator_tables.py")
        parts = m["filename"].split("_", 1)
        if parts and parts[0].isdigit():
            prefix = parts[0]
            prefix_map.setdefault(prefix, []).append(m["filename"])

    for prefix, files in sorted(prefix_map.items()):
        if len(files) > 1:
            warnings.append(
                f"Filename prefix collision on '{prefix}_': {files}. "
                f"This can be confusing even if Alembic revision IDs are distinct."
            )

    if not warnings:
        print("  OK: No filename prefix collisions")
    else:
        for w in warnings:
            print(f"  WARNING: {w}")

    # Filename collisions are warnings, not errors (Alembic uses revision IDs, not filenames)
    return True, []


def main() -> int:
    """Run all migration checks and return exit code."""
    print("=" * 60)
    print("VPE-3: Alembic Migration Chain Validation")
    print("=" * 60)

    versions_dir = get_versions_dir()
    print(f"\nVersions directory: {versions_dir}\n")

    # Discover and parse all migration files
    migration_files = sorted(
        f for f in versions_dir.iterdir()
        if f.suffix == ".py" and f.name != "__init__.py"
    )

    if not migration_files:
        print("ERROR: No migration files found")
        return 1

    print(f"Found {len(migration_files)} migration files\n")

    migrations = []
    parse_errors = []
    for f in migration_files:
        result = parse_migration_file(f)
        if result is None:
            parse_errors.append(f"Could not parse: {f.name}")
        elif result["revision"] is None:
            parse_errors.append(f"No revision ID found in: {f.name}")
        else:
            migrations.append(result)

    if parse_errors:
        print("Parse errors:")
        for e in parse_errors:
            print(f"  ERROR: {e}")
        print()

    all_passed = True
    all_errors = []

    # Check 1: Single head
    print("Check 1: Single head (no diverged branches)")
    passed, errors = check_single_head(migrations)
    if not passed:
        all_passed = False
        all_errors.extend(errors)
    print()

    # Check 2: Chain integrity
    print("Check 2: Revision chain integrity")
    passed, errors = check_chain_integrity(migrations)
    if not passed:
        all_passed = False
        all_errors.extend(errors)
    print()

    # Check 3: upgrade/downgrade functions
    print("Check 3: Migration functions (upgrade/downgrade)")
    passed, errors = check_functions(migrations)
    if not passed:
        all_passed = False
        all_errors.extend(errors)
    print()

    # Check 4: Filename collisions (warnings only)
    print("Check 4: Filename prefix collisions")
    check_filename_collisions(migrations)
    print()

    # Summary
    print("=" * 60)
    if all_errors:
        print("ERRORS:")
        for e in all_errors:
            print(f"  - {e}")
        print()

    if all_passed and not parse_errors:
        print("RESULT: ALL CHECKS PASSED")
        return 0
    else:
        print("RESULT: CHECKS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
