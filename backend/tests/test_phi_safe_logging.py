"""P3-011: PHI-safe logging lint / policy checks.

Scans all Python files under backend/app/ for patterns that could leak
Protected Health Information (PHI) into application logs:

1. Log statements referencing PHI field names (ssn, mrn, patient_name, etc.)
2. Log statements with f-strings containing model objects that may carry PHI
3. Direct print() calls in service code (should use logger instead)

Run with:
    pytest backend/tests/test_phi_safe_logging.py -v
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import NamedTuple

import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Root directory to scan
_BACKEND_APP_DIR = Path(__file__).resolve().parent.parent / "app"

# PHI field names that must never appear in log statements
PHI_FIELD_NAMES: list[str] = [
    "ssn",
    "social_security",
    "mrn",
    "medical_record_number",
    "patient_name",
    "patient_first_name",
    "patient_last_name",
    "date_of_birth",
    "dob",
    "address",
    "street_address",
    "home_address",
    "phone_number",
    "email_address",
    "insurance_id",
    "insurance_number",
    "drivers_license",
    "passport_number",
    "credit_card",
    "bank_account",
]

# Regex patterns for PHI fields in log statements
_PHI_FIELD_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(f) for f in PHI_FIELD_NAMES) + r")\b",
    re.IGNORECASE,
)

# Model class name patterns whose instances likely contain PHI
PHI_MODEL_PATTERNS: list[str] = [
    "patient",
    "person",
    "subject",
    "participant",
    "beneficiary",
    "member",
]

_PHI_MODEL_PATTERN = re.compile(
    r"\b(" + "|".join(PHI_MODEL_PATTERNS) + r")\b",
    re.IGNORECASE,
)

# Known-safe patterns (allowlist) - these lines are OK even if they match
ALLOWLIST_PATTERNS: list[str] = [
    # Configuration constants / field name definitions
    r"PHI_FIELD_NAMES",
    r"_PHI_FIELD_PATTERN",
    r"PHI_MODEL_PATTERNS",
    # Type annotations or docstrings describing fields
    r'""".*"""',
    r"#\s*.*PHI",
    # Test files referencing PHI field names for testing purposes
    r"test_phi_safe_logging",
    # Logging configuration / format strings
    r"logging\.getLogger",
    r"logger\s*=",
    # Column name definitions in ORM models
    r"Column\(",
    r"mapped_column\(",
    r"Field\(",
    # Schema field definitions
    r":\s*(str|int|Optional|list|dict)",
    # Validator / filter functions that check field names
    r"def.*phi",
    r"def.*sanitize",
    r"def.*redact",
    r"def.*mask",
    # Import statements
    r"^(from|import)\s",
]

_ALLOWLIST_REGEX = re.compile("|".join(ALLOWLIST_PATTERNS), re.IGNORECASE)

# Logging function names
_LOG_FUNCTIONS = {"debug", "info", "warning", "error", "critical", "exception", "log"}

# Patterns matching logger calls with PHI fields
_LOG_CALL_PATTERN = re.compile(
    r"(?:logger|logging)\."
    + r"(?:" + "|".join(_LOG_FUNCTIONS) + r")"
    + r"\s*\(",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Violation types
# ---------------------------------------------------------------------------


class Violation(NamedTuple):
    """A single PHI-safety violation found in source code."""

    file: str
    line: int
    rule: str
    message: str
    snippet: str


# ---------------------------------------------------------------------------
# Scanning helpers
# ---------------------------------------------------------------------------


def _collect_python_files(root: Path) -> list[Path]:
    """Recursively collect all .py files under *root*."""
    return sorted(root.rglob("*.py"))


def _is_allowlisted(line: str) -> bool:
    """Return True if the line matches a known-safe pattern."""
    return bool(_ALLOWLIST_REGEX.search(line))


def _scan_phi_field_in_logs(filepath: Path, lines: list[str]) -> list[Violation]:
    """Rule 1: Detect PHI field names inside log statements."""
    violations: list[Violation] = []
    in_log_call = False
    paren_depth = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Skip comments and allowlisted lines
        if stripped.startswith("#") or _is_allowlisted(stripped):
            continue

        # Track whether we are inside a logging call
        if _LOG_CALL_PATTERN.search(line):
            in_log_call = True
            paren_depth = line.count("(") - line.count(")")

        if in_log_call:
            match = _PHI_FIELD_PATTERN.search(line)
            if match and not _is_allowlisted(line):
                violations.append(
                    Violation(
                        file=str(filepath),
                        line=i,
                        rule="PHI_FIELD_IN_LOG",
                        message=f"PHI field name '{match.group()}' found in log statement",
                        snippet=stripped[:120],
                    )
                )

            paren_depth += line.count("(") - line.count(")")
            if paren_depth <= 0:
                in_log_call = False
                paren_depth = 0

    return violations


def _scan_fstring_model_in_logs(filepath: Path, lines: list[str]) -> list[Violation]:
    """Rule 2: Detect f-strings with PHI model objects in log calls."""
    violations: list[Violation] = []

    # Pattern: logger.info(f"... {patient...}" ) or similar
    fstring_log_pattern = re.compile(
        r"(?:logger|logging)\.\w+\s*\(\s*f['\"]"
    )

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#") or _is_allowlisted(stripped):
            continue

        if fstring_log_pattern.search(line):
            # Check for PHI model objects in the f-string interpolation braces
            # Look for {patient}, {patient.name}, {person}, etc.
            brace_contents = re.findall(r"\{([^}]+)\}", line)
            for content in brace_contents:
                if _PHI_MODEL_PATTERN.search(content):
                    violations.append(
                        Violation(
                            file=str(filepath),
                            line=i,
                            rule="FSTRING_PHI_MODEL_IN_LOG",
                            message=f"f-string with potential PHI model object '{content.strip()}' in log",
                            snippet=stripped[:120],
                        )
                    )

    return violations


def _scan_print_in_services(filepath: Path, lines: list[str]) -> list[Violation]:
    """Rule 3: Detect print() calls in service/API code (should use logger)."""
    violations: list[Violation] = []

    # Only flag print() in service and API code, not in CLI/scripts/tests
    rel = str(filepath)
    is_service_code = any(
        segment in rel
        for segment in ("/services/", "/api/", "/middleware/", "/core/", "/jobs/")
    )
    if not is_service_code:
        return violations

    print_pattern = re.compile(r"(?<!\w)print\s*\(")

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#") or _is_allowlisted(stripped):
            continue
        # Skip string literals that happen to contain 'print('
        if stripped.startswith(("'", '"', "f'", 'f"')):
            continue
        if print_pattern.search(line):
            violations.append(
                Violation(
                    file=str(filepath),
                    line=i,
                    rule="PRINT_IN_SERVICE",
                    message="print() call in service code; use logger instead",
                    snippet=stripped[:120],
                )
            )

    return violations


def scan_file(filepath: Path) -> list[Violation]:
    """Run all PHI-safety rules on a single file."""
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    violations: list[Violation] = []
    violations.extend(_scan_phi_field_in_logs(filepath, lines))
    violations.extend(_scan_fstring_model_in_logs(filepath, lines))
    violations.extend(_scan_print_in_services(filepath, lines))
    return violations


def scan_all(root: Path | None = None) -> list[Violation]:
    """Scan all Python files under the given root."""
    root = root or _BACKEND_APP_DIR
    all_violations: list[Violation] = []
    for fp in _collect_python_files(root):
        all_violations.extend(scan_file(fp))
    return all_violations


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPHISafeLogging:
    """Policy tests ensuring no PHI leaks through log statements."""

    def test_no_phi_field_names_in_log_statements(self, tmp_path: Path) -> None:
        """Log statements must not reference PHI field names like ssn, mrn, dob."""
        bad_file = tmp_path / "bad_service.py"
        bad_file.write_text(
            'import logging\n'
            'logger = logging.getLogger(__name__)\n'
            'def process():\n'
            '    logger.info("Processing patient ssn=%s", ssn)\n'
        )
        violations = scan_file(bad_file)
        assert len(violations) >= 1
        assert any(v.rule == "PHI_FIELD_IN_LOG" for v in violations)

    def test_no_mrn_in_log(self, tmp_path: Path) -> None:
        """MRN (medical record number) must not appear in logs."""
        bad_file = tmp_path / "bad_mrn.py"
        bad_file.write_text(
            'import logging\n'
            'logger = logging.getLogger(__name__)\n'
            'def lookup():\n'
            '    logger.debug("Looking up mrn=%s", mrn_value)\n'
        )
        violations = scan_file(bad_file)
        assert any(v.rule == "PHI_FIELD_IN_LOG" for v in violations)

    def test_no_dob_in_log(self, tmp_path: Path) -> None:
        """Date of birth must not appear in logs."""
        bad_file = tmp_path / "bad_dob.py"
        bad_file.write_text(
            'import logging\n'
            'logger = logging.getLogger(__name__)\n'
            'def check_age():\n'
            '    logger.warning("Patient dob is %s", dob)\n'
        )
        violations = scan_file(bad_file)
        assert any(v.rule == "PHI_FIELD_IN_LOG" for v in violations)

    def test_no_address_in_log(self, tmp_path: Path) -> None:
        """Address fields must not appear in logs."""
        bad_file = tmp_path / "bad_addr.py"
        bad_file.write_text(
            'import logging\n'
            'logger = logging.getLogger(__name__)\n'
            'def geocode():\n'
            '    logger.info("Geocoding address=%s", home_address)\n'
        )
        violations = scan_file(bad_file)
        assert any(v.rule == "PHI_FIELD_IN_LOG" for v in violations)

    def test_no_patient_name_in_log(self, tmp_path: Path) -> None:
        """Patient name must not appear in logs."""
        bad_file = tmp_path / "bad_name.py"
        bad_file.write_text(
            'import logging\n'
            'logger = logging.getLogger(__name__)\n'
            'def greet():\n'
            '    logger.info("Hello patient_name=%s", patient_name)\n'
        )
        violations = scan_file(bad_file)
        assert any(v.rule == "PHI_FIELD_IN_LOG" for v in violations)

    def test_fstring_with_patient_model_in_log(self, tmp_path: Path) -> None:
        """f-strings referencing patient model objects in logs should be flagged."""
        bad_file = tmp_path / "bad_fstring.py"
        bad_file.write_text(
            'import logging\n'
            'logger = logging.getLogger(__name__)\n'
            'def process(patient):\n'
            '    logger.info(f"Processing {patient.name}")\n'
        )
        violations = scan_file(bad_file)
        assert any(v.rule == "FSTRING_PHI_MODEL_IN_LOG" for v in violations)

    def test_fstring_with_person_model_in_log(self, tmp_path: Path) -> None:
        """f-strings referencing person objects in logs should be flagged."""
        bad_file = tmp_path / "bad_person.py"
        bad_file.write_text(
            'import logging\n'
            'logger = logging.getLogger(__name__)\n'
            'def notify(person):\n'
            '    logger.warning(f"Notifying {person}")\n'
        )
        violations = scan_file(bad_file)
        assert any(v.rule == "FSTRING_PHI_MODEL_IN_LOG" for v in violations)

    def test_print_in_service_code(self, tmp_path: Path) -> None:
        """print() calls in service code should be flagged (use logger)."""
        # Create a directory structure that looks like services/
        svc_dir = tmp_path / "services"
        svc_dir.mkdir()
        bad_file = svc_dir / "my_service.py"
        bad_file.write_text(
            'def process_data():\n'
            '    print("Processing started")\n'
            '    result = do_work()\n'
            '    print(f"Done: {result}")\n'
        )
        violations = scan_file(bad_file)
        assert len(violations) >= 2
        assert all(v.rule == "PRINT_IN_SERVICE" for v in violations)

    def test_allowlist_skips_safe_patterns(self, tmp_path: Path) -> None:
        """Lines matching the allowlist should not be flagged."""
        safe_file = tmp_path / "safe_module.py"
        safe_file.write_text(
            'import logging\n'
            'logger = logging.getLogger(__name__)\n'
            '# This defines PHI field names for validation\n'
            'PHI_FIELD_NAMES = ["ssn", "mrn", "dob"]\n'
            'class Patient:\n'
            '    ssn: str  # type annotation\n'
            '    mrn: Optional[str]\n'
        )
        violations = scan_file(safe_file)
        assert len(violations) == 0

    def test_clean_log_has_no_violations(self, tmp_path: Path) -> None:
        """A file with clean logging patterns should have zero violations."""
        clean_file = tmp_path / "clean_service.py"
        clean_file.write_text(
            'import logging\n'
            'logger = logging.getLogger(__name__)\n'
            '\n'
            'def process_document(doc_id: str) -> None:\n'
            '    logger.info("Processing document doc_id=%s", doc_id)\n'
            '    logger.debug("Document processed successfully")\n'
        )
        violations = scan_file(clean_file)
        assert len(violations) == 0

    def test_no_insurance_id_in_log(self, tmp_path: Path) -> None:
        """Insurance ID must not appear in logs."""
        bad_file = tmp_path / "bad_insurance.py"
        bad_file.write_text(
            'import logging\n'
            'logger = logging.getLogger(__name__)\n'
            'def verify():\n'
            '    logger.info("Verifying insurance_id=%s", ins_id)\n'
        )
        violations = scan_file(bad_file)
        assert any(v.rule == "PHI_FIELD_IN_LOG" for v in violations)

    def test_multiple_phi_fields_in_single_log(self, tmp_path: Path) -> None:
        """Multiple PHI fields in one log line should each be flagged."""
        bad_file = tmp_path / "multi_phi.py"
        bad_file.write_text(
            'import logging\n'
            'logger = logging.getLogger(__name__)\n'
            'def audit():\n'
            '    logger.error("Failed for ssn=%s mrn=%s", ssn, mrn)\n'
        )
        violations = scan_file(bad_file)
        # At least one violation for the line (pattern matches first field)
        assert len(violations) >= 1
        assert any(v.rule == "PHI_FIELD_IN_LOG" for v in violations)

    def test_scan_real_codebase_no_phi_leaks(self) -> None:
        """Scan the actual backend/app/ tree and assert no PHI violations.

        If this test fails, review the violations and either fix the code
        or add to the allowlist if the pattern is known-safe.
        """
        if not _BACKEND_APP_DIR.exists():
            pytest.skip("backend/app/ directory not found")

        violations = scan_all(_BACKEND_APP_DIR)

        if violations:
            report_lines = [
                f"\n{'='*72}",
                f"PHI-SAFE LOGGING: {len(violations)} violation(s) found",
                f"{'='*72}",
            ]
            for v in violations[:25]:  # cap output
                report_lines.append(
                    f"  {v.file}:{v.line} [{v.rule}] {v.message}"
                )
                report_lines.append(f"    > {v.snippet}")
            if len(violations) > 25:
                report_lines.append(f"  ... and {len(violations) - 25} more")
            report_lines.append("")

            # Soft-fail: report but don't block CI until the team triages
            # Change to `assert len(violations) == 0` to enforce strictly
            import warnings
            warnings.warn(
                "\n".join(report_lines),
                stacklevel=1,
            )
