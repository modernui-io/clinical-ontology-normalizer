"""Docker Compose Analyzer Service (VPE-6).

Parses and analyzes Docker Compose YAML files for production readiness,
checking resource limits, health checks, security directives, logging
configuration, and image pinning.

Usage:
    from app.services.compose_analyzer_service import get_compose_analyzer

    analyzer = get_compose_analyzer()
    result = analyzer.analyze_file("/path/to/docker-compose.prod.yml")
    # or
    result = analyzer.analyze_dict(compose_dict)
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

from app.schemas.infrastructure import (
    ComplianceScore,
    ComplianceSeverity,
    ComposeAnalysis,
    ComposeRecommendation,
    ComposeServiceAnalysis,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Category weights for compliance scoring
# ---------------------------------------------------------------------------

CATEGORY_WEIGHTS: dict[str, float] = {
    "resource_limits": 20.0,
    "restart_policy": 10.0,
    "health_check": 15.0,
    "logging": 10.0,
    "security": 20.0,
    "network_isolation": 10.0,
    "volume_mounts": 5.0,
    "env_secrets": 5.0,
    "image_pinning": 5.0,
}


def _grade_from_score(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


class ComposeAnalyzerService:
    """Analyzes Docker Compose files for production compliance.

    Checks each service for:
    - Resource limits (CPU, memory)
    - Restart policies
    - Health checks
    - Logging configuration
    - Security directives (no_new_privileges, read_only, cap_drop)
    - Network isolation (no host network)
    - Volume mounts (no host path mounts in production)
    - Environment variable handling (secrets vs plain text)
    - Image pinning (no :latest tags)
    """

    def analyze_file(self, file_path: str) -> ComposeAnalysis:
        """Analyze a Docker Compose file from disk.

        Args:
            file_path: Path to docker-compose YAML file.

        Returns:
            ComposeAnalysis with per-service results and compliance score.
        """
        # Use yaml from stdlib-compatible approach (PyYAML)
        try:
            import yaml  # noqa: F811 — PyYAML is already in the project
        except ImportError:
            logger.warning("PyYAML not available, cannot parse compose file")
            return ComposeAnalysis(
                timestamp=datetime.now(timezone.utc),
                file_path=file_path,
                services_analyzed=0,
                service_analyses=[],
                recommendations=[],
                compliance=ComplianceScore(
                    score=0.0, grade="F", category_scores={}
                ),
            )

        if not os.path.exists(file_path):
            logger.warning(f"Compose file not found: {file_path}")
            return ComposeAnalysis(
                timestamp=datetime.now(timezone.utc),
                file_path=file_path,
                services_analyzed=0,
                service_analyses=[],
                recommendations=[],
                compliance=ComplianceScore(
                    score=0.0, grade="F", category_scores={}
                ),
            )

        with open(file_path) as f:
            data = yaml.safe_load(f) or {}

        return self.analyze_dict(data, file_path=file_path)

    def analyze_dict(
        self,
        compose_data: dict[str, Any],
        *,
        file_path: str | None = None,
    ) -> ComposeAnalysis:
        """Analyze a Docker Compose configuration dict.

        Args:
            compose_data: Parsed YAML content as dictionary.
            file_path: Optional source file path for reference.

        Returns:
            ComposeAnalysis with per-service results and compliance score.
        """
        services_dict = compose_data.get("services", {})
        if not services_dict:
            return ComposeAnalysis(
                timestamp=datetime.now(timezone.utc),
                file_path=file_path,
                services_analyzed=0,
                service_analyses=[],
                recommendations=[],
                compliance=ComplianceScore(
                    score=0.0, grade="F", category_scores={}
                ),
            )

        analyses: list[ComposeServiceAnalysis] = []
        recommendations: list[ComposeRecommendation] = []

        for svc_name, svc_config in services_dict.items():
            svc_config = svc_config or {}
            analysis = self._analyze_service(svc_name, svc_config)
            analyses.append(analysis)
            recommendations.extend(
                self._generate_recommendations(svc_name, svc_config, analysis)
            )

        compliance = self._calculate_compliance(analyses)

        return ComposeAnalysis(
            timestamp=datetime.now(timezone.utc),
            file_path=file_path,
            services_analyzed=len(analyses),
            service_analyses=analyses,
            recommendations=recommendations,
            compliance=compliance,
        )

    # ------------------------------------------------------------------
    # Per-service analysis
    # ------------------------------------------------------------------

    def _analyze_service(
        self, name: str, config: dict[str, Any]
    ) -> ComposeServiceAnalysis:
        """Analyze a single service configuration."""
        issues: list[str] = []

        # 1. Resource limits
        has_resource_limits = self._check_resource_limits(config)
        if not has_resource_limits:
            issues.append("Missing resource limits (CPU/memory)")

        # 2. Restart policy
        has_restart = self._check_restart_policy(config)
        if not has_restart:
            issues.append("Missing or inadequate restart policy")

        # 3. Health check
        has_health = self._check_health_check(config)
        if not has_health:
            issues.append("Missing health check")

        # 4. Logging
        has_logging = self._check_logging_config(config)
        if not has_logging:
            issues.append("Missing logging configuration")

        # 5. Security directives
        has_security = self._check_security_directives(config)
        if not has_security:
            issues.append("Missing security directives")

        # 6. Network isolation
        has_network = self._check_network_isolation(config)
        if not has_network:
            issues.append("Using host network mode")

        # 7. Volume mounts
        has_host_volumes = self._check_host_volume_mounts(config)
        if has_host_volumes:
            issues.append("Has host path volume mounts (not recommended for production)")

        # 8. Environment secret handling
        uses_env_secrets = self._check_env_secrets(config)
        if not uses_env_secrets:
            issues.append("Secrets may be exposed as plain-text environment variables")

        # 9. Image pinning
        image_pinned = self._check_image_pinning(config)
        if not image_pinned:
            issues.append("Image tag :latest used (should pin specific version)")

        return ComposeServiceAnalysis(
            service=name,
            has_resource_limits=has_resource_limits,
            has_restart_policy=has_restart,
            has_health_check=has_health,
            has_logging_config=has_logging,
            has_security_directives=has_security,
            has_network_isolation=has_network,
            has_host_volume_mounts=has_host_volumes,
            uses_env_secrets=uses_env_secrets,
            image_pinned=image_pinned,
            issues=issues,
        )

    @staticmethod
    def _check_resource_limits(config: dict[str, Any]) -> bool:
        """Check if service has CPU and memory limits."""
        deploy = config.get("deploy", {})
        resources = deploy.get("resources", {})
        limits = resources.get("limits", {})
        return bool(limits.get("cpus") and limits.get("memory"))

    @staticmethod
    def _check_restart_policy(config: dict[str, Any]) -> bool:
        """Check for restart policy (unless-stopped or always)."""
        # Top-level restart
        restart = config.get("restart", "")
        if restart in ("unless-stopped", "always", "on-failure"):
            return True

        # Deploy restart_policy
        deploy = config.get("deploy", {})
        restart_policy = deploy.get("restart_policy", {})
        condition = restart_policy.get("condition", "")
        return condition in ("on-failure", "any")

    @staticmethod
    def _check_health_check(config: dict[str, Any]) -> bool:
        """Check if health check is defined."""
        return "healthcheck" in config and bool(config["healthcheck"])

    @staticmethod
    def _check_logging_config(config: dict[str, Any]) -> bool:
        """Check for proper logging configuration (json-file driver with limits)."""
        logging_config = config.get("logging", {})
        if not logging_config:
            return False

        driver = logging_config.get("driver", "")
        if driver != "json-file":
            return False

        options = logging_config.get("options", {})
        return bool(options.get("max-size") and options.get("max-file"))

    @staticmethod
    def _check_security_directives(config: dict[str, Any]) -> bool:
        """Check for security directives (no_new_privileges, cap_drop)."""
        security_opts = config.get("security_opt", [])
        has_no_new_privs = any("no-new-privileges" in str(opt) for opt in security_opts)

        cap_drop = config.get("cap_drop", [])
        has_cap_drop = "ALL" in cap_drop

        return has_no_new_privs or has_cap_drop

    @staticmethod
    def _check_network_isolation(config: dict[str, Any]) -> bool:
        """Check that service is NOT using host network."""
        network_mode = config.get("network_mode", "")
        return network_mode != "host"

    @staticmethod
    def _check_host_volume_mounts(config: dict[str, Any]) -> bool:
        """Check if service has host path volume mounts."""
        volumes = config.get("volumes", [])
        if not volumes:
            return False

        for vol in volumes:
            if isinstance(vol, str) and ":" in vol:
                host_path = vol.split(":")[0]
                # Host path mounts start with ./ or / (not named volumes)
                if host_path.startswith(("./", "/", "../")):
                    return True
            elif isinstance(vol, dict):
                vol_type = vol.get("type", "")
                if vol_type == "bind":
                    return True

        return False

    @staticmethod
    def _check_env_secrets(config: dict[str, Any]) -> bool:
        """Check environment variable handling for secrets.

        Returns True if secrets appear to use env substitution or
        Docker secrets, False if passwords/keys are hard-coded.
        """
        env = config.get("environment", {})
        if isinstance(env, list):
            # List form: ["VAR=value", ...]
            for item in env:
                if "=" in item:
                    _key, val = item.split("=", 1)
                    key_lower = _key.lower()
                    if any(s in key_lower for s in ("password", "secret", "key", "token")):
                        # Check if value looks like a hard-coded secret
                        if val and not val.startswith("${") and val not in ("", "true", "false"):
                            return False
        elif isinstance(env, dict):
            for key, val in env.items():
                key_lower = key.lower()
                if any(s in key_lower for s in ("password", "secret", "key", "token")):
                    if isinstance(val, str) and val and not val.startswith("${") and val not in ("true", "false"):
                        return False

        return True

    @staticmethod
    def _check_image_pinning(config: dict[str, Any]) -> bool:
        """Check that image is pinned to a specific version (not :latest)."""
        image = config.get("image", "")
        if not image:
            # Build from Dockerfile — acceptable
            if config.get("build"):
                return True
            return True  # No image field, likely using build context

        if ":latest" in image:
            return False

        # If no tag at all, Docker defaults to :latest
        if ":" not in image:
            return False

        return True

    # ------------------------------------------------------------------
    # Recommendations generator
    # ------------------------------------------------------------------

    def _generate_recommendations(
        self,
        name: str,
        config: dict[str, Any],
        analysis: ComposeServiceAnalysis,
    ) -> list[ComposeRecommendation]:
        """Generate recommendations based on service analysis."""
        recs: list[ComposeRecommendation] = []

        if not analysis.has_resource_limits:
            recs.append(
                ComposeRecommendation(
                    service=name,
                    category="resource_limits",
                    severity=ComplianceSeverity.CRITICAL,
                    current_value="none",
                    recommended_value="deploy.resources.limits with cpus and memory",
                    message=f"Service '{name}' has no resource limits. "
                    "Add CPU and memory limits to prevent resource exhaustion.",
                )
            )

        if not analysis.has_restart_policy:
            recs.append(
                ComposeRecommendation(
                    service=name,
                    category="restart_policy",
                    severity=ComplianceSeverity.WARNING,
                    current_value=config.get("restart", "none"),
                    recommended_value="unless-stopped",
                    message=f"Service '{name}' has no restart policy. "
                    "Set 'restart: unless-stopped' for automatic recovery.",
                )
            )

        if not analysis.has_health_check:
            recs.append(
                ComposeRecommendation(
                    service=name,
                    category="health_check",
                    severity=ComplianceSeverity.CRITICAL,
                    current_value="none",
                    recommended_value="healthcheck with test, interval, and retries",
                    message=f"Service '{name}' has no health check. "
                    "Add a healthcheck to enable automatic recovery.",
                )
            )

        if not analysis.has_logging_config:
            recs.append(
                ComposeRecommendation(
                    service=name,
                    category="logging",
                    severity=ComplianceSeverity.WARNING,
                    current_value="default",
                    recommended_value="json-file driver with max-size and max-file",
                    message=f"Service '{name}' has no logging configuration. "
                    "Configure json-file driver with rotation limits.",
                )
            )

        if not analysis.has_security_directives:
            recs.append(
                ComposeRecommendation(
                    service=name,
                    category="security",
                    severity=ComplianceSeverity.CRITICAL,
                    current_value="none",
                    recommended_value="security_opt: no-new-privileges, cap_drop: ALL",
                    message=f"Service '{name}' has no security hardening. "
                    "Add no-new-privileges and drop all capabilities.",
                )
            )

        if not analysis.has_network_isolation:
            recs.append(
                ComposeRecommendation(
                    service=name,
                    category="network_isolation",
                    severity=ComplianceSeverity.CRITICAL,
                    current_value="host",
                    recommended_value="default bridge or custom network",
                    message=f"Service '{name}' uses host network mode. "
                    "Use Docker bridge networks for isolation.",
                )
            )

        if analysis.has_host_volume_mounts:
            recs.append(
                ComposeRecommendation(
                    service=name,
                    category="volume_mounts",
                    severity=ComplianceSeverity.WARNING,
                    current_value="host bind mounts",
                    recommended_value="named volumes or read-only mounts",
                    message=f"Service '{name}' has host path volume mounts. "
                    "Use named volumes in production.",
                )
            )

        if not analysis.image_pinned:
            recs.append(
                ComposeRecommendation(
                    service=name,
                    category="image_pinning",
                    severity=ComplianceSeverity.WARNING,
                    current_value=config.get("image", ""),
                    recommended_value="Pin to specific version tag",
                    message=f"Service '{name}' uses unpinned image tag. "
                    "Pin images to specific versions for reproducibility.",
                )
            )

        return recs

    # ------------------------------------------------------------------
    # Compliance scoring
    # ------------------------------------------------------------------

    def _calculate_compliance(
        self, analyses: list[ComposeServiceAnalysis]
    ) -> ComplianceScore:
        """Calculate compliance score from service analyses."""
        if not analyses:
            return ComplianceScore(score=0.0, grade="F", category_scores={})

        category_scores: dict[str, float] = {}
        n = len(analyses)

        # Resource limits
        passed = sum(1 for a in analyses if a.has_resource_limits)
        category_scores["resource_limits"] = round((passed / n) * 100, 1)

        # Restart policy
        passed = sum(1 for a in analyses if a.has_restart_policy)
        category_scores["restart_policy"] = round((passed / n) * 100, 1)

        # Health check
        passed = sum(1 for a in analyses if a.has_health_check)
        category_scores["health_check"] = round((passed / n) * 100, 1)

        # Logging
        passed = sum(1 for a in analyses if a.has_logging_config)
        category_scores["logging"] = round((passed / n) * 100, 1)

        # Security
        passed = sum(1 for a in analyses if a.has_security_directives)
        category_scores["security"] = round((passed / n) * 100, 1)

        # Network isolation
        passed = sum(1 for a in analyses if a.has_network_isolation)
        category_scores["network_isolation"] = round((passed / n) * 100, 1)

        # Volume mounts (inverted — not having host mounts is good)
        passed = sum(1 for a in analyses if not a.has_host_volume_mounts)
        category_scores["volume_mounts"] = round((passed / n) * 100, 1)

        # Env secrets
        passed = sum(1 for a in analyses if a.uses_env_secrets)
        category_scores["env_secrets"] = round((passed / n) * 100, 1)

        # Image pinning
        passed = sum(1 for a in analyses if a.image_pinned)
        category_scores["image_pinning"] = round((passed / n) * 100, 1)

        # Weighted overall score
        total_weight = sum(CATEGORY_WEIGHTS.values())
        weighted_sum = sum(
            category_scores.get(cat, 0.0) * weight
            for cat, weight in CATEGORY_WEIGHTS.items()
        )
        overall = round(weighted_sum / total_weight, 1) if total_weight > 0 else 0.0

        return ComplianceScore(
            score=overall,
            grade=_grade_from_score(overall),
            category_scores=category_scores,
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return service stats for prewarm logging."""
        return {"status": "loaded"}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ComposeAnalyzerService | None = None
_lock = threading.Lock()


def get_compose_analyzer() -> ComposeAnalyzerService:
    """Get or create the singleton ComposeAnalyzerService."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ComposeAnalyzerService()
    return _instance


def reset_compose_analyzer() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    _instance = None
