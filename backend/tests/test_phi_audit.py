"""Tests for PHI Audit Service (CISO-7).

Validates detection of PHI patterns in log output, false positive handling,
and redaction recommendations.  Covers all pattern types defined in
``app.services.phi_audit_service``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.services.phi_audit_service import (
    PHIAuditService,
    PHIFinding,
    PHIScanReport,
)


@pytest.fixture
def service() -> PHIAuditService:
    """Return a fresh PHIAuditService instance."""
    return PHIAuditService()


# ======================================================================
# SSN Detection (HIPAA #7)
# ======================================================================


class TestSSNDetection:
    """Test SSN pattern detection."""

    def test_detect_ssn_dashed(self, service: PHIAuditService) -> None:
        """Detect SSN in standard dashed format (XXX-XX-XXXX)."""
        findings = service.audit_line("Patient SSN is 123-45-6789")
        ssn_findings = [f for f in findings if f.phi_type == "SSN"]
        assert len(ssn_findings) >= 1
        assert any("123-45-6789" in f.matched_text for f in ssn_findings)

    def test_detect_ssn_with_label(self, service: PHIAuditService) -> None:
        """Detect SSN with explicit label prefix."""
        findings = service.audit_line("SSN: 123-45-6789 in patient record")
        ssn_findings = [f for f in findings if f.phi_type == "SSN"]
        assert len(ssn_findings) >= 1

    def test_ssn_invalid_area_000(self, service: PHIAuditService) -> None:
        """SSN starting with 000 is invalid -- should not match the dashed pattern."""
        findings = service.audit_line("Number: 000-12-3456")
        ssn_dashed = [
            f
            for f in findings
            if f.phi_type == "SSN"
            and f.description.startswith("US Social Security Number")
        ]
        assert len(ssn_dashed) == 0

    def test_ssn_invalid_area_666(self, service: PHIAuditService) -> None:
        """SSN starting with 666 is invalid -- should not match the dashed pattern."""
        findings = service.audit_line("Number: 666-12-3456")
        ssn_dashed = [
            f
            for f in findings
            if f.phi_type == "SSN"
            and f.description.startswith("US Social Security Number")
        ]
        assert len(ssn_dashed) == 0

    def test_ssn_hipaa_identifier(self, service: PHIAuditService) -> None:
        """SSN findings should reference HIPAA identifier #7."""
        findings = service.audit_line("SSN: 123-45-6789")
        ssn_findings = [f for f in findings if f.phi_type == "SSN"]
        for f in ssn_findings:
            assert f.hipaa_identifier == 7


# ======================================================================
# MRN Detection (HIPAA #8)
# ======================================================================


class TestMRNDetection:
    """Test MRN pattern detection."""

    def test_detect_mrn_dashed(self, service: PHIAuditService) -> None:
        """Detect MRN in dashed format (MRN-123456)."""
        findings = service.audit_line("Processing MRN-12345678 for import")
        mrn_findings = [f for f in findings if f.phi_type == "MRN"]
        assert len(mrn_findings) == 1
        assert "MRN-12345678" in mrn_findings[0].matched_text

    def test_detect_mrn_colon(self, service: PHIAuditService) -> None:
        """Detect MRN with colon separator (MRN: 123456)."""
        findings = service.audit_line("MRN: 987654 lookup complete")
        mrn_findings = [f for f in findings if f.phi_type == "MRN"]
        assert len(mrn_findings) == 1

    def test_detect_mrn_no_separator(self, service: PHIAuditService) -> None:
        """Detect MRN without separator (MRN123456)."""
        findings = service.audit_line("Record MRN654321 updated")
        mrn_findings = [f for f in findings if f.phi_type == "MRN"]
        assert len(mrn_findings) == 1


# ======================================================================
# DOB Detection (HIPAA #3)
# ======================================================================


class TestDOBDetection:
    """Test date of birth pattern detection."""

    def test_detect_dob_slash(self, service: PHIAuditService) -> None:
        """Detect DOB with slash-separated date (DOB: 01/15/1990)."""
        findings = service.audit_line("DOB: 01/15/1990 in patient record")
        dob_findings = [f for f in findings if f.phi_type == "DOB"]
        assert len(dob_findings) == 1

    def test_detect_birth_date_label(self, service: PHIAuditService) -> None:
        """Detect DOB with 'birth date' label."""
        findings = service.audit_line("birth date: 1990-01-15")
        dob_findings = [f for f in findings if f.phi_type == "DOB"]
        assert len(dob_findings) == 1

    def test_no_false_positive_plain_date(self, service: PHIAuditService) -> None:
        """Plain dates without DOB context should not trigger DOB detection."""
        findings = service.audit_line("Processed on 2024-01-15 successfully")
        dob_findings = [f for f in findings if f.phi_type == "DOB"]
        assert len(dob_findings) == 0


# ======================================================================
# Email Detection (HIPAA #6)
# ======================================================================


class TestEmailDetection:
    """Test email address pattern detection."""

    def test_detect_email(self, service: PHIAuditService) -> None:
        """Detect standard email address."""
        findings = service.audit_line("Contact patient at john.doe@example.com")
        email_findings = [f for f in findings if f.phi_type == "EMAIL"]
        assert len(email_findings) == 1
        assert email_findings[0].matched_text == "john.doe@example.com"

    def test_detect_email_subdomain(self, service: PHIAuditService) -> None:
        """Detect email with subdomain."""
        findings = service.audit_line("user@mail.hospital.org in notes")
        email_findings = [f for f in findings if f.phi_type == "EMAIL"]
        assert len(email_findings) == 1


# ======================================================================
# Phone Number Detection (HIPAA #4)
# ======================================================================


class TestPhoneDetection:
    """Test phone number pattern detection."""

    def test_detect_phone_with_label(self, service: PHIAuditService) -> None:
        """Detect phone number with 'phone' label."""
        findings = service.audit_line("phone: (555) 123-4567")
        phone_findings = [f for f in findings if f.phi_type == "PHONE"]
        assert len(phone_findings) >= 1

    def test_detect_phone_parens(self, service: PHIAuditService) -> None:
        """Detect phone with parenthesized area code, no label."""
        findings = service.audit_line("Call (555) 123-4567 for results")
        phone_findings = [f for f in findings if f.phi_type == "PHONE"]
        assert len(phone_findings) >= 1

    def test_no_false_positive_short_number(self, service: PHIAuditService) -> None:
        """Short digit sequences should not trigger phone detection."""
        findings = service.audit_line("Error code 12345 occurred")
        phone_findings = [f for f in findings if f.phi_type == "PHONE"]
        assert len(phone_findings) == 0


# ======================================================================
# Patient Name Detection (HIPAA #1)
# ======================================================================


class TestPatientNameDetection:
    """Test patient name pattern detection."""

    def test_detect_patient_name(self, service: PHIAuditService) -> None:
        """Detect patient name with explicit 'patient:' label."""
        findings = service.audit_line("patient: John Smith admitted today")
        name_findings = [f for f in findings if f.phi_type == "PATIENT_NAME"]
        assert len(name_findings) == 1

    def test_no_false_positive_generic_text(self, service: PHIAuditService) -> None:
        """Generic text without patient label should not trigger name detection."""
        findings = service.audit_line("The system processed 42 records today")
        name_findings = [f for f in findings if f.phi_type == "PATIENT_NAME"]
        assert len(name_findings) == 0


# ======================================================================
# IP Address Detection (HIPAA #15)
# ======================================================================


class TestIPAddressDetection:
    """Test IP address pattern detection and false positive filtering."""

    def test_detect_ip_address(self, service: PHIAuditService) -> None:
        """Detect a valid non-localhost IPv4 address."""
        findings = service.audit_line("Request from 192.168.1.100 for patient data")
        ip_findings = [f for f in findings if f.phi_type == "IP_ADDRESS"]
        assert len(ip_findings) == 1
        assert ip_findings[0].matched_text == "192.168.1.100"

    def test_skip_localhost(self, service: PHIAuditService) -> None:
        """Localhost (127.0.0.1) should be filtered as a false positive."""
        findings = service.audit_line("Listening on 127.0.0.1:8000")
        ip_findings = [f for f in findings if f.phi_type == "IP_ADDRESS"]
        assert len(ip_findings) == 0

    def test_skip_version_string(self, service: PHIAuditService) -> None:
        """Version strings like 'version 1.2.3.4' should not be flagged."""
        findings = service.audit_line("Running application version 1.2.3.4")
        ip_findings = [f for f in findings if f.phi_type == "IP_ADDRESS"]
        assert len(ip_findings) == 0


# ======================================================================
# Account Number Detection (HIPAA #10)
# ======================================================================


class TestAccountNumberDetection:
    """Test account number pattern detection."""

    def test_detect_acct(self, service: PHIAuditService) -> None:
        """Detect account number with ACCT prefix."""
        findings = service.audit_line("Processing ACCT-123456789 billing")
        acct_findings = [f for f in findings if f.phi_type == "ACCOUNT_NUMBER"]
        assert len(acct_findings) == 1


# ======================================================================
# Redaction Recommendations
# ======================================================================


class TestRedactionRecommendations:
    """Test that findings include appropriate redaction recommendations."""

    def test_ssn_redaction(self, service: PHIAuditService) -> None:
        """SSN findings should recommend [SSN-REDACTED]."""
        findings = service.audit_line("SSN: 123-45-6789")
        ssn_findings = [f for f in findings if f.phi_type == "SSN"]
        assert len(ssn_findings) >= 1
        assert ssn_findings[0].redaction_recommendation == "[SSN-REDACTED]"

    def test_email_redaction(self, service: PHIAuditService) -> None:
        """Email findings should recommend [EMAIL-REDACTED]."""
        findings = service.audit_line("user@example.com")
        email_findings = [f for f in findings if f.phi_type == "EMAIL"]
        assert len(email_findings) == 1
        assert email_findings[0].redaction_recommendation == "[EMAIL-REDACTED]"

    def test_get_redaction_recommendation(self, service: PHIAuditService) -> None:
        """get_redaction_recommendation should return the correct string."""
        assert service.get_redaction_recommendation("SSN") == "[SSN-REDACTED]"
        assert service.get_redaction_recommendation("MRN") == "[MRN-REDACTED]"
        assert service.get_redaction_recommendation("UNKNOWN") == "[PHI-REDACTED]"


# ======================================================================
# File Scanning
# ======================================================================


class TestFileScanning:
    """Test log file scanning capabilities."""

    def test_scan_file(self, service: PHIAuditService) -> None:
        """Scan a temporary log file and verify report structure."""
        log_content = (
            "2026-01-01 INFO Starting up\n"
            "2026-01-01 INFO Patient SSN: 123-45-6789\n"
            "2026-01-01 INFO Processing MRN-654321\n"
            "2026-01-01 INFO All clear, no PHI here\n"
            "2026-01-01 INFO Contact john.doe@hospital.org\n"
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as f:
            f.write(log_content)
            tmp_path = f.name

        try:
            report = service.scan_file(tmp_path)

            assert isinstance(report, PHIScanReport)
            assert report.total_lines == 5
            assert report.lines_with_phi >= 3  # SSN, MRN, EMAIL lines
            assert len(report.findings) >= 3
            assert report.source == tmp_path

            # Check type counts
            assert report.phi_type_counts.get("MRN", 0) >= 1
            assert report.phi_type_counts.get("EMAIL", 0) >= 1
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_scan_lines(self, service: PHIAuditService) -> None:
        """Scan a list of in-memory lines."""
        lines = [
            "Normal log line",
            "Patient DOB: 03/15/1985",
            "Another normal line",
        ]
        report = service.scan_lines(lines)
        assert report.total_lines == 3
        assert report.lines_with_phi == 1
        assert report.phi_type_counts.get("DOB", 0) == 1

    def test_scan_file_not_found(self, service: PHIAuditService) -> None:
        """Scanning a nonexistent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            service.scan_file("/nonexistent/path/file.log")


# ======================================================================
# Clean Lines (No False Positives)
# ======================================================================


class TestCleanLines:
    """Test that clean log lines produce no findings."""

    def test_clean_log_line(self, service: PHIAuditService) -> None:
        """Standard application log line should produce no findings."""
        findings = service.audit_line(
            '{"timestamp":"2026-01-01T00:00:00Z","level":"INFO",'
            '"message":"Document processed successfully","module":"fhir_import"}'
        )
        assert len(findings) == 0

    def test_clean_uuid(self, service: PHIAuditService) -> None:
        """UUID strings should not trigger any PHI detection."""
        findings = service.audit_line(
            "Processing document a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        )
        # UUIDs should not be detected as SSN, MRN, etc.
        ssn_findings = [f for f in findings if f.phi_type == "SSN"]
        mrn_findings = [f for f in findings if f.phi_type == "MRN"]
        assert len(ssn_findings) == 0
        assert len(mrn_findings) == 0

    def test_clean_omop_concept_id(self, service: PHIAuditService) -> None:
        """OMOP concept IDs (numeric) should not trigger SSN detection."""
        findings = service.audit_line(
            "Mapped to OMOP concept_id=44054006 (Type 2 Diabetes)"
        )
        ssn_findings = [f for f in findings if f.phi_type == "SSN"]
        assert len(ssn_findings) == 0
