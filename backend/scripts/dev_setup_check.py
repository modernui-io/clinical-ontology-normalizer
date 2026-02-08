#!/usr/bin/env python3
"""Development environment validator (CTO-7).

Checks that the local development environment has all required tools,
packages, services, and configuration for the Clinical Ontology Normalizer.

Usage:
    python backend/scripts/dev_setup_check.py
    python backend/scripts/dev_setup_check.py --json   # machine-readable output
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_PYTHON_MIN = (3, 11)

REQUIRED_TOOLS: list[tuple[str, str]] = [
    ("docker", "Docker container runtime"),
    ("docker-compose", "Docker Compose (standalone)"),
    ("git", "Git version control"),
    ("node", "Node.js runtime"),
    ("npm", "Node package manager"),
]

REQUIRED_ENV_VARS: list[str] = [
    "DATABASE_URL",
    "REDIS_URL",
]

CHECK_PORTS: list[tuple[int, str]] = [
    (8000, "FastAPI backend"),
    (3000, "Next.js frontend"),
    (5432, "PostgreSQL"),
    (6379, "Redis"),
]


# ---------------------------------------------------------------------------
# Colour helpers (ANSI; disabled when NO_COLOR or non-tty)
# ---------------------------------------------------------------------------

class _Colour:
    """Terminal colour codes, respecting NO_COLOR / non-tty."""

    def __init__(self) -> None:
        use_colour = (
            sys.stdout.isatty()
            and os.environ.get("NO_COLOR") is None
            and os.environ.get("TERM") != "dumb"
        )
        if use_colour:
            self.GREEN = "\033[32m"
            self.RED = "\033[31m"
            self.YELLOW = "\033[33m"
            self.CYAN = "\033[36m"
            self.BOLD = "\033[1m"
            self.RESET = "\033[0m"
        else:
            self.GREEN = self.RED = self.YELLOW = self.CYAN = ""
            self.BOLD = self.RESET = ""

C = _Colour()

PASS = f"{C.GREEN}[PASS]{C.RESET}"
FAIL = f"{C.RED}[FAIL]{C.RESET}"
WARN = f"{C.YELLOW}[WARN]{C.RESET}"
INFO = f"{C.CYAN}[INFO]{C.RESET}"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: Severity
    message: str = ""
    fix_hint: str = ""


@dataclass
class CheckReport:
    results: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    @property
    def critical_failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed and r.severity == Severity.CRITICAL]

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed and r.severity == Severity.WARNING]

    @property
    def all_critical_passed(self) -> bool:
        return len(self.critical_failures) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.all_critical_passed,
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "severity": r.severity.value,
                    "message": r.message,
                    "fix_hint": r.fix_hint,
                }
                for r in self.results
            ],
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.passed),
                "critical_failures": len(self.critical_failures),
                "warnings": len(self.warnings),
            },
        }


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _run_cmd(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    """Run a command and return (success, stdout_or_stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip() or result.stderr.strip()
        return result.returncode == 0, output
    except FileNotFoundError:
        return False, "command not found"
    except subprocess.TimeoutExpired:
        return False, "command timed out"
    except Exception as exc:
        return False, str(exc)


def check_python_version(report: CheckReport) -> None:
    """Check Python version >= REQUIRED_PYTHON_MIN."""
    v = sys.version_info
    current = f"{v.major}.{v.minor}.{v.micro}"
    ok = (v.major, v.minor) >= REQUIRED_PYTHON_MIN
    report.add(CheckResult(
        name="Python version",
        passed=ok,
        severity=Severity.CRITICAL,
        message=f"Python {current}" if ok else f"Python {current} < {REQUIRED_PYTHON_MIN[0]}.{REQUIRED_PYTHON_MIN[1]}",
        fix_hint="" if ok else f"Install Python >= {REQUIRED_PYTHON_MIN[0]}.{REQUIRED_PYTHON_MIN[1]}",
    ))


def check_system_tools(report: CheckReport) -> None:
    """Check required system tools are on PATH."""
    for tool, description in REQUIRED_TOOLS:
        found = shutil.which(tool) is not None
        version_str = ""
        if found:
            ok, out = _run_cmd([tool, "--version"])
            version_str = out.split("\n")[0] if ok else ""
        report.add(CheckResult(
            name=f"Tool: {tool}",
            passed=found,
            severity=Severity.CRITICAL,
            message=version_str if found else f"{tool} not found",
            fix_hint="" if found else f"Install {description} ({tool})",
        ))


def check_docker_daemon(report: CheckReport) -> None:
    """Check Docker daemon is running."""
    ok, out = _run_cmd(["docker", "info"])
    report.add(CheckResult(
        name="Docker daemon",
        passed=ok,
        severity=Severity.WARNING,
        message="Docker daemon running" if ok else "Docker daemon not reachable",
        fix_hint="" if ok else "Start Docker Desktop or run 'sudo systemctl start docker'",
    ))


def check_env_file(report: CheckReport, project_root: Path) -> None:
    """Check .env file exists and has required variables."""
    env_path = project_root / ".env"
    exists = env_path.is_file()
    report.add(CheckResult(
        name=".env file",
        passed=exists,
        severity=Severity.WARNING,
        message=f"Found {env_path}" if exists else ".env not found",
        fix_hint="" if exists else "Copy .env.example to .env and fill in values",
    ))
    if not exists:
        return

    # Parse key=value lines (simple)
    defined_vars: set[str] = set()
    try:
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                defined_vars.add(key)
    except OSError:
        pass

    for var in REQUIRED_ENV_VARS:
        present = var in defined_vars or os.environ.get(var) is not None
        report.add(CheckResult(
            name=f"Env var: {var}",
            passed=present,
            severity=Severity.WARNING,
            message=f"{var} is set" if present else f"{var} not found in .env or environment",
            fix_hint="" if present else f"Add {var}=... to .env",
        ))


def check_port_available(port: int, label: str) -> CheckResult:
    """Check if a TCP port is available (not in use)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(("127.0.0.1", port))
            in_use = result == 0
        return CheckResult(
            name=f"Port {port} ({label})",
            passed=not in_use,
            severity=Severity.WARNING,
            message=f"Port {port} available" if not in_use else f"Port {port} already in use",
            fix_hint="" if not in_use else f"Free port {port} or change config",
        )
    except OSError:
        return CheckResult(
            name=f"Port {port} ({label})",
            passed=True,
            severity=Severity.INFO,
            message=f"Port {port} check inconclusive",
        )


def check_ports(report: CheckReport) -> None:
    """Check that development ports are available."""
    for port, label in CHECK_PORTS:
        report.add(check_port_available(port, label))


def check_db_connectivity(report: CheckReport) -> None:
    """Check PostgreSQL and Redis connectivity (non-critical)."""
    # PostgreSQL
    pg_ok, pg_out = _run_cmd(["pg_isready", "-h", "localhost", "-p", "5432"])
    report.add(CheckResult(
        name="PostgreSQL connectivity",
        passed=pg_ok,
        severity=Severity.WARNING,
        message="PostgreSQL accepting connections" if pg_ok else "PostgreSQL not reachable",
        fix_hint="" if pg_ok else "Start PostgreSQL or run 'docker compose up -d db'",
    ))

    # Redis
    redis_ok, redis_out = _run_cmd(["redis-cli", "ping"])
    report.add(CheckResult(
        name="Redis connectivity",
        passed=redis_ok and "PONG" in redis_out.upper(),
        severity=Severity.WARNING,
        message="Redis responding" if redis_ok else "Redis not reachable",
        fix_hint="" if redis_ok else "Start Redis or run 'docker compose up -d redis'",
    ))


def check_python_packages(report: CheckReport, project_root: Path) -> None:
    """Check that critical Python packages from requirements.txt are installed."""
    req_path = project_root / "backend" / "requirements.txt"
    if not req_path.is_file():
        report.add(CheckResult(
            name="Python packages",
            passed=False,
            severity=Severity.WARNING,
            message="requirements.txt not found",
            fix_hint="Ensure backend/requirements.txt exists",
        ))
        return

    # Parse package names (ignore versions, extras, comments)
    packages: list[str] = []
    for line in req_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip version specifiers
        for sep in (">=", "<=", "==", "!=", "~=", ">", "<", "[", ";"):
            line = line.split(sep)[0]
        pkg = line.strip()
        if pkg:
            packages.append(pkg)

    missing: list[str] = []
    for pkg in packages:
        # importlib.metadata uses distribution names (replace _ with -)
        normalised = pkg.replace("_", "-").lower()
        try:
            importlib.metadata.distribution(normalised)
        except importlib.metadata.PackageNotFoundError:
            # Also try original name
            try:
                importlib.metadata.distribution(pkg)
            except importlib.metadata.PackageNotFoundError:
                missing.append(pkg)

    ok = len(missing) == 0
    if ok:
        report.add(CheckResult(
            name="Python packages",
            passed=True,
            severity=Severity.CRITICAL,
            message=f"All {len(packages)} packages installed",
        ))
    else:
        report.add(CheckResult(
            name="Python packages",
            passed=False,
            severity=Severity.CRITICAL,
            message=f"{len(missing)}/{len(packages)} packages missing: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}",
            fix_hint="pip install -r backend/requirements.txt",
        ))


def check_git_hooks(report: CheckReport, project_root: Path) -> None:
    """Check if git hooks directory has any hooks installed."""
    hooks_dir = project_root / ".git" / "hooks"
    if not hooks_dir.is_dir():
        report.add(CheckResult(
            name="Git hooks",
            passed=False,
            severity=Severity.INFO,
            message="No .git/hooks directory",
            fix_hint="Initialize git repo",
        ))
        return

    # Look for non-sample hooks
    hook_files = [
        f for f in hooks_dir.iterdir()
        if f.is_file() and not f.name.endswith(".sample")
    ]
    has_hooks = len(hook_files) > 0
    report.add(CheckResult(
        name="Git hooks",
        passed=has_hooks,
        severity=Severity.INFO,
        message=f"{len(hook_files)} hook(s) installed" if has_hooks else "No custom git hooks installed",
        fix_hint="" if has_hooks else "Consider adding pre-commit hooks",
    ))


def check_frontend_deps(report: CheckReport, project_root: Path) -> None:
    """Check that frontend node_modules exists."""
    node_modules = project_root / "frontend" / "node_modules"
    exists = node_modules.is_dir()
    report.add(CheckResult(
        name="Frontend dependencies",
        passed=exists,
        severity=Severity.WARNING,
        message="node_modules present" if exists else "frontend/node_modules not found",
        fix_hint="" if exists else "cd frontend && npm install",
    ))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_all_checks(project_root: Path | None = None) -> CheckReport:
    """Run all development environment checks and return a report."""
    if project_root is None:
        # Walk up from this script to find project root
        project_root = Path(__file__).resolve().parent.parent.parent

    report = CheckReport()

    check_python_version(report)
    check_system_tools(report)
    check_docker_daemon(report)
    check_env_file(report, project_root)
    check_ports(report)
    check_db_connectivity(report)
    check_python_packages(report, project_root)
    check_git_hooks(report, project_root)
    check_frontend_deps(report, project_root)

    return report


def print_report(report: CheckReport) -> None:
    """Print a human-readable report to stdout."""
    print(f"\n{C.BOLD}{'=' * 60}{C.RESET}")
    print(f"{C.BOLD}  Development Environment Check{C.RESET}")
    print(f"{C.BOLD}{'=' * 60}{C.RESET}\n")

    for r in report.results:
        if r.passed:
            icon = PASS
        elif r.severity == Severity.CRITICAL:
            icon = FAIL
        elif r.severity == Severity.WARNING:
            icon = WARN
        else:
            icon = INFO
        print(f"  {icon}  {r.name}: {r.message}")
        if not r.passed and r.fix_hint:
            print(f"         {C.YELLOW}Fix: {r.fix_hint}{C.RESET}")

    # Summary
    total = len(report.results)
    passed = sum(1 for r in report.results if r.passed)
    crit_fail = len(report.critical_failures)
    warns = len(report.warnings)

    print(f"\n{C.BOLD}{'=' * 60}{C.RESET}")
    print(f"  {C.BOLD}Summary:{C.RESET} {passed}/{total} checks passed", end="")
    if crit_fail:
        print(f" | {C.RED}{crit_fail} critical failure(s){C.RESET}", end="")
    if warns:
        print(f" | {C.YELLOW}{warns} warning(s){C.RESET}", end="")
    print()
    print(f"{C.BOLD}{'=' * 60}{C.RESET}\n")

    if report.all_critical_passed:
        print(f"  {C.GREEN}All critical checks passed. Ready to develop!{C.RESET}\n")
    else:
        print(f"  {C.RED}Some critical checks failed. Fix them before proceeding.{C.RESET}\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    json_mode = "--json" in sys.argv

    report = run_all_checks()

    if json_mode:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_report(report)

    sys.exit(0 if report.all_critical_passed else 1)


if __name__ == "__main__":
    main()
