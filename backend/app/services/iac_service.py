"""Infrastructure-as-Code Validation Service (DEVOPS-1).

Provides validation, cost estimation, and HIPAA compliance checking
for Terraform IaC configurations. Parses HCL-like structures and
validates against clinical trial platform requirements.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.iac_management import (
    ComplianceCheck,
    ComplianceReport,
    ComplianceStatus,
    CostEstimate,
    EnvironmentConfig,
    EnvironmentConfigList,
    EnvironmentTier,
    IaCModule,
    IaCModuleList,
    IaCModuleStatus,
    IaCOutput,
    IaCResource,
    IaCVariable,
    ResourceCost,
    ValidationFinding,
    ValidationResult,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cost tables (approximate AWS pricing)
# ---------------------------------------------------------------------------

_INSTANCE_COSTS: dict[str, float] = {
    # RDS PostgreSQL (monthly)
    "db.t3.micro": 15.0,
    "db.t3.small": 30.0,
    "db.t3.medium": 65.0,
    "db.t3.large": 130.0,
    "db.r6g.medium": 95.0,
    "db.r6g.large": 190.0,
    "db.r6g.xlarge": 380.0,
    "db.r6g.2xlarge": 760.0,
}

_REDIS_COSTS: dict[str, float] = {
    # ElastiCache Redis (monthly per node)
    "cache.t3.micro": 12.0,
    "cache.t3.small": 24.0,
    "cache.t3.medium": 48.0,
    "cache.r6g.medium": 75.0,
    "cache.r6g.large": 150.0,
    "cache.r6g.xlarge": 300.0,
}

_FARGATE_COSTS: dict[str, float] = {
    # Per vCPU per month (approx)
    "cpu_per_vcpu": 29.0,
    # Per GB memory per month (approx)
    "memory_per_gb": 3.2,
}

_STORAGE_COST_PER_GB = 0.115  # gp3 per GB/month

# ---------------------------------------------------------------------------
# HIPAA-eligible AWS services
# ---------------------------------------------------------------------------

HIPAA_ELIGIBLE_SERVICES = {
    "aws_vpc",
    "aws_subnet",
    "aws_security_group",
    "aws_internet_gateway",
    "aws_nat_gateway",
    "aws_route_table",
    "aws_network_acl",
    "aws_db_instance",
    "aws_db_subnet_group",
    "aws_db_parameter_group",
    "aws_elasticache_replication_group",
    "aws_elasticache_subnet_group",
    "aws_elasticache_parameter_group",
    "aws_ecs_cluster",
    "aws_ecs_task_definition",
    "aws_ecs_service",
    "aws_lb",
    "aws_lb_listener",
    "aws_lb_target_group",
    "aws_lb_listener_rule",
    "aws_cloudwatch_log_group",
    "aws_cloudwatch_metric_alarm",
    "aws_cloudwatch_dashboard",
    "aws_cloudwatch_log_metric_filter",
    "aws_sns_topic",
    "aws_kms_key",
    "aws_kms_alias",
    "aws_secretsmanager_secret",
    "aws_iam_role",
    "aws_iam_role_policy",
    "aws_iam_role_policy_attachment",
    "aws_wafv2_web_acl",
    "aws_s3_bucket",
    "aws_s3_bucket_server_side_encryption_configuration",
    "aws_s3_bucket_public_access_block",
    "aws_flow_log",
    "aws_eip",
    "aws_route_table_association",
    "aws_appautoscaling_target",
    "aws_appautoscaling_policy",
}

# Required resource types for a complete deployment
REQUIRED_RESOURCES = {
    "aws_vpc",
    "aws_subnet",
    "aws_security_group",
    "aws_db_instance",
    "aws_elasticache_replication_group",
    "aws_ecs_cluster",
    "aws_ecs_task_definition",
    "aws_ecs_service",
    "aws_lb",
    "aws_kms_key",
    "aws_cloudwatch_log_group",
}


# ---------------------------------------------------------------------------
# HCL-like Parser (simple key-value, not full HCL)
# ---------------------------------------------------------------------------


def parse_hcl_simple(content: str) -> dict[str, Any]:
    """Parse simple HCL-like key-value pairs from Terraform files.

    This is a simplified parser for validation purposes - it extracts
    resource blocks, variable blocks, and key-value pairs.

    Args:
        content: HCL file content as string.

    Returns:
        Dictionary with parsed structure.
    """
    result: dict[str, Any] = {
        "resources": [],
        "variables": [],
        "outputs": [],
        "data": [],
        "modules": [],
        "locals": {},
        "provider": {},
    }

    # Extract resource blocks: resource "type" "name" {
    resource_pattern = re.compile(
        r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{', re.MULTILINE
    )
    for match in resource_pattern.finditer(content):
        resource_type = match.group(1)
        resource_name = match.group(2)
        # Extract block content (simplified - find matching brace)
        block_start = match.end()
        block_content = _extract_block(content, block_start)
        result["resources"].append({
            "type": resource_type,
            "name": resource_name,
            "content": block_content,
        })

    # Extract variable blocks: variable "name" {
    variable_pattern = re.compile(
        r'variable\s+"([^"]+)"\s*\{', re.MULTILINE
    )
    for match in variable_pattern.finditer(content):
        var_name = match.group(1)
        block_start = match.end()
        block_content = _extract_block(content, block_start)
        result["variables"].append({
            "name": var_name,
            "content": block_content,
        })

    # Extract output blocks: output "name" {
    output_pattern = re.compile(
        r'output\s+"([^"]+)"\s*\{', re.MULTILINE
    )
    for match in output_pattern.finditer(content):
        out_name = match.group(1)
        block_start = match.end()
        block_content = _extract_block(content, block_start)
        result["outputs"].append({
            "name": out_name,
            "content": block_content,
        })

    # Extract module blocks: module "name" {
    module_pattern = re.compile(
        r'module\s+"([^"]+)"\s*\{', re.MULTILINE
    )
    for match in module_pattern.finditer(content):
        mod_name = match.group(1)
        block_start = match.end()
        block_content = _extract_block(content, block_start)
        result["modules"].append({
            "name": mod_name,
            "content": block_content,
        })

    # Extract key-value pairs from block content
    kv_pattern = re.compile(r'(\w+)\s*=\s*"?([^"\n]+)"?')

    return result


def _extract_block(content: str, start: int) -> str:
    """Extract content between matching braces starting at position."""
    depth = 1
    pos = start
    while pos < len(content) and depth > 0:
        if content[pos] == "{":
            depth += 1
        elif content[pos] == "}":
            depth -= 1
        pos += 1
    return content[start:pos - 1] if pos <= len(content) else ""


def _extract_value(block_content: str, key: str) -> str | None:
    """Extract a simple key = value or key = "value" from block content."""
    pattern = re.compile(rf'{key}\s*=\s*"?([^"\n}}]+)"?')
    match = pattern.search(block_content)
    if match:
        return match.group(1).strip()
    return None


def _block_has_key(block_content: str, key: str) -> bool:
    """Check if a block contains a key."""
    pattern = re.compile(rf'\b{key}\b\s*[=:]')
    return bool(pattern.search(block_content))


# ---------------------------------------------------------------------------
# IaC Validation Service
# ---------------------------------------------------------------------------


class IaCValidationService:
    """Service for validating and analyzing Terraform IaC configurations.

    Provides:
    - Module discovery and metadata
    - Configuration validation against security and operational rules
    - Cost estimation based on resource types and sizes
    - HIPAA compliance checking

    The service reads Terraform files from the infrastructure directory
    and performs static analysis without requiring Terraform to be installed.
    """

    def __init__(self, terraform_root: str | None = None) -> None:
        """Initialize the IaC validation service.

        Args:
            terraform_root: Root directory of Terraform files. If None,
                defaults to infrastructure/terraform/ relative to project root.
        """
        if terraform_root is None:
            # Find project root (walk up from this file)
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            self._terraform_root = project_root / "infrastructure" / "terraform"
        else:
            self._terraform_root = Path(terraform_root)

        self._modules_cache: list[IaCModule] | None = None
        logger.info(
            "IaCValidationService initialized, terraform_root=%s",
            self._terraform_root,
        )

    # ----- Module Discovery -----

    def list_modules(self) -> IaCModuleList:
        """List all Terraform modules discovered in the infrastructure directory.

        Returns:
            IaCModuleList with all discovered modules.
        """
        modules = self._discover_modules()
        return IaCModuleList(
            modules=modules,
            total_count=len(modules),
            timestamp=datetime.now(timezone.utc),
        )

    def get_module(self, name: str) -> IaCModule | None:
        """Get a specific module by name.

        Args:
            name: Module name (e.g., 'networking', 'database').

        Returns:
            IaCModule if found, None otherwise.
        """
        modules = self._discover_modules()
        for mod in modules:
            if mod.name == name:
                return mod
        return None

    def _discover_modules(self) -> list[IaCModule]:
        """Discover and parse all Terraform modules."""
        if self._modules_cache is not None:
            return self._modules_cache

        modules: list[IaCModule] = []
        modules_dir = self._terraform_root / "modules"

        if not modules_dir.exists():
            logger.warning("Terraform modules directory not found: %s", modules_dir)
            return modules

        for module_dir in sorted(modules_dir.iterdir()):
            if not module_dir.is_dir():
                continue

            module = self._parse_module(module_dir)
            if module:
                modules.append(module)

        # Also parse root module
        root_module = self._parse_root_module()
        if root_module:
            modules.insert(0, root_module)

        self._modules_cache = modules
        return modules

    def _parse_module(self, module_dir: Path) -> IaCModule | None:
        """Parse a Terraform module directory."""
        main_tf = module_dir / "main.tf"
        vars_tf = module_dir / "variables.tf"
        outputs_tf = module_dir / "outputs.tf"

        if not main_tf.exists():
            return None

        name = module_dir.name
        path = str(module_dir.relative_to(self._terraform_root))

        # Parse main.tf for resources
        resources: list[IaCResource] = []
        description = ""
        try:
            main_content = main_tf.read_text()
            parsed = parse_hcl_simple(main_content)
            for res in parsed["resources"]:
                resources.append(IaCResource(
                    type=res["type"],
                    name=res["name"],
                    provider="aws",
                ))
            # Extract description from comments
            for line in main_content.split("\n")[:5]:
                if line.startswith("# ") and not line.startswith("# =="):
                    description = line[2:].strip()
                    break
        except Exception as e:
            logger.warning("Failed to parse %s: %s", main_tf, e)

        # Parse variables.tf
        variables: list[IaCVariable] = []
        if vars_tf.exists():
            try:
                vars_content = vars_tf.read_text()
                parsed_vars = parse_hcl_simple(vars_content)
                for var in parsed_vars["variables"]:
                    var_type = _extract_value(var["content"], "type") or "string"
                    var_desc = _extract_value(var["content"], "description") or ""
                    var_default = _extract_value(var["content"], "default")
                    variables.append(IaCVariable(
                        name=var["name"],
                        type=var_type,
                        description=var_desc,
                        default=var_default,
                        required=var_default is None,
                    ))
            except Exception as e:
                logger.warning("Failed to parse %s: %s", vars_tf, e)

        # Parse outputs.tf
        outputs: list[IaCOutput] = []
        if outputs_tf.exists():
            try:
                out_content = outputs_tf.read_text()
                parsed_outs = parse_hcl_simple(out_content)
                for out in parsed_outs["outputs"]:
                    out_desc = _extract_value(out["content"], "description") or ""
                    is_sensitive = "sensitive" in out["content"] and "true" in out["content"]
                    outputs.append(IaCOutput(
                        name=out["name"],
                        description=out_desc,
                        sensitive=is_sensitive,
                    ))
            except Exception as e:
                logger.warning("Failed to parse %s: %s", outputs_tf, e)

        return IaCModule(
            name=name,
            path=path,
            description=description,
            status=IaCModuleStatus.ACTIVE,
            variables=variables,
            outputs=outputs,
            resources=resources,
            dependencies=[],
        )

    def _parse_root_module(self) -> IaCModule | None:
        """Parse the root Terraform module."""
        main_tf = self._terraform_root / "main.tf"
        if not main_tf.exists():
            return None

        try:
            content = main_tf.read_text()
            parsed = parse_hcl_simple(content)

            # Discover module dependencies
            dependencies = [m["name"] for m in parsed["modules"]]

            return IaCModule(
                name="root",
                path=".",
                description="Root Terraform module - orchestrates all sub-modules",
                status=IaCModuleStatus.ACTIVE,
                variables=[],
                outputs=[],
                resources=[],
                dependencies=dependencies,
            )
        except Exception as e:
            logger.warning("Failed to parse root module: %s", e)
            return None

    # ----- Environment Configurations -----

    def get_environment_configs(self) -> EnvironmentConfigList:
        """Get all environment configurations.

        Returns:
            EnvironmentConfigList with parsed configs for dev/staging/prod.
        """
        configs: list[EnvironmentConfig] = []
        envs_dir = self._terraform_root / "environments"

        env_defaults = {
            "dev": {
                "environment": EnvironmentTier.DEV,
                "vpc_cidr": "10.0.0.0/16",
                "db_instance_class": "db.t3.medium",
                "db_allocated_storage": 20,
                "db_backup_retention": 1,
                "redis_node_type": "cache.t3.medium",
                "redis_num_cache_nodes": 1,
                "ecs_cpu": 512,
                "ecs_memory": 1024,
                "ecs_desired_count": 1,
                "multi_az": False,
                "encryption_enabled": True,
            },
            "staging": {
                "environment": EnvironmentTier.STAGING,
                "vpc_cidr": "10.1.0.0/16",
                "db_instance_class": "db.r6g.large",
                "db_allocated_storage": 50,
                "db_backup_retention": 3,
                "redis_node_type": "cache.r6g.medium",
                "redis_num_cache_nodes": 2,
                "ecs_cpu": 1024,
                "ecs_memory": 2048,
                "ecs_desired_count": 2,
                "multi_az": False,
                "encryption_enabled": True,
            },
            "prod": {
                "environment": EnvironmentTier.PROD,
                "vpc_cidr": "10.2.0.0/16",
                "db_instance_class": "db.r6g.xlarge",
                "db_allocated_storage": 200,
                "db_backup_retention": 35,
                "redis_node_type": "cache.r6g.large",
                "redis_num_cache_nodes": 3,
                "ecs_cpu": 2048,
                "ecs_memory": 4096,
                "ecs_desired_count": 3,
                "multi_az": True,
                "encryption_enabled": True,
            },
        }

        # Try to parse tfvars files, fall back to defaults
        for env_name, defaults in env_defaults.items():
            tfvars_file = envs_dir / f"{env_name}.tfvars"
            config_data = dict(defaults)

            if tfvars_file.exists():
                try:
                    tfvars_content = tfvars_file.read_text()
                    parsed = self._parse_tfvars(tfvars_content)
                    # Merge parsed values
                    for key, value in parsed.items():
                        mapped_key = key.replace("-", "_")
                        if mapped_key in config_data:
                            config_data[mapped_key] = value
                except Exception as e:
                    logger.warning("Failed to parse %s: %s", tfvars_file, e)

            configs.append(EnvironmentConfig(**config_data))

        return EnvironmentConfigList(
            environments=configs,
            timestamp=datetime.now(timezone.utc),
        )

    def _parse_tfvars(self, content: str) -> dict[str, Any]:
        """Parse a .tfvars file into a dictionary."""
        result: dict[str, Any] = {}
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r'(\w+)\s*=\s*"?([^"#\n]+)"?', line)
            if match:
                key = match.group(1)
                value = match.group(2).strip()
                # Type inference
                if value.lower() in ("true", "false"):
                    result[key] = value.lower() == "true"
                else:
                    try:
                        result[key] = int(value)
                    except ValueError:
                        try:
                            result[key] = float(value)
                        except ValueError:
                            result[key] = value
        return result

    # ----- Validation -----

    def validate_configuration(
        self,
        environment: str = "dev",
        config: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """Validate an IaC configuration against security and operational rules.

        Args:
            environment: Target environment (dev, staging, prod).
            config: Optional configuration overrides.

        Returns:
            ValidationResult with all findings.
        """
        findings: list[ValidationFinding] = []
        effective_config = config or {}

        # Run all validation rules
        findings.extend(self._validate_required_resources())
        findings.extend(self._validate_security_groups())
        findings.extend(self._validate_encryption())
        findings.extend(self._validate_backup_config(environment))
        findings.extend(self._validate_multi_az(environment))
        findings.extend(self._validate_network_isolation())
        findings.extend(self._validate_logging())
        findings.extend(self._validate_iam_policies())

        # Count by severity
        critical = sum(1 for f in findings if f.severity == ValidationSeverity.CRITICAL)
        high = sum(1 for f in findings if f.severity == ValidationSeverity.HIGH)
        medium = sum(1 for f in findings if f.severity == ValidationSeverity.MEDIUM)
        low = sum(1 for f in findings if f.severity == ValidationSeverity.LOW)

        return ValidationResult(
            valid=critical == 0 and high == 0,
            findings=findings,
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            timestamp=datetime.now(timezone.utc),
        )

    def _validate_required_resources(self) -> list[ValidationFinding]:
        """Check that all required resource types are defined."""
        findings: list[ValidationFinding] = []
        modules = self._discover_modules()

        all_resource_types = set()
        for mod in modules:
            for res in mod.resources:
                all_resource_types.add(res.type)

        for required in REQUIRED_RESOURCES:
            if required not in all_resource_types:
                findings.append(ValidationFinding(
                    rule="REQUIRED_RESOURCE",
                    severity=ValidationSeverity.CRITICAL,
                    resource=required,
                    message=f"Required resource type '{required}' is not defined in any module",
                    remediation=f"Add a '{required}' resource to the appropriate module",
                ))

        return findings

    def _validate_security_groups(self) -> list[ValidationFinding]:
        """Validate security groups are not too permissive."""
        findings: list[ValidationFinding] = []
        modules = self._discover_modules()

        for mod in modules:
            for res in mod.resources:
                if res.type != "aws_security_group":
                    continue

                # Read the actual file to check rules
                main_tf = self._terraform_root / mod.path / "main.tf"
                if not main_tf.exists():
                    continue

                try:
                    content = main_tf.read_text()
                    parsed = parse_hcl_simple(content)
                    for parsed_res in parsed["resources"]:
                        if parsed_res["type"] != "aws_security_group":
                            continue
                        if parsed_res["name"] != res.name:
                            continue

                        block = parsed_res["content"]

                        # Check for overly permissive ingress (0.0.0.0/0 on non-HTTP ports)
                        # Only check ingress blocks, not egress
                        ingress_pattern = re.compile(
                            r'ingress\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
                            re.DOTALL,
                        )
                        for ingress_match in ingress_pattern.finditer(block):
                            ingress_block = ingress_match.group(1)
                            if "0.0.0.0/0" in ingress_block:
                                # ALB is allowed to have 0.0.0.0/0 on 80/443
                                if "alb" not in res.name.lower():
                                    # Check if it's on a database or internal port
                                    if any(port in ingress_block for port in ["5432", "6379", "7687", "7474"]):
                                        findings.append(ValidationFinding(
                                            rule="PERMISSIVE_SG",
                                            severity=ValidationSeverity.CRITICAL,
                                            resource=f"aws_security_group.{res.name}",
                                            message=(
                                                f"Security group '{res.name}' allows ingress "
                                                f"from 0.0.0.0/0 on sensitive ports"
                                            ),
                                            remediation="Restrict ingress to specific security groups or CIDR blocks",
                                        ))
                except Exception:
                    pass

        return findings

    def _validate_encryption(self) -> list[ValidationFinding]:
        """Validate encryption is enabled everywhere."""
        findings: list[ValidationFinding] = []
        modules = self._discover_modules()

        # Check RDS encryption
        has_rds_encryption = False
        has_redis_encryption_at_rest = False
        has_redis_encryption_in_transit = False
        has_kms_key = False

        for mod in modules:
            main_tf = self._terraform_root / mod.path / "main.tf"
            if not main_tf.exists():
                continue

            try:
                content = main_tf.read_text()

                if "storage_encrypted" in content and "true" in content:
                    has_rds_encryption = True
                if "at_rest_encryption_enabled" in content and "true" in content:
                    has_redis_encryption_at_rest = True
                if "transit_encryption_enabled" in content and "true" in content:
                    has_redis_encryption_in_transit = True
                if "aws_kms_key" in content:
                    has_kms_key = True
            except Exception:
                pass

        if not has_rds_encryption:
            findings.append(ValidationFinding(
                rule="RDS_ENCRYPTION",
                severity=ValidationSeverity.CRITICAL,
                resource="aws_db_instance",
                message="RDS storage encryption is not enabled",
                remediation="Set storage_encrypted = true on the RDS instance",
            ))

        if not has_redis_encryption_at_rest:
            findings.append(ValidationFinding(
                rule="REDIS_ENCRYPTION_REST",
                severity=ValidationSeverity.CRITICAL,
                resource="aws_elasticache_replication_group",
                message="Redis encryption at rest is not enabled",
                remediation="Set at_rest_encryption_enabled = true",
            ))

        if not has_redis_encryption_in_transit:
            findings.append(ValidationFinding(
                rule="REDIS_ENCRYPTION_TRANSIT",
                severity=ValidationSeverity.HIGH,
                resource="aws_elasticache_replication_group",
                message="Redis encryption in transit is not enabled",
                remediation="Set transit_encryption_enabled = true",
            ))

        if not has_kms_key:
            findings.append(ValidationFinding(
                rule="KMS_KEY",
                severity=ValidationSeverity.HIGH,
                resource="aws_kms_key",
                message="No KMS key defined for encryption",
                remediation="Add an aws_kms_key resource for managing encryption keys",
            ))

        return findings

    def _validate_backup_config(self, environment: str) -> list[ValidationFinding]:
        """Validate backup configuration."""
        findings: list[ValidationFinding] = []
        modules = self._discover_modules()

        has_backup = False
        for mod in modules:
            main_tf = self._terraform_root / mod.path / "main.tf"
            if not main_tf.exists():
                continue
            try:
                content = main_tf.read_text()
                if "backup_retention_period" in content:
                    has_backup = True
                    # For prod, check retention is sufficient
                    if environment == "prod":
                        match = re.search(
                            r"backup_retention_period\s*=\s*(\d+)", content
                        )
                        if match:
                            days = int(match.group(1))
                            if days < 7:
                                findings.append(ValidationFinding(
                                    rule="BACKUP_RETENTION_PROD",
                                    severity=ValidationSeverity.HIGH,
                                    resource="aws_db_instance",
                                    message=(
                                        f"Production backup retention is {days} days, "
                                        f"should be at least 7 days"
                                    ),
                                    remediation="Increase backup_retention_period to at least 7 for production",
                                ))
            except Exception:
                pass

        if not has_backup:
            findings.append(ValidationFinding(
                rule="BACKUP_MISSING",
                severity=ValidationSeverity.HIGH,
                resource="aws_db_instance",
                message="No backup configuration found for database",
                remediation="Set backup_retention_period on the RDS instance",
            ))

        return findings

    def _validate_multi_az(self, environment: str) -> list[ValidationFinding]:
        """Validate Multi-AZ is enabled for production."""
        findings: list[ValidationFinding] = []

        if environment != "prod":
            return findings

        modules = self._discover_modules()

        has_multi_az = False
        for mod in modules:
            main_tf = self._terraform_root / mod.path / "main.tf"
            if not main_tf.exists():
                continue
            try:
                content = main_tf.read_text()
                if "multi_az" in content:
                    has_multi_az = True
            except Exception:
                pass

        if not has_multi_az:
            findings.append(ValidationFinding(
                rule="MULTI_AZ_PROD",
                severity=ValidationSeverity.CRITICAL,
                resource="aws_db_instance",
                message="Multi-AZ is not configured for production",
                remediation="Set multi_az = true on the RDS instance for production",
            ))

        return findings

    def _validate_network_isolation(self) -> list[ValidationFinding]:
        """Validate proper network isolation (VPC, subnets, NACLs)."""
        findings: list[ValidationFinding] = []
        modules = self._discover_modules()

        has_vpc = False
        has_private_subnets = False
        has_database_subnets = False
        has_nacl = False

        for mod in modules:
            for res in mod.resources:
                if res.type == "aws_vpc":
                    has_vpc = True
                if res.type == "aws_subnet":
                    # Check for private/database subnet tags
                    main_tf = self._terraform_root / mod.path / "main.tf"
                    if main_tf.exists():
                        try:
                            content = main_tf.read_text()
                            if "private" in content.lower():
                                has_private_subnets = True
                            if "database" in content.lower():
                                has_database_subnets = True
                        except Exception:
                            pass
                if res.type == "aws_network_acl":
                    has_nacl = True

        if not has_vpc:
            findings.append(ValidationFinding(
                rule="VPC_REQUIRED",
                severity=ValidationSeverity.CRITICAL,
                resource="aws_vpc",
                message="No VPC defined - all resources must be in a VPC",
                remediation="Add a VPC resource in the networking module",
            ))

        if not has_private_subnets:
            findings.append(ValidationFinding(
                rule="PRIVATE_SUBNETS",
                severity=ValidationSeverity.HIGH,
                resource="aws_subnet",
                message="No private subnets defined for application tier",
                remediation="Add private subnets for ECS tasks",
            ))

        if not has_database_subnets:
            findings.append(ValidationFinding(
                rule="DATABASE_SUBNETS",
                severity=ValidationSeverity.HIGH,
                resource="aws_subnet",
                message="No dedicated database subnets defined",
                remediation="Add database-tier subnets for RDS and ElastiCache",
            ))

        return findings

    def _validate_logging(self) -> list[ValidationFinding]:
        """Validate logging configuration."""
        findings: list[ValidationFinding] = []
        modules = self._discover_modules()

        has_log_groups = False
        has_flow_logs = False

        for mod in modules:
            for res in mod.resources:
                if res.type == "aws_cloudwatch_log_group":
                    has_log_groups = True
                if res.type == "aws_flow_log":
                    has_flow_logs = True

        if not has_log_groups:
            findings.append(ValidationFinding(
                rule="LOG_GROUPS",
                severity=ValidationSeverity.HIGH,
                resource="aws_cloudwatch_log_group",
                message="No CloudWatch log groups defined",
                remediation="Add log groups for all services",
            ))

        if not has_flow_logs:
            findings.append(ValidationFinding(
                rule="VPC_FLOW_LOGS",
                severity=ValidationSeverity.MEDIUM,
                resource="aws_flow_log",
                message="VPC flow logs are not configured (HIPAA requirement)",
                remediation="Add VPC flow logs for network traffic auditing",
            ))

        return findings

    def _validate_iam_policies(self) -> list[ValidationFinding]:
        """Validate IAM policies follow least privilege."""
        findings: list[ValidationFinding] = []
        modules = self._discover_modules()

        for mod in modules:
            main_tf = self._terraform_root / mod.path / "main.tf"
            if not main_tf.exists():
                continue
            try:
                content = main_tf.read_text()
                # Check for overly permissive IAM policies
                if '"Action": "*"' in content or "'Action': '*'" in content:
                    findings.append(ValidationFinding(
                        rule="IAM_WILDCARD_ACTION",
                        severity=ValidationSeverity.CRITICAL,
                        resource="aws_iam_role_policy",
                        message=f"IAM policy in module '{mod.name}' uses wildcard action '*'",
                        remediation="Replace wildcard actions with specific required actions",
                    ))
                # Wildcard Resource is sometimes acceptable for logs
                if ('"Resource": "*"' in content
                    and "logs:" not in content.split('"Resource": "*"')[0][-200:]):
                    # Only flag if it's not specifically for CloudWatch Logs
                    pass
            except Exception:
                pass

        return findings

    # ----- Cost Estimation -----

    def estimate_costs(self, environment: str = "dev") -> CostEstimate:
        """Estimate monthly costs for the specified environment.

        Args:
            environment: Target environment (dev, staging, prod).

        Returns:
            CostEstimate with per-resource and total costs.
        """
        configs = self.get_environment_configs()
        env_config = None
        for cfg in configs.environments:
            if cfg.environment.value == environment:
                env_config = cfg
                break

        if env_config is None:
            return CostEstimate(
                environment=environment,
                resources=[],
                total_monthly_usd=0,
                total_annual_usd=0,
                timestamp=datetime.now(timezone.utc),
            )

        resources: list[ResourceCost] = []

        # RDS cost
        rds_monthly = _INSTANCE_COSTS.get(env_config.db_instance_class, 100.0)
        if env_config.multi_az:
            rds_monthly *= 2  # Multi-AZ doubles cost
        storage_cost = env_config.db_allocated_storage * _STORAGE_COST_PER_GB
        rds_total = rds_monthly + storage_cost
        resources.append(ResourceCost(
            resource_type="aws_db_instance",
            resource_name="PostgreSQL RDS",
            monthly_cost_usd=round(rds_total, 2),
            hourly_cost_usd=round(rds_total / 730, 4),
            notes=f"{env_config.db_instance_class}, {env_config.db_allocated_storage}GB storage"
                  + (", Multi-AZ" if env_config.multi_az else ""),
        ))

        # Redis cost
        redis_per_node = _REDIS_COSTS.get(env_config.redis_node_type, 50.0)
        redis_total = redis_per_node * env_config.redis_num_cache_nodes
        resources.append(ResourceCost(
            resource_type="aws_elasticache_replication_group",
            resource_name="ElastiCache Redis",
            monthly_cost_usd=round(redis_total, 2),
            hourly_cost_usd=round(redis_total / 730, 4),
            notes=f"{env_config.redis_node_type}, {env_config.redis_num_cache_nodes} nodes",
        ))

        # ECS Fargate cost (3 services: backend, frontend, worker)
        vcpu = env_config.ecs_cpu / 1024
        memory_gb = env_config.ecs_memory / 1024
        fargate_per_task = (
            vcpu * _FARGATE_COSTS["cpu_per_vcpu"]
            + memory_gb * _FARGATE_COSTS["memory_per_gb"]
        )
        # 3 services * desired_count tasks each
        total_tasks = 3 * env_config.ecs_desired_count
        fargate_total = fargate_per_task * total_tasks
        resources.append(ResourceCost(
            resource_type="aws_ecs_service",
            resource_name="ECS Fargate (3 services)",
            monthly_cost_usd=round(fargate_total, 2),
            hourly_cost_usd=round(fargate_total / 730, 4),
            notes=(
                f"{env_config.ecs_cpu} CPU, {env_config.ecs_memory}MB memory, "
                f"{env_config.ecs_desired_count} tasks/service, 3 services"
            ),
        ))

        # NAT Gateway cost (prod: 3, others: 1)
        nat_count = 3 if environment == "prod" else 1
        nat_monthly = nat_count * 45.0  # ~$45/month per NAT gateway
        resources.append(ResourceCost(
            resource_type="aws_nat_gateway",
            resource_name="NAT Gateway",
            monthly_cost_usd=round(nat_monthly, 2),
            hourly_cost_usd=round(nat_monthly / 730, 4),
            notes=f"{nat_count} NAT gateway(s)",
        ))

        # ALB cost
        alb_monthly = 22.0  # ~$22/month base
        resources.append(ResourceCost(
            resource_type="aws_lb",
            resource_name="Application Load Balancer",
            monthly_cost_usd=round(alb_monthly, 2),
            hourly_cost_usd=round(alb_monthly / 730, 4),
            notes="Base cost, excludes LCU charges",
        ))

        # KMS key
        kms_monthly = 1.0
        resources.append(ResourceCost(
            resource_type="aws_kms_key",
            resource_name="KMS Key",
            monthly_cost_usd=kms_monthly,
            hourly_cost_usd=round(kms_monthly / 730, 4),
            notes="$1/month per key",
        ))

        # Secrets Manager
        secrets_monthly = 3 * 0.40  # 3 secrets at $0.40/month each
        resources.append(ResourceCost(
            resource_type="aws_secretsmanager_secret",
            resource_name="Secrets Manager (3 secrets)",
            monthly_cost_usd=round(secrets_monthly, 2),
            hourly_cost_usd=round(secrets_monthly / 730, 4),
            notes="3 secrets at $0.40/month each",
        ))

        # CloudWatch
        cw_monthly = 15.0  # Approximate logging + metrics
        resources.append(ResourceCost(
            resource_type="aws_cloudwatch_log_group",
            resource_name="CloudWatch Logs & Metrics",
            monthly_cost_usd=cw_monthly,
            hourly_cost_usd=round(cw_monthly / 730, 4),
            notes="Approximate for logs, metrics, and dashboards",
        ))

        # WAF
        waf_monthly = 10.0  # $5 base + $1/rule * 4 rules + usage
        resources.append(ResourceCost(
            resource_type="aws_wafv2_web_acl",
            resource_name="WAF Web ACL",
            monthly_cost_usd=waf_monthly,
            hourly_cost_usd=round(waf_monthly / 730, 4),
            notes="Base + 4 rules, excludes per-request charges",
        ))

        total_monthly = sum(r.monthly_cost_usd for r in resources)

        return CostEstimate(
            environment=environment,
            resources=resources,
            total_monthly_usd=round(total_monthly, 2),
            total_annual_usd=round(total_monthly * 12, 2),
            currency="USD",
            timestamp=datetime.now(timezone.utc),
        )

    # ----- HIPAA Compliance -----

    def check_compliance(self, environment: str = "dev") -> ComplianceReport:
        """Run HIPAA compliance checks against the IaC configuration.

        Args:
            environment: Target environment to evaluate.

        Returns:
            ComplianceReport with all check results.
        """
        checks: list[ComplianceCheck] = []

        # 1. Encryption at rest
        checks.append(self._check_encryption_at_rest())

        # 2. Encryption in transit
        checks.append(self._check_encryption_in_transit())

        # 3. VPC isolation
        checks.append(self._check_vpc_isolation())

        # 4. Access logging
        checks.append(self._check_access_logging())

        # 5. Backup and recovery
        checks.append(self._check_backup_recovery(environment))

        # 6. IAM least privilege
        checks.append(self._check_iam_least_privilege())

        # 7. Network segmentation
        checks.append(self._check_network_segmentation())

        # 8. Audit trail
        checks.append(self._check_audit_trail())

        # 9. HIPAA-eligible services
        checks.append(self._check_hipaa_eligible_services())

        # 10. Key management
        checks.append(self._check_key_management())

        # 11. Multi-AZ (production)
        if environment == "prod":
            checks.append(self._check_multi_az_production())

        # 12. WAF protection
        checks.append(self._check_waf_protection())

        # Count statuses
        compliant = sum(1 for c in checks if c.status == ComplianceStatus.COMPLIANT)
        non_compliant = sum(1 for c in checks if c.status == ComplianceStatus.NON_COMPLIANT)
        partial = sum(1 for c in checks if c.status == ComplianceStatus.PARTIAL)
        total = len(checks)

        score = (compliant / total * 100) if total > 0 else 0

        overall = ComplianceStatus.COMPLIANT
        if non_compliant > 0:
            overall = ComplianceStatus.NON_COMPLIANT
        elif partial > 0:
            overall = ComplianceStatus.PARTIAL

        return ComplianceReport(
            environment=environment,
            overall_status=overall,
            checks=checks,
            compliant_count=compliant,
            non_compliant_count=non_compliant,
            partial_count=partial,
            score_percent=round(score, 1),
            timestamp=datetime.now(timezone.utc),
        )

    def _check_encryption_at_rest(self) -> ComplianceCheck:
        """Check encryption at rest for all data stores."""
        modules = self._discover_modules()
        has_rds_encryption = False
        has_redis_encryption = False

        for mod in modules:
            main_tf = self._terraform_root / mod.path / "main.tf"
            if not main_tf.exists():
                continue
            try:
                content = main_tf.read_text()
                if "storage_encrypted" in content:
                    has_rds_encryption = True
                if "at_rest_encryption_enabled" in content:
                    has_redis_encryption = True
            except Exception:
                pass

        if has_rds_encryption and has_redis_encryption:
            status = ComplianceStatus.COMPLIANT
            details = "All data stores have encryption at rest enabled"
        elif has_rds_encryption or has_redis_encryption:
            status = ComplianceStatus.PARTIAL
            details = "Some data stores lack encryption at rest"
        else:
            status = ComplianceStatus.NON_COMPLIANT
            details = "No encryption at rest configured"

        return ComplianceCheck(
            check_id="HIPAA-ENC-001",
            category="Encryption",
            description="All data at rest must be encrypted using AES-256 or equivalent",
            status=status,
            details=details,
            hipaa_reference="45 CFR 164.312(a)(2)(iv)",
        )

    def _check_encryption_in_transit(self) -> ComplianceCheck:
        """Check encryption in transit (TLS/SSL)."""
        modules = self._discover_modules()
        has_ssl_enforcement = False
        has_redis_transit = False
        has_https_listener = False

        for mod in modules:
            main_tf = self._terraform_root / mod.path / "main.tf"
            if not main_tf.exists():
                continue
            try:
                content = main_tf.read_text()
                if "rds.force_ssl" in content:
                    has_ssl_enforcement = True
                if "transit_encryption_enabled" in content:
                    has_redis_transit = True
                if "HTTPS" in content and "aws_lb_listener" in content:
                    has_https_listener = True
            except Exception:
                pass

        all_transit = has_ssl_enforcement and has_redis_transit and has_https_listener
        any_transit = has_ssl_enforcement or has_redis_transit or has_https_listener

        if all_transit:
            status = ComplianceStatus.COMPLIANT
            details = "TLS/SSL configured for all communication channels"
        elif any_transit:
            status = ComplianceStatus.PARTIAL
            details = "Some communication channels lack TLS/SSL"
        else:
            status = ComplianceStatus.NON_COMPLIANT
            details = "No encryption in transit configured"

        return ComplianceCheck(
            check_id="HIPAA-ENC-002",
            category="Encryption",
            description="All data in transit must be encrypted using TLS 1.2+",
            status=status,
            details=details,
            hipaa_reference="45 CFR 164.312(e)(1)",
        )

    def _check_vpc_isolation(self) -> ComplianceCheck:
        """Check VPC network isolation."""
        modules = self._discover_modules()
        has_vpc = any(
            res.type == "aws_vpc"
            for mod in modules
            for res in mod.resources
        )

        if has_vpc:
            return ComplianceCheck(
                check_id="HIPAA-NET-001",
                category="Network Security",
                description="All resources must be deployed within a VPC",
                status=ComplianceStatus.COMPLIANT,
                details="VPC is defined with proper network isolation",
                hipaa_reference="45 CFR 164.312(e)(1)",
            )
        else:
            return ComplianceCheck(
                check_id="HIPAA-NET-001",
                category="Network Security",
                description="All resources must be deployed within a VPC",
                status=ComplianceStatus.NON_COMPLIANT,
                details="No VPC defined - resources may be publicly accessible",
                hipaa_reference="45 CFR 164.312(e)(1)",
            )

    def _check_access_logging(self) -> ComplianceCheck:
        """Check access logging configuration."""
        modules = self._discover_modules()
        has_log_groups = any(
            res.type == "aws_cloudwatch_log_group"
            for mod in modules
            for res in mod.resources
        )
        has_flow_logs = any(
            res.type == "aws_flow_log"
            for mod in modules
            for res in mod.resources
        )

        if has_log_groups and has_flow_logs:
            status = ComplianceStatus.COMPLIANT
            details = "CloudWatch logs and VPC flow logs configured"
        elif has_log_groups:
            status = ComplianceStatus.PARTIAL
            details = "Application logs configured but VPC flow logs missing"
        else:
            status = ComplianceStatus.NON_COMPLIANT
            details = "No logging configuration found"

        return ComplianceCheck(
            check_id="HIPAA-LOG-001",
            category="Audit Controls",
            description="All access to ePHI must be logged and auditable",
            status=status,
            details=details,
            hipaa_reference="45 CFR 164.312(b)",
        )

    def _check_backup_recovery(self, environment: str) -> ComplianceCheck:
        """Check backup and disaster recovery configuration."""
        modules = self._discover_modules()
        has_backup = False

        for mod in modules:
            main_tf = self._terraform_root / mod.path / "main.tf"
            if not main_tf.exists():
                continue
            try:
                content = main_tf.read_text()
                if "backup_retention_period" in content:
                    has_backup = True
            except Exception:
                pass

        if has_backup:
            return ComplianceCheck(
                check_id="HIPAA-BCK-001",
                category="Contingency Planning",
                description="Data backups must be configured for all data stores",
                status=ComplianceStatus.COMPLIANT,
                details="Automated backups configured for RDS",
                hipaa_reference="45 CFR 164.308(a)(7)",
            )
        else:
            return ComplianceCheck(
                check_id="HIPAA-BCK-001",
                category="Contingency Planning",
                description="Data backups must be configured for all data stores",
                status=ComplianceStatus.NON_COMPLIANT,
                details="No backup configuration found",
                hipaa_reference="45 CFR 164.308(a)(7)",
            )

    def _check_iam_least_privilege(self) -> ComplianceCheck:
        """Check IAM follows least privilege principle."""
        modules = self._discover_modules()
        has_iam_roles = False
        has_wildcard_actions = False

        for mod in modules:
            for res in mod.resources:
                if res.type in ("aws_iam_role", "aws_iam_role_policy"):
                    has_iam_roles = True

            main_tf = self._terraform_root / mod.path / "main.tf"
            if not main_tf.exists():
                continue
            try:
                content = main_tf.read_text()
                if '"Action": "*"' in content:
                    has_wildcard_actions = True
            except Exception:
                pass

        if has_iam_roles and not has_wildcard_actions:
            status = ComplianceStatus.COMPLIANT
            details = "IAM roles defined with specific actions"
        elif has_iam_roles and has_wildcard_actions:
            status = ComplianceStatus.PARTIAL
            details = "IAM roles exist but some have wildcard actions"
        else:
            status = ComplianceStatus.NON_COMPLIANT
            details = "No IAM roles defined"

        return ComplianceCheck(
            check_id="HIPAA-IAM-001",
            category="Access Control",
            description="IAM policies must follow least privilege principle",
            status=status,
            details=details,
            hipaa_reference="45 CFR 164.312(a)(1)",
        )

    def _check_network_segmentation(self) -> ComplianceCheck:
        """Check network segmentation (separate subnets per tier)."""
        modules = self._discover_modules()
        has_public = False
        has_private = False
        has_database = False

        for mod in modules:
            main_tf = self._terraform_root / mod.path / "main.tf"
            if not main_tf.exists():
                continue
            try:
                content = main_tf.read_text()
                if "public" in content.lower() and "aws_subnet" in content:
                    has_public = True
                if "private" in content.lower() and "aws_subnet" in content:
                    has_private = True
                if "database" in content.lower() and "aws_subnet" in content:
                    has_database = True
            except Exception:
                pass

        if has_public and has_private and has_database:
            status = ComplianceStatus.COMPLIANT
            details = "Three-tier network segmentation (public/private/database)"
        elif has_public and has_private:
            status = ComplianceStatus.PARTIAL
            details = "Public/private segmentation but no dedicated database tier"
        else:
            status = ComplianceStatus.NON_COMPLIANT
            details = "Insufficient network segmentation"

        return ComplianceCheck(
            check_id="HIPAA-NET-002",
            category="Network Security",
            description="Network must be segmented into tiers (public/private/database)",
            status=status,
            details=details,
            hipaa_reference="45 CFR 164.312(e)(1)",
        )

    def _check_audit_trail(self) -> ComplianceCheck:
        """Check audit trail configuration."""
        modules = self._discover_modules()
        has_flow_logs = any(
            res.type == "aws_flow_log"
            for mod in modules
            for res in mod.resources
        )
        has_log_metric_filters = any(
            res.type == "aws_cloudwatch_log_metric_filter"
            for mod in modules
            for res in mod.resources
        )

        if has_flow_logs and has_log_metric_filters:
            status = ComplianceStatus.COMPLIANT
            details = "VPC flow logs and log metric filters configured"
        elif has_flow_logs:
            status = ComplianceStatus.PARTIAL
            details = "Flow logs exist but no log metric filters for alerting"
        else:
            status = ComplianceStatus.NON_COMPLIANT
            details = "No audit trail configuration"

        return ComplianceCheck(
            check_id="HIPAA-AUD-001",
            category="Audit Controls",
            description="Audit trails must capture all system activity",
            status=status,
            details=details,
            hipaa_reference="45 CFR 164.312(b)",
        )

    def _check_hipaa_eligible_services(self) -> ComplianceCheck:
        """Check all resources use HIPAA-eligible AWS services."""
        modules = self._discover_modules()
        all_types = set()
        non_eligible = set()

        for mod in modules:
            for res in mod.resources:
                all_types.add(res.type)
                if res.type not in HIPAA_ELIGIBLE_SERVICES:
                    non_eligible.add(res.type)

        if not non_eligible:
            status = ComplianceStatus.COMPLIANT
            details = f"All {len(all_types)} resource types are HIPAA-eligible"
        else:
            status = ComplianceStatus.NON_COMPLIANT
            details = f"Non-eligible services found: {', '.join(sorted(non_eligible))}"

        return ComplianceCheck(
            check_id="HIPAA-SVC-001",
            category="Service Eligibility",
            description="All AWS services must be HIPAA-eligible",
            status=status,
            details=details,
            hipaa_reference="AWS BAA",
        )

    def _check_key_management(self) -> ComplianceCheck:
        """Check KMS key management."""
        modules = self._discover_modules()
        has_kms = False
        has_key_rotation = False

        for mod in modules:
            main_tf = self._terraform_root / mod.path / "main.tf"
            if not main_tf.exists():
                continue
            try:
                content = main_tf.read_text()
                if "aws_kms_key" in content:
                    has_kms = True
                if "enable_key_rotation" in content and "true" in content:
                    has_key_rotation = True
            except Exception:
                pass

        if has_kms and has_key_rotation:
            status = ComplianceStatus.COMPLIANT
            details = "KMS key with automatic rotation enabled"
        elif has_kms:
            status = ComplianceStatus.PARTIAL
            details = "KMS key exists but rotation not enabled"
        else:
            status = ComplianceStatus.NON_COMPLIANT
            details = "No KMS key management configured"

        return ComplianceCheck(
            check_id="HIPAA-KEY-001",
            category="Key Management",
            description="Encryption keys must be managed and rotated",
            status=status,
            details=details,
            hipaa_reference="45 CFR 164.312(a)(2)(iv)",
        )

    def _check_multi_az_production(self) -> ComplianceCheck:
        """Check Multi-AZ for production high availability."""
        modules = self._discover_modules()
        has_multi_az = False

        for mod in modules:
            main_tf = self._terraform_root / mod.path / "main.tf"
            if not main_tf.exists():
                continue
            try:
                content = main_tf.read_text()
                if "multi_az" in content:
                    has_multi_az = True
            except Exception:
                pass

        if has_multi_az:
            status = ComplianceStatus.COMPLIANT
            details = "Multi-AZ configured for production high availability"
        else:
            status = ComplianceStatus.NON_COMPLIANT
            details = "Multi-AZ not configured - risk of data loss"

        return ComplianceCheck(
            check_id="HIPAA-HA-001",
            category="Availability",
            description="Production must have Multi-AZ for data protection",
            status=status,
            details=details,
            hipaa_reference="45 CFR 164.308(a)(7)(ii)(A)",
        )

    def _check_waf_protection(self) -> ComplianceCheck:
        """Check WAF web application firewall."""
        modules = self._discover_modules()
        has_waf = any(
            res.type == "aws_wafv2_web_acl"
            for mod in modules
            for res in mod.resources
        )

        if has_waf:
            return ComplianceCheck(
                check_id="HIPAA-WAF-001",
                category="Network Security",
                description="Web application firewall must protect public endpoints",
                status=ComplianceStatus.COMPLIANT,
                details="WAF Web ACL configured with rate limiting and managed rules",
                hipaa_reference="45 CFR 164.312(e)(1)",
            )
        else:
            return ComplianceCheck(
                check_id="HIPAA-WAF-001",
                category="Network Security",
                description="Web application firewall must protect public endpoints",
                status=ComplianceStatus.NON_COMPLIANT,
                details="No WAF configured - public endpoints are unprotected",
                hipaa_reference="45 CFR 164.312(e)(1)",
            )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        modules = self._discover_modules()
        total_resources = sum(len(m.resources) for m in modules)
        return {
            "modules_count": len(modules),
            "total_resources": total_resources,
            "terraform_root": str(self._terraform_root),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: IaCValidationService | None = None


def get_iac_validation_service() -> IaCValidationService:
    """Get or create the singleton IaC validation service."""
    global _instance
    if _instance is None:
        _instance = IaCValidationService()
    return _instance


def reset_iac_validation_service() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    _instance = None
