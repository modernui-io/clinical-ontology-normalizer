"""
Container security tests for DEVOPS-6: Container Hardening.

These tests parse Dockerfiles and docker-compose files to verify
that security best practices are followed. They do not require
Docker to be running -- they are file-content (static) tests.
"""

import os
import re
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent.parent  # repo root


def _read_file(rel_path: str) -> str:
    """Read a file relative to the repo root and return its contents."""
    full_path = ROOT_DIR / rel_path
    assert full_path.exists(), f"File not found: {full_path}"
    return full_path.read_text()


def _load_compose(rel_path: str) -> dict:
    """Load a docker-compose YAML file and return parsed dict."""
    content = _read_file(rel_path)
    return yaml.safe_load(content)


# ---------------------------------------------------------------------------
# Backend Dockerfile (dev) tests
# ---------------------------------------------------------------------------


class TestBackendDockerfile:
    """Tests for backend/Dockerfile security hardening."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.content = _read_file("backend/Dockerfile")

    def test_has_non_root_user(self):
        """Dockerfile must contain a USER directive to run as non-root."""
        assert re.search(r"^USER\s+\S+", self.content, re.MULTILINE), (
            "backend/Dockerfile must have a USER directive"
        )

    def test_user_is_not_root(self):
        """USER must not be root."""
        users = re.findall(r"^USER\s+(\S+)", self.content, re.MULTILINE)
        assert users, "No USER directive found"
        # The last USER directive is what the container runs as
        assert users[-1] != "root", "Container must not run as root"

    def test_has_healthcheck(self):
        """Dockerfile must contain a HEALTHCHECK instruction."""
        assert "HEALTHCHECK" in self.content, (
            "backend/Dockerfile must have a HEALTHCHECK instruction"
        )

    def test_base_image_pinned(self):
        """Base image must use a pinned version tag (not just 'python:3.x')."""
        from_lines = re.findall(r"^FROM\s+(\S+)", self.content, re.MULTILINE)
        assert from_lines, "No FROM directive found"
        for image in from_lines:
            # Strip any AS alias
            base = image.split()[0] if " " in image else image
            if "python:" in base:
                tag = base.split(":")[1] if ":" in base else ""
                # Tag should have at least 3 version parts (e.g., 3.11.11)
                # or be a digest reference
                assert re.match(r"\d+\.\d+\.\d+", tag) or "@sha256:" in base, (
                    f"Python base image should be pinned to patch version, got: {base}"
                )

    def test_python_env_vars_set(self):
        """PYTHONDONTWRITEBYTECODE and PYTHONUNBUFFERED must be set."""
        assert "PYTHONDONTWRITEBYTECODE=1" in self.content, (
            "PYTHONDONTWRITEBYTECODE=1 not found"
        )
        assert "PYTHONUNBUFFERED=1" in self.content, (
            "PYTHONUNBUFFERED=1 not found"
        )

    def test_multi_stage_build(self):
        """Dockerfile should use multi-stage build."""
        from_count = len(re.findall(r"^FROM\s+", self.content, re.MULTILINE))
        assert from_count >= 2, (
            f"Expected multi-stage build (>=2 FROM), got {from_count}"
        )


# ---------------------------------------------------------------------------
# Backend Dockerfile.prod tests
# ---------------------------------------------------------------------------


class TestBackendDockerfileProd:
    """Tests for backend/Dockerfile.prod security hardening."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.content = _read_file("backend/Dockerfile.prod")

    def test_has_non_root_user(self):
        users = re.findall(r"^USER\s+(\S+)", self.content, re.MULTILINE)
        assert users, "No USER directive found"
        assert users[-1] != "root", "Container must not run as root"

    def test_has_healthcheck(self):
        assert "HEALTHCHECK" in self.content

    def test_base_image_pinned(self):
        from_lines = re.findall(r"^FROM\s+(\S+)", self.content, re.MULTILINE)
        for image in from_lines:
            base = image.split()[0]
            if "python:" in base:
                tag = base.split(":")[1] if ":" in base else ""
                assert re.match(r"\d+\.\d+\.\d+", tag) or "@sha256:" in base, (
                    f"Python base image should be pinned: {base}"
                )

    def test_multi_stage_build(self):
        from_count = len(re.findall(r"^FROM\s+", self.content, re.MULTILINE))
        assert from_count >= 2


# ---------------------------------------------------------------------------
# Frontend Dockerfile tests
# ---------------------------------------------------------------------------


class TestFrontendDockerfile:
    """Tests for frontend/Dockerfile security hardening."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.content = _read_file("frontend/Dockerfile")

    def test_has_non_root_user(self):
        users = re.findall(r"^USER\s+(\S+)", self.content, re.MULTILINE)
        assert users, "No USER directive found"
        assert users[-1] != "root", "Container must not run as root"

    def test_has_healthcheck(self):
        assert "HEALTHCHECK" in self.content

    def test_base_image_pinned(self):
        from_lines = re.findall(r"^FROM\s+(\S+)", self.content, re.MULTILINE)
        for image in from_lines:
            base = image.split()[0]
            if "node:" in base:
                tag = base.split(":")[1] if ":" in base else ""
                # Accept e.g. 20.11-alpine (major.minor with variant)
                assert re.match(r"\d+\.\d+", tag), (
                    f"Node base image should be pinned: {base}"
                )

    def test_node_modules_not_in_final_stage(self):
        """The final stage should NOT copy node_modules directly."""
        # Split by FROM to isolate stages; check the last stage
        stages = re.split(r"^FROM\s+", self.content, flags=re.MULTILINE)
        if len(stages) > 1:
            final_stage = stages[-1]
            # Should not have a raw COPY of node_modules
            assert not re.search(
                r"COPY\s+.*node_modules", final_stage
            ), "Final stage should not copy node_modules"


# ---------------------------------------------------------------------------
# .dockerignore tests
# ---------------------------------------------------------------------------


class TestDockerignore:
    """Tests for .dockerignore files."""

    @pytest.mark.parametrize(
        "path",
        ["backend/.dockerignore", "frontend/.dockerignore"],
    )
    def test_dockerignore_exists(self, path):
        full_path = ROOT_DIR / path
        assert full_path.exists(), f"{path} must exist"

    @pytest.mark.parametrize(
        "path,patterns",
        [
            (
                "backend/.dockerignore",
                [".git", "__pycache__", ".env", "tests/", "*.md", ".mypy_cache", ".pytest_cache"],
            ),
            (
                "frontend/.dockerignore",
                [".git", "node_modules", ".env", "*.md"],
            ),
        ],
    )
    def test_dockerignore_excludes_sensitive_files(self, path, patterns):
        content = _read_file(path)
        for pattern in patterns:
            assert pattern in content, (
                f"{path} should exclude '{pattern}'"
            )


# ---------------------------------------------------------------------------
# docker-compose.prod.yml security tests
# ---------------------------------------------------------------------------


class TestDockerComposeProdSecurity:
    """Tests for docker-compose.prod.yml security directives."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.compose = _load_compose("docker-compose.prod.yml")
        self.services = self.compose.get("services", {})

    def test_no_privileged_containers(self):
        """No service should run in privileged mode."""
        for name, svc in self.services.items():
            assert svc.get("privileged") is not True, (
                f"Service '{name}' must not run privileged"
            )

    def test_all_services_have_security_opt(self):
        """All services must have security_opt: [no-new-privileges:true]."""
        for name, svc in self.services.items():
            security_opts = svc.get("security_opt", [])
            assert "no-new-privileges:true" in security_opts, (
                f"Service '{name}' missing security_opt: no-new-privileges:true"
            )

    def test_all_services_have_cap_drop_all(self):
        """All services must drop ALL capabilities."""
        for name, svc in self.services.items():
            cap_drop = svc.get("cap_drop", [])
            assert "ALL" in cap_drop, (
                f"Service '{name}' must have cap_drop: [ALL]"
            )

    def test_nginx_has_net_bind_service(self):
        """Nginx needs NET_BIND_SERVICE capability added back."""
        nginx = self.services.get("nginx", {})
        cap_add = nginx.get("cap_add", [])
        assert "NET_BIND_SERVICE" in cap_add, (
            "nginx must add NET_BIND_SERVICE capability"
        )

    def test_all_services_have_resource_limits(self):
        """All services must define resource limits (memory and cpus)."""
        for name, svc in self.services.items():
            deploy = svc.get("deploy", {})
            resources = deploy.get("resources", {})
            limits = resources.get("limits", {})
            assert "memory" in limits, (
                f"Service '{name}' missing deploy.resources.limits.memory"
            )
            assert "cpus" in limits, (
                f"Service '{name}' missing deploy.resources.limits.cpus"
            )

    def test_all_services_have_healthchecks(self):
        """All services must define a healthcheck."""
        for name, svc in self.services.items():
            assert "healthcheck" in svc, (
                f"Service '{name}' missing healthcheck"
            )

    def test_backend_and_frontend_read_only(self):
        """Backend and frontend services should use read-only root filesystem."""
        for name in ("backend", "frontend"):
            svc = self.services.get(name, {})
            assert svc.get("read_only") is True, (
                f"Service '{name}' should have read_only: true"
            )

    def test_read_only_containers_have_tmpfs(self):
        """Read-only containers must have tmpfs mounts for writable dirs."""
        for name, svc in self.services.items():
            if svc.get("read_only"):
                tmpfs = svc.get("tmpfs", [])
                assert len(tmpfs) > 0, (
                    f"Service '{name}' is read_only but has no tmpfs mounts"
                )
