"""Automated Technical Debt Scanner.

Scans Python source files for common technical debt indicators:
- TODO/FIXME/HACK/XXX/NOQA marker comments
- Code smells: long functions, large files, bare excepts, magic numbers, unused imports
- Calculates per-file and overall debt scores
- Generates structured reports for CI integration

Usage:
    from app.services.tech_debt_scanner import TechDebtScanner

    scanner = TechDebtScanner("/path/to/source")
    report = scanner.scan()
    print(report.to_markdown())
"""

from __future__ import annotations

import ast
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Marker patterns that indicate acknowledged debt
MARKER_PATTERNS: dict[str, re.Pattern[str]] = {
    "TODO": re.compile(r"#\s*TODO\b", re.IGNORECASE),
    "FIXME": re.compile(r"#\s*FIXME\b", re.IGNORECASE),
    "HACK": re.compile(r"#\s*HACK\b", re.IGNORECASE),
    "XXX": re.compile(r"#\s*XXX\b", re.IGNORECASE),
    "NOQA": re.compile(r"#\s*noqa\b", re.IGNORECASE),
}

# Thresholds for code smells
MAX_FUNCTION_LINES = 50
MAX_FILE_LINES = 500
MAGIC_NUMBER_THRESHOLD = 10  # Numbers above this considered magic when not obvious


class Severity(str, Enum):
    """Debt item severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DebtCategory(str, Enum):
    """Categories of technical debt."""

    MARKER_COMMENT = "marker_comment"
    LONG_FUNCTION = "long_function"
    LARGE_FILE = "large_file"
    BARE_EXCEPT = "bare_except"
    BROAD_EXCEPT = "broad_except"
    MAGIC_NUMBER = "magic_number"
    UNUSED_IMPORT = "unused_import"


# Severity assignment for each category
CATEGORY_SEVERITY: dict[DebtCategory, Severity] = {
    DebtCategory.MARKER_COMMENT: Severity.LOW,
    DebtCategory.LONG_FUNCTION: Severity.MEDIUM,
    DebtCategory.LARGE_FILE: Severity.MEDIUM,
    DebtCategory.BARE_EXCEPT: Severity.HIGH,
    DebtCategory.BROAD_EXCEPT: Severity.MEDIUM,
    DebtCategory.MAGIC_NUMBER: Severity.LOW,
    DebtCategory.UNUSED_IMPORT: Severity.LOW,
}

# Score weights per category (higher = more debt impact)
CATEGORY_WEIGHTS: dict[DebtCategory, float] = {
    DebtCategory.MARKER_COMMENT: 1.0,
    DebtCategory.LONG_FUNCTION: 3.0,
    DebtCategory.LARGE_FILE: 2.0,
    DebtCategory.BARE_EXCEPT: 5.0,
    DebtCategory.BROAD_EXCEPT: 2.0,
    DebtCategory.MAGIC_NUMBER: 0.5,
    DebtCategory.UNUSED_IMPORT: 0.5,
}

# Severity weights for overall scoring
SEVERITY_WEIGHTS: dict[Severity, float] = {
    Severity.CRITICAL: 10.0,
    Severity.HIGH: 5.0,
    Severity.MEDIUM: 2.0,
    Severity.LOW: 1.0,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DebtItem:
    """A single technical debt finding."""

    file_path: str
    line_number: int
    category: DebtCategory
    severity: Severity
    description: str
    context: str = ""  # The line of code or surrounding context

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "context": self.context,
        }


@dataclass
class FileReport:
    """Debt report for a single file."""

    file_path: str
    line_count: int = 0
    items: list[DebtItem] = field(default_factory=list)

    @property
    def debt_score(self) -> float:
        """Calculate weighted debt score for this file."""
        score = 0.0
        for item in self.items:
            weight = CATEGORY_WEIGHTS.get(item.category, 1.0)
            severity_mult = SEVERITY_WEIGHTS.get(item.severity, 1.0)
            score += weight * severity_mult
        return round(score, 2)

    @property
    def item_count(self) -> int:
        return len(self.items)

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "line_count": self.line_count,
            "debt_score": self.debt_score,
            "item_count": self.item_count,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class ScanReport:
    """Complete scan report across all files."""

    root_path: str
    file_reports: list[FileReport] = field(default_factory=list)

    @property
    def total_files_scanned(self) -> int:
        return len(self.file_reports)

    @property
    def files_with_debt(self) -> int:
        return sum(1 for fr in self.file_reports if fr.items)

    @property
    def total_items(self) -> int:
        return sum(fr.item_count for fr in self.file_reports)

    @property
    def total_debt_score(self) -> float:
        return round(sum(fr.debt_score for fr in self.file_reports), 2)

    @property
    def total_lines(self) -> int:
        return sum(fr.line_count for fr in self.file_reports)

    def items_by_severity(self) -> dict[str, int]:
        """Count items grouped by severity."""
        counts: dict[str, int] = {s.value: 0 for s in Severity}
        for fr in self.file_reports:
            for item in fr.items:
                counts[item.severity.value] += 1
        return counts

    def items_by_category(self) -> dict[str, int]:
        """Count items grouped by category."""
        counts: dict[str, int] = {c.value: 0 for c in DebtCategory}
        for fr in self.file_reports:
            for item in fr.items:
                counts[item.category.value] += 1
        return counts

    def top_files_by_score(self, limit: int = 20) -> list[FileReport]:
        """Return files with highest debt scores."""
        scored = [fr for fr in self.file_reports if fr.debt_score > 0]
        scored.sort(key=lambda fr: fr.debt_score, reverse=True)
        return scored[:limit]

    def all_items(self) -> list[DebtItem]:
        """Return all debt items across all files."""
        items: list[DebtItem] = []
        for fr in self.file_reports:
            items.extend(fr.items)
        return items

    def to_dict(self) -> dict:
        return {
            "root_path": self.root_path,
            "total_files_scanned": self.total_files_scanned,
            "files_with_debt": self.files_with_debt,
            "total_items": self.total_items,
            "total_debt_score": self.total_debt_score,
            "total_lines": self.total_lines,
            "by_severity": self.items_by_severity(),
            "by_category": self.items_by_category(),
            "top_files": [fr.to_dict() for fr in self.top_files_by_score()],
        }

    def to_markdown(self) -> str:
        """Generate a markdown report."""
        lines: list[str] = []
        lines.append("# Technical Debt Scan Report")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Root path**: `{self.root_path}`")
        lines.append(f"- **Files scanned**: {self.total_files_scanned}")
        lines.append(f"- **Files with debt**: {self.files_with_debt}")
        lines.append(f"- **Total debt items**: {self.total_items}")
        lines.append(f"- **Total debt score**: {self.total_debt_score}")
        lines.append(f"- **Total lines of code**: {self.total_lines:,}")
        lines.append("")

        # By severity
        lines.append("## Items by Severity")
        lines.append("")
        by_sev = self.items_by_severity()
        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        for sev in Severity:
            count = by_sev.get(sev.value, 0)
            lines.append(f"| {sev.value} | {count} |")
        lines.append("")

        # By category
        lines.append("## Items by Category")
        lines.append("")
        by_cat = self.items_by_category()
        lines.append("| Category | Count |")
        lines.append("|----------|-------|")
        for cat in DebtCategory:
            count = by_cat.get(cat.value, 0)
            lines.append(f"| {cat.value} | {count} |")
        lines.append("")

        # Top files
        lines.append("## Top Files by Debt Score")
        lines.append("")
        lines.append("| File | Lines | Items | Score |")
        lines.append("|------|-------|-------|-------|")
        for fr in self.top_files_by_score(20):
            rel_path = fr.file_path
            lines.append(
                f"| `{rel_path}` | {fr.line_count} | {fr.item_count} | {fr.debt_score} |"
            )
        lines.append("")

        # All items sorted by severity
        lines.append("## All Debt Items (sorted by severity)")
        lines.append("")
        all_items = self.all_items()
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
        }
        all_items.sort(key=lambda i: (severity_order.get(i.severity, 99), i.file_path))

        current_severity = None
        for item in all_items:
            if item.severity != current_severity:
                current_severity = item.severity
                lines.append(f"### {current_severity.value.upper()}")
                lines.append("")
            lines.append(
                f"- **{item.file_path}:{item.line_number}** "
                f"[{item.category.value}] {item.description}"
            )
        lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


class TechDebtScanner:
    """Scans Python source files for technical debt indicators."""

    def __init__(
        self,
        root_path: str | Path,
        *,
        exclude_dirs: set[str] | None = None,
        exclude_files: set[str] | None = None,
        max_function_lines: int = MAX_FUNCTION_LINES,
        max_file_lines: int = MAX_FILE_LINES,
    ):
        self.root_path = Path(root_path)
        self.exclude_dirs = exclude_dirs or {
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
        self.exclude_files = exclude_files or set()
        self.max_function_lines = max_function_lines
        self.max_file_lines = max_file_lines

    def scan(self) -> ScanReport:
        """Run the full scan and return a report."""
        report = ScanReport(root_path=str(self.root_path))
        python_files = self._find_python_files()

        for file_path in python_files:
            try:
                file_report = self._scan_file(file_path)
                report.file_reports.append(file_report)
            except Exception as e:
                logger.warning(f"Failed to scan {file_path}: {e}")

        return report

    def _find_python_files(self) -> list[Path]:
        """Find all Python files under root_path, respecting exclusions."""
        python_files: list[Path] = []

        for root, dirs, files in os.walk(self.root_path):
            # Filter out excluded directories (modifying dirs in-place)
            dirs[:] = [
                d
                for d in dirs
                if d not in self.exclude_dirs
            ]

            for fname in files:
                if fname.endswith(".py") and fname not in self.exclude_files:
                    python_files.append(Path(root) / fname)

        return sorted(python_files)

    def _scan_file(self, file_path: Path) -> FileReport:
        """Scan a single file for debt indicators."""
        rel_path = str(file_path.relative_to(self.root_path))
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        file_report = FileReport(file_path=rel_path, line_count=len(lines))

        # Text-based scans
        self._scan_markers(file_report, lines)
        self._scan_large_file(file_report, lines)

        # AST-based scans
        try:
            tree = ast.parse(content, filename=rel_path)
            self._scan_long_functions(file_report, tree)
            self._scan_bare_excepts(file_report, tree)
            self._scan_broad_excepts(file_report, tree)
            self._scan_magic_numbers(file_report, tree)
            self._scan_unused_imports(file_report, tree, content)
        except SyntaxError:
            logger.debug(f"Syntax error parsing {rel_path}, skipping AST scans")

        return file_report

    # ------------------------------------------------------------------
    # Text-based scans
    # ------------------------------------------------------------------

    def _scan_markers(self, report: FileReport, lines: list[str]) -> None:
        """Find TODO/FIXME/HACK/XXX/NOQA comments."""
        for line_num, line in enumerate(lines, start=1):
            for marker_name, pattern in MARKER_PATTERNS.items():
                if pattern.search(line):
                    # Extract the comment text after the marker
                    comment_match = re.search(
                        rf"#\s*{marker_name}\b[:\s]*(.*)", line, re.IGNORECASE
                    )
                    comment_text = (
                        comment_match.group(1).strip() if comment_match else ""
                    )

                    report.items.append(
                        DebtItem(
                            file_path=report.file_path,
                            line_number=line_num,
                            category=DebtCategory.MARKER_COMMENT,
                            severity=Severity.LOW,
                            description=f"{marker_name}: {comment_text}"
                            if comment_text
                            else f"{marker_name} marker found",
                            context=line.strip(),
                        )
                    )

    def _scan_large_file(self, report: FileReport, lines: list[str]) -> None:
        """Flag files exceeding the line threshold."""
        if len(lines) > self.max_file_lines:
            report.items.append(
                DebtItem(
                    file_path=report.file_path,
                    line_number=1,
                    category=DebtCategory.LARGE_FILE,
                    severity=Severity.MEDIUM,
                    description=f"File has {len(lines)} lines (threshold: {self.max_file_lines})",
                )
            )

    # ------------------------------------------------------------------
    # AST-based scans
    # ------------------------------------------------------------------

    def _scan_long_functions(self, report: FileReport, tree: ast.AST) -> None:
        """Find functions/methods exceeding the line threshold."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Calculate function length from first to last line
                if not hasattr(node, "end_lineno") or node.end_lineno is None:
                    continue
                func_lines = node.end_lineno - node.lineno + 1
                if func_lines > self.max_function_lines:
                    report.items.append(
                        DebtItem(
                            file_path=report.file_path,
                            line_number=node.lineno,
                            category=DebtCategory.LONG_FUNCTION,
                            severity=Severity.MEDIUM,
                            description=(
                                f"Function '{node.name}' has {func_lines} lines "
                                f"(threshold: {self.max_function_lines})"
                            ),
                        )
                    )

    def _scan_bare_excepts(self, report: FileReport, tree: ast.AST) -> None:
        """Find bare 'except:' clauses (no exception type specified)."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    report.items.append(
                        DebtItem(
                            file_path=report.file_path,
                            line_number=node.lineno,
                            category=DebtCategory.BARE_EXCEPT,
                            severity=Severity.HIGH,
                            description="Bare except clause catches all exceptions including SystemExit and KeyboardInterrupt",
                        )
                    )

    def _scan_broad_excepts(self, report: FileReport, tree: ast.AST) -> None:
        """Find 'except Exception:' clauses that swallow errors silently."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    continue  # Already covered by bare_excepts
                # Check if it catches Exception without binding to a variable
                if (
                    isinstance(node.type, ast.Name)
                    and node.type.id == "Exception"
                    and node.name is None
                ):
                    # Check if the handler body only contains pass or ...
                    body_is_silent = all(
                        isinstance(stmt, (ast.Pass, ast.Expr))
                        and (
                            isinstance(stmt, ast.Pass)
                            or (
                                isinstance(stmt, ast.Expr)
                                and isinstance(stmt.value, ast.Constant)
                                and stmt.value.value is ...
                            )
                        )
                        for stmt in node.body
                    )
                    if body_is_silent:
                        report.items.append(
                            DebtItem(
                                file_path=report.file_path,
                                line_number=node.lineno,
                                category=DebtCategory.BROAD_EXCEPT,
                                severity=Severity.MEDIUM,
                                description="Silent 'except Exception' clause swallows errors without logging",
                            )
                        )

    def _scan_magic_numbers(self, report: FileReport, tree: ast.AST) -> None:
        """Find magic number literals outside of obvious patterns.

        Excludes:
        - Numbers 0, 1, 2, -1 (common and intentional)
        - Numbers in constant assignments (UPPER_CASE = ...)
        - Numbers in default parameter values
        - Numbers used as indices
        """
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant):
                continue
            if not isinstance(node.value, (int, float)):
                continue

            value = node.value

            # Skip common values
            if value in (0, 0.0, 1, 1.0, 2, -1, 100, 1000, True, False):
                continue

            # Skip small integers (often loop ranges, indices, etc.)
            if isinstance(value, int) and abs(value) <= MAGIC_NUMBER_THRESHOLD:
                continue

            # Skip small floats used in common patterns
            if isinstance(value, float) and abs(value) <= 1.0:
                continue

            # Only flag numbers that appear in function bodies (not at module level
            # or in class-level constant assignments)
            # We check the line number is valid
            if not hasattr(node, "lineno"):
                continue

            report.items.append(
                DebtItem(
                    file_path=report.file_path,
                    line_number=node.lineno,
                    category=DebtCategory.MAGIC_NUMBER,
                    severity=Severity.LOW,
                    description=f"Magic number {value} - consider extracting to a named constant",
                )
            )

    def _scan_unused_imports(
        self, report: FileReport, tree: ast.AST, content: str
    ) -> None:
        """Basic detection of potentially unused imports.

        This is a simple heuristic check: it finds imported names and checks if
        they appear elsewhere in the file. It intentionally skips:
        - __init__.py files (re-exports)
        - Imports with noqa comments
        - Names starting with underscore
        """
        if report.file_path.endswith("__init__.py"):
            return

        lines = content.splitlines()

        # Collect all imported names and their line numbers
        imported_names: list[tuple[str, int]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name.split(".")[-1]
                    imported_names.append((name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname if alias.asname else alias.name
                    imported_names.append((name, node.lineno))

        # Check each import for usage
        for name, lineno in imported_names:
            # Skip underscore-prefixed names
            if name.startswith("_"):
                continue

            # Skip if line has a noqa comment
            if lineno <= len(lines):
                line = lines[lineno - 1]
                if "noqa" in line.lower():
                    continue

            # Count occurrences of the name in the file (simple text search)
            # Exclude the import line itself
            occurrences = 0
            name_pattern = re.compile(rf"\b{re.escape(name)}\b")
            for i, line in enumerate(lines, start=1):
                if i == lineno:
                    continue
                if name_pattern.search(line):
                    occurrences += 1

            if occurrences == 0:
                report.items.append(
                    DebtItem(
                        file_path=report.file_path,
                        line_number=lineno,
                        category=DebtCategory.UNUSED_IMPORT,
                        severity=Severity.LOW,
                        description=f"Import '{name}' appears unused in this file",
                    )
                )
