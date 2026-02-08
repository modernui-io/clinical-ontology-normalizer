# =============================================================================
# Compute Module - Variables
# =============================================================================

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "public_subnets" {
  description = "List of public subnet IDs for ALB"
  type        = list(string)
}

variable "private_subnets" {
  description = "List of private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "alb_security_group" {
  description = "Security group ID for the ALB"
  type        = string
}

variable "backend_security_group" {
  description = "Security group ID for backend services"
  type        = string
}

variable "ecs_cpu" {
  description = "CPU units for ECS tasks"
  type        = number
}

variable "ecs_memory" {
  description = "Memory in MiB for ECS tasks"
  type        = number
}

variable "ecs_desired_count" {
  description = "Desired number of ECS task instances"
  type        = number
}

variable "rds_endpoint" {
  description = "RDS endpoint for backend configuration"
  type        = string
}

variable "redis_endpoint" {
  description = "Redis endpoint for backend configuration"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key ARN for encryption"
  type        = string
}

variable "execution_role_arn" {
  description = "ECS task execution role ARN"
  type        = string
}

variable "task_role_arn" {
  description = "ECS task role ARN"
  type        = string
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS"
  type        = string
}

variable "common_tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default     = {}
}
