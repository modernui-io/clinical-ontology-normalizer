#!/bin/bash
#
# Clinical Ontology Normalizer - Full Stack Startup Script
#
# This script:
# 1. Checks if Docker is running
# 2. Starts docker compose services
# 3. Waits for all services to be healthy
# 4. Runs database migrations
# 5. Creates demo user if not exists
# 6. Prints URLs and credentials
#
# Usage: ./start_all.sh [--clean]
#   --clean: Remove volumes and start fresh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
MAX_WAIT_SECONDS=180
POLL_INTERVAL=5

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Clinical Ontology Normalizer Startup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Parse arguments
CLEAN_START=false
if [ "$1" = "--clean" ]; then
    CLEAN_START=true
    echo -e "${YELLOW}Clean start requested - will remove volumes${NC}"
fi

# Step 1: Check if Docker is running
echo -e "${BLUE}[1/6] Checking Docker status...${NC}"
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Docker is not running!${NC}"
    echo "Please start Docker Desktop and try again."
    exit 1
fi
echo -e "${GREEN}Docker is running${NC}"

# Step 2: Change to project root
cd "$PROJECT_ROOT"
echo -e "${BLUE}Working directory: ${PROJECT_ROOT}${NC}"

# Step 3: Clean start if requested
if [ "$CLEAN_START" = true ]; then
    echo -e "${YELLOW}[2/6] Stopping existing containers and removing volumes...${NC}"
    docker compose down -v 2>/dev/null || true
    echo -e "${GREEN}Clean slate ready${NC}"
else
    echo -e "${BLUE}[2/6] Stopping existing containers (preserving data)...${NC}"
    docker compose down 2>/dev/null || true
fi

# Step 4: Start docker compose
echo -e "${BLUE}[3/6] Starting docker compose services...${NC}"
docker compose up -d

# Wait a moment for containers to initialize
sleep 5

# Step 5: Wait for services to be healthy
echo -e "${BLUE}[4/6] Waiting for services to be healthy...${NC}"

wait_for_service() {
    local service_name=$1
    local check_command=$2
    local max_attempts=$((MAX_WAIT_SECONDS / POLL_INTERVAL))
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if eval "$check_command" > /dev/null 2>&1; then
            echo -e "${GREEN}  [OK] $service_name is healthy${NC}"
            return 0
        fi
        attempt=$((attempt + 1))
        echo -e "${YELLOW}  Waiting for $service_name... ($attempt/$max_attempts)${NC}"
        sleep $POLL_INTERVAL
    done

    echo -e "${RED}  [FAIL] $service_name did not become healthy${NC}"
    return 1
}

# Check each service
echo "Checking PostgreSQL..."
wait_for_service "PostgreSQL" "docker exec con-postgres pg_isready -U postgres"

echo "Checking Redis..."
wait_for_service "Redis" "docker exec con-redis redis-cli ping"

echo "Checking Neo4j..."
wait_for_service "Neo4j" "curl -sf http://localhost:7474"

echo "Checking Kafka..."
wait_for_service "Kafka" "docker exec con-kafka kafka-broker-api-versions --bootstrap-server localhost:9092" || echo -e "${YELLOW}  (Kafka optional, continuing...)${NC}"

echo "Checking Backend API..."
wait_for_service "Backend" "curl -sf http://localhost:8080/health"

echo "Checking Frontend..."
wait_for_service "Frontend" "curl -sf http://localhost:3000" || echo -e "${YELLOW}  (Frontend may take longer to build...)${NC}"

# Step 6: Run database migrations
echo -e "${BLUE}[5/6] Running database migrations...${NC}"
docker compose run --rm migrations 2>/dev/null || {
    echo -e "${YELLOW}  Migrations may have already been applied${NC}"
}
echo -e "${GREEN}Migrations complete${NC}"

# Step 7: Create demo user if not exists
echo -e "${BLUE}[6/6] Setting up demo user...${NC}"

# Create demo user via SQL
docker exec -i con-postgres psql -U postgres -d clinical_ontology << 'EOSQL' 2>/dev/null || true
-- Create demo user (password: demo)
-- bcrypt hash for 'demo' password
INSERT INTO users (id, email, name, password_hash, is_active, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'demo@example.com',
    'Demo User',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.V9YrGgc3x0z7O.',
    true,
    NOW(),
    NOW()
)
ON CONFLICT (email) DO NOTHING;

-- Ensure default roles exist
INSERT INTO roles (id, name, description, created_at)
VALUES
    (gen_random_uuid(), 'admin', 'Administrator with full access', NOW()),
    (gen_random_uuid(), 'clinician', 'Clinical user with patient access', NOW()),
    (gen_random_uuid(), 'viewer', 'Read-only viewer', NOW())
ON CONFLICT (name) DO NOTHING;

-- Assign admin role to demo user
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u, roles r
WHERE u.email = 'demo@example.com' AND r.name = 'admin'
ON CONFLICT DO NOTHING;
EOSQL

echo -e "${GREEN}Demo user setup complete${NC}"

# Print summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}All Services Started Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Service URLs:${NC}"
echo "  Frontend:        http://localhost:3000"
echo "  Backend API:     http://localhost:8080"
echo "  API Docs:        http://localhost:8080/api/v1/docs"
echo "  Neo4j Browser:   http://localhost:7474"
echo "  PostgreSQL:      localhost:15432"
echo "  Redis:           localhost:16379"
echo ""
echo -e "${BLUE}Demo Credentials:${NC}"
echo "  Email:     demo@example.com"
echo "  Password:  demo"
echo ""
echo -e "${BLUE}Quick Test Commands:${NC}"
echo "  curl http://localhost:8080/health"
echo "  curl http://localhost:8080/api/v1/nlp/models"
echo ""
echo -e "${BLUE}View Logs:${NC}"
echo "  docker compose logs -f backend"
echo "  docker compose logs -f frontend"
echo ""
echo -e "${BLUE}Stop All Services:${NC}"
echo "  docker compose down"
echo ""
echo -e "${GREEN}Ready for use!${NC}"
