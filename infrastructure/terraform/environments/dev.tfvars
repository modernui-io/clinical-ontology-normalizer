# =============================================================================
# Development Environment Configuration
# =============================================================================

environment  = "dev"
region       = "us-east-1"
project_name = "clinical-trial-platform"

# Networking
vpc_cidr = "10.0.0.0/16"

# Database - Smaller instances for development
db_instance_class    = "db.t3.medium"
db_allocated_storage = 20
db_backup_retention  = 1

# Cache - Minimal Redis for development
redis_node_type       = "cache.t3.medium"
redis_num_cache_nodes = 1

# Compute - Minimal Fargate for development
ecs_cpu           = 512
ecs_memory        = 1024
ecs_desired_count = 1

# Domain (empty for dev - uses ALB DNS)
domain_name     = ""
certificate_arn = ""
