# =============================================================================
# Staging Environment Configuration
# =============================================================================

environment  = "staging"
region       = "us-east-1"
project_name = "clinical-trial-platform"

# Networking
vpc_cidr = "10.1.0.0/16"

# Database - Production-like but smaller
db_instance_class    = "db.r6g.large"
db_allocated_storage = 50
db_backup_retention  = 3

# Cache - Production-like but smaller
redis_node_type       = "cache.r6g.medium"
redis_num_cache_nodes = 2

# Compute - Production-like but fewer instances
ecs_cpu           = 1024
ecs_memory        = 2048
ecs_desired_count = 2

# Domain
domain_name     = "staging.clinicaltrial.example.com"
certificate_arn = ""
