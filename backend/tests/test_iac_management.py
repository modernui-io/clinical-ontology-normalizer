"""Tests for Infrastructure-as-Code Management (DEVOPS-1).

Covers:
- Module structure validation and discovery
- Security group rules (permissive checks)
- Encryption configuration (RDS, Redis, KMS)
- Multi-AZ for production environments
- Cost estimation ranges and accuracy
- HIPAA compliance checks
- Environment variable differences (dev vs staging vs prod)
- Resource dependency ordering
- HCL parsing
- API endpoint responses
- Edge cases and error handling
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

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
    ValidationRequest,
    ValidationResult,
    ValidationSeverity,
)
from app.services.iac_service import (
    HIPAA_ELIGIBLE_SERVICES,
    REQUIRED_RESOURCES,
    IaCValidationService,
    _extract_block,
    _extract_value,
    get_iac_validation_service,
    parse_hcl_simple,
    reset_iac_validation_service,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before each test."""
    reset_iac_validation_service()
    yield
    reset_iac_validation_service()


@pytest.fixture
def service():
    """Create a fresh IaCValidationService pointing at real terraform files."""
    project_root = Path(__file__).resolve().parent.parent.parent
    terraform_root = project_root / "infrastructure" / "terraform"
    return IaCValidationService(terraform_root=str(terraform_root))


@pytest.fixture
def empty_service(tmp_path):
    """Create a service with an empty terraform directory."""
    tf_dir = tmp_path / "terraform"
    tf_dir.mkdir()
    (tf_dir / "modules").mkdir()
    return IaCValidationService(terraform_root=str(tf_dir))


@pytest.fixture
def minimal_service(tmp_path):
    """Create a service with a minimal terraform setup (missing resources)."""
    tf_dir = tmp_path / "terraform"
    tf_dir.mkdir()
    modules_dir = tf_dir / "modules"
    modules_dir.mkdir()

    # Create a minimal networking module
    net_dir = modules_dir / "networking"
    net_dir.mkdir()
    (net_dir / "main.tf").write_text('''
resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr
}
''')
    (net_dir / "variables.tf").write_text('''
variable "vpc_cidr" {
  type = string
}
''')
    (net_dir / "outputs.tf").write_text('''
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}
''')

    # Create environments dir
    envs_dir = tf_dir / "environments"
    envs_dir.mkdir()
    (envs_dir / "dev.tfvars").write_text('''
environment = "dev"
db_instance_class = "db.t3.small"
''')

    return IaCValidationService(terraform_root=str(tf_dir))


# ===========================================================================
# HCL Parsing Tests
# ===========================================================================


class TestHCLParsing:
    """Tests for the simplified HCL parser."""

    def test_parse_resource_blocks(self):
        """Should extract resource type and name from HCL."""
        hcl = '''
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "public" {
  vpc_id = aws_vpc.main.id
}
'''
        result = parse_hcl_simple(hcl)
        assert len(result["resources"]) == 2
        assert result["resources"][0]["type"] == "aws_vpc"
        assert result["resources"][0]["name"] == "main"
        assert result["resources"][1]["type"] == "aws_subnet"
        assert result["resources"][1]["name"] == "public"

    def test_parse_variable_blocks(self):
        """Should extract variable definitions."""
        hcl = '''
variable "environment" {
  type    = string
  default = "dev"
}

variable "region" {
  type = string
}
'''
        result = parse_hcl_simple(hcl)
        assert len(result["variables"]) == 2
        assert result["variables"][0]["name"] == "environment"
        assert result["variables"][1]["name"] == "region"

    def test_parse_output_blocks(self):
        """Should extract output definitions."""
        hcl = '''
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.main.endpoint
  sensitive   = true
}
'''
        result = parse_hcl_simple(hcl)
        assert len(result["outputs"]) == 2
        assert result["outputs"][0]["name"] == "vpc_id"
        assert result["outputs"][1]["name"] == "rds_endpoint"

    def test_parse_module_blocks(self):
        """Should extract module references."""
        hcl = '''
module "networking" {
  source = "./modules/networking"
  vpc_cidr = var.vpc_cidr
}

module "database" {
  source = "./modules/database"
}
'''
        result = parse_hcl_simple(hcl)
        assert len(result["modules"]) == 2
        assert result["modules"][0]["name"] == "networking"
        assert result["modules"][1]["name"] == "database"

    def test_extract_block_nested_braces(self):
        """Should handle nested braces correctly."""
        content = '''{ inner { nested } } extra'''
        block = _extract_block(content, 1)
        assert "inner" in block
        assert "nested" in block
        assert "extra" not in block

    def test_extract_value_quoted(self):
        """Should extract quoted values."""
        block = 'type = "string"\ndescription = "My var"'
        assert _extract_value(block, "type") == "string"
        assert _extract_value(block, "description") == "My var"

    def test_extract_value_unquoted(self):
        """Should extract unquoted values."""
        block = "count = 3\nenabled = true"
        assert _extract_value(block, "count") == "3"
        assert _extract_value(block, "enabled") == "true"

    def test_extract_value_missing(self):
        """Should return None for missing keys."""
        assert _extract_value("foo = bar", "baz") is None

    def test_parse_empty_content(self):
        """Should handle empty content gracefully."""
        result = parse_hcl_simple("")
        assert result["resources"] == []
        assert result["variables"] == []


# ===========================================================================
# Module Discovery Tests
# ===========================================================================


class TestModuleDiscovery:
    """Tests for module discovery and metadata."""

    def test_list_modules_returns_all(self, service):
        """Should discover all Terraform modules."""
        result = service.list_modules()
        assert isinstance(result, IaCModuleList)
        assert result.total_count > 0
        # Should find the standard modules
        names = [m.name for m in result.modules]
        assert "networking" in names
        assert "database" in names
        assert "cache" in names
        assert "compute" in names
        assert "monitoring" in names
        assert "security" in names

    def test_list_modules_has_root(self, service):
        """Should include the root module."""
        result = service.list_modules()
        names = [m.name for m in result.modules]
        assert "root" in names

    def test_root_module_has_dependencies(self, service):
        """Root module should list sub-module dependencies."""
        result = service.list_modules()
        root = next(m for m in result.modules if m.name == "root")
        assert len(root.dependencies) > 0
        assert "networking" in root.dependencies

    def test_get_module_found(self, service):
        """Should return a specific module by name."""
        mod = service.get_module("networking")
        assert mod is not None
        assert mod.name == "networking"
        assert mod.status == IaCModuleStatus.ACTIVE

    def test_get_module_not_found(self, service):
        """Should return None for unknown module."""
        mod = service.get_module("nonexistent")
        assert mod is None

    def test_module_has_variables(self, service):
        """Modules should have parsed variables."""
        mod = service.get_module("networking")
        assert mod is not None
        assert len(mod.variables) > 0
        var_names = [v.name for v in mod.variables]
        assert "project_name" in var_names

    def test_module_has_outputs(self, service):
        """Modules should have parsed outputs."""
        mod = service.get_module("networking")
        assert mod is not None
        assert len(mod.outputs) > 0
        out_names = [o.name for o in mod.outputs]
        assert "vpc_id" in out_names

    def test_module_has_resources(self, service):
        """Modules should have parsed resources."""
        mod = service.get_module("networking")
        assert mod is not None
        assert len(mod.resources) > 0
        res_types = [r.type for r in mod.resources]
        assert "aws_vpc" in res_types
        assert "aws_security_group" in res_types

    def test_empty_terraform_dir(self, empty_service):
        """Should handle empty terraform directory gracefully."""
        result = empty_service.list_modules()
        # Might have 0 modules or just no sub-modules
        assert isinstance(result, IaCModuleList)

    def test_module_caching(self, service):
        """Module discovery should use caching."""
        result1 = service.list_modules()
        result2 = service.list_modules()
        assert result1.total_count == result2.total_count


# ===========================================================================
# Security Group Validation Tests
# ===========================================================================


class TestSecurityGroupValidation:
    """Tests for security group rule validation."""

    def test_no_permissive_database_sg(self, service):
        """Database security groups should not allow 0.0.0.0/0."""
        result = service.validate_configuration(environment="dev")
        # Our configuration restricts database SG to backend SG only
        permissive_sg_findings = [
            f for f in result.findings
            if f.rule == "PERMISSIVE_SG"
            and "database" in f.resource.lower()
        ]
        assert len(permissive_sg_findings) == 0

    def test_alb_sg_allowed_public(self, service):
        """ALB security group is allowed to have 0.0.0.0/0."""
        result = service.validate_configuration(environment="dev")
        alb_permissive = [
            f for f in result.findings
            if f.rule == "PERMISSIVE_SG"
            and "alb" in f.resource.lower()
        ]
        assert len(alb_permissive) == 0


# ===========================================================================
# Encryption Validation Tests
# ===========================================================================


class TestEncryptionValidation:
    """Tests for encryption configuration validation."""

    def test_rds_encryption_enabled(self, service):
        """RDS should have storage encryption enabled."""
        result = service.validate_configuration(environment="dev")
        rds_enc_findings = [
            f for f in result.findings if f.rule == "RDS_ENCRYPTION"
        ]
        assert len(rds_enc_findings) == 0, "RDS encryption should be enabled"

    def test_redis_encryption_at_rest(self, service):
        """Redis should have encryption at rest."""
        result = service.validate_configuration(environment="dev")
        redis_enc = [
            f for f in result.findings if f.rule == "REDIS_ENCRYPTION_REST"
        ]
        assert len(redis_enc) == 0, "Redis at-rest encryption should be enabled"

    def test_redis_encryption_in_transit(self, service):
        """Redis should have encryption in transit."""
        result = service.validate_configuration(environment="dev")
        redis_transit = [
            f for f in result.findings if f.rule == "REDIS_ENCRYPTION_TRANSIT"
        ]
        assert len(redis_transit) == 0, "Redis transit encryption should be enabled"

    def test_kms_key_exists(self, service):
        """KMS key should be defined."""
        result = service.validate_configuration(environment="dev")
        kms_findings = [
            f for f in result.findings if f.rule == "KMS_KEY"
        ]
        assert len(kms_findings) == 0, "KMS key should be defined"

    def test_missing_encryption_detected(self, minimal_service):
        """Should detect missing encryption in minimal config."""
        result = minimal_service.validate_configuration(environment="dev")
        enc_findings = [
            f for f in result.findings
            if "ENCRYPTION" in f.rule or "KMS" in f.rule
        ]
        assert len(enc_findings) > 0, "Should detect missing encryption"


# ===========================================================================
# Multi-AZ Validation Tests
# ===========================================================================


class TestMultiAZValidation:
    """Tests for Multi-AZ production requirement."""

    def test_multi_az_not_required_for_dev(self, service):
        """Multi-AZ should not be required for dev."""
        result = service.validate_configuration(environment="dev")
        multi_az_findings = [
            f for f in result.findings if f.rule == "MULTI_AZ_PROD"
        ]
        assert len(multi_az_findings) == 0

    def test_multi_az_not_required_for_staging(self, service):
        """Multi-AZ should not be required for staging."""
        result = service.validate_configuration(environment="staging")
        multi_az_findings = [
            f for f in result.findings if f.rule == "MULTI_AZ_PROD"
        ]
        assert len(multi_az_findings) == 0

    def test_multi_az_configured_for_prod(self, service):
        """Multi-AZ should be configured for production."""
        result = service.validate_configuration(environment="prod")
        multi_az_findings = [
            f for f in result.findings if f.rule == "MULTI_AZ_PROD"
        ]
        assert len(multi_az_findings) == 0, "Multi-AZ should be present in TF files"


# ===========================================================================
# Cost Estimation Tests
# ===========================================================================


class TestCostEstimation:
    """Tests for infrastructure cost estimation."""

    def test_dev_costs_lowest(self, service):
        """Dev environment should have the lowest costs."""
        dev = service.estimate_costs("dev")
        staging = service.estimate_costs("staging")
        prod = service.estimate_costs("prod")
        assert dev.total_monthly_usd < staging.total_monthly_usd
        assert staging.total_monthly_usd < prod.total_monthly_usd

    def test_cost_estimate_has_resources(self, service):
        """Cost estimate should list individual resources."""
        estimate = service.estimate_costs("dev")
        assert isinstance(estimate, CostEstimate)
        assert len(estimate.resources) > 0
        assert estimate.total_monthly_usd > 0
        assert estimate.total_annual_usd > 0

    def test_annual_cost_is_12x_monthly(self, service):
        """Annual cost should be 12x monthly."""
        estimate = service.estimate_costs("dev")
        expected_annual = round(estimate.total_monthly_usd * 12, 2)
        assert estimate.total_annual_usd == expected_annual

    def test_cost_includes_rds(self, service):
        """Cost estimate should include RDS."""
        estimate = service.estimate_costs("dev")
        rds_costs = [r for r in estimate.resources if r.resource_type == "aws_db_instance"]
        assert len(rds_costs) == 1
        assert rds_costs[0].monthly_cost_usd > 0

    def test_cost_includes_redis(self, service):
        """Cost estimate should include Redis."""
        estimate = service.estimate_costs("dev")
        redis_costs = [r for r in estimate.resources if "elasticache" in r.resource_type]
        assert len(redis_costs) == 1
        assert redis_costs[0].monthly_cost_usd > 0

    def test_cost_includes_ecs(self, service):
        """Cost estimate should include ECS Fargate."""
        estimate = service.estimate_costs("dev")
        ecs_costs = [r for r in estimate.resources if "ecs" in r.resource_type]
        assert len(ecs_costs) == 1
        assert ecs_costs[0].monthly_cost_usd > 0

    def test_prod_rds_multi_az_doubles_cost(self, service):
        """Production RDS cost should reflect Multi-AZ (roughly 2x)."""
        dev = service.estimate_costs("dev")
        prod = service.estimate_costs("prod")
        dev_rds = next(r for r in dev.resources if r.resource_type == "aws_db_instance")
        prod_rds = next(r for r in prod.resources if r.resource_type == "aws_db_instance")
        # Prod uses larger instance + multi-AZ, should be significantly more
        assert prod_rds.monthly_cost_usd > dev_rds.monthly_cost_usd * 2

    def test_cost_estimate_dev_reasonable_range(self, service):
        """Dev costs should be in a reasonable range (< $500/month)."""
        estimate = service.estimate_costs("dev")
        assert estimate.total_monthly_usd < 500

    def test_cost_estimate_prod_reasonable_range(self, service):
        """Prod costs should be in a reasonable range ($500-$5000/month)."""
        estimate = service.estimate_costs("prod")
        assert 500 < estimate.total_monthly_usd < 5000

    def test_cost_currency_is_usd(self, service):
        """Cost estimate should use USD."""
        estimate = service.estimate_costs("dev")
        assert estimate.currency == "USD"

    def test_cost_has_disclaimer(self, service):
        """Cost estimate should have a disclaimer."""
        estimate = service.estimate_costs("dev")
        assert len(estimate.disclaimer) > 0


# ===========================================================================
# HIPAA Compliance Tests
# ===========================================================================


class TestHIPAACompliance:
    """Tests for HIPAA compliance checking."""

    def test_compliance_report_structure(self, service):
        """Compliance report should have proper structure."""
        report = service.check_compliance("dev")
        assert isinstance(report, ComplianceReport)
        assert len(report.checks) > 0
        assert report.score_percent >= 0
        assert report.score_percent <= 100

    def test_encryption_at_rest_compliant(self, service):
        """Should be compliant for encryption at rest."""
        report = service.check_compliance("dev")
        enc_check = next(
            (c for c in report.checks if c.check_id == "HIPAA-ENC-001"),
            None,
        )
        assert enc_check is not None
        assert enc_check.status == ComplianceStatus.COMPLIANT

    def test_encryption_in_transit_compliant(self, service):
        """Should be compliant for encryption in transit."""
        report = service.check_compliance("dev")
        enc_check = next(
            (c for c in report.checks if c.check_id == "HIPAA-ENC-002"),
            None,
        )
        assert enc_check is not None
        assert enc_check.status == ComplianceStatus.COMPLIANT

    def test_vpc_isolation_compliant(self, service):
        """Should be compliant for VPC isolation."""
        report = service.check_compliance("dev")
        vpc_check = next(
            (c for c in report.checks if c.check_id == "HIPAA-NET-001"),
            None,
        )
        assert vpc_check is not None
        assert vpc_check.status == ComplianceStatus.COMPLIANT

    def test_access_logging_compliant(self, service):
        """Should be compliant for access logging."""
        report = service.check_compliance("dev")
        log_check = next(
            (c for c in report.checks if c.check_id == "HIPAA-LOG-001"),
            None,
        )
        assert log_check is not None
        assert log_check.status == ComplianceStatus.COMPLIANT

    def test_backup_recovery_compliant(self, service):
        """Should be compliant for backup/recovery."""
        report = service.check_compliance("dev")
        backup_check = next(
            (c for c in report.checks if c.check_id == "HIPAA-BCK-001"),
            None,
        )
        assert backup_check is not None
        assert backup_check.status == ComplianceStatus.COMPLIANT

    def test_iam_least_privilege_compliant(self, service):
        """Should be compliant for IAM least privilege."""
        report = service.check_compliance("dev")
        iam_check = next(
            (c for c in report.checks if c.check_id == "HIPAA-IAM-001"),
            None,
        )
        assert iam_check is not None
        assert iam_check.status == ComplianceStatus.COMPLIANT

    def test_network_segmentation_compliant(self, service):
        """Should be compliant for network segmentation."""
        report = service.check_compliance("dev")
        net_check = next(
            (c for c in report.checks if c.check_id == "HIPAA-NET-002"),
            None,
        )
        assert net_check is not None
        assert net_check.status == ComplianceStatus.COMPLIANT

    def test_hipaa_eligible_services(self, service):
        """All resource types should be HIPAA-eligible."""
        report = service.check_compliance("dev")
        svc_check = next(
            (c for c in report.checks if c.check_id == "HIPAA-SVC-001"),
            None,
        )
        assert svc_check is not None
        assert svc_check.status == ComplianceStatus.COMPLIANT

    def test_prod_has_multi_az_check(self, service):
        """Production compliance should include Multi-AZ check."""
        report = service.check_compliance("prod")
        ha_check = next(
            (c for c in report.checks if c.check_id == "HIPAA-HA-001"),
            None,
        )
        assert ha_check is not None

    def test_dev_no_multi_az_check(self, service):
        """Dev compliance should not include Multi-AZ check."""
        report = service.check_compliance("dev")
        ha_checks = [c for c in report.checks if c.check_id == "HIPAA-HA-001"]
        assert len(ha_checks) == 0

    def test_waf_protection_compliant(self, service):
        """Should be compliant for WAF protection."""
        report = service.check_compliance("dev")
        waf_check = next(
            (c for c in report.checks if c.check_id == "HIPAA-WAF-001"),
            None,
        )
        assert waf_check is not None
        assert waf_check.status == ComplianceStatus.COMPLIANT

    def test_overall_compliance_score(self, service):
        """Overall compliance score should be high for well-configured infra."""
        report = service.check_compliance("dev")
        assert report.score_percent > 80

    def test_non_compliant_detected(self, minimal_service):
        """Should detect non-compliance in minimal configuration."""
        report = minimal_service.check_compliance("dev")
        assert report.non_compliant_count > 0


# ===========================================================================
# Environment Configuration Tests
# ===========================================================================


class TestEnvironmentConfigs:
    """Tests for environment configuration differences."""

    def test_three_environments(self, service):
        """Should return configs for dev, staging, and prod."""
        configs = service.get_environment_configs()
        assert isinstance(configs, EnvironmentConfigList)
        assert len(configs.environments) == 3
        tiers = [c.environment for c in configs.environments]
        assert EnvironmentTier.DEV in tiers
        assert EnvironmentTier.STAGING in tiers
        assert EnvironmentTier.PROD in tiers

    def test_prod_larger_instances(self, service):
        """Production should use larger database instances."""
        configs = service.get_environment_configs()
        dev = next(c for c in configs.environments if c.environment == EnvironmentTier.DEV)
        prod = next(c for c in configs.environments if c.environment == EnvironmentTier.PROD)
        # Prod should have more allocated storage
        assert prod.db_allocated_storage > dev.db_allocated_storage

    def test_prod_has_multi_az(self, service):
        """Production should have Multi-AZ enabled."""
        configs = service.get_environment_configs()
        prod = next(c for c in configs.environments if c.environment == EnvironmentTier.PROD)
        assert prod.multi_az is True

    def test_dev_no_multi_az(self, service):
        """Dev should not have Multi-AZ."""
        configs = service.get_environment_configs()
        dev = next(c for c in configs.environments if c.environment == EnvironmentTier.DEV)
        assert dev.multi_az is False

    def test_prod_more_backup_retention(self, service):
        """Production should have longer backup retention."""
        configs = service.get_environment_configs()
        dev = next(c for c in configs.environments if c.environment == EnvironmentTier.DEV)
        prod = next(c for c in configs.environments if c.environment == EnvironmentTier.PROD)
        assert prod.db_backup_retention > dev.db_backup_retention

    def test_prod_more_ecs_capacity(self, service):
        """Production should have higher ECS capacity."""
        configs = service.get_environment_configs()
        dev = next(c for c in configs.environments if c.environment == EnvironmentTier.DEV)
        prod = next(c for c in configs.environments if c.environment == EnvironmentTier.PROD)
        assert prod.ecs_cpu > dev.ecs_cpu
        assert prod.ecs_memory > dev.ecs_memory
        assert prod.ecs_desired_count > dev.ecs_desired_count

    def test_all_environments_have_encryption(self, service):
        """All environments should have encryption enabled."""
        configs = service.get_environment_configs()
        for config in configs.environments:
            assert config.encryption_enabled is True

    def test_different_vpc_cidrs(self, service):
        """Each environment should have a different VPC CIDR."""
        configs = service.get_environment_configs()
        cidrs = [c.vpc_cidr for c in configs.environments]
        assert len(set(cidrs)) == 3, "Each environment should have unique CIDR"


# ===========================================================================
# Resource Dependency Tests
# ===========================================================================


class TestResourceDependencies:
    """Tests for resource dependency ordering."""

    def test_required_resources_defined(self, service):
        """All required resource types should be defined."""
        result = service.validate_configuration(environment="dev")
        required_findings = [
            f for f in result.findings if f.rule == "REQUIRED_RESOURCE"
        ]
        assert len(required_findings) == 0, (
            f"Missing required resources: "
            f"{[f.resource for f in required_findings]}"
        )

    def test_missing_resources_detected(self, minimal_service):
        """Should detect missing required resources."""
        result = minimal_service.validate_configuration(environment="dev")
        required_findings = [
            f for f in result.findings if f.rule == "REQUIRED_RESOURCE"
        ]
        assert len(required_findings) > 0

    def test_hipaa_eligible_services_constant(self):
        """HIPAA eligible services set should contain expected types."""
        assert "aws_vpc" in HIPAA_ELIGIBLE_SERVICES
        assert "aws_db_instance" in HIPAA_ELIGIBLE_SERVICES
        assert "aws_ecs_cluster" in HIPAA_ELIGIBLE_SERVICES
        assert "aws_kms_key" in HIPAA_ELIGIBLE_SERVICES

    def test_required_resources_constant(self):
        """Required resources set should contain essential types."""
        assert "aws_vpc" in REQUIRED_RESOURCES
        assert "aws_db_instance" in REQUIRED_RESOURCES
        assert "aws_ecs_cluster" in REQUIRED_RESOURCES
        assert "aws_lb" in REQUIRED_RESOURCES


# ===========================================================================
# Validation Result Tests
# ===========================================================================


class TestValidationResults:
    """Tests for overall validation results."""

    def test_valid_config_passes(self, service):
        """Well-configured infrastructure should pass validation."""
        result = service.validate_configuration(environment="dev")
        assert isinstance(result, ValidationResult)
        assert result.critical_count == 0
        assert result.valid is True

    def test_validation_has_timestamp(self, service):
        """Validation result should have a timestamp."""
        result = service.validate_configuration(environment="dev")
        assert result.timestamp is not None

    def test_validation_counts_match_findings(self, service):
        """Severity counts should match finding list."""
        result = service.validate_configuration(environment="dev")
        actual_critical = sum(
            1 for f in result.findings if f.severity == ValidationSeverity.CRITICAL
        )
        assert result.critical_count == actual_critical

    def test_minimal_config_fails_validation(self, minimal_service):
        """Minimal configuration should fail validation."""
        result = minimal_service.validate_configuration(environment="dev")
        assert result.valid is False


# ===========================================================================
# Service Stats Tests
# ===========================================================================


class TestServiceStats:
    """Tests for service statistics."""

    def test_get_stats(self, service):
        """Should return service statistics."""
        stats = service.get_stats()
        assert "modules_count" in stats
        assert "total_resources" in stats
        assert "terraform_root" in stats
        assert stats["modules_count"] > 0
        assert stats["total_resources"] > 0


# ===========================================================================
# Singleton Tests
# ===========================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_singleton(self):
        """Should return the same instance."""
        svc1 = get_iac_validation_service()
        svc2 = get_iac_validation_service()
        assert svc1 is svc2

    def test_reset_singleton(self):
        """Should create a new instance after reset."""
        svc1 = get_iac_validation_service()
        reset_iac_validation_service()
        svc2 = get_iac_validation_service()
        assert svc1 is not svc2


# ===========================================================================
# Schema Tests
# ===========================================================================


class TestSchemas:
    """Tests for Pydantic schema validation."""

    def test_iac_variable_schema(self):
        """IaCVariable should validate correctly."""
        var = IaCVariable(name="test", type="string", description="A test var")
        assert var.name == "test"
        assert var.required is True

    def test_iac_output_schema(self):
        """IaCOutput should validate correctly."""
        out = IaCOutput(name="vpc_id", description="VPC ID", sensitive=False)
        assert out.name == "vpc_id"
        assert out.sensitive is False

    def test_iac_resource_schema(self):
        """IaCResource should validate correctly."""
        res = IaCResource(type="aws_vpc", name="main")
        assert res.type == "aws_vpc"
        assert res.provider == "aws"

    def test_validation_finding_schema(self):
        """ValidationFinding should validate correctly."""
        finding = ValidationFinding(
            rule="TEST",
            severity=ValidationSeverity.HIGH,
            message="Test finding",
        )
        assert finding.severity == ValidationSeverity.HIGH

    def test_compliance_check_schema(self):
        """ComplianceCheck should validate correctly."""
        check = ComplianceCheck(
            check_id="TEST-001",
            category="Test",
            description="Test check",
            status=ComplianceStatus.COMPLIANT,
        )
        assert check.status == ComplianceStatus.COMPLIANT

    def test_environment_config_schema(self):
        """EnvironmentConfig should validate correctly."""
        config = EnvironmentConfig(
            environment=EnvironmentTier.DEV,
            db_instance_class="db.t3.medium",
        )
        assert config.environment == EnvironmentTier.DEV
        assert config.encryption_enabled is True

    def test_resource_cost_schema(self):
        """ResourceCost should validate correctly."""
        cost = ResourceCost(
            resource_type="aws_db_instance",
            monthly_cost_usd=100.0,
        )
        assert cost.monthly_cost_usd == 100.0

    def test_validation_request_schema(self):
        """ValidationRequest should validate correctly."""
        req = ValidationRequest(environment=EnvironmentTier.PROD)
        assert req.environment == EnvironmentTier.PROD


# ===========================================================================
# API Endpoint Tests
# ===========================================================================


@pytest.mark.asyncio
class TestAPIEndpoints:
    """Tests for IaC management API endpoints."""

    async def test_list_modules_endpoint(self):
        """GET /infrastructure/iac/modules should return modules."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/infrastructure/iac/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert "modules" in data
        assert "total_count" in data
        assert data["total_count"] > 0

    async def test_get_module_endpoint(self):
        """GET /infrastructure/iac/modules/networking should return module."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/infrastructure/iac/modules/networking")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "networking"

    async def test_get_module_not_found_endpoint(self):
        """GET /infrastructure/iac/modules/unknown should return 404."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/infrastructure/iac/modules/unknown")
        assert resp.status_code == 404

    async def test_list_environments_endpoint(self):
        """GET /infrastructure/iac/environments should return configs."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/infrastructure/iac/environments")
        assert resp.status_code == 200
        data = resp.json()
        assert "environments" in data
        assert len(data["environments"]) == 3

    async def test_validate_endpoint(self):
        """POST /infrastructure/iac/validate should validate config."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/infrastructure/iac/validate",
                json={"environment": "dev", "config": {}},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "valid" in data
        assert "findings" in data

    async def test_cost_estimate_endpoint(self):
        """GET /infrastructure/iac/cost-estimate should return costs."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/infrastructure/iac/cost-estimate",
                params={"environment": "dev"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_monthly_usd" in data
        assert "resources" in data
        assert data["total_monthly_usd"] > 0

    async def test_cost_estimate_invalid_env(self):
        """GET /infrastructure/iac/cost-estimate with bad env should 400."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/infrastructure/iac/cost-estimate",
                params={"environment": "invalid"},
            )
        assert resp.status_code == 400

    async def test_compliance_endpoint(self):
        """GET /infrastructure/iac/compliance should return report."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/infrastructure/iac/compliance",
                params={"environment": "dev"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_status" in data
        assert "checks" in data
        assert "score_percent" in data

    async def test_compliance_invalid_env(self):
        """GET /infrastructure/iac/compliance with bad env should 400."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/infrastructure/iac/compliance",
                params={"environment": "invalid"},
            )
        assert resp.status_code == 400
