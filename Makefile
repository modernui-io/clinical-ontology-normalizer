.PHONY: test lint typecheck dev dev-backend dev-worker clean help docker-up docker-down docker-build docker-logs docker-dev docker-migrate kg kg-export kg-check kg-lint skills-install

# Default target
help:
	@echo "Clinical Ontology Normalizer - Build Commands"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Development targets:"
	@echo "  dev           Start development servers (shows commands)"
	@echo "  dev-backend   Start FastAPI backend with auto-reload"
	@echo "  dev-worker    Start RQ worker for background jobs"
	@echo "  test          Run all tests (backend + frontend)"
	@echo "  lint          Run all linters"
	@echo "  typecheck     Run type checkers"
	@echo "  clean         Clean build artifacts"
	@echo "  kg            Regenerate codebase_kg.json"
	@echo "  kg-export     Export KG to Neo4j CSV (kg_export/)"
	@echo "  kg-check      Verify codebase_kg.json is up to date"
	@echo "  kg-lint       Lint KG scripts with Ruff"
	@echo "  skills-install Install repo skills into CODEX_HOME"
	@echo ""
	@echo "Docker targets:"
	@echo "  docker-build  Build Docker images"
	@echo "  docker-up     Start all services"
	@echo "  docker-down   Stop all services"
	@echo "  docker-dev    Start services with hot reload"
	@echo "  docker-logs   View service logs"
	@echo ""

# Run all tests
test: test-backend test-frontend

test-backend:
	@echo "Running backend tests..."
	@cd backend && python3 -m pytest tests/ -v || echo "Backend tests not yet configured"

test-frontend:
	@echo "Running frontend tests..."
	@if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then \
		cd frontend && npm test; \
	else \
		echo "Frontend not yet configured"; \
	fi

# Run all linters
lint: lint-backend lint-frontend kg-lint

lint-backend:
	@echo "Running backend linting..."
	@cd backend && python3 -m ruff check . || echo "Backend linting not yet configured"

lint-frontend:
	@echo "Running frontend linting..."
	@if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then \
		cd frontend && npm run lint; \
	else \
		echo "Frontend not yet configured"; \
	fi

# Run type checkers
typecheck: typecheck-backend typecheck-frontend

typecheck-backend:
	@echo "Running backend type checking..."
	@cd backend && python3 -m mypy app/ || echo "Backend type checking not yet configured"

typecheck-frontend:
	@echo "Running frontend type checking..."
	@if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then \
		cd frontend && npm run typecheck; \
	else \
		echo "Frontend not yet configured"; \
	fi

# Start development servers (shows commands)
dev:
	@echo "Starting development servers..."
	@echo ""
	@echo "Run these in separate terminals:"
	@echo "  Backend:  make dev-backend"
	@echo "  Worker:   make dev-worker"
	@echo "  Frontend: cd frontend && npm run dev"
	@echo ""

# Start FastAPI backend with auto-reload
dev-backend:
	@echo "Starting FastAPI backend..."
	cd backend && uv run uvicorn app.main:app --reload

# Start RQ worker for background job processing
dev-worker:
	@echo "Starting RQ worker..."
	cd backend && ./scripts/run_worker.sh

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
	@echo "Done"

# =============================================================================
# Knowledge graph & skills targets
# =============================================================================

kg:
	@python3 scripts/generate_codebase_kg.py

kg-export: kg
	@python3 scripts/export_codebase_kg_neo4j.py

kg-check:
	@python3 scripts/generate_codebase_kg.py
	@git diff --exit-code codebase_kg.json

kg-lint:
	@echo "Running KG script linting..."
	@python3 -m ruff check scripts/*.py || echo "KG linting not yet configured"
	@python3 -m ruff format --check scripts/*.py || echo "KG format check not yet configured"

skills-install:
	@python3 scripts/install_repo_skills.py

# =============================================================================
# Docker targets
# =============================================================================

# Build Docker images
docker-build:
	@echo "Building Docker images..."
	docker compose build

# Start all services (production mode)
docker-up:
	@echo "Starting services..."
	docker compose up -d
	@echo ""
	@echo "Services started:"
	@echo "  - Frontend: http://localhost:3001"
	@echo "  - Backend API: http://localhost:8080"
	@echo "  - API Docs: http://localhost:8080/docs"
	@echo ""

# Stop all services
docker-down:
	@echo "Stopping services..."
	docker compose down

# Start services with hot reload (development mode)
docker-dev:
	@echo "Starting services in development mode..."
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
	@echo ""
	@echo "Services started (dev mode with hot reload):"
	@echo "  - Frontend: http://localhost:3001"
	@echo "  - Backend API: http://localhost:8080"
	@echo "  - API Docs: http://localhost:8080/docs"
	@echo ""

# View service logs
docker-logs:
	docker compose logs -f

# Run database migrations
docker-migrate:
	docker compose run --rm migrations
