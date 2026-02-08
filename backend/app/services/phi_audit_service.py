"""PHI Audit Service (CISO-7) -- Detect PHI leakage in log output.

Provides regex-based detection of Protected Health Information (PHI)
patterns in log lines and log files. Designed to complement the
real-time PHIRedactionFilter in ``app.core.logging_config`` by
offering retrospective scanning and reporting capabilities.

Detectable PHI types (mapped to HIPAA 18 identifiers):
    - SSN (identifier #7): xxx-xx-xxxx and 9-digit sequences
    - MRN (identifier #8): MRN-123456, MRN: 123456, MRN123456
    - Date of birth (identifier #3): DOB/birth date patterns with dates
    - Email addresses (identifier #6): standard email patterns
    - Phone numbers (identifier #4): US phone formats
    - Patient names (identifier #1): contextual "patient: Name" patterns
    - IP addresses (identifier #15): IPv4 dotted-quad patterns
    - Account numbers (identifier #10): ACCT-123456 patterns

Usage::

    from app.services.phi_audit_service import PHIAuditService

    service = PHIAuditService()

    # Audit a single log line
    findings = service.audit_line("Patient SSN: 123-45-6789")
    # [PHIFinding(phi_type="SSN", matched_text="123-45-6789", ...)]

    # Scan a log file
    report = service.scan_file("/var/log/app/app.log")
    # PHIScanReport(total_lines=1000, lines_with_phi=3, findings=[...])
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# PHI Pattern Definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PHIPattern:
    """Definition of a PHI detection pattern.

    Attributes:
        phi_type: Human-readable PHI type label (e.g., "SSN", "MRN").
        hipaa_identifier: HIPAA identifier number (1-18).
        pattern: Compiled regex pattern.
        description: Explanation of what this pattern detects.
    """

    phi_type: str
    hipaa_identifier: int
    pattern: re.Pattern[str]
    description: str


# All PHI detection patterns.  Order matters only for reporting; all
# patterns are evaluated against every line.
PHI_PATTERNS: list[PHIPattern] = [
    # ---- SSN (HIPAA #7) ----
    PHIPattern(
        phi_type="SSN",
        hipaa_identifier=7,
        pattern=re.compile(
            r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"
        ),
        description="US Social Security Number (dashed format: XXX-XX-XXXX)",
    ),
    PHIPattern(
        phi_type="SSN",
        hipaa_identifier=7,
        pattern=re.compile(
            r"(?i)\b(?:ssn|social\s*security)[\s:=#]*(\d{3}-?\d{2}-?\d{4})\b"
        ),
        description="SSN with explicit label (SSN: XXXXXXXXX)",
    ),

    # ---- MRN (HIPAA #8) ----
    PHIPattern(
        phi_type="MRN",
        hipaa_identifier=8,
        pattern=re.compile(r"(?i)\bMRN[-:\s]*\d{4,10}\b"),
        description="Medical Record Number (MRN-123456, MRN: 123456)",
    ),

    # ---- Date of Birth (HIPAA #3) ----
    PHIPattern(
        phi_type="DOB",
        hipaa_identifier=3,
        pattern=re.compile(
            r"(?i)\b(?:dob|date\s*of\s*birth|birth\s*date|born)[\s:=]*"
            r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})"
        ),
        description="Date of birth with explicit label",
    ),

    # ---- Email (HIPAA #6) ----
    PHIPattern(
        phi_type="EMAIL",
        hipaa_identifier=6,
        pattern=re.compile(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
        ),
        description="Email address",
    ),

    # ---- Phone Numbers (HIPAA #4) ----
    PHIPattern(
        phi_type="PHONE",
        hipaa_identifier=4,
        pattern=re.compile(
            r"(?i)(?:phone|tel|cell|mobile|fax|contact)[\s:=#]*"
            r"(?:\+?1[\s.-]*)?"
            r"\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}\b"
        ),
        description="US phone number with label (phone: (555) 123-4567)",
    ),
    PHIPattern(
        phi_type="PHONE",
        hipaa_identifier=4,
        pattern=re.compile(
            r"(?<!\w)(?:\+?1[\s.-]*)?\(\d{3}\)[\s.\-]*\d{3}[\s.\-]*\d{4}\b"
        ),
        description="US phone number with parenthesized area code",
    ),

    # ---- Patient Names (HIPAA #1) ----
    PHIPattern(
        phi_type="PATIENT_NAME",
        hipaa_identifier=1,
        pattern=re.compile(
            r"(?i)\b(?:patient|pt|name)[\s:=#]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"
        ),
        description="Patient name with explicit label (patient: John Smith)",
    ),

    # ---- IP Addresses (HIPAA #15) ----
    PHIPattern(
        phi_type="IP_ADDRESS",
        hipaa_identifier=15,
        pattern=re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b"
        ),
        description="IPv4 address",
    ),

    # ---- Account Numbers (HIPAA #10) ----
    PHIPattern(
        phi_type="ACCOUNT_NUMBER",
        hipaa_identifier=10,
        pattern=re.compile(r"(?i)\bACCT[-:\s]?\d{6,12}\b"),
        description="Account number (ACCT-123456789)",
    ),
]

# Patterns that should be excluded from IP address detection
# to reduce false positives (common non-PHI IPs).
_IP_ALLOWLIST: set[str] = {
    "0.0.0.0",
    "127.0.0.1",
    "255.255.255.255",
    "localhost",
}

# Common version-like strings that look like IPs
_IP_FALSE_POSITIVE_PATTERN = re.compile(
    r"(?:version|ver|v)\s*[:=]?\s*\d+\.\d+\.\d+\.\d+"
)


# ---------------------------------------------------------------------------
# Findings and Reports
# ---------------------------------------------------------------------------

@dataclass
class PHIFinding:
    """A single PHI detection finding.

    Attributes:
        phi_type: Type of PHI detected (e.g., "SSN", "MRN").
        hipaa_identifier: HIPAA identifier number.
        matched_text: The text that matched the pattern.
        description: Human-readable description of the pattern.
        line_number: Line number in the file (1-based), or None for single-line audit.
        line_content: The full log line where PHI was found.
        redaction_recommendation: Suggested replacement text.
    """

    phi_type: str
    hipaa_identifier: int
    matched_text: str
    description: str
    line_number: int | None = None
    line_content: str = ""
    redaction_recommendation: str = ""


@dataclass
class PHIScanReport:
    """Summary report from scanning a log file or set of lines.

    Attributes:
        total_lines: Total number of lines scanned.
        lines_with_phi: Number of lines containing at least one PHI finding.
        findings: All individual PHI findings.
        phi_type_counts: Count of findings per PHI type.
        source: Source identifier (file path, stream name, etc.).
    """

    total_lines: int = 0
    lines_with_phi: int = 0
    findings: list[PHIFinding] = field(default_factory=list)
    phi_type_counts: dict[str, int] = field(default_factory=dict)
    source: str = ""


# ---------------------------------------------------------------------------
# Redaction Recommendations
# ---------------------------------------------------------------------------

_REDACTION_MAP: dict[str, str] = {
    "SSN": "[SSN-REDACTED]",
    "MRN": "[MRN-REDACTED]",
    "DOB": "[DOB-REDACTED]",
    "EMAIL": "[EMAIL-REDACTED]",
    "PHONE": "[PHONE-REDACTED]",
    "PATIENT_NAME": "[NAME-REDACTED]",
    "IP_ADDRESS": "[IP-REDACTED]",
    "ACCOUNT_NUMBER": "[ACCT-REDACTED]",
}


# ---------------------------------------------------------------------------
# PHI Audit Service
# ---------------------------------------------------------------------------

class PHIAuditService:
    """Service for detecting PHI leakage in log output.

    Complements the real-time ``PHIRedactionFilter`` in
    ``app.core.logging_config`` by providing retrospective scanning
    and detailed reporting.

    Usage::

        service = PHIAuditService()
        findings = service.audit_line("Patient SSN: 123-45-6789")
        report = service.scan_file("/var/log/app.log")
    """

    def __init__(
        self,
        patterns: list[PHIPattern] | None = None,
        skip_ip_allowlist: bool = True,
    ) -> None:
        """Initialize the PHI audit service.

        Args:
            patterns: Custom pattern list.  Defaults to ``PHI_PATTERNS``.
            skip_ip_allowlist: If True, skip common non-PHI IP addresses
                (localhost, 0.0.0.0, etc.) to reduce false positives.
        """
        self.patterns = patterns if patterns is not None else PHI_PATTERNS
        self.skip_ip_allowlist = skip_ip_allowlist

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def audit_line(self, line: str) -> list[PHIFinding]:
        """Audit a single log line for PHI patterns.

        Args:
            line: A single log line (or any text string).

        Returns:
            List of ``PHIFinding`` objects for each detected PHI element.
            Returns an empty list if no PHI is detected.
        """
        findings: list[PHIFinding] = []

        for phi_pattern in self.patterns:
            for match in phi_pattern.pattern.finditer(line):
                matched_text = match.group(0)

                # Apply false-positive filters
                if phi_pattern.phi_type == "IP_ADDRESS":
                    if self._is_ip_false_positive(matched_text, line):
                        continue

                redaction = _REDACTION_MAP.get(
                    phi_pattern.phi_type, "[PHI-REDACTED]"
                )

                findings.append(
                    PHIFinding(
                        phi_type=phi_pattern.phi_type,
                        hipaa_identifier=phi_pattern.hipaa_identifier,
                        matched_text=matched_text,
                        description=phi_pattern.description,
                        line_content=line,
                        redaction_recommendation=redaction,
                    )
                )

        return findings

    def scan_file(self, file_path: str | Path) -> PHIScanReport:
        """Scan a log file for PHI leakage.

        Reads the file line by line and applies all PHI patterns.
        Handles large files efficiently by streaming.

        Args:
            file_path: Path to the log file to scan.

        Returns:
            ``PHIScanReport`` with findings and summary statistics.

        Raises:
            FileNotFoundError: If the file does not exist.
            PermissionError: If the file cannot be read.
        """
        path = Path(file_path)
        report = PHIScanReport(source=str(path))

        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, start=1):
                report.total_lines += 1
                line = line.rstrip("\n")

                findings = self.audit_line(line)
                if findings:
                    report.lines_with_phi += 1
                    for finding in findings:
                        finding.line_number = line_num
                        report.findings.append(finding)
                        report.phi_type_counts[finding.phi_type] = (
                            report.phi_type_counts.get(finding.phi_type, 0) + 1
                        )

        return report

    def scan_lines(self, lines: list[str]) -> PHIScanReport:
        """Scan a list of log lines for PHI leakage.

        Convenience method for scanning in-memory log lines
        (e.g., from a log buffer or test fixtures).

        Args:
            lines: List of log line strings.

        Returns:
            ``PHIScanReport`` with findings and summary statistics.
        """
        report = PHIScanReport(source="<memory>")

        for line_num, line in enumerate(lines, start=1):
            report.total_lines += 1

            findings = self.audit_line(line)
            if findings:
                report.lines_with_phi += 1
                for finding in findings:
                    finding.line_number = line_num
                    report.findings.append(finding)
                    report.phi_type_counts[finding.phi_type] = (
                        report.phi_type_counts.get(finding.phi_type, 0) + 1
                    )

        return report

    def get_redaction_recommendation(self, phi_type: str) -> str:
        """Get the recommended redaction replacement for a PHI type.

        Args:
            phi_type: PHI type label (e.g., "SSN", "MRN").

        Returns:
            Recommended replacement string.
        """
        return _REDACTION_MAP.get(phi_type, "[PHI-REDACTED]")

    # ------------------------------------------------------------------
    # False Positive Filters
    # ------------------------------------------------------------------

    def _is_ip_false_positive(self, ip_text: str, line: str) -> bool:
        """Check if an IP address match is a false positive.

        Filters out:
        - Localhost and broadcast addresses (allowlist)
        - Version strings that look like IPs (e.g., "version 1.2.3.4")

        Args:
            ip_text: The matched IP address text.
            line: The full log line for context.

        Returns:
            True if the match should be treated as a false positive.
        """
        if not self.skip_ip_allowlist:
            return False

        # Skip common non-PHI addresses
        if ip_text in _IP_ALLOWLIST:
            return True

        # Skip version-like patterns (e.g., "v1.2.3.4", "version 1.2.3.4")
        if _IP_FALSE_POSITIVE_PATTERN.search(line):
            # Check if this specific IP is part of a version string
            ip_pos = line.find(ip_text)
            if ip_pos > 0:
                prefix = line[max(0, ip_pos - 20):ip_pos].lower()
                if any(
                    kw in prefix
                    for kw in ("version", "ver ", "ver:", "v", "release")
                ):
                    return True

        return False
