# =============================================================================
# Root Outputs - Clinical Trial Patient Recruitment Platform
# =============================================================================

# -----------------------------------------------------------------------------
# Networking
# -----------------------------------------------------------------------------

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.networking.private_subnet_ids
}

output "database_subnet_ids" {
  description = "IDs of the database subnets"
  value       = module.networking.database_subnet_ids
}

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = module.database.rds_endpoint
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Cache
# -----------------------------------------------------------------------------

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = module.cache.redis_endpoint
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Compute
# -----------------------------------------------------------------------------

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = module.compute.ecs_cluster_arn
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.compute.alb_dns_name
}

# -----------------------------------------------------------------------------
# Monitoring
# -----------------------------------------------------------------------------

output "cloudwatch_log_group_backend" {
  description = "CloudWatch log group for backend service"
  value       = module.monitoring.log_group_backend
}

output "cloudwatch_log_group_frontend" {
  description = "CloudWatch log group for frontend service"
  value       = module.monitoring.log_group_frontend
}

output "cloudwatch_log_group_worker" {
  description = "CloudWatch log group for worker service"
  value       = module.monitoring.log_group_worker
}

output "sns_alerts_topic_arn" {
  description = "ARN of the SNS topic for alerts"
  value       = module.monitoring.sns_alerts_topic_arn
}
