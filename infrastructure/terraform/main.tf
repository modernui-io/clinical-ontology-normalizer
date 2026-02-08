# =============================================================================
# Clinical Trial Patient Recruitment Platform - Root Terraform Configuration
# =============================================================================
# HIPAA-compliant infrastructure on AWS using ECS Fargate, RDS PostgreSQL,
# ElastiCache Redis, and comprehensive monitoring/security controls.
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "clinical-trial-platform-tfstate"
    key            = "infrastructure/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Compliance  = "hipaa"
    }
  }
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# Local Values
# -----------------------------------------------------------------------------

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  azs         = slice(data.aws_availability_zones.available.names, 0, 3)
  account_id  = data.aws_caller_identity.current.account_id

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Compliance  = "hipaa"
  }
}

# -----------------------------------------------------------------------------
# Modules
# -----------------------------------------------------------------------------

module "networking" {
  source = "./modules/networking"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
  azs          = local.azs
  common_tags  = local.common_tags
}

module "security" {
  source = "./modules/security"

  project_name = var.project_name
  environment  = var.environment
  account_id   = local.account_id
  vpc_id       = module.networking.vpc_id
  common_tags  = local.common_tags
}

module "database" {
  source = "./modules/database"

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.networking.vpc_id
  database_subnets   = module.networking.database_subnet_ids
  db_security_group  = module.networking.database_security_group_id
  instance_class     = var.db_instance_class
  allocated_storage  = var.db_allocated_storage
  backup_retention   = var.db_backup_retention
  kms_key_arn        = module.security.kms_key_arn
  common_tags        = local.common_tags
}

module "cache" {
  source = "./modules/cache"

  project_name        = var.project_name
  environment         = var.environment
  vpc_id              = module.networking.vpc_id
  private_subnets     = module.networking.private_subnet_ids
  redis_security_group = module.networking.redis_security_group_id
  node_type           = var.redis_node_type
  num_cache_nodes     = var.redis_num_cache_nodes
  kms_key_arn         = module.security.kms_key_arn
  common_tags         = local.common_tags
}

module "compute" {
  source = "./modules/compute"

  project_name       = var.project_name
  environment        = var.environment
  region             = var.region
  vpc_id             = module.networking.vpc_id
  public_subnets     = module.networking.public_subnet_ids
  private_subnets    = module.networking.private_subnet_ids
  alb_security_group = module.networking.alb_security_group_id
  backend_security_group = module.networking.backend_security_group_id
  ecs_cpu            = var.ecs_cpu
  ecs_memory         = var.ecs_memory
  ecs_desired_count  = var.ecs_desired_count
  rds_endpoint       = module.database.rds_endpoint
  redis_endpoint     = module.cache.redis_endpoint
  kms_key_arn        = module.security.kms_key_arn
  execution_role_arn = module.security.ecs_execution_role_arn
  task_role_arn      = module.security.ecs_task_role_arn
  domain_name        = var.domain_name
  certificate_arn    = var.certificate_arn
  common_tags        = local.common_tags
}

module "monitoring" {
  source = "./modules/monitoring"

  project_name      = var.project_name
  environment       = var.environment
  ecs_cluster_name  = module.compute.ecs_cluster_name
  alb_arn_suffix    = module.compute.alb_arn_suffix
  rds_identifier    = module.database.rds_identifier
  redis_cluster_id  = module.cache.redis_cluster_id
  common_tags       = local.common_tags
}
