# =============================================================================
# Production Environment Configuration
# =============================================================================

environment  = "prod"
region       = "us-east-1"
project_name = "clinical-trial-platform"

# Networking
vpc_cidr = "10.2.0.0/16"

# Database - Full production with Multi-AZ
db_instance_class    = "db.r6g.xlarge"
db_allocated_storage = 200
db_backup_retention  = 35

# Cache - Full production Redis cluster
redis_node_type       = "cache.r6g.large"
redis_num_cache_nodes = 3

# Compute - Full production Fargate
ecs_cpu           = 2048
ecs_memory        = 4096
ecs_desired_count = 3

# Domain
domain_name     = "clinicaltrial.example.com"
certificate_arn = ""
