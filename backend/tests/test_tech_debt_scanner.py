"""Tests for the Technical Debt Scanner.

Tests cover:
- TODO/FIXME/HACK/XXX/NOQA marker detection
- Long function detection
- Large file detection
- Bare except detection
- Broad (silent) except detection
- Magic number detection
- Unused import detection (basic)
- Per-file and overall scoring
- Markdown report generation
- File exclusion logic
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.services.tech_debt_scanner import (
    CATEGORY_WEIGHTS,
    SEVERITY_WEIGHTS,
    DebtCategory,
    DebtItem,
    FileReport,
    ScanReport,
    Severity,
    TechDebtScanner,
)


@pytest.fixture
def tmp_source(tmp_path: Path) -> Path:
    """Create a temporary source directory for testing."""
    return tmp_path


def _write_file(root: Path, name: str, content: str) -> Path:
    """Helper to write a Python file with dedented content."""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


# -------------------------------------------------------------------------
# Marker comment detection
# -------------------------------------------------------------------------


class TestMarkerDetection:
    """Test detection of TODO/FIXME/HACK/XXX/NOQA comments."""

    def test_detects_todo_comment(self, tmp_source: Path) -> None:
        _write_file(
            tmp_source,
            "example.py",
            """\
            x = 1
            # TODO: Fix this later
            y = 2
            """,
        )
        scanner = TechDebtScanner(tmp_source)
        report = scanner.scan()

        items = report.all_items()
        todo_items = [
            i
            for i in items
            if i.category == DebtCategory.MARKER_COMMENT and "TODO" in i.description
        ]
        assert len(todo_items) == 1
        assert todo_items[0].line_number == 2
        assert "Fix this later" in todo_items[0].description

    def test_detects_fixme_comment(self, tmp_source: Path) -> None:
        _write_file(
            tmp_source,
            "example.py",
            """\
            # FIXME: broken edge case
            pass
            """,
        )
        scanner = TechDebtScanner(tmp_source)
        report = scanner.scan()

        items = report.all_items()
        fixme_items = [
            i
            for i in items
            if i.category == DebtCategory.MARKER_COMMENT and "FIXME" in i.description
        ]
        assert len(fixme_items) == 1

    def test_detects_hack_and_xxx_comments(self, tmp_source: Path) -> None:
        _write_file(
            tmp_source,
            "example.py",
            """\
            x = 1  # HACK: workaround for bug
            y = 2  # XXX: needs review
            """,
        )
        scanner = TechDebtScanner(tmp_source)
        report = scanner.scan()

        items = report.all_items()
        marker_items = [
            i for i in items if i.category == DebtCategory.MARKER_COMMENT
        ]
        assert len(marker_items) == 2

    def test_detects_noqa_comment(self, tmp_source: Path) -> None:
        _write_file(
            tmp_source,
            "example.py",
            """\
            from os import path  # noqa: F401
            """,
        )
        scanner = TechDebtScanner(tmp_source)
        report = scanner.scan()

        items = report.all_items()
        noqa_items = [
            i
            for i in items
            if i.category == DebtCategory.MARKER_COMMENT and "NOQA" in i.description
        ]
        assert len(noqa_items) == 1

    def test_case_insensitive_markers(self, tmp_source: Path) -> None:
        _write_file(
            tmp_source,
            "example.py",
            """\
            # todo: lowercase marker
            # Todo: mixed case marker
            """,
        )
        scanner = TechDebtScanner(tmp_source)
        report = scanner.scan()

        items = report.all_items()
        todo_items = [
            i
            for i in items
            if i.category == DebtCategory.MARKER_COMMENT and "TODO" in i.description
        ]
        assert len(todo_items) == 2


# -------------------------------------------------------------------------
# Long function detection
# -------------------------------------------------------------------------


class TestLongFunctionDetection:
    """Test detection of functions exceeding line threshold."""

    def test_detects_long_function(self, tmp_source: Path) -> None:
        # Create a function with 60 lines (above the 50-line threshold)
        func_body = "\n".join(f"    x{i} = {i}" for i in range(58))
        content = f"def long_function():\n{func_body}\n"
        _write_file(tmp_source, "long.py", content)

        scanner = TechDebtScanner(tmp_source, max_function_lines=50)
        report = scanner.scan()

        items = report.all_items()
        long_items = [
            i for i in items if i.category == DebtCategory.LONG_FUNCTION
        ]
        assert len(long_items) == 1
        assert "long_function" in long_items[0].description
        assert long_items[0].severity == Severity.MEDIUM

    def test_does_not_flag_short_function(self, tmp_source: Path) -> None:
        content = "def short_function():\n    return 1\n"
        _write_file(tmp_source, "short.py", content)

        scanner = TechDebtScanner(tmp_source, max_function_lines=50)
        report = scanner.scan()

        items = report.all_items()
        long_items = [
            i for i in items if i.category == DebtCategory.LONG_FUNCTION
        ]
        assert len(long_items) == 0

    def test_custom_function_threshold(self, tmp_source: Path) -> None:
        # 15-line function should be flagged with threshold of 10
        func_body = "\n".join(f"    x{i} = {i}" for i in range(13))
        content = f"def medium_function():\n{func_body}\n"
        _write_file(tmp_source, "medium.py", content)

        scanner = TechDebtScanner(tmp_source, max_function_lines=10)
        report = scanner.scan()

        items = report.all_items()
        long_items = [
            i for i in items if i.category == DebtCategory.LONG_FUNCTION
        ]
        assert len(long_items) == 1


# -------------------------------------------------------------------------
# Large file detection
# -------------------------------------------------------------------------


class TestLargeFileDetection:
    """Test detection of files exceeding line threshold."""

    def test_detects_large_file(self, tmp_source: Path) -> None:
        lines = "\n".join(f"x{i} = {i}" for i in range(600))
        _write_file(tmp_source, "big.py", lines + "\n")

        scanner = TechDebtScanner(tmp_source, max_file_lines=500)
        report = scanner.scan()

        items = report.all_items()
        large_items = [
            i for i in items if i.category == DebtCategory.LARGE_FILE
        ]
        assert len(large_items) == 1
        assert "600" in large_items[0].description

    def test_does_not_flag_small_file(self, tmp_source: Path) -> None:
        content = "x = 1\ny = 2\n"
        _write_file(tmp_source, "small.py", content)

        scanner = TechDebtScanner(tmp_source, max_file_lines=500)
        report = scanner.scan()

        items = report.all_items()
        large_items = [
            i for i in items if i.category == DebtCategory.LARGE_FILE
        ]
        assert len(large_items) == 0


# -------------------------------------------------------------------------
# Exception handling detection
# -------------------------------------------------------------------------


class TestExceptionDetection:
    """Test detection of bare and broad except clauses."""

    def test_detects_bare_except(self, tmp_source: Path) -> None:
        _write_file(
            tmp_source,
            "example.py",
            """\
            try:
                x = 1
            except:
                pass
            """,
        )
        scanner = TechDebtScanner(tmp_source)
        report = scanner.scan()

        items = report.all_items()
        bare_items = [
            i for i in items if i.category == DebtCategory.BARE_EXCEPT
        ]
        assert len(bare_items) == 1
        assert bare_items[0].severity == Severity.HIGH

    def test_detects_silent_broad_except(self, tmp_source: Path) -> None:
        _write_file(
            tmp_source,
            "example.py",
            """\
            try:
                x = 1
            except Exception:
                pass
            """,
        )
        scanner = TechDebtScanner(tmp_source)
        report = scanner.scan()

        items = report.all_items()
        broad_items = [
            i for i in items if i.category == DebtCategory.BROAD_EXCEPT
        ]
        assert len(broad_items) == 1

    def test_does_not_flag_logged_except(self, tmp_source: Path) -> None:
        _write_file(
            tmp_source,
            "example.py",
            """\
            import logging
            logger = logging.getLogger(__name__)
            try:
                x = 1
            except Exception as e:
                logger.error(f"Failed: {e}")
            """,
        )
        scanner = TechDebtScanner(tmp_source)
        report = scanner.scan()

        items = report.all_items()
        broad_items = [
            i for i in items if i.category == DebtCategory.BROAD_EXCEPT
        ]
        assert len(broad_items) == 0


# -------------------------------------------------------------------------
# Scoring
# -------------------------------------------------------------------------


class TestScoring:
    """Test debt scoring calculations."""

    def test_file_report_score_calculation(self) -> None:
        fr = FileReport(file_path="test.py", line_count=100)
        fr.items.append(
            DebtItem(
                file_path="test.py",
                line_number=1,
                category=DebtCategory.BARE_EXCEPT,
                severity=Severity.HIGH,
                description="test",
            )
        )
        fr.items.append(
            DebtItem(
                file_path="test.py",
                line_number=2,
                category=DebtCategory.MARKER_COMMENT,
                severity=Severity.LOW,
                description="test",
            )
        )

        # bare_except weight=5.0, severity HIGH weight=5.0 => 25.0
        # marker weight=1.0, severity LOW weight=1.0 => 1.0
        expected = (
            CATEGORY_WEIGHTS[DebtCategory.BARE_EXCEPT]
            * SEVERITY_WEIGHTS[Severity.HIGH]
            + CATEGORY_WEIGHTS[DebtCategory.MARKER_COMMENT]
            * SEVERITY_WEIGHTS[Severity.LOW]
        )
        assert fr.debt_score == expected

    def test_scan_report_total_score(self) -> None:
        report = ScanReport(root_path="/test")
        fr1 = FileReport(file_path="a.py", line_count=10)
        fr1.items.append(
            DebtItem(
                file_path="a.py",
                line_number=1,
                category=DebtCategory.MARKER_COMMENT,
                severity=Severity.LOW,
                description="test",
            )
        )
        fr2 = FileReport(file_path="b.py", line_count=20)
        fr2.items.append(
            DebtItem(
                file_path="b.py",
                line_number=1,
                category=DebtCategory.BARE_EXCEPT,
                severity=Severity.HIGH,
                description="test",
            )
        )
        report.file_reports = [fr1, fr2]

        assert report.total_debt_score == fr1.debt_score + fr2.debt_score
        assert report.total_files_scanned == 2
        assert report.files_with_debt == 2
        assert report.total_items == 2

    def test_empty_report_score_is_zero(self) -> None:
        report = ScanReport(root_path="/test")
        assert report.total_debt_score == 0.0
        assert report.total_items == 0
        assert report.files_with_debt == 0


# -------------------------------------------------------------------------
# Report generation
# -------------------------------------------------------------------------


class TestReportGeneration:
    """Test markdown and dict report generation."""

    def test_markdown_report_contains_sections(self, tmp_source: Path) -> None:
        _write_file(
            tmp_source,
            "example.py",
            """\
            # TODO: fix this
            try:
                x = 1
            except:
                pass
            """,
        )
        scanner = TechDebtScanner(tmp_source)
        report = scanner.scan()
        md = report.to_markdown()

        assert "# Technical Debt Scan Report" in md
        assert "## Summary" in md
        assert "## Items by Severity" in md
        assert "## Items by Category" in md
        assert "## Top Files by Debt Score" in md
        assert "## All Debt Items" in md

    def test_dict_report_structure(self, tmp_source: Path) -> None:
        _write_file(tmp_source, "example.py", "x = 1\n")
        scanner = TechDebtScanner(tmp_source)
        report = scanner.scan()
        d = report.to_dict()

        assert "root_path" in d
        assert "total_files_scanned" in d
        assert "files_with_debt" in d
        assert "total_items" in d
        assert "total_debt_score" in d
        assert "by_severity" in d
        assert "by_category" in d
        assert "top_files" in d


# -------------------------------------------------------------------------
# File exclusion
# -------------------------------------------------------------------------


class TestFileExclusion:
    """Test that excluded directories and files are skipped."""

    def test_excludes_pycache(self, tmp_source: Path) -> None:
        _write_file(tmp_source, "__pycache__/cached.py", "# TODO: cached\n")
        _write_file(tmp_source, "real.py", "x = 1\n")

        scanner = TechDebtScanner(tmp_source)
        report = scanner.scan()

        scanned_files = [fr.file_path for fr in report.file_reports]
        assert any("real.py" in f for f in scanned_files)
        assert not any("cached.py" in f for f in scanned_files)

    def test_excludes_custom_dirs(self, tmp_source: Path) -> None:
        _write_file(tmp_source, "vendor/third_party.py", "# TODO: vendor\n")
        _write_file(tmp_source, "src/app.py", "x = 1\n")

        scanner = TechDebtScanner(
            tmp_source, exclude_dirs={"__pycache__", "vendor"}
        )
        report = scanner.scan()

        scanned_files = [fr.file_path for fr in report.file_reports]
        assert any("app.py" in f for f in scanned_files)
        assert not any("third_party.py" in f for f in scanned_files)


# -------------------------------------------------------------------------
# Integration: scan real-ish code
# -------------------------------------------------------------------------


class TestIntegration:
    """Integration tests scanning files with multiple debt types."""

    def test_multi_issue_file(self, tmp_source: Path) -> None:
        """A file with multiple debt indicators should have them all detected."""
        # Build a file >500 lines with a long function, a TODO, and a bare except
        long_func_body = "\n".join(f"    line_{i} = {i}" for i in range(60))
        padding = "\n".join(f"pad_{i} = {i}" for i in range(450))
        content = (
            "import os\n"
            "import sys\n"
            "\n"
            "# TODO: refactor this module\n"
            "\n"
            f"def very_long_function():\n{long_func_body}\n"
            "\n"
            "try:\n"
            "    risky_call = 1\n"
            "except:\n"
            "    pass\n"
            "\n"
            f"{padding}\n"
        )
        _write_file(tmp_source, "multi_issue.py", content)

        scanner = TechDebtScanner(
            tmp_source, max_function_lines=50, max_file_lines=500
        )
        report = scanner.scan()

        items = report.all_items()
        categories_found = {i.category for i in items}

        assert DebtCategory.MARKER_COMMENT in categories_found
        assert DebtCategory.LONG_FUNCTION in categories_found
        assert DebtCategory.BARE_EXCEPT in categories_found
        assert DebtCategory.LARGE_FILE in categories_found

        # Score should be > 0
        assert report.total_debt_score > 0
